"""
同步管理器 - 协调各个模块
"""
import time
import logging
import threading
from file_watcher import FileWatcher
from sync_db import SyncDatabase
from sync_engine import SyncEngine
from conflict_resolver import ConflictResolver

logger = logging.getLogger(__name__)


class SyncManager:
    """同步管理器"""
    
    def __init__(self, api_client, sync_folder, db_path='sync.db'):
        """
        初始化同步管理器
        
        Args:
            api_client: API客户端
            sync_folder: 同步文件夹路径
            db_path: 同步数据库路径
        """
        self.api_client = api_client
        self.sync_folder = sync_folder
        
        # 初始化各个组件
        self.sync_db = SyncDatabase(db_path)
        self.file_watcher = FileWatcher(sync_folder)
        self.sync_engine = SyncEngine(api_client, self.sync_db, self.file_watcher)
        self.conflict_resolver = ConflictResolver(strategy=ConflictResolver.STRATEGY_COPY)
        
        # 控制标志
        self.running = False
        self.sync_thread = None
        self.pull_interval = 30  # 从服务器拉取的间隔（秒）
    
    def start(self, do_initial_sync=True):
        """
        启动同步
        
        Args:
            do_initial_sync: 是否执行初始同步
        """
        if self.running:
            logger.warning("同步已在运行中")
            return
        
        logger.info("=" * 50)
        logger.info("启动云盘自动同步")
        logger.info(f"同步文件夹: {self.sync_folder}")
        logger.info("=" * 50)
        
        # 启动文件监控
        self.file_watcher.start()
        
        # 初始同步
        if do_initial_sync:
            logger.info("执行初始同步...")
            self.sync_engine.initial_sync()
        
        # 启动同步线程
        self.running = True
        self.sync_thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.sync_thread.start()
        
        logger.info("自动同步已启动")
        logger.info("监控文件变化中...")
    
    def stop(self):
        """停止同步"""
        if not self.running:
            return
        
        logger.info("正在停止同步...")
        
        self.running = False
        
        # 停止文件监控
        self.file_watcher.stop()
        
        # 等待同步线程结束
        if self.sync_thread:
            self.sync_thread.join(timeout=5)
        
        logger.info("同步已停止")
    
    def _sync_loop(self):
        """同步主循环"""
        last_pull_time = 0
        
        while self.running:
            try:
                # 1. 处理本地文件变化
                event = self.file_watcher.get_event(timeout=1)
                
                if event:
                    self._handle_event(event)
                
                # 2. 定期从服务器拉取更新
                current_time = time.time()
                if current_time - last_pull_time >= self.pull_interval:
                    logger.info("定期从服务器拉取更新...")
                    self.sync_engine.sync_from_server()
                    last_pull_time = current_time
                
                # 短暂休息
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"同步循环错误: {e}", exc_info=True)
                time.sleep(1)
    
    def _handle_event(self, event):
        """
        处理文件变化事件
        
        Args:
            event: FileChangeEvent对象
        """
        try:
            if event.event_type == 'created':
                self.sync_engine.handle_file_created(event.src_path)
            
            elif event.event_type == 'modified':
                self.sync_engine.handle_file_modified(event.src_path)
            
            elif event.event_type == 'deleted':
                self.sync_engine.handle_file_deleted(event.src_path)
            
            elif event.event_type == 'moved':
                self.sync_engine.handle_file_moved(event.src_path, event.dest_path)
        
        except Exception as e:
            logger.error(f"处理事件失败 {event}: {e}")
    
    def force_sync_now(self):
        """立即执行一次完整同步"""
        logger.info("执行强制同步...")
        
        # 上传本地变更
        self.sync_engine.initial_sync()
        
        # 下载远程变更
        self.sync_engine.sync_from_server()
        
        logger.info("强制同步完成")
    
    def get_status(self):
        """
        获取同步状态
        
        Returns:
            状态字典
        """
        all_files = self.sync_db.get_all_files()
        
        synced_count = sum(1 for f in all_files if f.status == 'synced')
        pending_count = sum(1 for f in all_files if f.status == 'pending')
        error_count = sum(1 for f in all_files if f.status == 'error')
        
        return {
            'running': self.running,
            'total_files': len(all_files),
            'synced': synced_count,
            'pending': pending_count,
            'errors': error_count,
            'sync_folder': self.sync_folder
        }
    
    def list_synced_files(self):
        """列出所有已同步的文件"""
        return self.sync_db.get_all_files()

