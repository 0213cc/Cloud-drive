# 块级去重功能 - 快速开始

## [object Object]分钟快速体验

### 步骤 1: 数据库迁移

```bash
cd backend
python migrate_block_deduplication.py
```

**预期输出：**
```
================================================================================
块级去重数据库迁移
================================================================================

开始迁移数据库: cloud_drive.db
创建 block_chunks 表...
✓ block_chunks 表创建成功
创建 file_block_maps 表...
✓ file_block_maps 表创建成功
创建 file_block_metadata 表...
✓ file_block_metadata 表创建成功

✓ 数据库迁移成功！

块级去重功能已启用，可以开始使用。
```

### 步骤 2: 重启后端服务

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

### 步骤 3: 运行测试

```bash
# 在项目根目录
python test_block_deduplication.py
```

**预期输出：**
```
================================================================================
块级去重功能测试
================================================================================

登录用户: testuser_block
✓ 登录成功

================================================================================
测试 1: 基本块级去重功能
================================================================================
✓ 生成测试文件: test_block_dedup_basic.bin (10 MB, pattern=repeat)

=== 块级上传: test_block_dedup_basic.bin (10.00 MB) ===
计算文件哈希...
分块文件（块大小: 2.00 MB）...
✓ 文件已分成 5 个数据块
检查数据块去重...
✓ 已存在: 0 个块, 需上传: 5 个块

上传数据块...
上传进度: 100%|████████████████████| 5/5 [00:02<00:00,  2.1块/s]
✓ 已上传 5 个数据块

组装文件...
✓ 文件组装成功（块级去重率: 80%）
  - 总块数: 5
  - 唯一块数: 1
  - 去重率: 80%

✅ 测试通过: 基本块级去重功能

[更多测试...]

================================================================================
测试结果汇总
================================================================================
  ✅ 通过: 基本块级去重功能
  ✅ 通过: 大文件块级上传
  ✅ 通过: 部分重复内容
  ✅ 通过: 块级去重统计

总计: 4/4 通过

🎉 所有测试通过！块级去重功能正常工作！
```

---

## 📝 手动测试

### 测试场景 1: 上传大文件

```bash
# 1. 创建一个20MB的测试文件
python -c "with open('test_large.bin', 'wb') as f: f.write(b'A' * (20 * 1024 * 1024))"

# 2. 使用Python客户端上传
python -c "
import sys
sys.path.insert(0, 'client')
from client import CloudDriveClient

client = CloudDriveClient()
result = client.upload_file('test_large.bin', enable_block_deduplication=True)
print(f'上传结果: {result}')
"
```

**预期输出：**
```
上传文件: test_large.bin (20.00 MB)
使用块级去重上传...

=== 块级上传: test_large.bin (20.00 MB) ===
计算文件哈希...
分块文件（块大小: 4.00 MB）...
✓ 文件已分成 5 个数据块
检查数据块去重...
✓ 已存在: 0 个块, 需上传: 5 个块

上传数据块...
上传进度: 100%|████████████████████| 5/5 [00:03<00:00,  1.5块/s]
✓ 已上传 5 个数据块

组装文件...
✓ 文件组装成功（块级去重率: 80%）
  - 总块数: 5
  - 唯一块数: 1
  - 去重率: 80%
```

### 测试场景 2: 部分重复内容

```bash
# 1. 创建两个部分重复的文件
# 文件1: AAA (3MB)
python -c "with open('file1.bin', 'wb') as f: f.write(b'A' * (3 * 1024 * 1024))"

# 文件2: AAB (3MB) - 前2MB与文件1相同
python -c "
data = b'A' * (2 * 1024 * 1024) + b'B' * (1 * 1024 * 1024)
with open('file2.bin', 'wb') as f: f.write(data)
"

# 2. 上传文件1
python -c "
import sys
sys.path.insert(0, 'client')
from client import CloudDriveClient

client = CloudDriveClient()
result1 = client.upload_file('file1.bin', enable_block_deduplication=True, chunk_size=1*1024*1024)
print(f'文件1上传: {result1.get(\"message\")}')
"

# 3. 上传文件2（应该复用前2MB的块）
python -c "
import sys
sys.path.insert(0, 'client')
from client import CloudDriveClient

client = CloudDriveClient()
result2 = client.upload_file('file2.bin', enable_block_deduplication=True, chunk_size=1*1024*1024)
print(f'文件2上传: {result2.get(\"message\")}')
print(f'预期: 应该有66%的块被去重（前2MB）')
"
```

### 测试场景 3: 查看去重统计

```bash
# 使用Python脚本查看统计
python -c "
import sys
sys.path.insert(0, 'client')
from client import CloudDriveClient
import requests

client = CloudDriveClient()
headers = client._get_headers()

response = client.session.get(
    f'{client.base_url}/api/block-upload/stats',
    headers=headers
)

if response.status_code == 200:
    result = response.json()
    stats = result['stats']
    
    print('块级去重统计:')
    print(f'  总数据块数: {stats[\"total_blocks\"]}')
    print(f'  总引用次数: {stats[\"total_references\"]}')
    print(f'  总大小: {stats[\"total_size_mb\"]:.2f} MB')
    print(f'  节省空间: {stats[\"saved_space_mb\"]:.2f} MB')
    print(f'  去重率: {stats[\"deduplication_ratio\"]}%')
    print(f'  压缩块数: {stats[\"compressed_blocks\"]}')
"
```

**预期输出：**
```
块级去重统计:
  总数据块数: 50
  总引用次数: 150
  总大小: 200.00 MB
  节省空间: 400.00 MB
  去重率: 66%
  压缩块数: 30
```

---

## 🔍 验证功能

### 方法 1: 查看数据库

```bash
cd backend
sqlite3 cloud_drive.db

# 查看数据块
SELECT 
    id,
    substr(hash_value, 1, 16) as hash,
    size / 1024 / 1024 as size_mb,
    reference_count,
    is_compressed
FROM block_chunks
ORDER BY reference_count DESC
LIMIT 10;

# 查看文件块映射
SELECT 
    fbm.file_chunk_id,
    COUNT(*) as total_blocks,
    SUM(bc.size) / 1024 / 1024 as total_size_mb
FROM file_block_maps fbm
JOIN block_chunks bc ON fbm.block_chunk_id = bc.id
GROUP BY fbm.file_chunk_id;

# 查看去重统计
SELECT 
    COUNT(*) as total_blocks,
    SUM(reference_count) as total_refs,
    SUM(size * (reference_count - 1)) / 1024 / 1024 as saved_mb
FROM block_chunks;
```

### 方法 2: 使用API文档

1. 打开浏览器访问: http://localhost:8000/docs
2. 找到 `GET /api/block-upload/stats`
3. 点击 "Try it out" -> "Execute"
4. 查看返回的统计信息

### 方法 3: 查看后端日志

启动后端时会看到块级去重相关日志：

```
INFO: 创建数据块: block_id=42, hash=abc123..., size=4194304, compressed=True
INFO: 增加数据块引用: block_id=42, hash=abc123..., refs=2
INFO: 文件组装成功: file_id=123, file_chunk_id=45, version=1, file_dedup=False
```

---

## 🎯 实际应用场景

### 场景 1: 虚拟机镜像备份

多个虚拟机镜像共享相同的基础系统：

```python
# 上传基础镜像（10GB）
client.upload_file('base_image.vmdk', enable_block_deduplication=True)

# 上传定制镜像1（10GB，但90%内容与基础镜像相同）
client.upload_file('custom_image1.vmdk', enable_block_deduplication=True)
# 预期: 只需上传10%的新块，节省90%的空间和时间

# 上传定制镜像2（10GB，但90%内容与基础镜像相同）
client.upload_file('custom_image2.vmdk', enable_block_deduplication=True)
# 预期: 只需上传10%的新块，节省90%的空间和时间
```

### 场景 2: 代码仓库备份

不同分支的代码有大量重复：

```python
# 上传主分支代码（100MB）
client.upload_file('main_branch.tar.gz', enable_block_deduplication=True)

# 上传开发分支代码（100MB，但80%内容与主分支相同）
client.upload_file('dev_branch.tar.gz', enable_block_deduplication=True)
# 预期: 只需上传20%的新块，节省80%的空间和时间
```

### 场景 3: 数据库增量备份

每天的数据库备份大部分内容相同：

```python
# 第1天备份（1GB）
client.upload_file('db_backup_day1.sql', enable_block_deduplication=True)

# 第2天备份（1GB，但95%内容与第1天相同）
client.upload_file('db_backup_day2.sql', enable_block_deduplication=True)
# 预期: 只需上传5%的新块，节省95%的空间和时间

# 第3天备份（1GB，但95%内容与第2天相同）
client.upload_file('db_backup_day3.sql', enable_block_deduplication=True)
# 预期: 只需上传5%的新块，节省95%的空间和时间
```

---

## 🛠️ 配置选项

### 客户端配置

```python
from client import CloudDriveClient

client = CloudDriveClient()

# 1. 基本上传（使用默认设置）
client.upload_file('file.bin')

# 2. 自定义块大小
client.upload_file('file.bin', chunk_size=2*1024*1024)  # 2MB块

# 3. 禁用块级去重（使用文件级去重）
client.upload_file('file.bin', enable_block_deduplication=False)

# 4. 禁用压缩
client.upload_file('file.bin', enable_compression=False)

# 5. 完全自定义
client.upload_file(
    'file.bin',
    remote_path='/backups',
    enable_block_deduplication=True,
    chunk_size=4*1024*1024,
    enable_compression=True,
    show_progress=True
)
```

### 服务器端配置

在 `backend/app/utils/chunking.py` 中修改默认设置：

```python
class ChunkingService:
    # 默认块大小：4MB
    DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
    
    # 最小块大小：1MB
    MIN_CHUNK_SIZE = 1 * 1024 * 1024
    
    # 最大块大小：16MB
    MAX_CHUNK_SIZE = 16 * 1024 * 1024
```

---

## 🐛 故障排查

### 问题 1: 块级上传失败

**症状：** 显示"块级上传失败"，回退到常规上传

**解决方法：**
```bash
# 1. 检查数据库是否已迁移
cd backend
python migrate_block_deduplication.py

# 2. 检查后端日志
tail -f backend.log

# 3. 重启后端服务
python -m uvicorn app.main:app --reload
```

### 问题 2: 下载文件损坏

**症状：** 下载的文件与原文件不一致

**解决方法：**
```bash
# 查看文件块映射
cd backend
sqlite3 cloud_drive.db "
SELECT 
    fbm.block_index,
    fbm.block_offset,
    bc.hash_value,
    bc.size
FROM file_block_maps fbm
JOIN block_chunks bc ON fbm.block_chunk_id = bc.id
WHERE fbm.file_chunk_id = <FILE_CHUNK_ID>
ORDER BY fbm.block_index;
"
```

### 问题 3: 去重率低于预期

**症状：** 预期去重率高，但实际很低

**解决方法：**
```python
# 尝试更小的块大小
client.upload_file('file.bin', chunk_size=1*1024*1024)  # 1MB块
```

---

## 📚 下一步

1. **阅读完整文档**: [BLOCK_DEDUPLICATION_GUIDE.md](BLOCK_DEDUPLICATION_GUIDE.md)
2. **查看API文档**: http://localhost:8000/docs
3. **了解文件级去重**: [DEDUPLICATION_GUIDE.md](docs/DEDUPLICATION_GUIDE.md)
4. **了解压缩功能**: [COMPRESSION_GUIDE.md](docs/COMPRESSION_GUIDE.md)

---

## 💡 提示

- ✅ 块级去重默认对大文件（>8MB）启用
- ✅ 小文件自动使用文件级去重（更高效）
- ✅ 块级去重与压缩可以同时使用，效果叠加
- ✅ 删除文件时会自动管理引用计数
- ✅ 支持与现有版本控制功能完全兼容

---

## 🎉 享受块级去重带来的便利！

- 💾 **节省50-90%存储空间**
- ⚡ **提升上传速度90%+**
- 💰 **降低存储和带宽成本**
- 🔒 **保持数据完整性和安全**

开始使用块级去重功能，让你的云盘更高效！🚀

