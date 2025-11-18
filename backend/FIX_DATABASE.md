# 数据库字段缺失问题修复

## 问题描述

服务器报错：
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such column: files.compressed_size
```

## 原因分析

之前的迁移脚本 `migrate_compression.py` 存在逻辑错误：
- 当检测到 `is_compressed` 字段已存在时，会跳过整个迁移
- 导致 `compressed_size` 和 `compression_ratio` 字段没有被添加

当前数据库缺少的字段：
- ❌ `files.compressed_size` (BIGINT)
- ❌ `files.compression_ratio` (INTEGER)
- ❌ `file_history.compressed_size` (BIGINT)

## 解决方案

### 方案1：使用修复后的迁移脚本（推荐）

```bash
cd backend
python migrate_compression.py
```

修复后的脚本会：
- 逐个检查每个字段是否存在
- 只添加缺失的字段
- 不会重复添加已存在的字段

### 方案2：使用专门的修复脚本

```bash
cd backend
python check_and_fix_db.py
```

这个脚本会：
- 详细显示当前数据库结构
- 检测缺失的字段
- 自动添加缺失的字段
- 进行最终验证

## 验证修复

运行以下命令验证数据库结构：

```bash
cd backend
python -c "import sqlite3; conn = sqlite3.connect('cloud_drive.db'); cursor = conn.cursor(); cursor.execute('PRAGMA table_info(files)'); print('\n'.join([f'{col[1]} ({col[2]})' for col in cursor.fetchall()]))"
```

应该看到以下字段：
- ✓ is_compressed (BOOLEAN)
- ✓ compressed_size (BIGINT)
- ✓ compression_ratio (INTEGER)

## 重启服务

修复完成后，重启后端服务：

```bash
cd backend
python main.py
```

错误应该消失，压缩功能可以正常使用。

