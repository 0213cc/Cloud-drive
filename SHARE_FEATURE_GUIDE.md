# 文件共享功能使用指南

## 📋 功能概述

文件共享功能允许用户将自己的文件或文件夹分享给其他用户，并设置不同的访问权限。

### 主要特性

- ✅ **权限控制**: 支持只读（read）和可写（write）两种权限
- ✅ **过期时间**: 可设置共享的过期时间
- ✅ **启用/禁用**: 可随时启用或禁用共享
- ✅ **操作日志**: 记录所有共享相关的操作
- ✅ **安全验证**: 只有文件所有者可以创建、修改、删除共享
- ✅ **权限隔离**: 共享用户即使有写权限也不能删除文件

---

## 🚀 快速开始

### 1. 数据库迁移

首先需要运行数据库迁移脚本，添加共享功能所需的表：

```powershell
cd backend
python migrate_share.py
```

**预期输出：**

```
============================================================
数据库迁移 - 添加共享功能
============================================================

检查现有表...
现有表: users, files, file_history

✓ 需要创建 'shares' 表
✓ 需要创建 'share_logs' 表

开始迁移...

✓ 迁移成功！

新增表结构:

1. shares (文件共享表):
   - id: INTEGER
   - owner_id: INTEGER
   - shared_with_user_id: INTEGER
   - file_id: INTEGER
   - permission: VARCHAR
   - share_token: VARCHAR(64)
   - is_active: BOOLEAN
   - expires_at: DATETIME
   - created_at: DATETIME
   - updated_at: DATETIME

2. share_logs (共享操作日志表):
   - id: INTEGER
   - share_id: INTEGER
   - user_id: INTEGER
   - action: VARCHAR(50)
   - details: VARCHAR(500)
   - created_at: DATETIME

============================================================
迁移完成！现在可以使用共享功能了
============================================================
```

### 2. 启动后端服务

```powershell
cd backend
.\start.bat
```

---

## 📖 使用教程

### 场景 1: 创建只读共享

Alice 想要将文件分享给 Bob，只允许查看和下载：

```powershell
# 1. Alice 登录
python client.py login
# Username: alice
# Password: ****

# 2. Alice 查看自己的文件列表
python client.py list

# 输出示例:
# 目录: /
# 类型     ID     大小            文件名
# ------------------------------------------------------------
# 📄 文件  1      1.23 KB        report.pdf
# 📄 文件  2      0.45 KB        notes.txt

# 3. Alice 创建只读共享（文件ID为1）
python client.py share 1 bob

# 输出:
# ✓ 共享创建成功
#   共享ID: 1
#   文件: report.pdf
#   分享给: bob
#   权限: read
```

### 场景 2: 创建可写共享

Alice 想要与 Bob 协作编辑文档：

```powershell
# 创建可写共享
python client.py share 2 bob --permission write

# 输出:
# ✓ 共享创建成功
#   共享ID: 2
#   文件: notes.txt
#   分享给: bob
#   权限: write
```

### 场景 3: 设置过期时间

Alice 想要创建一个临时共享，24 小时后自动失效：

```powershell
# 创建带过期时间的共享
python client.py share 1 bob --expires "2024-12-31T23:59:59"

# 输出:
# ✓ 共享创建成功
#   共享ID: 3
#   文件: report.pdf
#   分享给: bob
#   权限: read
#   过期时间: 2024-12-31T23:59:59
```

### 场景 4: Bob 查看分享给自己的文件

```powershell
# 1. Bob 登录
python client.py login
# Username: bob
# Password: ****

# 2. 查看分享给自己的文件
python client.py shared-with-me

# 输出:
# 分享给我的文件 (共 2 项):
#
#   ID     文件名                    所有者          权限     文件ID   过期时间
#   ----------------------------------------------------------------------------------
#   1      report.pdf               alice          read     1        永久
#   2      notes.txt                alice          write    2        永久
```

### 场景 5: Bob 下载共享文件

```powershell
# 下载文件（使用文件ID，不是共享ID）
python client.py download 1

# 输出:
# 下载文件: report.pdf (1.23 MB)
# 下载 report.pdf: 100%|████████████████| 1.23M/1.23M [00:01<00:00, 1.15MB/s]
# ✓ 下载成功: downloads/report.pdf
```

### 场景 6: Alice 查看自己的共享列表

```powershell
# Alice 查看自己创建的所有共享
python client.py my-shares

# 输出:
# 我的共享 (共 2 项):
#
#   ID     文件名                    分享给          权限     状态     过期时间
#   ----------------------------------------------------------------------------------
#   1      report.pdf               bob            read     有效     永久
#   2      notes.txt                bob            write    有效     永久
```

### 场景 7: Alice 修改共享权限

```powershell
# 将只读权限改为可写权限
python client.py update-share 1 --permission write

# 输出:
# ✓ 共享更新成功
```

### 场景 8: Alice 禁用共享

```powershell
# 临时禁用共享（不删除）
python client.py update-share 1 --inactive

# 输出:
# ✓ 共享更新成功
```

### 场景 9: Alice 重新启用共享

```powershell
# 重新启用共享
python client.py update-share 1 --active

# 输出:
# ✓ 共享更新成功
```

### 场景 10: Alice 查看共享详情

```powershell
# 查看共享的详细信息
python client.py share-info 1

# 输出:
# 共享详情:
#   共享ID: 1
#   文件: report.pdf (ID: 1)
#   路径: /report.pdf
#   所有者: alice
#   分享给: bob
#   权限: write
#   状态: 有效
#   创建时间: 2024-11-17T08:30:00
```

### 场景 11: Alice 删除共享

```powershell
# 删除共享
python client.py unshare 1
# 确定要删除此共享吗? [y/N]: y

# 输出:
# ✓ 共享删除成功
```

---

## 🔧 API 接口文档

### 1. 创建共享

**端点**: `POST /api/share/create`

**请求体**:

```json
{
  "file_id": 1,
  "shared_with_username": "bob",
  "permission": "read",
  "expires_at": "2024-12-31T23:59:59" // 可选
}
```

**响应**:

```json
{
  "success": true,
  "message": "共享创建成功",
  "share_info": {
    "id": 1,
    "owner_id": 1,
    "owner_username": "alice",
    "shared_with_user_id": 2,
    "shared_with_username": "bob",
    "file_id": 1,
    "file_path": "/report.pdf",
    "filename": "report.pdf",
    "permission": "read",
    "share_token": "abc123...",
    "is_active": true,
    "expires_at": "2024-12-31T23:59:59",
    "created_at": "2024-11-17T08:30:00",
    "updated_at": "2024-11-17T08:30:00",
    "is_expired": false,
    "is_valid": true
  }
}
```

### 2. 查看我的共享

**端点**: `GET /api/share/my-shares`

**响应**:

```json
{
  "shares": [
    {
      "id": 1,
      "owner_username": "alice",
      "shared_with_username": "bob",
      "filename": "report.pdf",
      "permission": "read",
      "is_valid": true,
      ...
    }
  ],
  "total": 1
}
```

### 3. 查看分享给我的

**端点**: `GET /api/share/shared-with-me`

**响应**: 同上

### 4. 更新共享

**端点**: `PUT /api/share/update/{share_id}`

**请求体**:

```json
{
  "permission": "write", // 可选
  "is_active": false, // 可选
  "expires_at": "2024-12-31" // 可选
}
```

### 5. 删除共享

**端点**: `DELETE /api/share/delete/{share_id}`

### 6. 查看共享详情

**端点**: `GET /api/share/info/{share_id}`

### 7. 查看共享日志

**端点**: `GET /api/share/logs/{share_id}`

---

## 🧪 自动化测试

运行完整的共享功能测试：

```powershell
cd client
python test_share.py
```

**测试覆盖**:

- ✅ 创建只读共享
- ✅ 创建可写共享
- ✅ 查看共享列表
- ✅ 下载共享文件
- ✅ 权限验证（只读用户不能删除）
- ✅ 更新共享权限
- ✅ 禁用/启用共享
- ✅ 共享过期验证
- ✅ 删除共享

**预期输出**:

```
============================================================
  共享功能测试
============================================================

测试用户:
  Alice: alice_1699545678
  Bob: bob_1699545678

============================================================
  步骤 1: 注册测试用户
============================================================

注册 Alice (alice_1699545678)...
✓ Alice 注册成功 (ID: 1)

注册 Bob (bob_1699545678)...
✓ Bob 注册成功 (ID: 2)

...

============================================================
  测试完成
============================================================

✓ 所有测试通过！

测试覆盖:
  ✓ 创建只读共享
  ✓ 创建可写共享
  ✓ 查看共享列表
  ✓ 下载共享文件
  ✓ 权限验证（只读用户不能删除）
  ✓ 更新共享权限
  ✓ 禁用/启用共享
  ✓ 共享过期验证
  ✓ 删除共享

==========================================================[object Object]共享功能测试全部通过！
============================================================
```

---

## 🔒 权限说明

### 只读权限 (read)

用户可以：

- ✅ 查看文件信息
- ✅ 下载文件
- ✅ 查看文件历史版本

用户不能：

- ❌ 修改文件
- ❌ 删除文件
- ❌ 上传新版本

### 可写权限 (write)

用户可以：

- ✅ 查看文件信息
- ✅ 下载文件
- ✅ 查看文件历史版本
- ✅ 上传新版本（覆盖文件）

用户不能：

- ❌ 删除文件（只有所有者可以删除）

---

## 📊 数据库表结构

### shares 表

| 字段                | 类型        | 说明                     |
| ------------------- | ----------- | ------------------------ |
| id                  | INTEGER     | 主键                     |
| owner_id            | INTEGER     | 文件所有者 ID            |
| shared_with_user_id | INTEGER     | 接收共享的用户 ID        |
| file_id             | INTEGER     | 文件 ID                  |
| permission          | ENUM        | 权限（read/write）       |
| share_token         | VARCHAR(64) | 共享令牌（用于链接分享） |
| is_active           | BOOLEAN     | 是否启用                 |
| expires_at          | DATETIME    | 过期时间（可选）         |
| created_at          | DATETIME    | 创建时间                 |
| updated_at          | DATETIME    | 更新时间                 |

### share_logs 表

| 字段       | 类型         | 说明        |
| ---------- | ------------ | ----------- |
| id         | INTEGER      | 主键        |
| share_id   | INTEGER      | 共享 ID     |
| user_id    | INTEGER      | 操作用户 ID |
| action     | VARCHAR(50)  | 操作类型    |
| details    | VARCHAR(500) | 操作详情    |
| created_at | DATETIME     | 操作时间    |

---

## 🛡️ 安全特性

1. **权限验证**: 所有文件访问都会验证用户权限
2. **过期检查**: 自动检查共享是否过期
3. **操作日志**: 记录所有共享相关操作
4. **所有者保护**: 只有文件所有者可以删除文件
5. **用户隔离**: 用户只能看到与自己相关的共享

---

## ❓ 常见问题

### Q1: 如何撤销共享？

有两种方式：

1. **禁用共享**: `python client.py update-share <share_id> --inactive`
2. **删除共享**: `python client.py unshare <share_id>`

### Q2: 共享用户可以删除文件吗？

不可以。即使有写权限，共享用户也不能删除文件，只有文件所有者可以删除。

### Q3: 如何设置共享的过期时间？

创建共享时使用 `--expires` 参数：

```powershell
python client.py share 1 bob --expires "2024-12-31T23:59:59"
```

### Q4: 过期的共享会自动删除吗？

不会。过期的共享会被标记为无效，但不会自动删除。所有者可以手动删除或重新设置过期时间。

### Q5: 如何查看谁访问了我的共享文件？

使用 API 查看共享日志（命令行暂不支持）：

```
GET /api/share/logs/{share_id}
```

### Q6: 可以同时分享给多个用户吗？

可以。对同一个文件创建多个共享即可：

```powershell
python client.py share 1 bob
python client.py share 1 charlie
python client.py share 1 david
```

---

## 🎯 命令速查表

```powershell
# 创建共享
python client.py share <file_id> <username> [--permission read|write] [--expires <datetime>]

# 查看我的共享
python client.py my-shares

# 查看分享给我的
python client.py shared-with-me

# 查看共享详情
python client.py share-info <share_id>

# 更新共享权限
python client.py update-share <share_id> --permission write

# 禁用共享
python client.py update-share <share_id> --inactive

# 启用共享
python client.py update-share <share_id> --active

# 删除共享
python client.py unshare <share_id>
```

---

## 🎉 总结

文件共享功能已完全集成到云盘系统中，支持：

- ✅ 灵活的权限控制（只读/可写）
- ✅ 过期时间设置
- ✅ 启用/禁用控制
- ✅ 完整的操作日志
- ✅ 安全的权限验证
- ✅ 用户友好的命令行界面
- ✅ 完整的自动化测试

现在可以安全、便捷地与团队成员共享文件了！
