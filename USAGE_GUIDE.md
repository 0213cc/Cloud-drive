# 云盘系统使用指南

完整的从零开始使用指南。

## 📋 目录

1. [AWS配置](#1-aws配置)
2. [本地开发](#2-本地开发)
3. [远程部署](#3-远程部署)
4. [客户端使用](#4-客户端使用)
5. [进阶使用](#5-进阶使用)

---

## 1. AWS配置

### 在远程Ubuntu EC2上配置

```bash
# 1. SSH连接到EC2
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com

# 2. 下载并运行配置脚本
wget https://raw.githubusercontent.com/YOUR_REPO/cloud-drive/main/setup_aws.sh
chmod +x setup_aws.sh
./setup_aws.sh

# 或者手动配置：
aws configure
# 输入 Access Key ID
# 输入 Secret Access Key
# 区域: ap-northeast-1
# 输出格式: json

# 3. 创建S3存储桶
aws s3 mb s3://cloud-drive-yourname-123

# 4. 测试
aws s3 ls
```

**详细步骤**: [docs/AWS_SETUP.md](docs/AWS_SETUP.md)

---

## 2. 本地开发

### Windows本地测试（无需AWS）

```powershell
# 1. 进入后端目录
cd D:\Dase\云计算\Cloud-drive\backend

# 2. 运行启动脚本
.\start.bat

# 或手动启动：
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python app/main.py
```

### 访问API

- API地址: http://localhost:8000
- API文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

---

## 3. 远程部署

### 方法A: 使用Git部署（推荐）

```bash
# 在本地Windows上提交代码
cd D:\Dase\云计算\Cloud-drive
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/cloud-drive.git
git push -u origin main

# SSH到远程
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com

# 在远程克隆
cd ~
git clone https://github.com/YOUR_USERNAME/cloud-drive.git
cd cloud-drive/backend

# 启动服务
chmod +x start.sh
./start.sh
```

### 方法B: 直接上传（快速测试）

```powershell
# 在本地Windows PowerShell中
scp -i "D:\cloud2.pem" -r D:\Dase\云计算\Cloud-drive ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:~/

# SSH到远程
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com

# 启动服务
cd ~/Cloud-drive/backend
chmod +x start.sh
./start.sh
```

### 配置后台运行

```bash
# 使用systemd（推荐）
sudo nano /etc/systemd/system/cloud-drive.service

# 粘贴配置（见 docs/DEPLOYMENT.md）

# 启动服务
sudo systemctl start cloud-drive
sudo systemctl enable cloud-drive
sudo systemctl status cloud-drive
```

**详细步骤**: [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)

---

## 4. 客户端使用

### 安装客户端

```powershell
# 在本地Windows
cd D:\Dase\云计算\Cloud-drive\client

# 运行安装脚本
.\setup.bat

# 或手动安装：
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### 配置客户端

编辑 `client/.env`：

```env
# 本地开发
API_BASE_URL=http://localhost:8000

# 远程服务器
# API_BASE_URL=http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:8000

USER_ID=1
DOWNLOAD_DIR=./downloads
```

### 基础命令

```powershell
# 1. 查看帮助
python client.py --help

# 2. 列出所有文件
python client.py list

# 3. 上传文件
python client.py upload myfile.txt

# 4. 上传到指定目录
python client.py upload myfile.txt --path /documents

# 5. 下载文件（假设文件ID为1）
python client.py download 1

# 6. 下载到指定位置
python client.py download 1 --output D:\Downloads\myfile.txt

# 7. 创建目录
python client.py mkdir /photos

# 8. 查看文件信息
python client.py info 1

# 9. 删除文件
python client.py delete 1
```

### 创建测试文件

```powershell
# 运行测试脚本创建不同大小的文件
cd D:\Dase\云计算\Cloud-drive
python test_upload.py

# 会创建：
# - small_file.txt (1KB)
# - medium_file.txt (10MB)
# - large_file.bin (150MB) - 触发多线程上传

# 上传测试
cd client
python client.py upload ..\small_file.txt
python client.py upload ..\large_file.bin   # 多线程上传
```

---

## 5. 进阶使用

### 测试多线程上传下载

```powershell
# 创建大文件（200MB）
fsutil file createnew large_test.bin 209715200

# 上传（自动使用多线程）
python client.py upload large_test.bin

# 观察后端日志，应该看到：
# INFO - 使用多线程上传 (文件大小: 200.00 MB)
# INFO - 开始多线程上传: 25 个分块
# INFO - 分块 1/25 上传完成
# ...

# 下载（自动使用多线程）
python client.py download 1 --output downloaded.bin
```

### 调整性能参数

编辑 `backend/.env`：

```env
# 分块大小（字节）
CHUNK_SIZE=8388608           # 8MB (默认)
# 可选: 4194304 (4MB) 或 16777216 (16MB)

# 多线程阈值（超过此大小使用多线程）
MULTIPART_THRESHOLD=104857600  # 100MB (默认)
# 可选: 52428800 (50MB) 或 209715200 (200MB)

# 最大并发线程数
MAX_CONCURRENCY=10            # 10线程 (默认)
# 根据EC2实例调整: t2.micro=3, t2.small=5, t2.medium=10
```

### 批量操作示例

```powershell
# 批量上传目录下所有文件
Get-ChildItem *.txt | ForEach-Object { python client.py upload $_.FullName --path /documents }

# 批量下载（假设有多个文件）
1..10 | ForEach-Object { python client.py download $_ --output "file_$_.bin" }
```

### 使用Python脚本调用

```python
# example.py
from client import CloudDriveClient

# 创建客户端
client = CloudDriveClient("http://localhost:8000")

# 上传文件
result = client.upload_file("myfile.txt", remote_path="/documents")
print(f"上传结果: {result}")

# 列出文件
files = client.list_files("/documents")
for file in files:
    print(f"{file['filename']} - {file['size']} bytes")

# 下载文件
client.download_file(file_id=1, output_path="downloaded.txt")
```

### API直接调用

```python
import requests

API_URL = "http://localhost:8000"

# 上传文件
with open("myfile.txt", "rb") as f:
    files = {"file": f}
    params = {"path": "/"}
    response = requests.post(f"{API_URL}/api/files/upload", files=files, params=params)
    print(response.json())

# 列出文件
response = requests.get(f"{API_URL}/api/files/list", params={"path": "/"})
print(response.json())

# 下载文件
response = requests.get(f"{API_URL}/api/files/download/1", stream=True)
with open("downloaded.txt", "wb") as f:
    for chunk in response.iter_content(chunk_size=8192):
        f.write(chunk)
```

---

## 📊 功能对照表

| 功能 | 状态 | 命令示例 |
|-----|------|---------|
| 上传小文件 | ✅ | `python client.py upload file.txt` |
| 上传大文件（多线程） | ✅ | `python client.py upload large.bin` |
| 下载小文件 | ✅ | `python client.py download 1` |
| 下载大文件（多线程） | ✅ | `python client.py download 1` |
| 列出文件 | ✅ | `python client.py list` |
| 删除文件 | ✅ | `python client.py delete 1` |
| 创建目录 | ✅ | `python client.py mkdir /docs` |
| 查看文件信息 | ✅ | `python client.py info 1` |
| 文件哈希计算 | ✅ | 自动 |
| 进度显示 | ✅ | 自动 |

---

## 🔧 故障排查

### 问题1: 找不到模块

```powershell
# 确保虚拟环境已激活
cd backend
venv\Scripts\activate

# 重新安装依赖
pip install -r requirements.txt
```

### 问题2: 无法连接到后端

```powershell
# 检查后端是否运行
# 访问: http://localhost:8000

# 检查端口占用
netstat -ano | findstr :8000

# 修改客户端配置
notepad client\.env
# 确保 API_BASE_URL 正确
```

### 问题3: AWS权限错误

```bash
# 在远程服务器检查
aws s3 ls

# 如果失败，重新配置
aws configure

# 检查IAM权限（在AWS控制台）
```

### 问题4: 上传失败

```powershell
# 检查文件大小
# 默认最大5GB，可在 .env 中修改 MAX_FILE_SIZE

# 检查后端日志
# 在远程服务器: sudo journalctl -u cloud-drive -f

# 检查S3存储桶是否存在
aws s3 ls | grep your-bucket-name
```

---

## 📈 性能监控

### 查看上传下载速度

客户端会自动显示进度和速度：

```
上传 large_file.bin: 45%|████████      | 90MB/200MB [00:15<00:18, 6.1MB/s]
```

### 查看后端日志

```bash
# 实时日志
sudo journalctl -u cloud-drive -f

# 最近100行
sudo journalctl -u cloud-drive -n 100

# 过滤错误
sudo journalctl -u cloud-drive | grep ERROR
```

### 查看S3使用情况

```bash
# 查看存储桶大小和文件数
aws s3 ls s3://your-bucket-name --recursive --human-readable --summarize

# 示例输出：
# Total Objects: 42
# Total Size: 1.2 GiB
```

---

## 🎯 最佳实践

1. **小文件**（<1MB）: 直接上传，不需要多线程
2. **中等文件**（1-100MB）: 系统自动优化
3. **大文件**（>100MB）: 自动启用多线程，显著提升速度
4. **巨型文件**（>1GB）: 建议调整 `CHUNK_SIZE` 为 16MB

---

## 📚 相关文档

- [AWS配置指南](docs/AWS_SETUP.md)
- [部署指南](docs/DEPLOYMENT.md)
- [快速开始](docs/QUICK_START.md)
- [API文档](http://localhost:8000/docs)

---

## 🆘 获取帮助

遇到问题？

1. 查看文档: `docs/` 目录
2. 查看日志: 后端控制台或 `journalctl`
3. 检查配置: `.env` 文件
4. 测试连接: `curl http://localhost:8000/health`

---

**祝你使用愉快！🚀**

