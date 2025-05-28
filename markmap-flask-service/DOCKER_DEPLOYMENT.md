# Docker 部署指南

本文档介绍了如何使用Docker部署markmap Flask服务，包含完整的思维导图生成、PNG截图和文件下载功能。

## 方法一：使用Docker Compose（推荐）

使用Docker Compose是最简单的部署方式，只需几个简单的步骤即可完成部署。

### 前提条件

- 安装了Docker和Docker Compose
- 克隆或下载了本项目代码

### 部署步骤

1. 复制环境变量示例文件并根据需要修改

```bash
cp env.example .env
```

2. 编辑`.env`文件，配置您的环境变量，特别是`PUBLIC_URL`，确保它指向您的公网地址

```
# 服务配置
PUBLIC_URL=http://your-domain:5003  # 修改为您的公网地址
PORT=5003                           # 服务端口

# 数据存储
DATA_VOLUME=./data                  # 数据存储路径

# 文件管理
FILE_EXPIRY_HOURS=24                # 文件过期时间(小时)
CLEANUP_INTERVAL_HOURS=1            # 清理间隔(小时)
```

3. 使用Docker Compose构建并启动服务

```bash
docker-compose up -d
```

4. 服务将在`http://localhost:5003`（或您在`.env`中配置的地址）上运行

### 查看日志

```bash
docker-compose logs -f
```

### 停止服务

```bash
docker-compose down
```

### 更新服务

```bash
git pull                # 获取最新代码
docker-compose build    # 重新构建镜像
docker-compose up -d    # 重启服务
```

## 方法二：使用Docker直接部署

### 🐳 Docker镜像特性

#### 已安装组件
- **Python 3.11**: 基础运行环境
- **Node.js 18**: 用于运行markmap-cli
- **Google Chrome**: 用于生成PNG截图
- **ChromeDriver**: Selenium WebDriver
- **markmap-cli**: 思维导图生成工具
- **中文字体支持**: Noto CJK字体

#### 环境变量配置
```dockerfile
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DISPLAY=:99
ENV CHROME_BIN=/usr/bin/google-chrome
ENV CHROME_PATH=/usr/bin/google-chrome
```

## 🚀 快速部署

### 1. 构建Docker镜像

```bash
# 在项目根目录执行
cd /Users/skillre/Library/Mobile\ Documents/com~apple~CloudDocs/Trae/cursor/dify-tool-service/markmap-flask-service

# 构建镜像
docker build -t markmap-service .
```

### 2. 运行容器

```bash
# 基本运行
docker run -d \
  --name markmap-service \
  -p 5003:5003 \
  markmap-service

# 带数据持久化运行
docker run -d \
  --name markmap-service \
  -p 5003:5003 \
  -v $(pwd)/data:/app/data \
  markmap-service

# 带环境变量配置运行
docker run -d \
  --name markmap-service \
  -p 5003:5003 \
  -v $(pwd)/data:/app/data \
  -e PUBLIC_URL="http://your-domain.com:5003" \
  markmap-service
```

### 3. 验证部署

```bash
# 检查容器状态
docker ps

# 查看日志
docker logs markmap-service

# 测试服务
curl -X POST "http://localhost:5003/upload?filename=test" \
  -H "Content-Type: text/plain" \
  -d "# 测试思维导图\n\n## 第一章\n- 要点1\n- 要点2"
```

## 🔧 高级配置

### 生产环境配置

#### 1. 反向代理配置 (Nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;
    
    client_max_body_size 10M;
    
    location / {
        proxy_pass http://localhost:5003;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 增加超时时间，用于PNG生成
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

#### 2. 环境变量配置

创建 `.env` 文件：

```bash
# 服务配置
PUBLIC_URL=https://your-domain.com
HOST=0.0.0.0
PORT=5003

# 文件管理
FILE_EXPIRY_HOURS=24
CLEANUP_INTERVAL_HOURS=1

# Chrome配置
CHROME_BIN=/usr/bin/google-chrome
DISPLAY=:99
```

## 📊 监控和维护

### 容器监控

```bash
# 查看资源使用情况
docker stats markmap-service

# 查看容器详细信息
docker inspect markmap-service

# 进入容器调试
docker exec -it markmap-service /bin/bash
```

### 日志管理

```bash
# 查看实时日志
docker logs -f markmap-service

# 查看最近100行日志
docker logs --tail 100 markmap-service

# 配置日志轮转
docker run -d \
  --name markmap-service \
  --log-driver json-file \
  --log-opt max-size=10m \
  --log-opt max-file=3 \
  -p 5003:5003 \
  markmap-service
```

### 数据备份

```bash
# 备份数据目录
docker run --rm \
  -v markmap_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/markmap-backup-$(date +%Y%m%d).tar.gz -C /data .

# 恢复数据
docker run --rm \
  -v markmap_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/markmap-backup-20231201.tar.gz -C /data
```

## 🐛 故障排除

### 常见问题

#### 1. PNG生成失败

```bash
# 检查Chrome是否正常安装
docker exec markmap-service google-chrome --version

# 检查ChromeDriver
docker exec markmap-service chromedriver --version

# 测试Chrome无头模式
docker exec markmap-service google-chrome --headless --no-sandbox --dump-dom https://www.google.com
```

#### 2. markmap-cli问题

```bash
# 检查Node.js和npm
docker exec markmap-service node --version
docker exec markmap-service npm --version

# 检查markmap-cli
docker exec markmap-service markmap --version
```

#### 3. 权限问题

```bash
# 检查数据目录权限
docker exec markmap-service ls -la /app/data

# 修复权限
docker exec markmap-service chmod 777 /app/data
```

### 性能优化

#### 1. 内存限制

```bash
# 限制容器内存使用
docker run -d \
  --name markmap-service \
  --memory=1g \
  --memory-swap=2g \
  -p 5003:5003 \
  markmap-service
```

#### 2. CPU限制

```bash
# 限制CPU使用
docker run -d \
  --name markmap-service \
  --cpus="1.5" \
  -p 5003:5003 \
  markmap-service
```

## 🔄 更新部署

```bash
# 停止旧容器
docker stop markmap-service
docker rm markmap-service

# 重新构建镜像
docker build -t markmap-service .

# 启动新容器
docker run -d \
  --name markmap-service \
  -p 5003:5003 \
  -v $(pwd)/data:/app/data \
  markmap-service
```

## 📝 注意事项

1. **资源需求**: Chrome和ChromeDriver需要较多内存，建议至少分配1GB内存
2. **网络访问**: 确保容器能访问外网以下载ChromeDriver
3. **文件权限**: 数据目录需要适当的读写权限
4. **安全考虑**: 生产环境建议使用HTTPS和适当的访问控制
5. **备份策略**: 定期备份重要的思维导图文件

## 🔗 相关链接

- [Docker官方文档](https://docs.docker.com/)
- [markmap-cli文档](https://markmap.js.org/)
- [Selenium文档](https://selenium-python.readthedocs.io/)
- [Chrome Headless文档](https://developers.google.com/web/updates/2017/04/headless-chrome)