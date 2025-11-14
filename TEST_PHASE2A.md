# Phase 2A - 用户认证测试指南

## 🚀 5分钟快速测试

### 前提条件

```powershell
# 1. 安装依赖（如果还没装）
cd D:\Dase\云计算\Cloud-drive\backend
venv\Scripts\activate
pip install python-jose[cryptography] passlib[bcrypt]

# 2. 启动后端
.\start.bat
```

---

## 测试方法1：自动化测试（推荐）

```powershell
# 运行自动测试脚本
cd D:\Dase\云计算\Cloud-drive\client
venv\Scripts\activate
python test_auth.py
```

脚本会自动测试：
1. ✅ 用户注册
2. ✅ 查看用户信息
3. ✅ 退出登录
4. ✅ 重新登录
5. ✅ 文件操作认证
6. ✅ Token状态

---

## 测试方法2：手动命令行测试

### 步骤1：注册第一个用户

```powershell
cd D:\Dase\云计算\Cloud-drive\client

python client.py register
# Username: alice
# Email: alice@example.com
# Password: alice123
# Repeat for confirmation: alice123
```

**预期结果：**
```
✓ 注册成功！
  用户名: alice
  用户ID: 1

现在可以使用客户端上传下载文件了
```

---

### 步骤2：查看当前用户

```powershell
python client.py whoami
```

**预期结果：**
```
当前用户:
  用户名: alice
  邮箱: alice@example.com
  用户ID: 1
  注册时间: 2024-11-09T12:00:00
```

---

### 步骤3：上传文件（自动认证）

```powershell
echo "Alice's document" > alice_doc.txt
python client.py upload alice_doc.txt
```

**预期结果：**
```
上传文件: alice_doc.txt
✓ 上传成功: alice_doc.txt
```

---

### 步骤4：列出文件

```powershell
python client.py list
```

**预期结果：**
```
目录: /
类型     ID     大小            文件名
------------------------------------------------------------
📄 文件  1      0.02 KB        alice_doc.txt

总计: 1 项
```

---

### 步骤5：测试用户隔离（重要！）

```powershell
# 退出Alice账号
python client.py logout

# 注册Bob账号
python client.py register
# Username: bob
# Email: bob@example.com
# Password: bob123

# Bob上传文件
echo "Bob's file" > bob_file.txt
python client.py upload bob_file.txt

# Bob列出文件
python client.py list
```

**预期结果：**
```
目录: /
类型     ID     大小            文件名
------------------------------------------------------------
📄 文件  2      0.01 KB        bob_file.txt

总计: 1 项
```

**关键验证：Bob看不到Alice的文件！** ✅

---

### 步骤6：重新登录Alice

```powershell
# 退出Bob
python client.py logout

# 登录Alice
python client.py login
# Username: alice
# Password: alice123

# 列出文件
python client.py list
```

**预期结果：**
```
目录: /
类型     ID     大小            文件名
------------------------------------------------------------
📄 文件  1      0.02 KB        alice_doc.txt

总计: 1 项
```

**关键验证：Alice看不到Bob的文件！** ✅

---

## 测试方法3：API文档测试

### 1. 打开API文档

浏览器访问：http://localhost:8000/docs

### 2. 测试注册

- 找到 `POST /api/auth/register`
- 点击 "Try it out"
- 输入：
  ```json
  {
    "username": "charlie",
    "email": "charlie@example.com",
    "password": "charlie123"
  }
  ```
- 点击 "Execute"
- 应该返回200，包含Token

### 3. 使用Token认证

- 复制返回的 `access_token`
- 点击右上角 **"Authorize"** 按钮
- 输入：`Bearer your_access_token_here`
- 点击 "Authorize"
- 点击 "Close"

### 4. 测试文件上传

- 找到 `POST /api/files/upload`
- 点击 "Try it out"
- 选择文件
- 点击 "Execute"
- 应该成功上传（已认证）

### 5. 测试用户信息

- 找到 `GET /api/auth/me`
- 点击 "Try it out"
- 点击 "Execute"
- 应该返回当前用户信息

---

## ✅ 验证清单

测试完成后验证：

- [ ] 用户注册成功
- [ ] 用户登录成功
- [ ] Token自动保存（查看 ~/.cloud_drive_token.json）
- [ ] 文件上传需要认证
- [ ] 未登录无法上传文件
- [ ] Alice看不到Bob的文件（用户隔离）
- [ ] Bob看不到Alice的文件（用户隔离）
- [ ] 退出登录后无法操作
- [ ] 重新登录后恢复功能
- [ ] whoami命令显示正确信息

---

## 🐛 常见错误

### 错误1: 401 Unauthorized

```
{"detail":"无效的认证凭证"}
```

**原因**：未登录或Token过期

**解决**：
```powershell
python client.py login
```

---

### 错误2: 400 Bad Request - 用户名已存在

```
{"detail":"用户名已存在"}
```

**原因**：用户已注册

**解决**：
1. 使用不同的用户名
2. 或者直接登录：`python client.py login`

---

### 错误3: ModuleNotFoundError: No module named 'jose'

**原因**：缺少依赖

**解决**：
```powershell
pip install python-jose[cryptography] passlib[bcrypt]
```

---

### 错误4: API连接失败

**原因**：后端未启动

**解决**：
```powershell
cd ..\backend
.\start.bat
```

---

## 📊 测试结果示例

### 成功的测试输出

```
============================================================
步骤 1: 测试用户注册
============================================================
注册用户: testuser_1699545678
邮箱: testuser_1699545678@example.com
密码: test123456

✓ 注册成功！
  用户ID: 1
  用户名: testuser_1699545678

============================================================
步骤 2: 查看当前用户信息
============================================================

✓ 获取成功
  用户名: testuser_1699545678
  邮箱: testuser_1699545678@example.com
  注册时间: 2024-11-09T12:34:56

============================================================
步骤 3: 测试退出登录
============================================================
退出登录...
✓ 已退出登录

============================================================
步骤 4: 测试重新登录
============================================================
使用用户名 testuser_1699545678 登录...

✓ 登录成功！
  Token已保存

============================================================
步骤 5: 测试文件操作（需要认证）
============================================================
创建测试文件...
✓ 创建文件: auth_test_file.txt

上传文件到云端...
上传文件: auth_test_file.txt
✓ 上传成功: auth_test_file.txt
✓ 上传成功
  文件ID: 1

列出云端文件...

目录: /
类型     ID     大小            文件名
------------------------------------------------------------
📄 文件  1      0.05 KB        auth_test_file.txt

总计: 1 项

✓ 已清理本地测试文件

============================================================
步骤 6: 测试Token状态
============================================================
✓ Token有效
  用户: testuser_1699545678
  过期时间: 2024-11-09T13:00:00

Token会在过期前自动刷新（25分钟后）

============================================================
     测试完成！
============================================================

验证要点：
  ✓ 用户注册成功
  ✓ 获取用户信息成功
  ✓ 退出登录成功
  ✓ 重新登录成功
  ✓ 文件操作需要认证
  ✓ Token自动管理
```

---

## 🎯 快速命令参考

```powershell
# 认证命令
python client.py register           # 注册
python client.py login              # 登录
python client.py logout             # 退出
python client.py whoami             # 查看当前用户

# 文件命令（需要先登录）
python client.py upload file.txt    # 上传
python client.py list               # 列表
python client.py download 1         # 下载
python client.py delete 1           # 删除

# 测试命令
python test_auth.py                 # 自动化测试
```

---

## 🎉 测试完成标志

看到以下输出说明测试成功：

1. ✅ 注册返回Token
2. ✅ 登录返回Token
3. ✅ whoami显示用户信息
4. ✅ 文件上传成功（带认证）
5. ✅ 多用户文件隔离
6. ✅ 退出登录清除Token
7. ✅ 未登录无法操作

**恭喜！Phase 2A - 用户认证系统测试通过！** 🎉

