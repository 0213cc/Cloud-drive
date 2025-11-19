# 块级去重功能指南

## 📋 目录

- [功能概述](#功能概述)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [详细说明](#详细说明)
- [API文档](#api文档)
- [性能优化](#性能优化)
- [故障排查](#故障排查)

---

## 功能概述

### 什么是块级去重？

块级去重（Block-level Deduplication）是一种高级的数据去重技术，它将文件分割成固定或可变大小的数据块，并对每个数据块进行去重。相比文件级去重，块级去重能够：

- ✅ **更高的去重率**：即使文件内容部分相同，也能去重共同的数据块
- ✅ **节省更多存储空间**：特别适合大文件和有部分重复内容的文件
- ✅ **提高上传效率**：只需上传新的数据块，已存在的块直接复用
- ✅ **支持增量更新**：文件修改后，只需上传变化的数据块

### 与文件级去重的对比

| 特性 | 文件级去重 | 块级去重 |
|------|-----------|---------|
| 去重粒度 | 整个文件 | 数据块（如4MB） |
| 适用场景 | 完全相同的文件 | 部分相同的文件 |
| 去重率 | 低-中 | 中-高 |
| 存储效率 | 中 | 高 |
| 上传效率 | 高（完全相同时） | 高（部分相同时） |
| 复杂度 | 低 | 中 |

### 应用场景

1. **大文件备份**：多个版本的大文件，只有部分内容变化
2. **虚拟机镜像**：多个虚拟机镜像共享相同的基础系统块
3. **代码仓库**：不同分支的代码文件有大量重复块
4. **媒体文件**：视频、音频文件的部分片段重复
5. **数据库备份**：增量备份时，大部分数据块未变化

---

## 技术架构

### 数据模型

#### 1. BlockChunk（数据块表）

存储实际的数据块内容引用：

```python
class BlockChunk:
    id: int                      # 数据块ID
    hash_value: str              # SHA-256哈希值（唯一）
    size: int                    # 数据块大小（字节）
    s3_key: str                  # S3存储键
    is_compressed: bool          # 是否压缩
    compressed_size: int         # 压缩后大小
    reference_count: int         # 引用计数
    created_at: datetime         # 创建时间
    last_accessed_at: datetime   # 最后访问时间
```

#### 2. FileBlockMap（文件-数据块映射表）

记录文件由哪些数据块组成：

```python
class FileBlockMap:
    id: int                      # 映射ID
    file_chunk_id: int           # 文件块ID（关联FileChunk）
    block_chunk_id: int          # 数据块ID（关联BlockChunk）
    block_index: int             # 数据块序号
    block_offset: int            # 数据块在文件中的偏移量
    created_at: datetime         # 创建时间
```

#### 3. FileBlockMetadata（文件块元数据表）

存储文件的分块策略和统计信息：

```python
class FileBlockMetadata:
    id: int                      # 元数据ID
    file_chunk_id: int           # 文件块ID
    chunking_algorithm: str      # 分块算法（fixed/rabin）
    chunk_size: int              # 块大小
    total_blocks: int            # 总块数
    unique_blocks: int           # 唯一块数
    deduplication_ratio: int     # 去重率（%）
    created_at: datetime         # 创建时间
```

### 工作流程

#### 上传流程

```
1. 客户端分块
   ├─ 读取文件
   ├─ 按算法分块（固定大小/Rabin）
   └─ 计算每个块的哈希值

2. 检查去重
   ├─ 发送所有块的哈希值到服务器
   ├─ 服务器检查哪些块已存在
   └─ 返回需要上传的块列表

3. 上传数据块
   ├─ 只上传不存在的块
   ├─ 可选压缩每个块
   └─ 存储到S3

4. 组装文件
   ├─ 创建FileChunk记录
   ├─ 创建FileBlockMap映射
   ├─ 创建FileBlockMetadata元数据
   └─ 创建File记录
```

#### 下载流程

```
1. 获取文件信息
   ├─ 查询File记录
   ├─ 获取FileChunk ID
   └─ 检查是否使用块级去重

2. 获取数据块列表
   ├─ 查询FileBlockMap
   ├─ 按block_index排序
   └─ 获取每个BlockChunk的S3键

3. 下载并组装
   ├─ 按顺序下载每个数据块
   ├─ 如果块被压缩，则解压
   └─ 按顺序写入输出文件

4. 返回文件
   └─ 返回组装后的完整文件
```

### 分块算法

#### 1. 固定大小分块（Fixed-size Chunking）

- **原理**：将文件按固定大小（如4MB）分割
- **优点**：简单、快速、可预测
- **缺点**：对文件修改不够鲁棒（插入/删除会导致所有后续块变化）
- **适用场景**：静态文件、完全不同的文件

```python
# 示例
chunk_size = 4 * 1024 * 1024  # 4MB
chunks = []
while data := file.read(chunk_size):
    chunks.append(data)
```

#### 2. Rabin指纹分块（Content-Defined Chunking）

- **原理**：基于文件内容特征动态确定分块边界
- **优点**：对文件修改鲁棒（插入/删除只影响局部块）
- **缺点**：计算复杂度较高
- **适用场景**：频繁修改的文件、增量备份

```python
# 示例（简化版）
window_size = 48
mask = (1 << mask_bits) - 1

for pos in range(len(data)):
    fingerprint = (fingerprint << 1) ^ data[pos]
    
    if (fingerprint & mask) == 0:  # 分块边界
        chunks.append(data[chunk_start:pos])
        chunk_start = pos
```

---

## 快速开始

### 步骤1：数据库迁移

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
```

### 步骤2：重启后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload
```

### 步骤3：运行测试

```bash
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

## 详细说明

### 客户端使用

#### 基本上传

```python
from client import CloudDriveClient

client = CloudDriveClient()

# 上传文件（自动使用块级去重）
result = client.upload_file(
    "large_file.bin",
    enable_block_deduplication=True,  # 启用块级去重
    chunk_size=4 * 1024 * 1024,       # 4MB块大小
    enable_compression=True            # 启用压缩
)

if result['success']:
    print(f"上传成功: {result['message']}")
    if result.get('deduplication_stats'):
        stats = result['deduplication_stats']
        print(f"去重率: {stats['deduplication_ratio']}%")
```

#### 自定义块大小

```python
# 小块（1MB）- 更高的去重率，但更多的网络请求
result = client.upload_file(
    "file.bin",
    chunk_size=1 * 1024 * 1024
)

# 大块（16MB）- 更少的网络请求，但去重率可能较低
result = client.upload_file(
    "file.bin",
    chunk_size=16 * 1024 * 1024
)
```

#### 禁用块级去重

```python
# 对于小文件，可以禁用块级去重
result = client.upload_file(
    "small_file.txt",
    enable_block_deduplication=False  # 使用文件级去重
)
```

### 服务器端配置

#### 块大小配置

在 `backend/app/utils/chunking.py` 中：

```python
class ChunkingService:
    # 默认块大小：4MB
    DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
    
    # 最小块大小：1MB
    MIN_CHUNK_SIZE = 1 * 1024 * 1024
    
    # 最大块大小：16MB
    MAX_CHUNK_SIZE = 16 * 1024 * 1024
```

#### 自动切换策略

系统会自动判断是否使用块级去重：

```python
def should_use_chunking(file_size: int, chunk_size: int = None) -> bool:
    """
    文件大小超过2倍块大小时，使用块级去重
    否则使用文件级去重（更高效）
    """
    if chunk_size is None:
        chunk_size = DEFAULT_CHUNK_SIZE
    
    return file_size > (chunk_size * 2)
```

---

## API文档

### 1. 检查数据块

**端点：** `POST /api/block-upload/check-blocks`

**请求：**
```json
{
  "hash_values": [
    "abc123...",
    "def456...",
    "ghi789..."
  ]
}
```

**响应：**
```json
{
  "existing_blocks": {
    "abc123...": 42,
    "def456...": 43
  },
  "missing_blocks": [
    "ghi789..."
  ]
}
```

### 2. 上传数据块

**端点：** `POST /api/block-upload/upload-block`

**参数：**
- `block_hash`: 数据块哈希值
- `block_index`: 数据块序号
- `enable_compression`: 是否启用压缩

**请求：**
```
POST /api/block-upload/upload-block?block_hash=abc123...&block_index=0&enable_compression=true
Content-Type: multipart/form-data

file: <binary data>
```

**响应：**
```json
{
  "success": true,
  "message": "上传成功",
  "block_chunk_id": 42,
  "deduplicated": false,
  "compressed": true,
  "compression_ratio": 65
}
```

### 3. 组装文件

**端点：** `POST /api/block-upload/assemble`

**请求：**
```json
{
  "filename": "large_file.bin",
  "path": "/",
  "content_type": "application/octet-stream",
  "total_size": 10485760,
  "file_hash": "abc123...",
  "chunking_algorithm": "fixed",
  "chunk_size": 4194304,
  "blocks": [
    {
      "hash": "block1_hash",
      "index": 0,
      "offset": 0,
      "size": 4194304
    },
    {
      "hash": "block2_hash",
      "index": 1,
      "offset": 4194304,
      "size": 4194304
    }
  ]
}
```

**响应：**
```json
{
  "success": true,
  "message": "文件组装成功（块级去重率: 50%）",
  "file_id": 123,
  "version": 1,
  "deduplication_stats": {
    "total_blocks": 2,
    "unique_blocks": 1,
    "deduplication_ratio": 50,
    "chunking_algorithm": "fixed"
  }
}
```

### 4. 获取统计信息

**端点：** `GET /api/block-upload/stats`

**响应：**
```json
{
  "success": true,
  "stats": {
    "total_blocks": 1000,
    "total_references": 5000,
    "total_size_mb": 4096.00,
    "saved_space_mb": 16384.00,
    "deduplication_ratio": 80,
    "compressed_blocks": 800,
    "total_compressed_size_mb": 1024.00
  }
}
```

---

## 性能优化

### 1. 块大小选择

| 块大小 | 优点 | 缺点 | 适用场景 |
|--------|------|------|----------|
| 1MB | 高去重率、细粒度 | 更多网络请求、更多元数据 | 频繁修改的文件 |
| 4MB | 平衡性能和去重率 | - | 通用场景（推荐） |
| 16MB | 少网络请求、少元数据 | 低去重率 | 大型静态文件 |

### 2. 并行上传

```python
# 可以实现多线程并行上传数据块
import concurrent.futures

def upload_blocks_parallel(blocks, max_workers=4):
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [
            executor.submit(upload_block, block)
            for block in blocks
        ]
        results = [f.result() for f in futures]
    return results
```

### 3. 压缩策略

- **文本文件**：高压缩率（60-80%），建议启用
- **图片/视频**：低压缩率（<10%），建议禁用
- **已压缩文件**：无效果，自动跳过

### 4. 缓存优化

服务器端可以缓存热门数据块：

```python
# 使用Redis缓存热门块的元数据
cache.set(f"block:{hash_value}", block_info, ttl=3600)
```

---

## 故障排查

### 问题1：上传失败

**症状：** 块级上传失败，回退到常规上传

**可能原因：**
1. 数据库未迁移
2. 网络超时
3. S3存储问题

**解决方法：**
```bash
# 1. 检查数据库
cd backend
python migrate_block_deduplication.py

# 2. 检查后端日志
tail -f backend.log

# 3. 测试S3连接
python -c "from app.services.storage import S3StorageService; S3StorageService().test_connection()"
```

### 问题2：下载文件损坏

**症状：** 下载的文件哈希值不匹配

**可能原因：**
1. 数据块顺序错误
2. 数据块缺失
3. 解压失败

**解决方法：**
```python
# 验证文件块映射
from app.utils.block_deduplication import BlockDeduplicationService

blocks = BlockDeduplicationService.get_file_blocks(db, file_chunk_id)
print(f"总块数: {len(blocks)}")
for block in blocks:
    print(f"块 {block['block_index']}: {block['hash_value'][:16]}...")
```

### 问题3：去重率低

**症状：** 预期去重率高，但实际很低

**可能原因：**
1. 块大小不合适
2. 文件内容差异大
3. 使用了不同的分块算法

**解决方法：**
```python
# 1. 尝试更小的块大小
result = client.upload_file(
    "file.bin",
    chunk_size=1 * 1024 * 1024  # 1MB
)

# 2. 使用Rabin分块（未来支持）
result = client.upload_file(
    "file.bin",
    chunking_algorithm="rabin"
)
```

### 问题4：引用计数不准确

**症状：** 删除文件后，数据块未被清理

**解决方法：**
```bash
# 运行引用计数修复脚本
cd backend
python fix_block_reference_counts.py
```

---

## 最佳实践

### 1. 选择合适的场景

✅ **适合使用块级去重：**
- 大文件（>8MB）
- 有版本历史的文件
- 部分内容重复的文件
- 虚拟机镜像、数据库备份

❌ **不适合使用块级去重：**
- 小文件（<8MB）
- 完全不同的文件
- 已经高度压缩的文件

### 2. 监控和维护

```python
# 定期检查去重统计
stats = get_block_deduplication_stats()
print(f"去重率: {stats['deduplication_ratio']}%")
print(f"节省空间: {stats['saved_space_mb']:.2f} MB")

# 清理零引用的数据块
cleanup_orphaned_blocks()
```

### 3. 备份策略

- 定期备份数据库（包含块映射信息）
- 保留S3数据块的完整性
- 监控引用计数的准确性

---

## 总结

块级去重是一个强大的功能，能够显著提高存储效率和上传速度。通过合理配置和使用，可以：

- 🎯 **节省50-90%的存储空间**（取决于数据重复度）
- ⚡ **提升上传速度90%+**（对于部分重复的文件）
- 💰 **降低存储和带宽成本**
- 🔒 **保持数据完整性和安全性**

开始使用块级去重，让你的云盘更高效！🚀

