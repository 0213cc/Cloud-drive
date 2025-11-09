# AWS配置指南

本指南将帮助你配置AWS S3和EC2，用于云盘项目。

## 前提条件

- AWS账号
- 已经可以SSH连接到EC2：`ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com`
- 已安装AWS CLI

---

## 第一步：配置AWS CLI（在远程Ubuntu上）

### 1. SSH连接到EC2

```powershell
# 在本地Windows PowerShell中
ssh -i "D:\cloud2.pem" ubuntu@ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com
```

### 2. 配置AWS凭证

```bash
# 在远程Ubuntu上
ubuntu@ec2:~$ aws configure

# 按提示输入：
AWS Access Key ID [None]: YOUR_ACCESS_KEY_ID
AWS Secret Access Key [None]: YOUR_SECRET_ACCESS_KEY
Default region name [None]: ap-northeast-1
Default output format [None]: json
```

**如何获取Access Key：**
1. 登录AWS控制台
2. 进入 IAM (Identity and Access Management)
3. 点击 "用户" -> 选择你的用户 -> "安全凭证"
4. 创建访问密钥（Access Key）

### 3. 验证配置

```bash
# 测试AWS CLI
aws s3 ls

# 如果能看到S3存储桶列表（可能为空），说明配置成功
```

---

## 第二步：创建S3存储桶

### 方法A：使用AWS CLI（推荐）

```bash
# 在远程Ubuntu上

# 1. 创建存储桶（桶名必须全局唯一）
aws s3 mb s3://cloud-drive-YOUR-NAME-123

# 2. 验证创建成功
aws s3 ls

# 3. 查看存储桶详情
aws s3 ls s3://cloud-drive-YOUR-NAME-123

# 4. 设置存储桶CORS（可选，用于浏览器访问）
cat > cors.json << 'EOF'
{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "PUT", "POST", "DELETE", "HEAD"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag"]
    }
  ]
}
EOF

aws s3api put-bucket-cors --bucket cloud-drive-YOUR-NAME-123 --cors-configuration file://cors.json
```

### 方法B：使用AWS控制台

1. 登录AWS控制台
2. 进入 S3 服务
3. 点击 "创建存储桶"
4. 输入桶名称（如：`cloud-drive-yourname-123`）
5. 区域选择：`亚太地区（东京）ap-northeast-1`
6. 其他保持默认，点击"创建存储桶"

---

## 第三步：配置IAM权限（重要！）

你的AWS用户需要有S3的读写权限。

### 检查当前权限

```bash
# 尝试上传测试文件
echo "test" > test.txt
aws s3 cp test.txt s3://cloud-drive-YOUR-NAME-123/test.txt

# 如果成功，说明权限正确
# 如果失败，需要添加权限
```

### 添加S3权限（如果需要）

1. 登录AWS控制台
2. 进入 IAM 服务
3. 点击 "用户" -> 选择你的用户
4. 点击 "添加权限"
5. 选择 "直接附加策略"
6. 搜索并选择 `AmazonS3FullAccess`（或创建自定义策略）
7. 点击"添加权限"

**自定义S3策略示例（更安全）：**

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
        "arn:aws:s3:::cloud-drive-YOUR-NAME-123",
        "arn:aws:s3:::cloud-drive-YOUR-NAME-123/*"
      ]
    }
  ]
}
```

---

## 第四步：测试S3上传下载

```bash
# 在远程Ubuntu上

# 1. 创建测试文件
echo "Hello Cloud Drive!" > test.txt

# 2. 上传到S3
aws s3 cp test.txt s3://cloud-drive-YOUR-NAME-123/test.txt

# 3. 列出文件
aws s3 ls s3://cloud-drive-YOUR-NAME-123/

# 4. 下载文件
aws s3 cp s3://cloud-drive-YOUR-NAME-123/test.txt downloaded.txt

# 5. 验证内容
cat downloaded.txt

# 6. 删除测试文件
aws s3 rm s3://cloud-drive-YOUR-NAME-123/test.txt
rm test.txt downloaded.txt
```

---

## 第五步：配置后端环境变量

### 1. 创建.env文件

```bash
# 在远程Ubuntu上，进入项目目录
cd ~/cloud-drive/backend

# 复制配置模板
cp env.example .env

# 编辑配置文件
nano .env
```

### 2. 填写配置信息

```bash
# AWS配置
AWS_ACCESS_KEY_ID=你的AccessKeyID
AWS_SECRET_ACCESS_KEY=你的SecretAccessKey
AWS_REGION=ap-northeast-1
AWS_S3_BUCKET=cloud-drive-YOUR-NAME-123

# 数据库配置
DATABASE_URL=sqlite:///./cloud_drive.db

# JWT配置
SECRET_KEY=your-random-secret-key-change-this
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# 服务器配置
HOST=0.0.0.0
PORT=8000

# 文件上传配置
MAX_FILE_SIZE=5368709120
CHUNK_SIZE=8388608
MULTIPART_THRESHOLD=104857600
MAX_CONCURRENCY=10
```

**生成随机SECRET_KEY：**

```bash
# 使用Python生成
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. 保护.env文件

```bash
# 设置文件权限
chmod 600 .env

# 确保.env不被提交到Git
echo ".env" >> .gitignore
```

---

## 第六步：在本地Windows配置客户端

### 1. 创建客户端配置

在本地Windows上创建 `Cloud-drive/client/.env`：

```bash
# 在本地Windows PowerShell中
cd D:\Dase\云计算\Cloud-drive\client

# 创建.env文件（使用记事本或编辑器）
notepad .env
```

填写内容：

```
API_BASE_URL=http://ec2-3-112-92-41.ap-northeast-1.compute.amazonaws.com:8000
USER_ID=1
DOWNLOAD_DIR=./downloads
```

---

## 常见问题

### Q1: AccessDenied错误

**错误信息：** `An error occurred (AccessDenied) when calling the PutObject operation`

**解决方法：**
1. 检查IAM用户是否有S3权限
2. 检查存储桶名称是否正确
3. 检查AWS凭证是否正确配置

### Q2: NoSuchBucket错误

**错误信息：** `An error occurred (NoSuchBucket) when calling the PutObject operation`

**解决方法：**
1. 检查存储桶是否已创建：`aws s3 ls`
2. 检查存储桶名称拼写
3. 检查区域是否正确

### Q3: 存储桶名称冲突

**错误信息：** `BucketAlreadyExists`

**解决方法：**
- S3存储桶名称是全局唯一的，换一个名称

### Q4: 连接超时

**错误信息：** `Connection timeout`

**解决方法：**
1. 检查EC2安全组是否允许出站流量到S3
2. 检查网络连接
3. 尝试切换AWS区域

---

## S3存储桶命名建议

- 使用小写字母、数字和连字符
- 不要使用下划线或大写字母
- 建议格式：`cloud-drive-[项目名]-[随机数字]`
- 例如：
  - `cloud-drive-dase-2024`
  - `cloud-drive-student-123`
  - `cloud-drive-test-456`

---

## 成本估算

**免费套餐（前12个月）：**
- S3: 5GB标准存储
- EC2: t2.micro 750小时/月
- 数据传输: 15GB/月

**超出免费套餐后：**
- S3标准存储: ~$0.023/GB/月
- 数据传输: ~$0.09/GB（出站）
- API请求: PUT ~$0.005/1000次

**节省成本建议：**
1. 使用S3智能分层存储
2. 启用S3生命周期策略
3. 压缩文件后再上传
4. 使用去重减少存储

---

## 下一步

完成配置后，请查看 [DEPLOYMENT.md](./DEPLOYMENT.md) 了解如何部署后端服务。

