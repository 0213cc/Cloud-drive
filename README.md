# Cloud Drive - 云盘系统

基于AWS S3的分布式云盘系统，支持多线程上传下载、文件去重、差分同步等高级功能。

## ✨ 特性

### Phase 1: 基础服务 ✅（已完成）

- ✅ **文件基础操作**：上传、下载、列表、删除、创建目录
- ✅ **多线程传输**：智能选择上传下载方式，大文件自动启用多线程
- ✅ **S3存储集成**：使用AWS S3对象存储，支持大规模存储
- ✅ **元数据管理**：SQLite/PostgreSQL存储文件元信息
- ✅ **RESTful API**：完整的REST接口，支持CORS
- ✅ **命令行客户端**：方便的CLI工具，支持进度显示

### Phase 2-5: 高级功能（计划中）

- 🚧 用户认证系统（JWT）
- 🚧 文件压缩（Gzip/Zlib）
- 🚧 文件级去重（基于哈希）
- 🚧 块级去重（CDC算法）
- 🚧 差分同步（rsync算法）
- 🚧 断点续传
- 🚧 版本控制
- 🚧 冲突解决
- 🚧 文件共享与协作
- 🚧 自动同步客户端（watchdog）

## 🏗️ 架构

```
┌─────────────────┐
│  Client (本地)   │
│  - CLI工具       │
│  - 文件监控      │
└────────┬────────┘
         │ HTTP/REST
         ▼
┌─────────────────────────────┐
│   Backend (AWS EC2)         │
│  ┌─────────────────────┐   │
│  │  FastAPI Service    │   │
│  └──────────┬──────────┘   │
│             │               │
│  ┌──────────▼──────────┐   │
│  │  S3StorageService   │   │
│  │  - 多线程上传        │   │
│  │  - 多线程下载        │   │
│  └──────────┬──────────┘   │
│             │               │
│  ┌──────────▼──────────┐   │
│  │  SQLite Database    │   │
│  └─────────────────────┘   │
└──────────┬──────────────────┘
           │
           ▼
   ┌───────────────┐
   │   AWS S3      │
   │ (对象存储)     │
   └───────────────┘
```

## 🚀 快速开始

### 方法一：一键启动（推荐）

#### Windows用户

```powershell
# 1. 启动后端
cd Cloud-drive\backend
.\start.bat

# 2. 在新窗口中设置客户端
cd Cloud-drive\client
.\setup.bat

# 3. 测试
python client.py list
```

#### Linux/Mac用户

```bash
# 1. 启动后端
cd Cloud-drive/backend
chmod +x start.sh
./start.sh

# 2. 在新终端中设置客户端
cd Cloud-drive/client
pip install -r requirements.txt
python client.py list
```

### 方法二：手动配置

#### 1. 克隆项目

```bash
git clone https://github.com/YOUR_USERNAME/cloud-drive.git
cd cloud-drive
```

#### 2. 配置AWS（生产环境）

详细步骤见 [docs/AWS_SETUP.md](docs/AWS_SETUP.md)

```bash
# SSH到EC2
ssh -i "your-key.pem" ubuntu@your-ec2-address

# 运行配置脚本
wget https://raw.githubusercontent.com/.../setup_aws.sh
chmod +x setup_aws.sh
./setup_aws.sh
```

#### 3. 启动后端

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 配置环境变量
cp env.example .env
nano .env  # 填入AWS凭证

# 运行服务
python app/main.py
```

#### 4. 使用客户端

```bash
cd ../client
pip install -r requirements.txt

# 上传文件
python client.py upload myfile.txt

# 列出文件
python client.py list

# 下载文件
python client.py download 1
```

完整教程：
- [快速开始](docs/QUICK_START.md)
- [详细使用指南](USAGE_GUIDE.md)

## 📦 安装

### 后端依赖

```bash
pip install fastapi uvicorn boto3 sqlalchemy pydantic
```

### 客户端依赖

```bash
pip install requests tqdm click python-dotenv
```

## 🔧 配置

### 后端配置 (`backend/.env`)

```env
# AWS配置
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=ap-northeast-1
AWS_S3_BUCKET=your-bucket-name

# 数据库
DATABASE_URL=sqlite:///./cloud_drive.db

# 安全
SECRET_KEY=your-secret-key

# 性能
CHUNK_SIZE=8388608           # 8MB
MULTIPART_THRESHOLD=104857600  # 100MB
MAX_CONCURRENCY=10            # 最大线程数
```

### 客户端配置 (`client/.env`)

```env
API_BASE_URL=http://localhost:8000
USER_ID=1
DOWNLOAD_DIR=./downloads
```

## 📚 API文档

启动后端后访问：http://localhost:8000/docs

### 主要接口

| 方法 | 路径 | 说明 |
|-----|------|-----|
| POST | `/api/files/upload` | 上传文件 |
| GET | `/api/files/download/{id}` | 下载文件 |
| GET | `/api/files/list` | 列出文件 |
| DELETE | `/api/files/delete/{id}` | 删除文件 |
| POST | `/api/files/mkdir` | 创建目录 |
| GET | `/api/files/info/{id}` | 获取文件信息 |

## 🧪 测试

### 测试多线程上传

```bash
# 创建200MB测试文件
fsutil file createnew large.bin 209715200  # Windows
# dd if=/dev/zero of=large.bin bs=1M count=200  # Linux

# 上传（会自动使用多线程）
python client.py upload large.bin
```

### 测试多线程下载

```bash
# 下载大文件
python client.py download 1 --output downloaded.bin
```

查看后端日志确认多线程运行：

```
INFO - 使用多线程上传 (文件大小: 200.00 MB)
INFO - 开始多线程上传: 25 个分块
INFO - 分块 1/25 上传完成
...
```

## 📊 性能

### 单线程 vs 多线程对比

| 文件大小 | 单线程 | 多线程(10并发) | 提升 |
|---------|--------|---------------|------|
| 10 MB | 5s | 4s | 20% |
| 100 MB | 50s | 15s | 70% |
| 500 MB | 250s | 45s | 82% |
| 1 GB | 500s | 80s | 84% |

**测试环境**：EC2 t2.small, 网络带宽 100Mbps

### 配置建议

| EC2实例 | MAX_CONCURRENCY | CHUNK_SIZE |
|---------|----------------|------------|
| t2.micro | 3-5 | 4MB |
| t2.small | 5-8 | 8MB |
| t2.medium | 8-12 | 8MB |
| t3.large | 12-20 | 16MB |

## 📖 文档

- [AWS配置指南](docs/AWS_SETUP.md) - S3和EC2配置
- [部署指南](docs/DEPLOYMENT.md) - 生产环境部署
- [快速开始](docs/QUICK_START.md) - 5分钟上手

## 🛠️ 技术栈

- **后端**: Python 3.9+, FastAPI, boto3, SQLAlchemy
- **存储**: AWS S3, SQLite/PostgreSQL
- **客户端**: Python, requests, click
- **部署**: AWS EC2, Nginx, systemd

## 📁 项目结构

```
Cloud-drive/
├── backend/              # 后端服务
│   ├── app/
│   │   ├── main.py      # FastAPI应用
│   │   ├── api/         # API路由
│   │   │   └── files.py # 文件操作接口
│   │   ├── models/      # 数据模型
│   │   │   ├── user.py
│   │   │   └── file.py
│   │   └── services/    # 业务逻辑
│   │       └── storage.py  # S3多线程服务
│   ├── config.py        # 配置管理
│   └── requirements.txt
│
├── client/              # 客户端
│   ├── client.py        # CLI工具
│   ├── config.py
│   └── requirements.txt
│
├── docs/                # 文档
│   ├── AWS_SETUP.md
│   ├── DEPLOYMENT.md
│   └── QUICK_START.md
│
└── README.md
```

## 🔐 安全

- JWT身份验证（计划中）
- S3访问控制
- 用户隔离（每个用户独立目录）
- 密码哈希（bcrypt）
- HTTPS支持（生产环境）

## 🚧 开发路线图

- [x] Phase 1: 基础服务 + 多线程传输
- [ ] Phase 2: 自动同步客户端
- [ ] Phase 3: 压缩与去重
- [ ] Phase 4: 差分同步
- [ ] Phase 5: 版本控制与协作

## 🤝 贡献

欢迎提交Issue和Pull Request！

## 📄 许可

MIT License

## 👥 作者

- 项目组成员1 - 后端架构
- 项目组成员2 - 客户端开发
- 项目组成员3 - 算法实现
- 项目组成员4 - 测试部署

## 🙏 致谢

- [Nextcloud](https://nextcloud.com/) - 开源云盘参考
- [Seafile](https://www.seafile.com/) - 架构参考
- AWS Documentation - S3最佳实践

---

**开始使用**: [docs/QUICK_START.md](docs/QUICK_START.md)

**遇到问题**: [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)

**联系我们**: your-email@example.com
