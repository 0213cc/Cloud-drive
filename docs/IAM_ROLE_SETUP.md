# 使用IAM角色部署指南

如果你的EC2实例已经配置了IAM角色，这是**最安全和推荐**的方式！

## 🎯 什么是IAM角色？

IAM角色让EC2实例**自动获取临时凭证**来访问AWS服务，无需在代码中硬编码Access Key。

**优势：**
- ✅ 更安全（凭证自动轮换）
- ✅ 无需管理Access Key
- ✅ 避免凭证泄露风险
- ✅ AWS推荐的最佳实践

---

## 📋 检查EC2是否有IAM角色

### 步骤1：SSH到EC2

```bash
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com
```

### 步骤2：检查IAM角色

```bash
# 方法1：查看实例元数据
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/

# 如果返回角色名称（如 "MyEC2Role"），说明有IAM角色 ✅
# 如果返回 404 错误，说明没有IAM角色 ❌
```

```bash
# 方法2：直接测试AWS CLI
aws s3 ls

# 如果能列出存储桶（或显示空列表），说明IAM角色工作 ✅
# 如果报错 "Unable to locate credentials"，说明没有IAM角色 ❌
```

### 步骤3：查看IAM角色权限

```bash
# 查看当前角色名称
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/

# 假设返回 "MyEC2Role"，查看临时凭证（可选）
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/MyEC2Role
```

---

## ✅ 如果有IAM角色：简化配置

### 1. 部署后端

```bash
# SSH到EC2
cd ~
git clone https://github.com/YOUR_USERNAME/cloud-drive.git
cd cloud-drive/backend

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 创建配置文件（无需Access Key）

```bash
# 使用IAM角色配置模板
cp env.example.iam-role .env

# 编辑配置
nano .env
```

**只需要配置这些（无需Access Key）：**

```env
# AWS Configuration - Using IAM Role
# 不需要填写这两项！
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=

AWS_REGION=ap-northeast-1
AWS_S3_BUCKET=your-actual-bucket-name

# Database
DATABASE_URL=sqlite:///./cloud_drive.db

# JWT Secret (generate a random one)
SECRET_KEY=your-random-secret-key

# Server
HOST=0.0.0.0
PORT=8000

# Performance
MAX_FILE_SIZE=5368709120
CHUNK_SIZE=8388608
MULTIPART_THRESHOLD=104857600
MAX_CONCURRENCY=10
```

**生成随机SECRET_KEY：**

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. 启动服务

```bash
# 初始化数据库
python3 -c "from app.models.database import init_db; init_db()"

# 测试运行
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 在日志中你应该看到：
# INFO: Using IAM role credentials (EC2 Instance Profile)
```

### 4. 配置后台运行（systemd）

```bash
# 创建服务文件
sudo nano /etc/systemd/system/cloud-drive.service
```

粘贴内容：

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
sudo systemctl daemon-reload
sudo systemctl start cloud-drive
sudo systemctl enable cloud-drive
sudo systemctl status cloud-drive
```

---

## ❌ 如果没有IAM角色：需要配置权限

### 选项1：请求管理员添加IAM角色（推荐）

联系AWS管理员，请求为你的EC2实例附加IAM角色，角色需要有以下权限：

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-bucket-name",
        "arn:aws:s3:::your-bucket-name/*"
      ]
    }
  ]
}
```

**管理员操作步骤：**
1. 进入IAM控制台
2. 创建角色 → 选择 "AWS服务" → EC2
3. 附加权限策略（S3相关）
4. 为角色命名（如 "CloudDriveEC2Role"）
5. 进入EC2控制台
6. 选择实例 → 操作 → 安全 → 修改IAM角色
7. 选择刚创建的角色

### 选项2：使用Access Key（不推荐，但可行）

如果无法添加IAM角色，询问管理员获取Access Key：

```bash
# 使用Access Key配置模板
cp env.example.access-key .env

# 编辑配置
nano .env
```

填入：

```env
AWS_ACCESS_KEY_ID=获取的Access_Key_ID
AWS_SECRET_ACCESS_KEY=获取的Secret_Access_Key
AWS_REGION=ap-northeast-1
AWS_S3_BUCKET=your-bucket-name
SECRET_KEY=random-secret-key
```

---

## 🧪 测试IAM角色是否工作

### 测试1：AWS CLI

```bash
# 列出S3存储桶
aws s3 ls

# 测试上传
echo "test" > test.txt
aws s3 cp test.txt s3://your-bucket-name/test.txt

# 测试下载
aws s3 cp s3://your-bucket-name/test.txt downloaded.txt

# 清理
aws s3 rm s3://your-bucket-name/test.txt
rm test.txt downloaded.txt
```

### 测试2：Python boto3

```bash
python3 << EOF
import boto3

# 创建S3客户端（不提供凭证，使用IAM角色）
s3 = boto3.client('s3', region_name='ap-northeast-1')

# 测试列出存储桶
try:
    response = s3.list_buckets()
    print("✅ IAM角色工作正常！")
    print("存储桶列表：")
    for bucket in response['Buckets']:
        print(f"  - {bucket['Name']}")
except Exception as e:
    print(f"❌ IAM角色不工作：{e}")
EOF
```

### 测试3：启动后端查看日志

```bash
cd ~/cloud-drive/backend
source venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

在日志中查找：

```
✅ 应该看到：
INFO: Using IAM role credentials (EC2 Instance Profile)

❌ 如果看到：
INFO: Using explicit AWS credentials (Access Key)
说明还在使用Access Key
```

---

## 🔒 安全最佳实践

### ✅ 推荐做法（IAM角色）

```bash
# .env 文件中：
# AWS_ACCESS_KEY_ID=  # 留空或删除
# AWS_SECRET_ACCESS_KEY=  # 留空或删除
AWS_S3_BUCKET=my-bucket
```

### ❌ 不推荐（硬编码Access Key）

```bash
# .env 文件中：
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE  # 不要这样做！
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
```

**原因：**
- 凭证可能泄露到Git
- 凭证可能被其他用户看到
- 凭证需要手动轮换
- 不符合安全最佳实践

---

## 📊 对比总结

| 特性 | IAM角色 | Access Key |
|-----|--------|-----------|
| **安全性** | ✅ 高（自动轮换） | ⚠️ 低（固定凭证） |
| **配置复杂度** | ✅ 简单 | ⚠️ 需要管理凭证 |
| **泄露风险** | ✅ 低 | ❌ 高 |
| **AWS推荐** | ✅ 是 | ❌ 否 |
| **需要管理员** | ⚠️ 需要附加角色 | ⚠️ 需要创建凭证 |

---

## 🎯 你应该怎么做

### 情况1：EC2已有IAM角色（检查后确认）

```bash
✅ 使用 env.example.iam-role
✅ 不填写 Access Key
✅ 直接部署
```

### 情况2：EC2没有IAM角色

```bash
1. 联系管理员添加IAM角色（推荐）
2. 或者获取Access Key（临时方案）
```

### 情况3：不确定是否有IAM角色

```bash
# 运行检查脚本
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
aws s3 ls

# 根据结果决定
```

---

## 📞 需要帮助？

**如果不确定你的EC2配置：**
1. SSH到EC2
2. 运行 `aws s3 ls`
3. 把结果告诉我，我帮你判断

**如果需要配置IAM角色：**
- 联系AWS管理员
- 或者查看 AWS控制台 → EC2 → 实例详情 → 安全

---

**记住：使用IAM角色是AWS的最佳实践！** 🎯

