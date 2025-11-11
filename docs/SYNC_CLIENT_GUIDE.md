# 自动同步客户端使用指南

## 🎯 功能说明

自动同步客户端实现了**云盘的核心功能**：

- ✅ 实时监控本地文件夹
- ✅ 自动上传文件变更
- ✅ 定期从服务器拉取更新
- ✅ 双向同步（本地↔云端）
- ✅ 冲突检测与解决
- ✅ 同步状态管理

---

## 📋 前提条件

1. 后端服务已启动（本地或远程EC2）
2. 已安装客户端依赖

---

## 🚀 快速开始

### 步骤1：安装依赖

```powershell
# 在本地Windows
cd D:\Dase\云计算\Cloud-drive\client

# 激活虚拟环境
venv\Scripts\activate

# 安装新增的依赖
pip install watchdog==3.0.0 sqlalchemy==2.0.23
```

### 步骤2：配置API地址

确保 `client/.env` 配置正确：

```env
# 本地测试
API_BASE_URL=http://localhost:8000

# 远程服务器（如果后端在EC2）
# API_BASE_URL=http://your-ec2-address:8000

USER_ID=1
DOWNLOAD_DIR=./downloads
```

### 步骤3：启动同步客户端

```powershell
# 方法1：使用默认同步文件夹（./sync_folder）
python sync_client.py

# 方法2：指定自定义同步文件夹
python sync_client.py --folder D:\MyCloudSync

# 方法3：跳过初始同步（如果已经同步过）
python sync_client.py --no-initial-sync
```

### 步骤4：测试自动同步

**在新的PowerShell窗口或文件管理器中：**

```powershell
# 进入同步文件夹
cd sync_folder

# 创建测试文件
echo "Hello Cloud Drive!" > test1.txt

# 等待几秒，查看同步日志
# 应该看到：检测到文件创建 -> 上传成功

# 修改文件
echo "Modified content" >> test1.txt

# 应该自动检测并上传

# 删除文件
del test1.txt

# 应该自动删除远程文件
```

---

## 📊 查看同步状态

### 方法1：查看日志

```powershell
# 实时查看日志
Get-Content sync.log -Wait -Tail 20

# 或者用记事本打开
notepad sync.log
```

### 方法2：使用状态命令

```powershell
python sync_client.py --status
```

---

## 🧪 完整测试流程

### 测试1：基本同步功能

```powershell
# 1. 启动同步客户端（窗口1）
cd D:\Dase\云计算\Cloud-drive\client
venv\Scripts\activate
python sync_client.py

# 2. 在sync_folder中操作（窗口2）
cd sync_folder

# 创建文件
echo "Test file 1" > file1.txt
echo "Test file 2" > file2.txt

# 创建目录和文件
mkdir documents
echo "Important doc" > documents\report.txt

# 等待10秒，观察日志输出
# 应该看到文件自动上传
```

**验证：**
- 查看日志：应该有 "上传成功" 消息
- 使用旧的客户端检查：`python client.py list`
- 在浏览器查看：http://localhost:8000/docs

---

### 测试2：文件修改同步

```powershell
cd sync_folder

# 修改现有文件
echo "Updated content" >> file1.txt

# 观察日志
# 应该看到：检测到文件修改 -> 重新上传
```

---

### 测试3：文件删除同步

```powershell
cd sync_folder

# 删除文件
del file2.txt

# 观察日志
# 应该看到：检测到文件删除 -> 删除远程文件

# 验证：使用客户端查看
cd ..
python client.py list
# file2.txt 应该已经不在列表中
```

---

### 测试4：文件重命名

```powershell
cd sync_folder

# 重命名文件
ren file1.txt file1_renamed.txt

# 观察日志
# 应该看到：文件移动 -> 删除旧文件 -> 上传新文件
```

---

### 测试5：双向同步（从服务器拉取）

```powershell
# 1. 使用旧客户端上传一个文件（模拟其他设备）
cd D:\Dase\云计算\Cloud-drive\client
echo "From another device" > external_file.txt
python client.py upload external_file.txt

# 2. 等待30秒（同步客户端会定期拉取）
# 或者重启同步客户端（会执行初始同步）

# 3. 检查sync_folder
dir sync_folder
# 应该看到 external_file.txt 被自动下载了
```

---

### 测试6：冲突处理

```powershell
# 1. 在sync_folder创建文件
cd sync_folder
echo "Local version" > conflict_test.txt

# 2. 等待上传完成

# 3. 手动使用客户端上传同名文件（模拟冲突）
cd ..
echo "Remote version" > temp_conflict.txt
python client.py upload temp_conflict.txt --path /
# 然后在服务器端重命名为 conflict_test.txt

# 4. 同步客户端检测到冲突时，会创建冲突副本
# 应该看到：conflict_test_conflict_20241109_153045.txt
```

---

## 📁 目录结构

运行同步客户端后的目录结构：

```
client/
├── sync_folder/           # 同步文件夹
│   ├── .sync.db          # 同步状态数据库（隐藏）
│   ├── file1.txt         # 你的文件
│   ├── file2.txt
│   └── documents/
│       └── report.txt
├── sync.log              # 同步日志
├── sync_client.py        # 同步客户端主程序
└── src/
    ├── sync_manager.py
    ├── sync_engine.py
    ├── file_watcher.py
    ├── sync_db.py
    └── conflict_resolver.py
```

---

## 🔧 常见问题

### Q1: 同步客户端无法启动

**错误：** `ModuleNotFoundError: No module named 'watchdog'`

**解决：**
```powershell
pip install watchdog sqlalchemy
```

---

### Q2: 无法连接到API

**错误：** `API连接失败: Connection refused`

**解决：**
1. 检查后端是否运行：浏览器访问 http://localhost:8000
2. 检查 `.env` 中的 `API_BASE_URL`
3. 如果使用SSH隧道，确保隧道窗口在运行

---

### Q3: 文件没有自动同步

**检查：**
```powershell
# 1. 查看日志
type sync.log

# 2. 检查文件是否被忽略
# 隐藏文件（以.开头）会被忽略
# 临时文件（.tmp, ~结尾）会被忽略

# 3. 手动触发同步
python client.py upload sync_folder\your_file.txt
```

---

### Q4: 同步数据库损坏

**解决：**
```powershell
# 删除同步数据库，重新初始化
del sync_folder\.sync.db

# 重启同步客户端（会重新扫描并同步所有文件）
python sync_client.py
```

---

### Q5: 如何停止同步

**方法1：** 按 `Ctrl+C`

**方法2：** 关闭PowerShell窗口

---

## 📊 性能说明

### 同步间隔

- **文件变化监控：** 实时（watchdog）
- **服务器拉取：** 每30秒一次
- **状态显示：** 每30秒一次

### 配置调优

编辑 `src/sync_manager.py` 中的参数：

```python
self.pull_interval = 30  # 改为60秒减少服务器请求
```

---

## 🎯 高级功能

### 忽略特定文件

编辑 `src/file_watcher.py` 中的 `should_ignore` 方法：

```python
def should_ignore(self, path):
    # 添加自定义忽略规则
    if path.endswith('.log'):
        return True
    if 'temp' in path.lower():
        return True
    return False
```

### 修改冲突解决策略

编辑 `sync_client.py`：

```python
# 改为"最后写入获胜"策略
self.conflict_resolver = ConflictResolver(
    strategy=ConflictResolver.STRATEGY_LWW
)
```

---

## 📝 日志说明

### 正常日志

```
2024-11-09 15:30:45 - 检测到文件创建: D:\...\sync_folder\test.txt
2024-11-09 15:30:45 - 上传文件: test.txt -> /test.txt
2024-11-09 15:30:46 - ✓ 上传成功: test.txt
```

### 错误日志

```
2024-11-09 15:31:00 - ✗ 上传失败: test.txt - Connection timeout
2024-11-09 15:31:01 - 更新状态: test.txt -> error
```

---

## 🆘 获取帮助

```powershell
# 查看帮助
python sync_client.py --help

# 查看日志
notepad sync.log

# 查看同步状态
python sync_client.py --status
```

---

## ✅ 测试清单

完成以下测试确保功能正常：

- [ ] 启动同步客户端成功
- [ ] 创建文件自动上传
- [ ] 修改文件自动同步
- [ ] 删除文件自动同步
- [ ] 重命名文件自动处理
- [ ] 从服务器拉取文件成功
- [ ] 多个文件同时同步
- [ ] 嵌套目录同步
- [ ] 停止同步正常退出
- [ ] 重启后状态恢复

---

**恭喜！你已经实现了云盘的核心自动同步功能！** 🎉

