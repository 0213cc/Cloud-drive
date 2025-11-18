# 压缩功能测试指南

本指南帮助你快速测试云盘的数据压缩功能。

## 前提条件

- ✅ 后端服务已启动
- ✅ 已注册并登录用户
- ✅ Python 3.7+ 环境

## 快速测试步骤

### 步骤 1：数据库迁移

添加压缩功能所需的数据库字段：

```bash
cd backend
python migrate_compression.py
```

**预期输出：**

```
开始迁移数据库: cloud_drive.db
添加压缩字段到files表...
✓ files表迁移完成
添加压缩字段到file_history表...
✓ file_history表迁移完成

✓ 数据库迁移成功！
现在可以使用压缩功能了
```

### 步骤 2：重启后端服务

```bash
# Windows
cd backend
venv\Scripts\activate
python -m uvicorn app.main:app --reload

# Linux/Mac
cd backend
source venv/bin/activate
python -m uvicorn app.main:app --reload
```

### 步骤 3：登录客户端

```bash
cd client
python client.py login
```

输入你的用户名和密码。

### 步骤 4：运行自动化测试

```bash
# 在项目根目录
python test_compression.py
```

这个脚本会自动：

1. 生成各种测试文件（小文件、大文件、可压缩、不可压缩）
2. 上传文件并测试压缩功能
3. 下载文件并验证完整性
4. 显示压缩率和性能数据
5. 清理测试文件

**预期输出示例：**

```
================================================================================
压缩功能测试
================================================================================

当前用户: testuser

================================================================================
测试 1: 小文件（< 1KB，不会被压缩）
================================================================================
文件大小: 18 字节
上传前哈希: abc123...
上传文件: test_small.txt (0.00 MB)
✓ 上传成功: test_small.txt (版本: 1)
文件ID: 45
是否压缩: False
预期: 不压缩（文件太小）
✓ 测试通过：小文件未被压缩
下载文件: test_small.txt (0.00 MB)
✓ 下载成功: client/downloads/test_small.txt
下载后哈希: abc123...
✓ 哈希验证通过：文件完整

================================================================================
测试 2: 可压缩文本文件（10MB）
================================================================================
生成测试文件: test_compressible_10mb.txt (10 MB, 可压缩)
✓ 文件已生成: test_compressible_10mb.txt
原始大小: 10.00 MB
上传前哈希: def456...
上传文件: test_compressible_10mb.txt (10.00 MB)
✓ 上传成功: test_compressible_10mb.txt (版本: 1)（已压缩，节省 95% 空间）
文件ID: 46
是否压缩: True
压缩后大小: 0.50 MB
压缩率: 95%
节省空间: 9.50 MB
✓ 测试通过：文件已压缩

下载文件...
下载文件: test_compressible_10mb.txt (10.00 MB)
✓ 下载成功: client/downloads/test_compressible_10mb.txt
下载后哈希: def456...
✓ 哈希验证通过：文件完整（自动解压成功）

[更多测试...]

================================================================================
测试完成！
================================================================================
```

## 手动测试步骤

如果你想手动测试，可以按以下步骤操作：

### 1. 生成测试文件

#### Windows PowerShell

```powershell
# 生成10MB可压缩文本文件
$content = "This is a test line for compression. " * 100000
$content | Out-File -FilePath test_text_10mb.txt -Encoding utf8

# 生成5MB随机二进制文件
$bytes = New-Object byte[] (5*1024*1024)
(New-Object Random).NextBytes($bytes)
[IO.File]::WriteAllBytes("test_random_5mb.bin", $bytes)

# 生成小文件
"Small file" | Out-File -FilePath test_small.txt
```

#### Linux/Mac

```bash
# 生成10MB可压缩文本文件
yes "This is a test line for compression." | head -c 10M > test_text_10mb.txt

# 生成5MB随机二进制文件
dd if=/dev/urandom of=test_random_5mb.bin bs=1M count=5

# 生成小文件
echo "Small file" > test_small.txt
```

### 2. 上传文件

```bash
# 上传可压缩文件
python client.py upload test_text_10mb.txt

# 上传不可压缩文件
python client.py upload test_random_5mb.bin

# 上传小文件
python client.py upload test_small.txt
```

### 3. 查看文件信息

```bash
# 列出所有文件
python client/client.py list

# 查看具体文件信息（替换<FILE_ID>为实际ID）
python client/client.py info <FILE_ID>
```

**查看压缩信息：**

```
文件信息:
  ID: 46
  文件名: test_text_10mb.txt
  路径: /test_text_10mb.txt
  大小: 10.00 MB
  版本: 1
  类型: text/plain
  哈希: def456...
  是否压缩: True
  压缩后大小: 0.50 MB
  压缩率: 95%
  创建时间: 2024-01-01 12:00:00
  更新时间: 2024-01-01 12:00:00
```

### 4. 下载并验证

```bash
# 下载文件
python client/client.py download <FILE_ID>
```

#### 验证文件完整性（Windows PowerShell）

```powershell
# 计算原始文件哈希
Get-FileHash test_text_10mb.txt -Algorithm SHA256

# 计算下载文件哈希
Get-FileHash client\downloads\test_text_10mb.txt -Algorithm SHA256

# 两个哈希值应该完全相同
```

#### 验证文件完整性（Linux/Mac）

```bash
# 计算原始文件哈希
sha256sum test_text_10mb.txt

# 计算下载文件哈希
sha256sum client/downloads/test_text_10mb.txt

# 两个哈希值应该完全相同
```

## 测试场景

### 场景 1：文本文件压缩

**目标：** 验证文本文件能被高效压缩

```bash
# 生成重复内容的文本文件
python -c "print('Hello World! ' * 1000000)" > test_repeat.txt

# 上传
python client/client.py upload test_repeat.txt

# 查看信息（应该有很高的压缩率，90%+）
python client/client.py info <FILE_ID>
```

### 场景 2：二进制文件不压缩

**目标：** 验证随机二进制文件不会被压缩（或压缩率很低）

```bash
# 生成随机文件
python -c "import os; open('test_random.bin', 'wb').write(os.urandom(10*1024*1024))"

# 上传
python client/client.py upload test_random.bin

# 查看信息（压缩率应该接近0%或为负）
python client/client.py info <FILE_ID>
```

### 场景 3：小文件不压缩

**目标：** 验证小文件不会被压缩

```bash
# 生成小文件
echo "Small content" > test_tiny.txt

# 上传
python client/client.py upload test_tiny.txt

# 查看信息（is_compressed应该为False）
python client/client.py info <FILE_ID>
```

### 场景 4：大文件压缩+多线程

**目标：** 验证大文件同时使用压缩和多线程上传

```bash
# 生成50MB文本文件
python -c "print('Test line for compression\n' * 2000000)" > test_large_50mb.txt

# 上传（会自动使用多线程+压缩）
python client/client.py upload test_large_50mb.txt

# 查看信息
python client/client.py info <FILE_ID>

# 下载验证
python client/client.py download <FILE_ID>
```

### 场景 5：已压缩格式

**目标：** 验证已压缩格式不会被再次压缩

```bash
# 创建一个ZIP文件
# Windows: 使用文件资源管理器压缩一些文件
# Linux/Mac:
zip test.zip test_*.txt

# 上传
python client/client.py upload test.zip

# 查看信息（is_compressed应该为False）
python client/client.py info <FILE_ID>
```

## 性能测试

### 测试上传速度

```bash
# 生成测试文件
python -c "print('X' * 100000000)" > test_100mb.txt

# 测试上传时间
time python client/client.py upload test_100mb.txt
```

### 测试下载速度

```bash
# 下载文件
time python client/client.py download <FILE_ID>
```

### 对比压缩效果

创建一个表格记录不同文件的压缩效果：

| 文件名              | 原始大小 | 压缩后大小 | 压缩率 | 上传时间 | 下载时间 |
| ------------------- | -------- | ---------- | ------ | -------- | -------- |
| test_text_10mb.txt  | 10 MB    | 0.5 MB     | 95%    | 2s       | 1s       |
| test_random_5mb.bin | 5 MB     | 5 MB       | 0%     | 5s       | 5s       |
| test_small.txt      | 100 B    | 100 B      | 0%     | 0.1s     | 0.1s     |

## 常见问题

### Q1: 测试脚本报错 "未登录"

**解决：**

```bash
python client/client.py login
```

### Q2: 数据库迁移失败

**解决：**

```bash
# 备份数据库
cp backend/cloud_drive.db backend/cloud_drive.db.backup

# 重新运行迁移
python backend/migrate_compression.py
```

### Q3: 压缩率为 0%

**可能原因：**

- 文件太小（< 1KB）
- 文件已经是压缩格式
- 文件内容随机性高

**验证：**

```bash
# 查看文件类型
file test_file.txt

# 查看文件大小
ls -lh test_file.txt
```

### Q4: 下载后文件哈希不匹配

**检查步骤：**

1. 查看服务器日志：`sudo journalctl -u cloud-drive -f`
2. 检查文件信息：`python client/client.py info <FILE_ID>`
3. 重新上传文件

### Q5: 上传速度没有提升

**可能原因：**

- 网络速度是瓶颈
- 文件压缩率低
- CPU 性能限制

**优化：**

- 使用更快的网络
- 只对文本文件启用压缩
- 调整压缩级别

## 清理测试数据

### 删除测试文件

```bash
# 查看所有文件
python client/client.py list

# 删除指定文件
python client/client.py delete <FILE_ID>
```

### 清理本地测试文件

```bash
# Windows
del test_*.txt test_*.bin

# Linux/Mac
rm test_*.txt test_*.bin
```

## 下一步

测试完成后，你可以：

1. 查看完整文档：[docs/COMPRESSION_GUIDE.md](docs/COMPRESSION_GUIDE.md)
2. 部署到生产环境：[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
3. 查看 API 文档：http://localhost:8000/docs

## 技术支持

如有问题：

- 查看日志：`sudo journalctl -u cloud-drive -f`
- 运行测试：`python test_compression.py`
- 查看文档：`docs/COMPRESSION_GUIDE.md`
