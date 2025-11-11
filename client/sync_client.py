"""
云盘自动同步客户端
"""
import sys
import os
import time
import signal
import logging
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from client import CloudDriveClient
from sync_manager import SyncManager
from config import config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sync.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


class SyncClient:
    """同步客户端"""
    
    def __init__(self, sync_folder=None):
        """
        初始化同步客户端
        
        Args:
            sync_folder: 同步文件夹路径（默认为当前目录下的sync_folder）
        """
        # API客户端
        self.api_client = CloudDriveClient(config.API_BASE_URL)
        
        # 同步文件夹
        if sync_folder is None:
            sync_folder = os.path.join(os.getcwd(), 'sync_folder')
        self.sync_folder = os.path.abspath(sync_folder)
        
        # 创建同步文件夹
        os.makedirs(self.sync_folder, exist_ok=True)
        
        # 数据库路径
        db_path = os.path.join(self.sync_folder, '.sync.db')
        
        # 同步管理器
        self.sync_manager = SyncManager(
            self.api_client,
            self.sync_folder,
            db_path
        )
        
        # 信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """处理中断信号"""
        logger.info("\n收到停止信号，正在安全退出...")
        self.stop()
        sys.exit(0)
    
    def start(self, do_initial_sync=True):
        """
        启动同步客户端
        
        Args:
            do_initial_sync: 是否执行初始同步
        """
        logger.info("=" * 60)
        logger.info("云盘自动同步客户端")
        logger.info("=" * 60)
        logger.info(f"API地址: {config.API_BASE_URL}")
        logger.info(f"同步文件夹: {self.sync_folder}")
        logger.info("=" * 60)
        
        # 测试API连接
        try:
            logger.info("测试API连接...")
            files = self.api_client.list_files("/")
            logger.info(f"✓ API连接成功，服务器文件数: {len(files)}")
        except Exception as e:
            logger.error(f"✗ API连接失败: {e}")
            logger.error("请检查：")
            logger.error("  1. 后端服务是否运行")
            logger.error("  2. config.py中API_BASE_URL是否正确")
            logger.error("  3. 网络连接是否正常")
            return
        
        # 启动同步
        self.sync_manager.start(do_initial_sync=do_initial_sync)
        
        logger.info("")
        logger.info("提示：")
        logger.info(f"  - 将文件放入 {self.sync_folder} 即可自动同步")
        logger.info("  - 按 Ctrl+C 停止同步")
        logger.info("  - 查看 sync.log 了解详细日志")
        logger.info("")
        
        # 保持运行
        try:
            while self.sync_manager.running:
                time.sleep(1)
                
                # 每30秒显示一次状态
                if int(time.time()) % 30 == 0:
                    self._print_status()
        
        except KeyboardInterrupt:
            logger.info("\n收到停止信号")
            self.stop()
    
    def stop(self):
        """停止同步"""
        self.sync_manager.stop()
    
    def _print_status(self):
        """打印同步状态"""
        status = self.sync_manager.get_status()
        logger.info("=" * 60)
        logger.info("同步状态:")
        logger.info(f"  运行中: {status['running']}")
        logger.info(f"  同步文件夹: {status['sync_folder']}")
        logger.info(f"  总文件数: {status['total_files']}")
        logger.info(f"  已同步: {status['synced']}")
        logger.info(f"  待同步: {status['pending']}")
        logger.info(f"  错误: {status['errors']}")
        logger.info("=" * 60)
    
    def status(self):
        """显示状态"""
        self._print_status()
        
        # 显示文件列表
        files = self.sync_manager.list_synced_files()
        if files:
            logger.info("\n已同步文件:")
            for f in files[:10]:  # 只显示前10个
                status_icon = "✓" if f.status == 'synced' else "⏳" if f.status == 'pending' else "✗"
                logger.info(f"  {status_icon} {f.local_path}")
            
            if len(files) > 10:
                logger.info(f"  ... 还有 {len(files) - 10} 个文件")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='云盘自动同步客户端')
    parser.add_argument(
        '--folder', 
        type=str, 
        help='同步文件夹路径（默认：./sync_folder）'
    )
    parser.add_argument(
        '--no-initial-sync',
        action='store_true',
        help='跳过初始同步'
    )
    parser.add_argument(
        '--status',
        action='store_true',
        help='只显示状态，不启动同步'
    )
    
    args = parser.parse_args()
    
    # 创建客户端
    client = SyncClient(sync_folder=args.folder)
    
    if args.status:
        # 只显示状态
        client.status()
    else:
        # 启动同步
        client.start(do_initial_sync=not args.no_initial_sync)


if __name__ == '__main__':
    main()

