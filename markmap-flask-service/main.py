from flask import Flask, request, send_from_directory, jsonify
import time
import subprocess
import os
import threading
import shutil
import logging
import re
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

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

def generate_png_screenshot(html_path, png_path):
    """
    使用Selenium生成HTML文件的PNG截图
    """
    try:
        # 配置Chrome选项
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-plugins')
        chrome_options.add_argument('--disable-web-security')
        chrome_options.add_argument('--disable-features=VizDisplayCompositor')
        chrome_options.add_argument('--remote-debugging-port=9222')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        
        # 检查是否在Docker环境中
        chrome_binary = os.environ.get('CHROME_BIN', '/usr/bin/google-chrome')
        if os.path.exists(chrome_binary):
            chrome_options.binary_location = chrome_binary
        
        # 创建WebDriver服务
        try:
            service = Service(ChromeDriverManager().install())
        except Exception:
            # 如果ChromeDriverManager失败，尝试使用系统中的chromedriver
            service = Service('/usr/bin/chromedriver') if os.path.exists('/usr/bin/chromedriver') else None
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        try:
            # 打开HTML文件
            file_url = f"file://{os.path.abspath(html_path)}"
            driver.get(file_url)
            
            # 等待页面加载完成
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "svg"))
            )
            
            # 等待额外时间确保思维导图完全渲染
            time.sleep(3)
            
            # 获取页面截图
            driver.save_screenshot(png_path)
            logger.info(f"PNG截图已生成: {png_path}")
            return True
            
        finally:
            driver.quit()
            
    except Exception as e:
        logger.error(f"生成PNG截图失败: {e}")
        return False

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
        html_path = os.path.join(DATA_DIR, html_name)
        result = subprocess.run(
            ['npx', 'markmap-cli', file_path, '--no-open', '-o', html_path],
            capture_output=True,
            text=True,
            check=True
        )
        
        # 生成PNG图片文件
        png_name = f"{base_filename}.png"
        png_path = os.path.join(DATA_DIR, png_name)
        
        # 使用Selenium生成PNG截图
        png_success = generate_png_screenshot(html_path, png_path)
        
        # 使用固定的公共URL
        preview_url = f"{PUBLIC_URL}/html/{html_name}"
        download_urls = {
            "html": f"{PUBLIC_URL}/download/{html_name}",
            "markdown": f"{PUBLIC_URL}/download/{file_name}",
            "png": f"{PUBLIC_URL}/download/{png_name}" if png_success and os.path.exists(png_path) else None
        }
        
        return jsonify({
            "success": True,
            "message": "思维导图文件已生成",
            "preview_url": preview_url,
            "download_urls": download_urls,
            "files": {
                "html": html_name,
                "markdown": file_name,
                "png": png_name if png_success and os.path.exists(png_path) else None
            },
            "base_name": base_filename,
            "timestamp": timestamp,
            "png_generated": png_success
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
        elif filename.endswith('.png'):
            mimetype = 'image/png'
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
        file_types = ['html', 'md', 'png']
        
        for file_type in file_types:
            filename = f"{base_name}.{file_type}"
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
