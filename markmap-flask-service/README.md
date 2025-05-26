# Markmap Flask 服务

这是一个基于Flask的思维导图生成服务，可以将Markdown文件转换为交互式HTML思维导图，并同时生成PNG图片和提供原始文件下载。

## 功能特性

- 📝 **Markdown转思维导图**: 将Markdown文件转换为交互式HTML思维导图
- 🖼️ **PNG图片生成**: 自动生成思维导图的PNG截图
- 📁 **多格式下载**: 提供HTML、Markdown和PNG三种格式的文件下载
- 🔗 **在线预览**: 支持在线预览生成的思维导图
- 🧹 **自动清理**: 定时清理过期文件，节省存储空间
- 🔒 **文件名安全**: 自动清理和规范化文件名

## 安装依赖

```bash
pip install -r requirements.txt
```

### 系统依赖

确保系统已安装以下依赖：

1. **Node.js和npm**: 用于运行markmap-cli
   ```bash
   # macOS
   brew install node
   
   # 安装markmap-cli
   npm install -g markmap-cli
   ```

2. **Chrome浏览器**: 用于生成PNG截图
   - Selenium会自动下载ChromeDriver

## 配置

在 `main.py` 中修改以下配置：

```python
HOST = "192.168.3.11"  # 服务器地址
PORT = 5003            # 服务器端口
PUBLIC_URL = "http://your-domain:5003"  # 对外访问地址
FILE_EXPIRY_HOURS = 24      # 文件保留时间(小时)
CLEANUP_INTERVAL_HOURS = 1  # 清理间隔(小时)
```

## 启动服务

```bash
python main.py
```

## API接口

### 1. 上传Markdown文件

**POST** `/upload`

**参数:**
- `filename` (可选): 自定义文件名
- 请求体: Markdown内容

**响应:**
```json
{
  "success": true,
  "message": "思维导图文件已生成",
  "preview_url": "http://your-domain:5003/html/filename_timestamp.html",
  "download_urls": {
    "html": "http://your-domain:5003/download/filename_timestamp.html",
    "markdown": "http://your-domain:5003/download/filename_timestamp.md",
    "png": "http://your-domain:5003/download/filename_timestamp.png"
  },
  "files": {
    "html": "filename_timestamp.html",
    "markdown": "filename_timestamp.md",
    "png": "filename_timestamp.png"
  },
  "base_name": "filename_timestamp",
  "timestamp": 1234567890,
  "png_generated": true
}
```

### 2. 在线预览

**GET** `/html/<filename>`

直接在浏览器中查看生成的思维导图。

### 3. 文件下载

**GET** `/download/<filename>`

下载指定的文件（HTML、Markdown或PNG格式）。

### 4. 获取文件信息

**GET** `/files/<base_name>`

获取指定基础名称的所有相关文件信息。

**响应:**
```json
{
  "success": true,
  "base_name": "filename_timestamp",
  "files": {
    "html": {
      "filename": "filename_timestamp.html",
      "download_url": "http://your-domain:5003/download/filename_timestamp.html",
      "size": 12345,
      "modified_time": 1234567890.123
    },
    "md": {
      "filename": "filename_timestamp.md",
      "download_url": "http://your-domain:5003/download/filename_timestamp.md",
      "size": 1234,
      "modified_time": 1234567890.123
    },
    "png": {
      "filename": "filename_timestamp.png",
      "download_url": "http://your-domain:5003/download/filename_timestamp.png",
      "size": 123456,
      "modified_time": 1234567890.123
    }
  },
  "preview_url": "http://your-domain:5003/html/filename_timestamp.html"
}
```

## 使用示例

### 使用curl上传Markdown文件

```bash
# 上传Markdown内容
curl -X POST "http://localhost:5003/upload?filename=my-mindmap" \
  -H "Content-Type: text/plain" \
  -d "# 我的思维导图

## 第一章
- 要点1
- 要点2

## 第二章
- 要点A
- 要点B"
```

### 使用Python上传

```python
import requests

markdown_content = """
# 我的思维导图

## 第一章
- 要点1
- 要点2

## 第二章
- 要点A
- 要点B
"""

response = requests.post(
    "http://localhost:5003/upload",
    params={"filename": "my-mindmap"},
    data=markdown_content
)

result = response.json()
print(f"预览地址: {result['preview_url']}")
print(f"下载地址: {result['download_urls']}")
```

## 文件管理

- 所有生成的文件存储在 `data/` 目录中
- 文件会根据配置的过期时间自动清理
- 文件名格式: `{自定义名称}_{时间戳}.{扩展名}`

## 注意事项

1. **Chrome依赖**: PNG生成功能需要Chrome浏览器，服务会自动下载ChromeDriver
2. **Node.js依赖**: 需要安装Node.js和markmap-cli
3. **文件大小**: 建议Markdown文件不要过大，以免影响转换性能
4. **网络访问**: 确保PUBLIC_URL配置正确，以便外部访问

## 故障排除

### PNG生成失败
- 检查Chrome是否正确安装
- 查看日志中的错误信息
- 确保有足够的系统资源

### Markmap转换失败
- 检查Node.js和markmap-cli是否正确安装
- 验证Markdown语法是否正确
- 查看服务器日志获取详细错误信息

## 许可证

MIT License