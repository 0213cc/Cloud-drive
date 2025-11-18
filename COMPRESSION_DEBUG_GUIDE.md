# 压缩功能调试指南

## 问题描述

上传10MB文件时没有被压缩。

## 可能的原因

### 1. 客户端没有传递 `enable_compression` 参数

**检查位置:** `client/client.py`

```python
# 当前代码 (第175行)
params = {'path': remote_path}

# 应该改为
params = {
    'path': remote_path,
    'enable_compression': True  # 明确传递
}
```

虽然后端默认值是 `True`，但某些情况下可能不会生效。

### 2. 文件类型被判断为不可压缩

**检查位置:** `backend/app/utils/compression.py`

```python
SKIP_COMPRESS_TYPES = {
    'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
    'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
    'audio/mpeg', 'audio/mp4', 'audio/wav',
    'application/zip', 'application/x-zip-compressed',
    'application/x-rar-compressed', 'application/x-7z-compressed',
    'application/gzip', 'application/x-gzip'
}
```

如果文件的 `content_type` 在这个列表中，会跳过压缩。

### 3. 文件太小

**检查位置:** `backend/app/utils/compression.py`

```python
MIN_COMPRESS_SIZE = 1024  # 1KB
```

小于1KB的文件不会被压缩。

### 4. 数据库字段缺失

**症状:** 后端报错 `no such column: files.compressed_size`

**解决方案:** 运行数据库迁移脚本

```bash
cd backend
python migrate_compression.py
```

## 调试步骤

### 步骤 1: 运行调试脚本

```bash
python test_compression_debug.py
```

这个脚本会:
1. 生成10MB可压缩测试文件
2. 使用两种方式上传（直接API vs 客户端）
3. 对比压缩效果
4. 显示详细的调试信息

### 步骤 2: 查看后端日志

后端现在会输出详细的压缩日志：

```
INFO: 压缩检查: enable_compression=True, file_size=10.00 MB, content_type=text/plain, should_compress=True
INFO: 文件已压缩: test.txt, 原始: 10.00 MB, 压缩后: 0.50 MB, 压缩率: 95%
```

**关键信息:**
- `enable_compression`: 是否启用压缩参数
- `file_size`: 文件大小
- `content_type`: 文件MIME类型
- `should_compress`: 最终是否应该压缩

### 步骤 3: 检查文件信息

```bash
python client/client.py info <FILE_ID>
```

查看上传后的文件信息，确认：
- `is_compressed`: 是否压缩
- `compressed_size`: 压缩后大小
- `compression_ratio`: 压缩率

## 修复方案

### 方案 1: 修改客户端代码（推荐）

修改 `client/client.py` 的 `upload_file` 方法：

```python
def upload_file(
    self, 
    file_path: str, 
    remote_path: str = "/",
    show_progress: bool = True,
    enable_compression: bool = True  # 添加参数
) -> Dict:
    # ...
    
    params = {
        'path': remote_path,
        'enable_compression': enable_compression  # 传递参数
    }
    
    # ...
```

同样修改 `update_file` 方法。

### 方案 2: 检查文件类型

如果是特定类型的文件没有被压缩，检查文件的 MIME 类型：

```bash
# Linux/Mac
file --mime-type test.txt

# Python
import mimetypes
print(mimetypes.guess_type('test.txt'))
```

如果类型在 `SKIP_COMPRESS_TYPES` 中，可以：
1. 修改文件扩展名
2. 从跳过列表中移除该类型（不推荐）

### 方案 3: 调整压缩阈值

如果需要压缩更小的文件，修改 `backend/app/utils/compression.py`:

```python
MIN_COMPRESS_SIZE = 512  # 改为512字节
```

## 验证修复

### 1. 生成测试文件

```bash
# 生成10MB可压缩文本文件
python -c "print('Test line for compression\n' * 500000)" > test_10mb.txt
```

### 2. 上传文件

```bash
python client/client.py upload test_10mb.txt
```

### 3. 查看文件信息

```bash
python client/client.py info <FILE_ID>
```

**预期输出:**

```
文件信息:
  ID: 123
  文件名: test_10mb.txt
  大小: 10.00 MB
  是否压缩: True          ← 应该是 True
  压缩后大小: 0.50 MB     ← 应该明显小于原始大小
  压缩率: 95%             ← 文本文件应该有很高的压缩率
```

### 4. 下载并验证

```bash
python client/client.py download <FILE_ID>

# 验证文件完整性
sha256sum test_10mb.txt
sha256sum client/downloads/test_10mb.txt
# 两个哈希值应该相同
```

## 常见问题

### Q1: 压缩率为0%或很低

**可能原因:**
- 文件已经是压缩格式（如.zip, .jpg）
- 文件内容随机性高（如二进制文件）
- 文件太小

**解决方案:**
- 使用文本文件测试
- 生成重复内容的文件

### Q2: 后端日志显示 should_compress=False

**检查:**
1. `enable_compression` 是否为 True
2. 文件大小是否 >= 1KB
3. 文件类型是否在跳过列表中

### Q3: 压缩后文件更大

**原因:** GZIP压缩对于：
- 已压缩的文件
- 随机数据
- 加密文件

可能会增加文件大小（因为压缩头开销）。

**解决方案:** 后端应该检测压缩效果，如果压缩后更大，使用原始文件。

```python
if compress_result['success']:
    if compressed_size < original_size:
        is_compressed = True
        upload_file_path = compressed_file_path
    else:
        logger.info("压缩后文件更大，使用原始文件")
```

### Q4: 下载后文件损坏

**检查:**
1. 后端是否正确解压
2. 文件哈希是否匹配
3. 查看后端日志是否有解压错误

## 性能优化

### 1. 调整压缩级别

```python
# backend/app/utils/compression.py
DEFAULT_COMPRESSION_LEVEL = 6  # 1-9, 默认6

# 更快但压缩率低
DEFAULT_COMPRESSION_LEVEL = 1

# 更慢但压缩率高
DEFAULT_COMPRESSION_LEVEL = 9
```

### 2. 并行压缩

对于大文件，可以考虑分块并行压缩。

### 3. 选择性压缩

只对特定类型的文件启用压缩：

```python
COMPRESS_TYPES = {
    'text/plain',
    'text/html',
    'text/css',
    'application/javascript',
    'application/json',
    'application/xml'
}
```

## 监控和日志

### 查看压缩统计

```sql
-- 查看压缩文件统计
SELECT 
    COUNT(*) as total_compressed,
    SUM(size) / 1024 / 1024 as total_original_mb,
    SUM(compressed_size) / 1024 / 1024 as total_compressed_mb,
    AVG(compression_ratio) as avg_compression_ratio
FROM files 
WHERE is_compressed = 1;
```

### 查看压缩效果最好的文件

```sql
SELECT 
    filename,
    size / 1024 / 1024 as original_mb,
    compressed_size / 1024 / 1024 as compressed_mb,
    compression_ratio
FROM files 
WHERE is_compressed = 1
ORDER BY compression_ratio DESC
LIMIT 10;
```

## 相关文件

- `backend/app/api/files.py` - 文件上传/下载API
- `backend/app/utils/compression.py` - 压缩工具类
- `backend/migrate_compression.py` - 数据库迁移脚本
- `client/client.py` - 客户端上传/下载
- `test_compression_debug.py` - 调试脚本
- `COMPRESSION_TEST_GUIDE.md` - 测试指南

## 下一步

1. 运行 `python test_compression_debug.py` 诊断问题
2. 根据输出确定具体原因
3. 应用相应的修复方案
4. 重新测试验证
5. 查看后端日志确认压缩正常工作

