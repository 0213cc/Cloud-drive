"""
同步引擎 - 核心同步逻辑
"""
import os
import time
import hashlib
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncEngine:
    """同步引擎"""
    
    def __init__(self, api_client, sync_db, file_watcher):
        """
        初始化同步引擎
        
        Args:
            api_client: API客户端
            sync_db: 同步数据库
            file_watcher: 文件监控器
        """
        self.api_client = api_client
        self.sync_db = sync_db
        self.file_watcher = file_watcher
        self.syncing = False  # 正在同步标志（防止递归）
    
    def calculate_file_hash(self, file_path):
        """计算文件SHA-256哈希"""
        sha256_hash = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            return sha256_hash.hexdigest()
        except Exception as e:
            logger.error(f"计算哈希失败 {file_path}: {e}")
            return ""
    
    def get_file_modified_time(self, file_path):
        """获取文件修改时间"""
        try:
            return datetime.fromtimestamp(os.path.getmtime(file_path))
        except:
            return datetime.utcnow()
    
    def upload_file(self, local_path, remote_path):
        """
        上传文件到服务器
        
        Args:
            local_path: 本地文件绝对路径
            remote_path: 远程路径
            
        Returns:
            上传结果字典
        """
        try:
            logger.info(f"上传文件: {local_path} -> {remote_path}")
            
            # 更新状态为上传中
            rel_path = self.file_watcher.get_relative_path(local_path)
            self.sync_db.update_status(rel_path, 'uploading')
            
            # 上传
            result = self.api_client.upload_file(
                local_path,
                remote_path=os.path.dirname(remote_path),
                show_progress=False
            )
            
            if result.get('success'):
                # 更新同步数据库
                file_info = result.get('file_info', {})
                self.sync_db.add_file(
                    local_path=rel_path,
                    remote_path=remote_path,
                    remote_id=file_info.get('id'),
                    local_modified=self.get_file_modified_time(local_path),
                    size=file_info.get('size', 0),
                    hash_value=file_info.get('hash_value', ''),
                    is_directory=False
                )
                
                logger.info(f"✓ 上传成功: {local_path}")
                return {'success': True, 'file_id': file_info.get('id')}
            else:
                self.sync_db.update_status(rel_path, 'error')
                logger.error(f"✗ 上传失败: {local_path} - {result.get('error')}")
                return {'success': False, 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"上传异常: {local_path} - {e}")
            return {'success': False, 'error': str(e)}
    
    def download_file(self, file_id, local_path, remote_path):
        """
        从服务器下载文件
        
        Args:
            file_id: 服务器文件ID
            local_path: 本地保存路径
            remote_path: 远程路径
            
        Returns:
            下载结果字典
        """
        try:
            logger.info(f"下载文件: {remote_path} -> {local_path}")
            
            # 确保目录存在
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            
            # 下载
            result = self.api_client.download_file(
                file_id,
                output_path=local_path,
                show_progress=False
            )
            
            if result.get('success'):
                # 更新同步数据库
                rel_path = self.file_watcher.get_relative_path(local_path)
                self.sync_db.add_file(
                    local_path=rel_path,
                    remote_path=remote_path,
                    remote_id=file_id,
                    local_modified=self.get_file_modified_time(local_path),
                    size=os.path.getsize(local_path) if os.path.exists(local_path) else 0,
                    hash_value=self.calculate_file_hash(local_path),
                    is_directory=False
                )
                
                logger.info(f"✓ 下载成功: {local_path}")
                return {'success': True}
            else:
                logger.error(f"✗ 下载失败: {remote_path} - {result.get('error')}")
                return {'success': False, 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"下载异常: {remote_path} - {e}")
            return {'success': False, 'error': str(e)}
    
    def delete_remote_file(self, file_id):
        """
        删除服务器上的文件
        
        Args:
            file_id: 服务器文件ID
            
        Returns:
            删除结果字典
        """
        try:
            logger.info(f"删除远程文件: ID={file_id}")
            result = self.api_client.delete_file(file_id)
            
            if result.get('success'):
                logger.info(f"✓ 删除成功: ID={file_id}")
                return {'success': True}
            else:
                logger.error(f"✗ 删除失败: ID={file_id}")
                return {'success': False, 'error': result.get('error')}
                
        except Exception as e:
            logger.error(f"删除异常: ID={file_id} - {e}")
            return {'success': False, 'error': str(e)}
    
    def sync_file_to_server(self, local_path):
        """
        同步本地文件到服务器
        
        Args:
            local_path: 本地文件绝对路径
        """
        if not os.path.exists(local_path):
            logger.warning(f"文件不存在: {local_path}")
            return
        
        # 防止递归同步
        if self.syncing:
            return
        
        try:
            self.syncing = True
            
            rel_path = self.file_watcher.get_relative_path(local_path)
            remote_path = f"/{rel_path.replace(os.sep, '/')}"
            
            # 检查数据库记录
            record = self.sync_db.get_file(rel_path)
            
            if record and record.remote_id:
                # 文件已存在，检查是否需要更新
                current_modified = self.get_file_modified_time(local_path)
                
                if current_modified > record.local_modified:
                    logger.info(f"文件已修改，重新上传: {rel_path}")
                    # 先删除旧文件（简化处理）
                    self.delete_remote_file(record.remote_id)
                    # 上传新文件
                    self.upload_file(local_path, remote_path)
                else:
                    logger.debug(f"文件未修改，跳过: {rel_path}")
            else:
                # 新文件，直接上传
                self.upload_file(local_path, remote_path)
        
        finally:
            self.syncing = False
    
    def handle_file_created(self, local_path):
        """处理文件创建事件"""
        logger.info(f"处理文件创建: {local_path}")
        self.sync_file_to_server(local_path)
    
    def handle_file_modified(self, local_path):
        """处理文件修改事件"""
        logger.info(f"处理文件修改: {local_path}")
        # 等待文件写入完成
        time.sleep(0.5)
        self.sync_file_to_server(local_path)
    
    def handle_file_deleted(self, local_path):
        """处理文件删除事件"""
        logger.info(f"处理文件删除: {local_path}")
        
        rel_path = self.file_watcher.get_relative_path(local_path)
        record = self.sync_db.get_file(rel_path)
        
        if record and record.remote_id:
            # 删除服务器文件
            self.delete_remote_file(record.remote_id)
            # 标记为已删除
            self.sync_db.mark_deleted(rel_path)
    
    def handle_file_moved(self, src_path, dest_path):
        """处理文件移动/重命名事件"""
        logger.info(f"处理文件移动: {src_path} -> {dest_path}")
        
        # 简化处理：先删除旧文件，再上传新文件
        self.handle_file_deleted(src_path)
        time.sleep(0.2)
        self.handle_file_created(dest_path)
    
    def initial_sync(self):
        """
        初始同步：扫描本地文件并上传
        """
        logger.info("开始初始同步...")
        
        files = self.file_watcher.scan_folder()
        logger.info(f"发现 {len(files)} 个文件需要同步")
        
        for rel_path in files:
            local_path = self.file_watcher.get_absolute_path(rel_path)
            
            # 检查是否已同步
            record = self.sync_db.get_file(rel_path)
            if not record or not record.remote_id:
                logger.info(f"同步文件: {rel_path}")
                remote_path = f"/{rel_path.replace(os.sep, '/')}"
                self.upload_file(local_path, remote_path)
                time.sleep(0.1)  # 避免过快
            else:
                logger.debug(f"文件已同步，跳过: {rel_path}")
        
        logger.info("初始同步完成")
    
    def sync_from_server(self):
        """
        从服务器同步到本地（拉取远程变更）
        """
        try:
            logger.info("检查服务器更新...")
            
            # 获取服务器文件列表
            files = self.api_client.list_files("/")
            
            for file_info in files:
                if file_info.get('is_directory'):
                    continue
                
                remote_path = file_info.get('path', '')
                remote_id = file_info.get('id')
                remote_hash = file_info.get('hash_value', '')
                remote_modified = file_info.get('updated_at')
                
                # 转换为本地路径
                rel_path = remote_path.lstrip('/').replace('/', os.sep)
                local_path = self.file_watcher.get_absolute_path(rel_path)
                
                # 检查本地是否存在
                record = self.sync_db.get_file(rel_path)
                
                # 情况1：本地不存在，直接下载
                if not record or not os.path.exists(local_path):
                    logger.info(f"发现新文件，下载: {remote_path}")
                    self.download_file(remote_id, local_path, remote_path)
                    time.sleep(0.1)
                    continue
                
                # 情况2：本地存在，检查是否需要更新
                # 计算本地文件哈希
                local_hash = self.calculate_file_hash(local_path)
                
                # 如果哈希不同，说明文件已被修改
                if remote_hash and local_hash != remote_hash:
                    logger.warning(f"检测到文件差异: {remote_path}")
                    logger.info(f"  本地哈希: {local_hash[:16]}...")
                    logger.info(f"  远程哈希: {remote_hash[:16]}...")
                    
                    # 检查冲突
                    local_modified = self.get_file_modified_time(local_path)
                    
                    # 简单策略：如果本地也被修改过（与数据库记录不同）
                    if record.hash_value and local_hash != record.hash_value:
                        # 本地也修改了，产生冲突
                        logger.warning(f"检测到冲突: {remote_path}")
                        logger.info("  本地和远程都被修改，创建冲突副本")
                        
                        # 创建冲突副本
                        from conflict_resolver import ConflictResolver
                        resolver = ConflictResolver(strategy=ConflictResolver.STRATEGY_COPY)
                        result = resolver._resolve_create_copy(local_path)
                        
                        if result.get('action') == 'create_copy':
                            logger.info(f"  冲突副本: {result.get('copy_path')}")
                        
                        # 下载远程版本覆盖本地
                        logger.info("  保留远程版本")
                        self.syncing = True  # 防止触发上传
                        self.download_file(remote_id, local_path, remote_path)
                        self.syncing = False
                    else:
                        # 只有远程被修改，直接下载覆盖
                        logger.info(f"远程文件已更新，下载: {remote_path}")
                        self.syncing = True  # 防止触发上传
                        self.download_file(remote_id, local_path, remote_path)
                        self.syncing = False
                    
                    time.sleep(0.1)
        
        except Exception as e:
            logger.error(f"从服务器同步失败: {e}")

