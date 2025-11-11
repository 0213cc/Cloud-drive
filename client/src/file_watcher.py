"""
文件系统监控器 - 使用watchdog监控文件变化
"""
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import os
import time
import logging
from queue import Queue
from pathlib import Path

logger = logging.getLogger(__name__)


class FileChangeEvent:
    """文件变化事件"""
    
    def __init__(self, event_type, src_path, dest_path=None):
        self.event_type = event_type  # created, modified, deleted, moved
        self.src_path = src_path
        self.dest_path = dest_path
        self.timestamp = time.time()
    
    def __repr__(self):
        if self.dest_path:
            return f"<FileChangeEvent {self.event_type}: {self.src_path} -> {self.dest_path}>"
        return f"<FileChangeEvent {self.event_type}: {self.src_path}>"


class SyncEventHandler(FileSystemEventHandler):
    """同步事件处理器"""
    
    def __init__(self, event_queue, sync_folder, ignore_patterns=None):
        super().__init__()
        self.event_queue = event_queue
        self.sync_folder = os.path.abspath(sync_folder)
        self.ignore_patterns = ignore_patterns or []
        self.processing = False  # 防止递归监控
    
    def should_ignore(self, path):
        """检查是否应该忽略此路径"""
        # 忽略隐藏文件
        if os.path.basename(path).startswith('.'):
            return True
        
        # 忽略临时文件
        if path.endswith('.tmp') or path.endswith('~'):
            return True
        
        # 忽略同步数据库
        if 'sync.db' in path:
            return True
        
        # 自定义忽略模式
        for pattern in self.ignore_patterns:
            if pattern in path:
                return True
        
        return False
    
    def on_created(self, event):
        """文件/目录创建"""
        if event.is_directory or self.should_ignore(event.src_path):
            return
        
        logger.info(f"检测到文件创建: {event.src_path}")
        self.event_queue.put(FileChangeEvent('created', event.src_path))
    
    def on_modified(self, event):
        """文件修改"""
        if event.is_directory or self.should_ignore(event.src_path):
            return
        
        logger.info(f"检测到文件修改: {event.src_path}")
        self.event_queue.put(FileChangeEvent('modified', event.src_path))
    
    def on_deleted(self, event):
        """文件/目录删除"""
        if event.is_directory or self.should_ignore(event.src_path):
            return
        
        logger.info(f"检测到文件删除: {event.src_path}")
        self.event_queue.put(FileChangeEvent('deleted', event.src_path))
    
    def on_moved(self, event):
        """文件/目录移动/重命名"""
        if event.is_directory or self.should_ignore(event.src_path):
            return
        
        logger.info(f"检测到文件移动: {event.src_path} -> {event.dest_path}")
        self.event_queue.put(FileChangeEvent('moved', event.src_path, event.dest_path))


class FileWatcher:
    """文件监控器"""
    
    def __init__(self, sync_folder, ignore_patterns=None):
        """
        初始化文件监控器
        
        Args:
            sync_folder: 要监控的同步文件夹路径
            ignore_patterns: 忽略的文件模式列表
        """
        self.sync_folder = os.path.abspath(sync_folder)
        self.event_queue = Queue()
        self.observer = Observer()
        self.event_handler = SyncEventHandler(
            self.event_queue, 
            self.sync_folder,
            ignore_patterns
        )
        
        # 确保同步文件夹存在
        os.makedirs(self.sync_folder, exist_ok=True)
        
        logger.info(f"文件监控器初始化: {self.sync_folder}")
    
    def start(self):
        """启动监控"""
        self.observer.schedule(
            self.event_handler, 
            self.sync_folder, 
            recursive=True
        )
        self.observer.start()
        logger.info("文件监控已启动")
    
    def stop(self):
        """停止监控"""
        self.observer.stop()
        self.observer.join()
        logger.info("文件监控已停止")
    
    def get_event(self, timeout=1):
        """
        获取文件变化事件
        
        Args:
            timeout: 超时时间（秒）
            
        Returns:
            FileChangeEvent 或 None
        """
        try:
            return self.event_queue.get(timeout=timeout)
        except:
            return None
    
    def get_relative_path(self, absolute_path):
        """
        获取相对于同步文件夹的相对路径
        
        Args:
            absolute_path: 绝对路径
            
        Returns:
            相对路径字符串
        """
        return os.path.relpath(absolute_path, self.sync_folder)
    
    def get_absolute_path(self, relative_path):
        """
        获取绝对路径
        
        Args:
            relative_path: 相对路径
            
        Returns:
            绝对路径字符串
        """
        return os.path.join(self.sync_folder, relative_path)
    
    def scan_folder(self):
        """
        扫描同步文件夹中的所有文件
        
        Returns:
            文件路径列表（相对路径）
        """
        files = []
        for root, dirs, filenames in os.walk(self.sync_folder):
            # 忽略隐藏目录
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            for filename in filenames:
                if filename.startswith('.') or filename == 'sync.db':
                    continue
                
                full_path = os.path.join(root, filename)
                rel_path = self.get_relative_path(full_path)
                files.append(rel_path)
        
        return files

