"""
冲突解决器 - 处理同步冲突
"""
import os
import shutil
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ConflictResolver:
    """冲突解决器"""
    
    STRATEGY_LWW = 'last_write_wins'  # 最后写入获胜
    STRATEGY_COPY = 'create_copy'     # 创建冲突副本
    STRATEGY_ASK = 'ask_user'         # 询问用户（暂不实现）
    
    def __init__(self, strategy=STRATEGY_COPY):
        """
        初始化冲突解决器
        
        Args:
            strategy: 冲突解决策略
        """
        self.strategy = strategy
    
    def detect_conflict(self, local_modified, remote_modified):
        """
        检测是否存在冲突
        
        Args:
            local_modified: 本地修改时间
            remote_modified: 远程修改时间
            
        Returns:
            是否存在冲突（布尔值）
        """
        if not local_modified or not remote_modified:
            return False
        
        # 如果两边都在最近被修改，认为存在冲突
        time_diff = abs((local_modified - remote_modified).total_seconds())
        
        # 时间差小于10秒认为可能冲突
        if time_diff < 10:
            return True
        
        return False
    
    def resolve_conflict(self, local_path, remote_path, local_modified, remote_modified):
        """
        解决冲突
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            local_modified: 本地修改时间
            remote_modified: 远程修改时间
            
        Returns:
            解决方案字典
        """
        if self.strategy == self.STRATEGY_LWW:
            return self._resolve_last_write_wins(local_modified, remote_modified)
        
        elif self.strategy == self.STRATEGY_COPY:
            return self._resolve_create_copy(local_path)
        
        else:
            # 默认使用最后写入获胜
            return self._resolve_last_write_wins(local_modified, remote_modified)
    
    def _resolve_last_write_wins(self, local_modified, remote_modified):
        """
        最后写入获胜策略
        
        Returns:
            {'action': 'keep_local' | 'keep_remote'}
        """
        if local_modified > remote_modified:
            logger.info("冲突解决：保留本地版本（更新）")
            return {'action': 'keep_local'}
        else:
            logger.info("冲突解决：保留远程版本（更新）")
            return {'action': 'keep_remote'}
    
    def _resolve_create_copy(self, local_path):
        """
        创建冲突副本策略
        
        Args:
            local_path: 本地文件路径
            
        Returns:
            {'action': 'create_copy', 'copy_path': 副本路径}
        """
        # 生成冲突副本文件名
        base_name, ext = os.path.splitext(local_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        copy_path = f"{base_name}_conflict_{timestamp}{ext}"
        
        try:
            # 复制本地文件为冲突副本
            if os.path.exists(local_path):
                shutil.copy2(local_path, copy_path)
                logger.info(f"创建冲突副本: {copy_path}")
            
            return {
                'action': 'create_copy',
                'copy_path': copy_path,
                'original_action': 'keep_remote'  # 原文件保留远程版本
            }
        
        except Exception as e:
            logger.error(f"创建冲突副本失败: {e}")
            # 失败时使用最后写入获胜
            return {'action': 'keep_local'}
    
    def handle_conflict(self, local_path, remote_path, local_modified, remote_modified):
        """
        完整的冲突处理流程
        
        Args:
            local_path: 本地文件路径
            remote_path: 远程文件路径
            local_modified: 本地修改时间
            remote_modified: 远程修改时间
            
        Returns:
            解决结果字典
        """
        logger.warning(f"检测到冲突: {local_path}")
        
        # 检测冲突
        if not self.detect_conflict(local_modified, remote_modified):
            # 无冲突，使用时间戳判断
            if local_modified > remote_modified:
                return {'action': 'keep_local', 'conflict': False}
            else:
                return {'action': 'keep_remote', 'conflict': False}
        
        # 解决冲突
        result = self.resolve_conflict(
            local_path, remote_path,
            local_modified, remote_modified
        )
        result['conflict'] = True
        
        return result

