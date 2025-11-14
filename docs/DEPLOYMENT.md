# 部署指南

本指南介绍如何在AWS EC2上部署云盘后端服务。

## 前提条件

- ✅ 已完成 [AWS_SETUP.md](./AWS_SETUP.md) 中的配置
- ✅ S3存储桶已创建
- ✅ AWS CLI已配置
- ✅ 本地代码已准备好

---

## 部署流程

### 第一步：在本地准备代码

#### 1. 初始化Git仓库（如果还没有）

```powershell
# 在本地Windows PowerShell中
cd D:\Dase\云计算\Cloud-drive

# 初始化Git
git init

# 创建.gitignore
@"
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
*.egg-info/
dist/
build/

# 环境变量
.env
*.pem

# IDE
.vscode/
.idea/
*.swp

# 数据库
*.db
*.sqlite3

# 日志
*.log

# 临时文件
temp/
tmp/
downloads/
"@ | Out-File -FilePath .gitignore -Encoding utf8

# 提交代码
git add .
git commit -m "Initial commit: Cloud Drive基础服务"
```

#### 2. 推送到GitHub（推荐）

```powershell
# 创建GitHub仓库后
git remote add origin https://github.com/YOUR_USERNAME/cloud-drive.git
git branch -M main
git push -u origin main
```

---

### 第二步：部署到远程EC2

#### 1. SSH连接到EC2

```powershell
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com
```

#### 2. 安装依赖环境

```bash
# 更新系统
sudo apt update
sudo apt upgrade -y

# 安装Python 3和pip
sudo apt install python3 python3-pip python3-venv -y

# 安装Git
sudo apt install git -y

# 安装其他工具
sudo apt install nginx -y  # Web服务器（可选）
```

#### 3. 克隆代码

```bash
# 方法A: 从GitHub克隆（推荐）
cd ~
git clone https://github.com/YOUR_USERNAME/cloud-drive.git
cd Cloud-drive

# 方法B: 如果没有GitHub，从本地SCP上传
# 在本地Windows运行：
# scp -i "D:\cloud2.pem" -r D:\Dase\云计算\Cloud-drive ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:~/
```

#### 4. 配置后端环境

```bash
# 进入后端目录
cd ~/Cloud-drive/backend

# 创建虚拟环境
python3 -m venv venv

# 激活虚拟环境
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp env.example .env

# 编辑配置（填入你的AWS信息）
nano .env
```

**重要：填写正确的配置！**

```bash
AWS_ACCESS_KEY_ID=你的Key
AWS_SECRET_ACCESS_KEY=你的Secret
AWS_REGION=ap-northeast-1
AWS_S3_BUCKET=你的存储桶名称
SECRET_KEY=随机生成的密钥
```

#### 5. 初始化数据库

```bash
# 在backend目录中，虚拟环境已激活
python3 -c "from app.models.database import init_db; init_db()"
```

#### 6. 测试运行

```bash
# 临时运行测试
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 如果看到：
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
# 说明启动成功！
```

#### 7. 配置EC2安全组

**重要：允许外部访问8000端口**

1. 登录AWS控制台
2. 进入EC2服务
3. 选择你的实例
4. 点击"安全"选项卡
5. 点击安全组链接
6. 点击"编辑入站规则"
7. 添加规则：
   - 类型: 自定义TCP
   - 端口: 8000
   - 源: 0.0.0.0/0（或你的IP地址）
8. 保存规则

#### 8. 测试API访问

在本地Windows浏览器中访问：

```
http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:8000
```

应该看到：

```json
{
  "message": "Cloud Drive API",
  "version": "0.1.0",
  "docs": "/docs"
}
```

访问API文档：

```
http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:8000/docs
```

---

### 第三步：配置后台运行

#### 方法A: 使用systemd（推荐）

```bash
# 创建systemd服务文件
sudo nano /etc/systemd/system/cloud-drive.service
```

填入内容：

```ini
[Unit]
Description=Cloud Drive Backend Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/cloud-drive/backend
Environment="PATH=/home/ubuntu/cloud-drive/backend/venv/bin"
ExecStart=/home/ubuntu/cloud-drive/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
# 重新加载systemd
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start cloud-drive

# 设置开机自启
sudo systemctl enable cloud-drive

# 查看状态
sudo systemctl status cloud-drive

# 查看日志
sudo journalctl -u cloud-drive -f
```

#### 方法B: 使用screen（简单但不推荐）

```bash
# 安装screen
sudo apt install screen -y

# 创建会话
screen -S cloud-drive

# 在screen中运行
cd ~/cloud-drive/backend
source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 按 Ctrl+A, 然后按 D 退出screen
# 重新连接: screen -r cloud-drive
```

---

### 第四步：配置Nginx反向代理（可选，推荐生产环境）

```bash
# 创建Nginx配置
sudo nano /etc/nginx/sites-available/cloud-drive
```

填入内容：

```nginx
server {
    listen 80;
    server_name ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com;

    client_max_body_size 5G;  # 允许上传大文件

    location / {
        # Handle preflight (OPTIONS) requests for CORS
        if ($request_method = 'OPTIONS') {
            add_header 'Access-Control-Allow-Origin' '*';
            add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS, DELETE, PUT';
            add_header 'Access-Control-Allow-Headers' 'Authorization, Content-Type';
            add_header 'Access-Control-Max-Age' 1728000;
            add_header 'Content-Type' 'text/plain; charset=utf-8';
            add_header 'Content-Length' 0;
            return 204;
        }

        # Add CORS headers to actual requests
        add_header 'Access-Control-Allow-Origin' '*' always;

        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Timeout settings for large file uploads
        proxy_connect_timeout 600;
        proxy_send_timeout 600;
        proxy_read_timeout 600;
    }
}
```

启用配置：

```bash
# 创建软链接
sudo ln -s /etc/nginx/sites-available/cloud-drive /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重启Nginx
sudo systemctl restart nginx
```

现在可以通过80端口访问（无需指定端口）：

```
http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com
```

---

### 第五步：本地客户端测试

#### 1. 配置本地客户端

```powershell
# 在本地Windows
cd D:\Dase\云计算\Cloud-drive\client

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 创建配置文件
notepad .env
```

填入：

```
API_BASE_URL=http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:8000
USER_ID=1
DOWNLOAD_DIR=./downloads
```

#### 2. 测试客户端功能

```powershell
# 查看帮助
python client.py --help

# 列出文件
python client.py list

# 上传文件
python client.py upload test.txt

# 下载文件（假设ID为1）
python client.py download 1

# 创建目录
python client.py mkdir /documents

# 查看文件信息
python client.py info 1

# 删除文件
python client.py delete 1
```

---

## 运维命令

### 查看服务状态

```bash
# 查看服务状态
sudo systemctl status cloud-drive

# 查看实时日志
sudo journalctl -u cloud-drive -f

# 查看最近100行日志
sudo journalctl -u cloud-drive -n 100
```

### 重启服务

```bash
# 重启服务
sudo systemctl restart cloud-drive

# 停止服务
sudo systemctl stop cloud-drive

# 启动服务
sudo systemctl start cloud-drive
```

### 更新代码

```bash
# SSH到远程
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com

# 拉取最新代码
cd ~/cloud-drive
git pull origin main

# 更新依赖
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 重启服务
sudo systemctl restart cloud-drive
```

### 查看S3使用情况

```bash
# 查看存储桶大小
aws s3 ls s3://your-bucket-name --recursive --human-readable --summarize

# 列出最近上传的文件
aws s3 ls s3://your-bucket-name/ --recursive | sort | tail -n 20
```

---

## 故障排查

### 问题1: 无法连接到API

**检查清单：**
1. 服务是否运行：`sudo systemctl status cloud-drive`
2. 端口是否开放：`netstat -tlnp | grep 8000`
3. EC2安全组是否允许8000端口
4. 防火墙是否阻止：`sudo ufw status`

### 问题2: S3上传失败

**检查清单：**
1. AWS凭证是否正确：`aws s3 ls`
2. 存储桶是否存在：`aws s3 ls | grep your-bucket`
3. 查看后端日志：`sudo journalctl -u cloud-drive -f`

### 问题3: 数据库错误

**解决方法：**
```bash
# 重新初始化数据库
cd ~/cloud-drive/backend
source venv/bin/activate
rm -f cloud_drive.db  # 警告：会删除所有数据
python3 -c "from app.models.database import init_db; init_db()"
sudo systemctl restart cloud-drive
```

### 问题4: 内存不足

**检查内存：**
```bash
free -h
```

**优化配置：**
编辑 `.env`，减少并发数：
```
MAX_CONCURRENCY=5  # 从10改为5
```

---

## 性能优化

### 1. 调整并发配置

根据EC2实例类型调整 `.env`：

| 实例类型 | 推荐MAX_CONCURRENCY |
|---------|-------------------|
| t2.micro | 3-5 |
| t2.small | 5-8 |
| t2.medium | 8-12 |
| t3.large | 12-20 |

### 2. 启用Gzip压缩（Nginx）

在Nginx配置中添加：

```nginx
gzip on;
gzip_types text/plain application/json;
gzip_min_length 1000;
```

### 3. 使用PostgreSQL替代SQLite

对于生产环境，建议使用PostgreSQL：

```bash
# 安装PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# 创建数据库
sudo -u postgres psql
CREATE DATABASE cloud_drive;
CREATE USER cloud_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE cloud_drive TO cloud_user;
\q

# 修改.env
DATABASE_URL=postgresql://cloud_user:your_password@localhost/cloud_drive
```

---

## 监控和告警

### 安装监控工具

```bash
# 安装htop
sudo apt install htop -y

# 实时监控
htop
```

### 日志轮转

```bash
# 创建logrotate配置
sudo nano /etc/logrotate.d/cloud-drive
```

内容：

```
/var/log/cloud-drive/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
}
```

---

## 安全建议

1. **限制S3访问**：只允许EC2实例的IAM角色访问
2. **使用HTTPS**：配置SSL证书（Let's Encrypt）
3. **定期备份**：自动备份数据库
4. **更新系统**：定期执行 `sudo apt update && sudo apt upgrade`
5. **监控日志**：定期检查异常访问

---

## 下一步

完成部署后，可以：
1. 实现用户认证系统（JWT）
2. 添加文件去重功能
3. 实现差分同步
4. 添加版本控制
5. 实现文件共享

查看完整项目规划：[README.md](../README.md)

