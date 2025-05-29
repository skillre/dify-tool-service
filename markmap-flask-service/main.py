from flask import Flask, request, send_from_directory, jsonify
import time
import subprocess
import os
import threading
import shutil
import logging
import re
import fcntl
import hashlib
import json
from functools import wraps
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置最大请求大小为5MB
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024

# 配置请求限流器
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# 配置
DATA_DIR = os.environ.get("DATA_DIR", "data")
FILE_EXPIRY_HOURS = int(os.environ.get("FILE_EXPIRY_HOURS", "24"))  # 文件过期时间(小时)
CLEANUP_INTERVAL_HOURS = int(os.environ.get("CLEANUP_INTERVAL_HOURS", "1"))  # 清理间隔(小时)
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5003"))
# 对外提供的固定链接地址
PUBLIC_URL = os.environ.get("PUBLIC_URL", "http://localhost:5003")

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 内容缓存，存储结构为 {content_hash: {file_info}}
content_cache = {}
# 缓存锁，防止并发写入
cache_lock = threading.Lock()

def get_content_hash(content):
    """计算内容的SHA-256哈希值"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def clean_old_files():
    """定时清理过期文件，使用文件锁避免并发问题"""
    while True:
        try:
            now = time.time()
            expiry_time = now - (FILE_EXPIRY_HOURS * 3600)
            count = 0
            
            # 创建一个锁文件
            lock_file = os.path.join(DATA_DIR, ".cleanup.lock")
            with open(lock_file, 'w') as f:
                try:
                    # 尝试获取文件锁
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    
                    # 执行清理操作
                    for filename in os.listdir(DATA_DIR):
                        if filename == ".cleanup.lock":
                            continue
                            
                        file_path = os.path.join(DATA_DIR, filename)
                        if os.path.isfile(file_path):
                            # 获取文件的修改时间
                            file_time = os.path.getmtime(file_path)
                            if file_time < expiry_time:
                                try:
                                    os.remove(file_path)
                                    count += 1
                                except (OSError, PermissionError) as e:
                                    logger.error(f"无法删除文件 {file_path}: {e}")
                    
                    if count > 0:
                        logger.info(f"已清理 {count} 个过期文件")
                        
                    # 释放锁
                    fcntl.flock(f, fcntl.LOCK_UN)
                except IOError:
                    # 无法获取锁，说明另一个进程正在执行清理
                    logger.info("另一个清理进程正在运行，跳过本次清理")
            
            # 等待下一次清理
            time.sleep(CLEANUP_INTERVAL_HOURS * 3600)
        except Exception as e:
            logger.error(f"清理文件时出错: {e}")
            time.sleep(300)  # 发生错误后等待5分钟再尝试

def sanitize_filename(filename):
    """
    清理文件名，移除不安全的字符
    """
    # 如果文件名为空，使用默认值
    if not filename or filename.strip() == "":
        return str(int(time.time()))
    
    # 仅保留字母、数字、下划线、横杠和点
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    
    # 确保文件名不超过100个字符
    if len(filename) > 100:
        filename = filename[:100]
    
    return filename

@app.route('/upload', methods=['POST'])
@limiter.limit("10 per minute")
def upload_markdown():
    try:
        content = request.get_data(as_text=True)
        if not content.strip():
            return jsonify({
                "success": False,
                "message": "上传内容为空",
                "error": "内容不能为空"
            }), 400
        
        # 计算内容哈希值
        content_hash = get_content_hash(content)
        
        # 检查缓存中是否已有此内容
        with cache_lock:
            if content_hash in content_cache:
                cache_data = content_cache[content_hash]
                # 检查文件是否仍然存在
                html_path = os.path.join(DATA_DIR, cache_data['files']['html'])
                md_path = os.path.join(DATA_DIR, cache_data['files']['markdown'])
                
                if (os.path.exists(html_path) and os.path.exists(md_path)):
                    logger.info(f"使用缓存的思维导图: {cache_data['base_name']}")
                    return jsonify(cache_data)
        
        # 获取自定义文件名参数
        custom_filename = request.args.get('filename', '')
        
        # 处理并清理文件名
        safe_filename = sanitize_filename(custom_filename)
        timestamp = int(time.time())
        
        # 构建文件名
        if safe_filename:
            base_filename = f"{safe_filename}_{timestamp}"
        else:
            base_filename = str(timestamp)
        
        file_name = f"{base_filename}.md"
        html_name = f"{base_filename}.html"
        file_path = os.path.join(DATA_DIR, file_name)
        
        # 保存 Markdown 文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 转换 Markdown 为 HTML
        html_path = os.path.join(DATA_DIR, html_name)
        result = subprocess.run(
            ['npx', 'markmap-cli', file_path, '--no-open', '-o', html_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 使用固定的公共URL
        preview_url = f"{PUBLIC_URL}/html/{html_name}"
        download_urls = {
            "html": f"{PUBLIC_URL}/download/{html_name}",
            "markdown": f"{PUBLIC_URL}/download/{file_name}"
        }
        
        response_data = {
            "success": True,
            "message": "思维导图HTML文件已生成",
            "preview_url": preview_url,
            "download_urls": download_urls,
            "files": {
                "html": html_name,
                "markdown": file_name
            },
            "base_name": base_filename,
            "timestamp": timestamp
        }
        
        # 将结果存入缓存
        with cache_lock:
            content_cache[content_hash] = response_data
            # 限制缓存大小，最多保存100项
            if len(content_cache) > 100:
                # 移除最早的缓存项
                oldest_key = next(iter(content_cache))
                del content_cache[oldest_key]
        
        return jsonify(response_data)
    
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr
        logger.error(f"转换 Markdown 失败: {error_msg}")
        return jsonify({
            "success": False,
            "message": "转换 Markdown 失败",
            "error": error_msg
        }), 500
    except Exception as e:
        error_msg = str(e)
        logger.error(f"处理上传时出错: {error_msg}")
        return jsonify({
            "success": False,
            "message": "处理上传时出错",
            "error": error_msg
        }), 500

@app.route('/html/<filename>', methods=['GET'])
def get_html(filename):
    return send_from_directory(DATA_DIR, filename)

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """提供文件下载服务"""
    try:
        file_path = os.path.join(DATA_DIR, filename)
        if not os.path.exists(file_path):
            return jsonify({
                "success": False,
                "message": "文件不存在",
                "error": "请求的文件未找到"
            }), 404
        
        # 根据文件扩展名设置合适的MIME类型
        if filename.endswith('.html'):
            mimetype = 'text/html'
        elif filename.endswith('.md'):
            mimetype = 'text/markdown'
        else:
            mimetype = 'application/octet-stream'
        
        return send_from_directory(
            DATA_DIR, 
            filename, 
            as_attachment=True,
            mimetype=mimetype
        )
    except Exception as e:
        logger.error(f"下载文件时出错: {e}")
        return jsonify({
            "success": False,
            "message": "下载文件时出错",
            "error": str(e)
        }), 500

@app.route('/files/<base_name>', methods=['GET'])
def get_file_info(base_name):
    """获取指定基础名称的所有相关文件信息"""
    try:
        files_info = {}
        file_types = ['html', 'md']
        
        for file_type in file_types:
            extension = '.html' if file_type == 'html' else '.md'
            filename = f"{base_name}{extension}"
            file_path = os.path.join(DATA_DIR, filename)
            if os.path.exists(file_path):
                files_info[file_type] = {
                    "filename": filename,
                    "download_url": f"{PUBLIC_URL}/download/{filename}",
                    "size": os.path.getsize(file_path),
                    "modified_time": os.path.getmtime(file_path)
                }
        
        if not files_info:
            return jsonify({
                "success": False,
                "message": "未找到相关文件",
                "error": "指定的文件组不存在"
            }), 404
        
        return jsonify({
            "success": True,
            "base_name": base_name,
            "files": files_info,
            "preview_url": f"{PUBLIC_URL}/html/{base_name}.html" if 'html' in files_info else None
        })
    
    except Exception as e:
        logger.error(f"获取文件信息时出错: {e}")
        return jsonify({
            "success": False,
            "message": "获取文件信息时出错",
            "error": str(e)
        }), 500

if __name__ == '__main__':
    # 启动清理线程
    cleanup_thread = threading.Thread(target=clean_old_files, daemon=True)
    cleanup_thread.start()
    logger.info(f"文件清理服务已启动，每 {CLEANUP_INTERVAL_HOURS} 小时清理一次，文件保留 {FILE_EXPIRY_HOURS} 小时")
    
    # 启动 Flask 应用
    logger.info(f"服务器正在启动于 {HOST}:{PORT}")
    logger.info(f"对外公开URL: {PUBLIC_URL}")
    app.run(host=HOST, port=PORT)
