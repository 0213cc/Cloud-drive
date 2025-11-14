# 用户认证系统使用指南

## 🎯 功能说明

Phase 2A实现了完整的用户认证系统：

- ✅ 用户注册
- ✅ 用户登录
- ✅ JWT Token认证
- ✅ Token自动刷新
- ✅ 用户隔离（每个用户只能访问自己的文件）
- ✅ 密码加密存储（bcrypt）

---

## 🚀 快速开始

### 步骤1：启动后端

```powershell
cd D:\Dase\云计算\Cloud-drive\backend

# 重启后端以加载新的认证API
.\start.bat
```

### 步骤2：注册新用户

```powershell
cd D:\Dase\云计算\Cloud-drive\client

# 激活虚拟环境
venv\Scripts\activate

# 注册用户
python client.py register

# 按提示输入：
# Username: alice
# Email: alice@example.com
# Password: ******
# Repeat for confirmation: ******
```

应该看到：

```
✓ 注册成功！
  用户名: alice
  用户ID: 1

现在可以使用客户端上传下载文件了
```

### 步骤3：登录

```powershell
# 登录（如果之前退出了）
python client.py login

# 输入用户名和密码
# Username: alice
# Password: ******
```

应该看到：

```
✓ 登录成功！
  用户名: alice
  用户ID: 1

Token已保存，后续操作将自动认证
```

### 步骤4：测试文件操作

```powershell
# Token会自动添加到请求中

# 上传文件
echo "Alice's file" > alice_file.txt
python client.py upload alice_file.txt

# 列出文件（只能看到自己的文件）
python client.py list

# 查看当前用户
python client.py whoami
```

---

## 📊 认证流程

### 注册流程

```
用户 → 注册 → 创建用户记录
                ↓
            密码加密（bcrypt）
                ↓
            生成JWT Token
                ↓
            保存Token到本地
```

### 登录流程

```
用户 → 登录 → 验证密码
                ↓
            生成JWT Token
                ↓
            保存Token到本地
                ↓
          后续请求自动携带Token
```

### Token刷新

```
Token即将过期（25分钟）
        ↓
    自动使用refresh_token刷新
        ↓
    获取新的access_token
        ↓
    保存新Token
```

---

## 🧪 完整测试场景

### 测试1：多用户隔离

```powershell
# 用户1：Alice
python client.py register
# Username: alice
# Email: alice@example.com
# Password: alice123

echo "Alice's file" > alice_file.txt
python client.py upload alice_file.txt
python client.py list
# 应该只看到alice_file.txt

# 退出
python client.py logout

# 用户2：Bob
python client.py register
# Username: bob
# Email: bob@example.com  
# Password: bob123

echo "Bob's file" > bob_file.txt
python client.py upload bob_file.txt
python client.py list
# 应该只看到bob_file.txt（看不到Alice的文件）

# 验证：每个用户只能看到自己的文件 ✓
```

### 测试2：Token自动管理

```powershell
# 登录
python client.py login

# 上传文件（Token自动添加）
python client.py upload file1.txt

# 等待30分钟（或修改配置测试）
# 再次上传，Token会自动刷新
python client.py upload file2.txt

# 查看日志，应该看到Token刷新记录
```

### 测试3：未认证访问

```powershell
# 退出登录
python client.py logout

# 尝试上传文件
python client.py upload test.txt

# 应该返回401 Unauthorized错误
```

### 测试4：API文档测试

1. 打开浏览器：http://localhost:8000/docs

2. 测试注册：
   - POST `/api/auth/register`
   - 输入用户信息
   - 获取Token

3. 测试认证：
   - 点击右上角 "Authorize" 按钮
   - 输入Token：`Bearer your_access_token`
   - 现在可以调用需要认证的API了

4. 测试文件操作：
   - POST `/api/files/upload`
   - 应该成功（已认证）

---

## 📁 Token存储

Token保存在：`~/.cloud_drive_token.json`

Windows: `C:\Users\YourName\.cloud_drive_token.json`

内容：

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6...",
  "user_id": 1,
  "username": "alice",
  "expires": "2024-11-09T16:30:00"
}
```

---

## 🔒 安全特性

### 1. 密码加密

```python
# 使用bcrypt加密
# 密码 "alice123" 加密后：
# $2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj...
```

### 2. JWT Token

```python
# Token包含：
{
  "user_id": 1,
  "username": "alice",
  "exp": 1699545600  # 过期时间
}
```

### 3. Token过期

- Access Token: 30分钟
- Refresh Token: 7天
- 自动刷新机制

### 4. 用户隔离

```python
# 每个API请求都会验证用户ID
@router.post("/upload")
async def upload_file(
    file: UploadFile,
    user_id: int = Depends(get_current_user_id)  # ← 自动获取
):
    # 只能操作自己的文件
    file.user_id = user_id
```

---

## 📖 API接口

### 认证接口

| 方法 | 路径 | 说明 | 认证 |
|-----|------|-----|------|
| POST | `/api/auth/register` | 注册新用户 | 否 |
| POST | `/api/auth/login` | 用户登录 | 否 |
| POST | `/api/auth/refresh` | 刷新Token | 否 |
| GET | `/api/auth/me` | 获取当前用户信息 | 是 |
| GET | `/api/auth/test` | 测试认证 | 是 |

### 文件接口（已改为需要认证）

| 方法 | 路径 | 说明 | 认证 |
|-----|------|-----|------|
| POST | `/api/files/upload` | 上传文件 | **是** ✓ |
| GET | `/api/files/download/{id}` | 下载文件 | **是** ✓ |
| GET | `/api/files/list` | 列出文件 | **是** ✓ |
| DELETE | `/api/files/delete/{id}` | 删除文件 | **是** ✓ |
| POST | `/api/files/mkdir` | 创建目录 | **是** ✓ |

---

## 🎯 命令行使用

### 认证命令

```powershell
# 注册
python client.py register

# 登录
python client.py login

# 查看当前用户
python client.py whoami

# 退出登录
python client.py logout

# 帮助
python client.py --help
```

### 文件操作（需要先登录）

```powershell
# 必须先登录
python client.py login

# 然后可以使用所有文件命令
python client.py upload file.txt
python client.py list
python client.py download 1
python client.py delete 1
```

---

## 🔧 配置说明

### 修改Token过期时间

编辑 `backend/.env`：

```env
# JWT配置
SECRET_KEY=your-secret-key
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30  # 修改这里（分钟）
```

### 修改刷新Token有效期

编辑 `backend/app/utils/jwt_handler.py`：

```python
def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # 修改这里（天数）
    ...
```

---

## 🐛 常见问题

### Q1: 401 Unauthorized错误

**错误信息**: `{"detail":"无效的认证凭证"}`

**解决方法**:
```powershell
# 重新登录
python client.py login
```

### Q2: Token已过期

**错误信息**: Token过期

**解决方法**:
Token会自动刷新，如果刷新失败，重新登录：

```powershell
python client.py logout
python client.py login
```

### Q3: 注册时用户名已存在

**错误信息**: `{"detail":"用户名已存在"}`

**解决方法**:
使用不同的用户名或登录现有账户

### Q4: 看不到其他用户的文件

这是**正常行为**！用户隔离功能工作正常。

每个用户只能看到自己上传的文件。

---

## 💡 高级用法

### 使用Python脚本

```python
from client import CloudDriveClient
from auth_client import AuthClient

# 创建认证客户端
auth = AuthClient("http://localhost:8000")

# 登录
result = auth.login("alice", "alice123")
if result['success']:
    print(f"登录成功: {result['username']}")

# 使用客户端（自动认证）
client = CloudDriveClient(auth_client=auth)
client.upload_file("test.txt")
```

### 手动使用API

```python
import requests

# 登录获取Token
response = requests.post(
    "http://localhost:8000/api/auth/login",
    json={"username": "alice", "password": "alice123"}
)
token = response.json()['access_token']

# 使用Token上传文件
headers = {"Authorization": f"Bearer {token}"}
with open("test.txt", "rb") as f:
    files = {"file": f}
    response = requests.post(
        "http://localhost:8000/api/files/upload",
        files=files,
        params={"path": "/"},
        headers=headers
    )
```

---

## ✅ 测试清单

- [ ] 注册新用户成功
- [ ] 登录现有用户成功
- [ ] Token自动保存到本地
- [ ] 文件操作自动添加Token
- [ ] 未登录时无法操作文件
- [ ] 多用户隔离生效
- [ ] Token自动刷新
- [ ] 退出登录清除Token
- [ ] 查看当前用户信息
- [ ] API文档测试认证

---

## 🎉 总结

Phase 2A实现了：

1. ✅ **完整的用户系统** - 注册、登录、认证
2. ✅ **JWT Token管理** - 自动保存、刷新、验证
3. ✅ **用户隔离** - 每个用户独立的文件空间
4. ✅ **密码安全** - bcrypt加密存储
5. ✅ **无缝集成** - 所有API自动认证

**现在你的云盘支持多用户了！** 🎉

