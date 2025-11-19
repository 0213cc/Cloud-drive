# 断点续传功能指南

## 📋 目录

- [功能概述](#功能概述)
- [技术架构](#技术架构)
- [快速开始](#快速开始)
- [命令行使用](#命令行使用)
- [API 文档](#api文档)
- [常见问题](#常见问题)

---

## 功能概述

### 什么是断点续传？

断点续传（Resumable Upload）允许用户在上传大文件时，如果上传过程意外中断（如网络问题、程序关闭），可以在下次重新上传时从上次中断的地方继续，而无需从头开始。这大大提高了大文件上传的可靠性和用户体验。

### 核心优势

- ✅ **高可靠性**：不再担心因网络波动导致长时间的上传失败。
- ✅ **节省时间**：只需上传剩余部分，无需重复上传已成功的部分。
- ✅ **节省带宽**：避免了不必要的数据传输。
- ✅ **自动恢复**：客户端可以自动检测并恢复未完成的上传。

### 工作流程

1.  **启动会话**：客户端在上传大文件前，向服务器请求一个唯一的 `upload_id`，用于标识本次上传任务。
2.  **状态查询**：客户端使用 `upload_id` 查询服务器，获取哪些数据块已经上传成功。
3.  **增量上传**：客户端只上传服务器上不存在的数据块。
4.  **完成上传**：所有数据块上传完成后，客户端通知服务器使用这些数据块组装文件。

---

## 技术架构

### 数据模型

#### `UploadSession` - 上传会话表

用于跟踪大文件的断点续传状态。

```python
class UploadSession:
    id: int
    upload_id: str          # 唯一的会话ID
    user_id: int
    file_hash: str          # 完整文件的哈希值
    filename: str
    path: str
    total_size: int
    chunk_size: int
    total_chunks: int
    uploaded_chunks: List[int] # 已上传的块索引列表
    status: str             # 状态 (pending, uploading, completed, etc.)
    created_at: datetime
    expires_at: datetime    # 会话过期时间
```

### API 端点

- `POST /api/resumable/start`：启动或恢复一个上传会话。
- `GET /api/resumable/status/{upload_id}`：查询上传状态。
- `POST /api/resumable/complete/{upload_id}`：完成上传并组装文件。

---

## 快速开始

### 步骤 1: 数据库迁移

```bash
cd backend
python migrate_resumable_upload.py
```

### 步骤 2: 重启后端服务

```bash
cd backend
python -m uvicorn app.main:app --reload
```

### 步骤 3: 手动测试

1.  **创建测试文件** (例如，50MB)

    ```bash
    python -c "import os; f=open('large_file.bin', 'wb'); f.write(os.urandom(50 * 1024 * 1024)); f.close()"
    ```

2.  **开始上传并中途停止**

    ```bash
    cd client
    python client.py upload ../large_file.bin
    ```

    在上传过程中按下 `Ctrl + C`。

3.  **恢复上传**
    ```bash
    # 重新运行完全相同的命令
    python client.py upload ../large_file.bin
    ```
    您会看到上传从上次中断的地方继续。

---

## 命令行使用

断点续传功能已集成到现有的 `upload` 命令中，并默认启用。

### 基本用法

```bash
# 上传文件（自动启用断点续传）
python client.py upload <文件路径>
```

### 禁用断点续传

如果您希望强制从头开始上传，可以使用 `--no-resume` 标志。

```bash
# 禁用断点续传进行上传
python client.py upload <文件路径> --no-resume
```

### 示例

```bash
# 场景：上传一个100MB的大文件

# 1. 第一次尝试，网络中断
python client.py upload big_video.mp4
# ...上传到45%时中断...

# 2. 第二次尝试，自动恢复
python client.py upload big_video.mp4
# 输出会显示 "已恢复上传会话"，并从45%继续
```

---

## API 文档

### 1. 开始上传会话

- **端点**: `POST /api/resumable/start`
- **请求体**: `{"filename": "...", "total_size": ..., ...}`
- **响应**: `{"upload_id": "...", "uploaded_chunks": [...]}`

### 2. 查询上传状态

- **端点**: `GET /api/resumable/status/{upload_id}`
- **响应**: `{"status": "uploading", "uploaded_chunks": [...]}`

### 3. 完成上传

- **端点**: `POST /api/resumable/complete/{upload_id}`
- **请求体**: (与块级上传的 `assemble` 请求相同)
- **响应**: (与 `assemble` 响应相同)

---

## 常见问题

### Q1: 断点续传功能是否默认开启？

**A:** 是的，对于使用块级上传的大文件，断点续传功能是默认启用的。

### Q2: 上传会话会过期吗？

**A:** 是的，为了清理未完成的上传，上传会话默认设置为 7 天后过期。过期的会话将被视为无效，需要重新开始上传。

### Q3: 如果文件内容发生变化，断点续传会怎样？

**A:** 断点续传是基于文件的哈希值来识别文件的。如果文件内容发生任何变化，其哈希值也会改变，客户端将启动一个全新的上传会话，而不会尝试恢复旧的会话。这确保了文件的完整性。

### Q4: 如何清理未完成的上传？

**A:** 目前，未完成的上传会话会在 7 天后自动过期。未来可以添加一个后台任务来定期清理过期的会话和相关的孤立数据块。
