# 文件去重功能 - 快速开始

## 🚀 5分钟快速体验

### 步骤 1: 数据库迁移（如果需要）

```bash
cd backend
python migrate_deduplication.py
```

**预期输出：**
```
开始迁移数据库: cloud_drive.db
✓ file_chunks表已存在
✓ files表已有chunk_id字段
✓ file_history表已有chunk_id字段
✓ 所有文件都已有chunk_id，无需迁移
✓ 数据库迁移成功！
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
python test_deduplication.py
```

**预期输出：**
```
================================================================================
文件去重功能测试
================================================================================

当前用户: testuser

================================================================================
测试 1: 基本去重功能
================================================================================
✓ 生成测试文件: test_dedup_1.txt (1.00 MB)

第一次上传（应该正常上传）:
上传文件: test_dedup_1.txt (1.00 MB)
计算文件哈希...
检查文件是否已存在...
常规上传...
✓ 上传成功: test_dedup_1.txt (版本: 1)
✓ 第一次上传成功，文件ID: 123

✓ 复制文件: test_dedup_2.txt

第二次上传相同内容的文件（应该通过去重）:
上传文件: test_dedup_2.txt (1.00 MB)
计算文件哈希...
检查文件是否已存在...
✓ 文件已存在（被引用2次），跳过上传
✓ 文件上传成功（通过去重，无需传输数据） (版本: 1)
✓ 第二次上传成功，文件ID: 124
✅ 去重成功！消息: 文件上传成功（通过去重，无需传输数据）

[更多测试...]

================================================================================
测试结果汇总
================================================================================
  ✅ 通过: 基本去重功能
  ✅ 通过: 不同文件不会去重
  ✅ 通过: 去重统计
  ✅ 通过: 去重与版本控制兼容性
  ✅ 通过: 大文件去重

总计: 5/5 通过

🎉 所有测试通过！文件去重功能正常工作！
```

---

## 📝 手动测试

### 测试场景 1: 上传重复文件

```bash
# 1. 创建测试文件
echo "Hello, Cloud Drive!" > test1.txt

# 2. 第一次上传
python client/client.py upload test1.txt
# 输出: ✓ 上传成功: test1.txt (版本: 1)

# 3. 复制文件
cp test1.txt test2.txt

# 4. 第二次上传（应该去重）
python client/client.py upload test2.txt
# 输出:
# 计算文件哈希...
# 检查文件是否已存在...
# ✓ 文件已存在（被引用2次），跳过上传
# ✓ 文件上传成功（通过去重，无需传输数据）
```

### 测试场景 2: 查看去重统计

```bash
# 方法1: 使用Python脚本
python -c "
import sys
sys.path.insert(0, 'client/src')
from client import CloudDriveClient
from dedup_client import DeduplicationClient

client = CloudDriveClient()
headers = client._get_headers()
stats = DeduplicationClient.get_deduplication_stats(
    client.session, client.base_url, headers
)

print(f'总文件块数: {stats[\"total_chunks\"]}')
print(f'被去重的文件块数: {stats[\"deduplicated_chunks\"]}')
print(f'节省空间: {stats[\"saved_space_mb\"]:.2f} MB')
print(f'去重率: {stats[\"deduplication_ratio\"]:.2f}%')
"

# 方法2: 访问API文档
# 打开浏览器: http://localhost:8000/docs
# 找到 GET /api/deduplication/stats
# 点击 "Try it out" -> "Execute"
```

### 测试场景 3: 大文件去重

```bash
# 1. 生成10MB测试文件
python -c "print('Test line\n' * 500000)" > large_test.txt

# 2. 第一次上传（需要传输）
time python client/client.py upload large_test.txt
# 耗时: ~5秒

# 3. 复制文件
cp large_test.txt large_test_copy.txt

# 4. 第二次上传（去重，几乎瞬间完成）
time python client/client.py upload large_test_copy.txt
# 耗时: ~0.3秒
# 速度提升: 94%+
```

---

## 🔍 验证去重效果

### 方法 1: 查看数据库

```bash
cd backend
sqlite3 cloud_drive.db

# 查看文件块
SELECT 
    id,
    substr(hash_value, 1, 16) as hash,
    size / 1024 / 1024 as size_mb,
    reference_count,
    is_compressed
FROM file_chunks
ORDER BY reference_count DESC
LIMIT 10;

# 查看去重统计
SELECT 
    COUNT(*) as total_chunks,
    SUM(CASE WHEN reference_count > 1 THEN 1 ELSE 0 END) as dedup_chunks,
    SUM(reference_count) as total_refs,
    SUM(size * (reference_count - 1)) / 1024 / 1024 as saved_mb
FROM file_chunks;
```

### 方法 2: 查看后端日志

启动后端时会看到去重相关日志：

```
INFO: 发现重复文件: hash=abc123..., refs=2
INFO: 增加引用计数: chunk_id=42, hash=abc123..., refs=3
INFO: 用户 1 通过去重创建文件: /test2.txt, chunk_id=42, refs=3
```

### 方法 3: 使用修复脚本查看统计

```bash
cd backend
python fix_reference_counts.py --stats
```

**输出示例：**
```
================================================================================
去重统计信息
================================================================================

文件块统计:
  总文件块数: 50
  被去重的文件块数: 15
  总引用次数: 120
  节省的副本数: 70

存储空间:
  实际存储: 500.00 MB
  无去重时需要: 1200.00 MB
  节省空间: 700.00 MB
  去重率: 58.33%

引用次数最多的文件块:
  Hash                 大小(MB)     引用次数   压缩
  ------------------------------------------------------------
  abc123...            10.00        12         是
  def456...            5.00         8          是
  ghi789...            2.50         5          否
```

---

## 🎯 实际应用场景

### 场景 1: 团队协作

多个团队成员上传相同的文档：

```bash
# 用户A上传
python client/client.py login  # 登录为用户A
python client/client.py upload project_plan.pdf

# 用户B上传相同文件
python client/client.py login  # 登录为用户B
python client/client.py upload project_plan.pdf
# ✓ 文件已存在，跳过上传（节省带宽和存储）
```

### 场景 2: 备份多个版本

同一文件的多个备份：

```bash
# 原始文件
python client/client.py upload document.docx

# 备份1（内容相同）
cp document.docx document_backup_2024.docx
python client/client.py upload document_backup_2024.docx
# ✓ 去重，不占用额外空间

# 备份2（内容相同）
cp document.docx document_backup_final.docx
python client/client.py upload document_backup_final.docx
# ✓ 去重，不占用额外空间
```

### 场景 3: 批量上传

上传包含重复文件的文件夹：

```python
import os
from client import CloudDriveClient

client = CloudDriveClient()

# 上传文件夹中的所有文件
for root, dirs, files in os.walk('my_folder'):
    for filename in files:
        file_path = os.path.join(root, filename)
        result = client.upload_file(file_path)
        
        # 自动去重，重复文件不会重复上传
        if '去重' in result.get('message', ''):
            print(f"✓ {filename} 已去重")
```

---

## 🛠️ 故障排查

### 问题 1: 文件没有去重

**检查步骤：**

```bash
# 1. 确认数据库已迁移
cd backend
python migrate_deduplication.py

# 2. 检查后端日志
# 应该看到: "检查文件是否已存在..." 和 "发现重复文件..." 等日志

# 3. 手动测试API
curl -X POST "http://localhost:8000/api/deduplication/check" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"hash_value":"test_hash","size":1024}'
```

### 问题 2: 引用计数不准确

```bash
cd backend
python fix_reference_counts.py
```

### 问题 3: 去重后下载失败

```bash
# 检查文件信息
python client/client.py info <FILE_ID>

# 查看chunk_id是否存在
cd backend
sqlite3 cloud_drive.db "SELECT * FROM file_chunks WHERE id=<CHUNK_ID>;"
```

---

## 📚 下一步

1. **阅读完整文档**: [docs/DEDUPLICATION_GUIDE.md](docs/DEDUPLICATION_GUIDE.md)
2. **查看API文档**: http://localhost:8000/docs
3. **测试压缩功能**: [COMPRESSION_TEST_GUIDE.md](COMPRESSION_TEST_GUIDE.md)
4. **了解版本控制**: 查看版本控制相关文档

---

## 💡 提示

- 去重功能默认启用，无需额外配置
- 第一次上传文件需要完整传输，后续相同文件会去重
- 去重与压缩可以同时使用，效果叠加
- 删除文件时会自动管理引用计数
- 可以通过 `enable_deduplication=False` 禁用去重

---

## 🎉 享受去重带来的便利！

-[object Object]** 50-90%
- ⚡ **提升上传速度** 90%+
- [object Object] 存储和带宽[object Object]安全** 完整的权限隔离

开始使用文件去重功能，让你的云盘更高效！🚀

