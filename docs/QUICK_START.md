# 快速开始指南

5分钟快速体验云盘系统！

## 本地开发测试（不需要AWS）

### 1. 安装依赖

```powershell
# 在本地Windows PowerShell中
cd D:\Dase\云计算\Cloud-drive\backend

# 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置环境变量（本地测试）

创建 `backend/.env`：

```env
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
AWS_REGION=ap-northeast-1
AWS_S3_BUCKET=test-bucket
DATABASE_URL=sqlite:///./cloud_drive.db
SECRET_KEY=test-secret-key-for-development-only
```

**注意**：本地测试时S3操作会失败，但可以测试API结构。

### 3. 运行后端

```powershell
# 在backend目录中
cd D:\Dase\云计算\Cloud-drive\backend
python app/main.py
```

访问：http://localhost:8000/docs

### 4. 测试API

在浏览器打开 http://localhost:8000/docs，你会看到：

- POST `/api/files/upload` - 上传文件
- GET `/api/files/download/{file_id}` - 下载文件
- GET `/api/files/list` - 列出文件
- DELETE `/api/files/delete/{file_id}` - 删除文件
- POST `/api/files/mkdir` - 创建目录

---

## 使用AWS S3（生产环境）

### 前置步骤

1. 完成 [AWS_SETUP.md](./AWS_SETUP.md) - 配置S3和凭证
2. 完成 [DEPLOYMENT.md](./DEPLOYMENT.md) - 部署到EC2

### 快速测试流程

```powershell
# 1. 配置客户端
cd D:\Dase\云计算\Cloud-drive\client
notepad .env

# 填入：
# API_BASE_URL=http://your-ec2-address:8000
# USER_ID=1
# DOWNLOAD_DIR=./downloads

# 2. 安装客户端依赖
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. 测试上传
python client.py upload test.txt

# 4. 列出文件
python client.py list

# 5. 下载文件
python client.py download 1
```

---

## 测试多线程上传下载

### 创建大文件测试

```powershell
# 创建一个200MB的测试文件
fsutil file createnew large_file.bin 209715200

# 上传（会自动使用多线程）
python client.py upload large_file.bin

# 下载（会自动使用多线程）
python client.py download 1 --output downloaded_large.bin
```

### 验证多线程效果

查看后端日志，你应该看到类似输出：

```
INFO - 使用多线程上传 (文件大小: 200.00 MB)
INFO - 开始多线程上传: 25 个分块
INFO - 分块 1/25 上传完成
INFO - 分块 2/25 上传完成
...
INFO - 多线程上传完成
```

---

## 功能清单

### ✅ 已实现

- [x] 基础文件操作（上传、下载、列表、删除）
- [x] 创建目录
- [x] 多线程上传（>100MB文件）
- [x] 多线程下载（>100MB文件）
- [x] 文件哈希计算（SHA-256）
- [x] S3对象存储集成
- [x] 数据库元数据管理
- [x] RESTful API
- [x] 命令行客户端

### 🚧 待实现（后续阶段）

- [ ] 用户认证（JWT）
- [ ] 文件压缩
- [ ] 文件级去重
- [ ] 块级去重
- [ ] 差分同步
- [ ] 断点续传
- [ ] 版本控制
- [ ] 文件共享
- [ ] 自动同步客户端

---

## 常用命令

### 后端命令

```powershell
# 启动后端
cd backend
venv\Scripts\activate
python app/main.py

# 初始化数据库
python -c "from app.models.database import init_db; init_db()"

# 查看数据库
pip install sqlite-web
sqlite_web cloud_drive.db
```

### 客户端命令

```powershell
# 列出所有文件
python client.py list

# 上传文件到根目录
python client.py upload myfile.txt

# 上传到指定目录
python client.py upload myfile.txt --path /documents

# 下载文件
python client.py download 1

# 创建目录
python client.py mkdir /photos

# 查看文件信息
python client.py info 1

# 删除文件
python client.py delete 1
```

---

## 项目结构

```
Cloud-drive/
├── backend/              # 后端服务
│   ├── app/
│   │   ├── main.py      # 主应用入口
│   │   ├── api/         # API路由
│   │   ├── models/      # 数据模型
│   │   └── services/    # S3服务
│   ├── config.py        # 配置管理
│   └── requirements.txt
│
├── client/              # 客户端工具
│   ├── client.py        # 命令行客户端
│   ├── config.py        # 客户端配置
│   └── requirements.txt
│
└── docs/                # 文档
    ├── AWS_SETUP.md     # AWS配置指南
    ├── DEPLOYMENT.md    # 部署指南
    └── QUICK_START.md   # 快速开始
```

---

## 下一步学习

1. **理解多线程上传下载原理**
   - 查看 `backend/app/services/storage.py`
   - 学习S3分块上传API
   - 理解ThreadPoolExecutor

2. **扩展功能**
   - 添加进度回调
   - 实现断点续传
   - 添加文件压缩

3. **性能优化**
   - 调整CHUNK_SIZE
   - 优化MAX_CONCURRENCY
   - 使用异步IO

---

## 获取帮助

- 查看API文档：http://localhost:8000/docs
- 查看客户端帮助：`python client.py --help`
- 查看详细日志：检查后端控制台输出

---

## 常见问题

**Q: 无法连接到后端？**
A: 检查后端是否运行，查看端口是否正确（8000）

**Q: S3上传失败？**
A: 检查AWS凭证配置，确保存储桶存在

**Q: 下载的文件损坏？**
A: 检查网络连接，确保多线程下载正确完成

**Q: 数据库找不到表？**
A: 运行数据库初始化命令

---

现在开始使用云盘系统吧！🚀

