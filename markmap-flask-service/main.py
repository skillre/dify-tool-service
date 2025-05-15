from flask import Flask, request, send_from_directory, jsonify
import time
import subprocess
import os
import threading
import shutil
import logging
import re

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

# 配置
DATA_DIR = "data"
FILE_EXPIRY_HOURS = 24  # 文件过期时间(小时)
CLEANUP_INTERVAL_HOURS = 1  # 清理间隔(小时)
HOST = "192.168.3.11"
PORT = 5003
# 对外提供的固定链接地址
PUBLIC_URL = "xxx" # 按需更改，格式为http://xxx:xxx

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

def clean_old_files():
    """定时清理过期文件"""
    while True:
        try:
            now = time.time()
            expiry_time = now - (FILE_EXPIRY_HOURS * 3600)
            count = 0
            
            for filename in os.listdir(DATA_DIR):
                file_path = os.path.join(DATA_DIR, filename)
                if os.path.isfile(file_path):
                    # 获取文件的修改时间
                    file_time = os.path.getmtime(file_path)
                    if file_time < expiry_time:
                        os.remove(file_path)
                        count += 1
            
            if count > 0:
                logger.info(f"已清理 {count} 个过期文件")
            
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
def upload_markdown():
    try:
        content = request.get_data(as_text=True)
        if not content.strip():
            return jsonify({
                "success": False,
                "message": "上传内容为空",
                "error": "内容不能为空"
            }), 400
        
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
        result = subprocess.run(
            ['npx', 'markmap-cli', file_path, '--no-open'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 使用固定的公共URL
        preview_url = f"{PUBLIC_URL}/html/{html_name}"
        return jsonify({
            "success": True,
            "message": "Markdown 文件已保存",
            "preview_url": preview_url,
            "file_name": html_name,
            "base_name": base_filename,
            "timestamp": timestamp
        })
    
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

if __name__ == '__main__':
    # 启动清理线程
    cleanup_thread = threading.Thread(target=clean_old_files, daemon=True)
    cleanup_thread.start()
    logger.info(f"文件清理服务已启动，每 {CLEANUP_INTERVAL_HOURS} 小时清理一次，文件保留 {FILE_EXPIRY_HOURS} 小时")
    
    # 启动 Flask 应用
    logger.info(f"服务器正在启动于 {HOST}:{PORT}")
    logger.info(f"对外公开URL: {PUBLIC_URL}")
    app.run(host=HOST, port=PORT)
