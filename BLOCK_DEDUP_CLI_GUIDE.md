# 块级去重命令行使用指南

## 📋 目录

- [快速开始](#快速开始)
- [命令详解](#命令详解)
- [使用示例](#使用示例)
- [常见问题](#常见问题)

---

## 快速开始

### 1. 准备工作

```bash
# 进入客户端目录
cd client

# 确保已安装依赖
pip install -r requirements.txt

# 查看帮助
python client.py --help
```

### 2. 登录

```bash
# 如果还没有账号，先注册
python client.py register

# 登录
python client.py login
```

### 3. 上传文件测试块级去重

```bash
# 创建一个测试文件（20MB）
python -c "with open('test_20mb.bin', 'wb') as f: f.write(b'A' * (20 * 1024 * 1024))"

# 上传文件（自动使用块级去重）
python client.py upload test_20mb.bin

# 查看块级去重统计
python client.py block-stats
```

---

## 命令详解

### 基本命令

#### `upload` - 上传文件（智能选择去重策略）

```bash
python client.py upload <文件路径> [选项]
```

**选项：**

- `--path <路径>`: 远程目录路径（默认：`/`）
- `--no-compression`: 禁用压缩
- `--no-dedup`: 禁用文件级去重
- `--no-block-dedup`: 禁用块级去重
- `--chunk-size <MB>`: 指定块大小（MB）

**说明：**

- 对于大文件（>8MB），自动使用块级去重
- 对于小文件（<8MB），自动使用文件级去重
- 可以通过 `--chunk-size` 强制使用块级去重

#### `block-upload` - 强制使用块级去重上传

```bash
python client.py block-upload <文件路径> [选项]
```

**选项：**

- `--path <路径>`: 远程目录路径（默认：`/`）
- `--chunk-size <MB>`: 块大小（默认：4MB）
- `--no-compression`: 禁用压缩

**说明：**

- 无论文件大小，都使用块级去重
- 适合测试和对比不同块大小的效果

#### `block-stats` - 查看块级去重统计

```bash
python client.py block-stats
```

**输出示例：**

```
============================================================
块级去重统计信息
============================================================

数据块统计:
  总数据块数:     150
  总引用次数:     450
  压缩块数:       120

存储空间:
  实际存储:       600.00 MB
  节省空间:       1200.00 MB
  去重率:         66%
  压缩后大小:     180.00 MB

============================================================
```

### 其他相关命令

```bash
# 下载文件（自动处理块级去重文件）
python client.py download <文件ID>

# 查看文件列表
python client.py list

# 查看文件信息
python client.py info <文件ID>

# 删除文件
python client.py delete <文件ID>
```

---

## 使用示例

### 示例 1：基本上传（自动选择策略）

```bash
# 创建测试文件
python -c "with open('test.bin', 'wb') as f: f.write(b'Test' * (5 * 1024 * 1024))"

# 上传（自动选择最优策略）
python client.py upload test.bin
```

**预期输出：**

```
上传文件: test.bin (20.00 MB)
使用块级去重上传...

=== 块级上传: test.bin (20.00 MB) ===
计算文件哈希...
分块文件（块大小: 4.00 MB）...
✓ 文件已分成 5 个数据块
检查数据块去重...
✓ 已存在: 0 个块, 需上传: 5 个块

上传数据块...
上传进度: 100%|████████████████████| 5/5 [00:03<00:00,  1.5块/s]
✓ 已上传 5 个数据块

组装文件...
✓ 文件组装成功
  - 总块数: 5
  - 唯一块数: 5
  - 去重率: 0%
```

### 示例 2：指定块大小上传

```bash
# 使用2MB块大小上传
python client.py upload large_file.bin --chunk-size 2

# 使用1MB块大小上传（更高的去重率）
python client.py upload large_file.bin --chunk-size 1
```

### 示例 3：禁用压缩

```bash
# 对于已压缩的文件（如.zip, .jpg），禁用压缩可以提高速度
python client.py upload compressed_file.zip --no-compression
```

### 示例 4：禁用块级去重

```bash
# 对于小文件或完全不同的文件，可以禁用块级去重
python client.py upload small_file.txt --no-block-dedup
```

### 示例 5：完全禁用去重和压缩

```bash
# 最快的上传方式（不进行任何优化）
python client.py upload file.bin --no-compression --no-dedup --no-block-dedup
```

### 示例 6：测试块级去重效果

```bash
# 1. 创建一个重复内容的文件（10MB，内容全是'A'）
python -c "with open('file1.bin', 'wb') as f: f.write(b'A' * (10 * 1024 * 1024))"

# 2. 上传第一个文件
python client.py block-upload file1.bin --chunk-size 2

# 3. 创建另一个相同内容的文件
python -c "with open('file2.bin', 'wb') as f: f.write(b'A' * (10 * 1024 * 1024))"

# 4. 上传第二个文件（应该完全去重）
python client.py block-upload file2.bin --chunk-size 2

# 5. 查看统计
python client.py block-stats
```

**预期结果：**

- 第一次上传：上传 5 个块（每个 2MB）
- 第二次上传：0 个块需要上传（完全去重）
- 去重率：50%（5 个唯一块，10 个总引用）

### 示例 7：测试部分重复内容

```bash
# 1. 创建文件1：AAA（3MB，全是'A'）
python -c "with open('file_a.bin', 'wb') as f: f.write(b'A' * (3 * 1024 * 1024))"

# 2. 上传文件1
python client.py block-upload file_a.bin --chunk-size 1

# 3. 创建文件2：AAB（3MB，前2MB是'A'，后1MB是'B'）
python -c "
data = b'A' * (2 * 1024 * 1024) + b'B' * (1 * 1024 * 1024)
with open('file_ab.bin', 'wb') as f: f.write(data)
"

# 4. 上传文件2（应该复用前2MB的块）
python client.py block-upload file_ab.bin --chunk-size 1

# 5. 查看统计
python client.py block-stats
```

**预期结果：**

- 第一次上传：上传 3 个块（每个 1MB）
- 第二次上传：只上传 1 个新块（'B'的块）
- 去重率：约 33%（4 个唯一块，6 个总引用）

### 示例 8：下载并验证

```bash
# 1. 上传文件
python client.py upload test.bin

# 2. 查看文件列表，获取文件ID
python client.py list

# 3. 下载文件
python client.py download <文件ID>

# 4. 验证文件完整性
python -c "
import hashlib

def file_hash(path):
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        while data := f.read(8192):
            sha256.update(data)
    return sha256.hexdigest()

original = file_hash('test.bin')
downloaded = file_hash('downloads/test.bin')

if original == downloaded:
    print('✓ 文件完整性验证通过')
    print(f'  哈希值: {original[:16]}...')
else:
    print('✗ 文件完整性验证失败')
"
```

---

## 常见问题

### Q1: 如何判断文件是否使用了块级去重？

**A:** 查看上传时的输出信息：

```bash
# 使用块级去重的输出
使用块级去重上传...
=== 块级上传: file.bin (20.00 MB) ===

# 使用文件级去重的输出
计算文件哈希...
检查文件是否已存在...

# 常规上传的输出
上传文件: file.bin (20.00 MB)
上传 file.bin: 100%|████████████████████|
```

### Q2: 什么时候应该使用块级去重？

**A:** 以下场景适合使用块级去重：

✅ **适合：**

- 大文件（>8MB）
- 有多个版本的文件
- 部分内容重复的文件
- 虚拟机镜像、数据库备份

❌ **不适合：**

- 小文件（<8MB）
- 完全不同的文件
- 已经高度压缩的文件（.zip, .jpg 等）

### Q3: 如何选择合适的块大小？

**A:** 块大小选择指南：

| 块大小 | 优点         | 缺点         | 适用场景       |
| ------ | ------------ | ------------ | -------------- |
| 1MB    | 高去重率     | 更多网络请求 | 频繁修改的文件 |
| 4MB    | 平衡（推荐） | -            | 通用场景       |
| 16MB   | 少网络请求   | 低去重率     | 大型静态文件   |

```bash
# 测试不同块大小
python client.py block-upload file.bin --chunk-size 1   # 1MB
python client.py block-upload file.bin --chunk-size 4   # 4MB（推荐）
python client.py block-upload file.bin --chunk-size 16  # 16MB
```

### Q4: 块级去重会影响下载速度吗？

**A:** 不会。下载时系统会自动组装数据块，对用户透明：

```bash
# 下载块级去重的文件（自动处理）
python client.py download <文件ID>
```

### Q5: 如何查看当前的去重效果？

**A:** 使用统计命令：

```bash
# 查看块级去重统计
python client.py block-stats

# 查看文件级去重统计（如果有的话）
# 访问 http://localhost:8000/docs 查看 /api/deduplication/stats
```

### Q6: 删除文件后，数据块会被自动清理吗？

**A:** 会的。系统使用引用计数管理数据块：

- 删除文件时，相关数据块的引用计数减 1
- 当引用计数降为 0 时，数据块会被自动删除
- 这确保了存储空间的高效利用

### Q7: 可以混合使用文件级去重和块级去重吗？

**A:** 可以。系统会自动选择最优策略：

```bash
# 小文件使用文件级去重
python client.py upload small.txt

# 大文件使用块级去重
python client.py upload large.bin

# 两种方式可以共存，互不影响
```

---

## 高级用法

### 批量上传测试

```bash
# 创建测试脚本 batch_upload.sh
cat > batch_upload.sh << 'EOF'
#!/bin/bash

# 创建10个测试文件
for i in {1..10}; do
    # 每个文件10MB，内容部分重复
    python -c "
import random
data = b'A' * (5 * 1024 * 1024)  # 前5MB相同
data += bytes([random.randint(0, 255) for _ in range(5 * 1024 * 1024)])  # 后5MB随机
with open('test_file_$i.bin', 'wb') as f:
    f.write(data)
"

    # 上传文件
    python client.py block-upload test_file_$i.bin --chunk-size 2

    echo "已上传文件 $i/10"
done

# 查看统计
python client.py block-stats

# 清理测试文件
rm test_file_*.bin
EOF

chmod +x batch_upload.sh
./batch_upload.sh
```

### 性能对比测试

```bash
# 创建对比测试脚本
cat > compare_upload.sh << 'EOF'
#!/bin/bash

# 创建20MB测试文件
python -c "with open('test_compare.bin', 'wb') as f: f.write(b'Test' * (5 * 1024 * 1024))"

echo "=== 测试1: 常规上传（无去重） ==="
time python client.py upload test_compare.bin --no-dedup --no-block-dedup --no-compression

echo -e "\n=== 测试2: 文件级去重 ==="
time python client.py upload test_compare.bin --no-block-dedup

echo -e "\n=== 测试3: 块级去重（4MB块） ==="
time python client.py block-upload test_compare.bin --chunk-size 4

echo -e "\n=== 测试4: 块级去重（2MB块） ==="
time python client.py block-upload test_compare.bin --chunk-size 2

# 清理
rm test_compare.bin
EOF

chmod +x compare_upload.sh
./compare_upload.sh
```

---

## 总结

块级去重功能现在可以通过简单的命令行使用：

```bash
# 最简单的用法（自动优化）
python client.py upload <文件>

# 强制块级去重
python client.py block-upload <文件>

# 查看效果
python client.py block-stats
```

开始使用块级去重，让你的云盘更高效！🚀
