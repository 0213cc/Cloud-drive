"""
文件分块服务

支持多种分块策略：
1. 固定大小分块（Fixed-size chunking）
2. 内容定义分块（Content-defined chunking，基于Rabin fingerprint）
"""
import hashlib
import io
from typing import List, Dict, BinaryIO, Tuple
import logging

logger = logging.getLogger(__name__)


class ChunkInfo:
    """数据块信息"""
    def __init__(self, data: bytes, offset: int, index: int):
        self.data = data
        self.offset = offset  # 在文件中的偏移量
        self.index = index  # 块序号
        self.size = len(data)
        self.hash_value = hashlib.sha256(data).hexdigest()
    
    def __repr__(self):
        return f"<ChunkInfo(index={self.index}, offset={self.offset}, size={self.size}, hash={self.hash_value[:16]}...)>"


class ChunkingService:
    """文件分块服务"""
    
    # 默认块大小：4MB
    DEFAULT_CHUNK_SIZE = 4 * 1024 * 1024
    
    # 最小块大小：1MB
    MIN_CHUNK_SIZE = 1 * 1024 * 1024
    
    # 最大块大小：16MB
    MAX_CHUNK_SIZE = 16 * 1024 * 1024
    
    # 内容定义分块的参数
    RABIN_WINDOW_SIZE = 48  # Rabin fingerprint窗口大小
    RABIN_POLYNOMIAL = 0x3DA3358B4DC173  # Rabin多项式
    
    @staticmethod
    def should_use_chunking(file_size: int, chunk_size: int = None) -> bool:
        """
        判断是否应该使用块级去重
        
        对于小文件（小于2倍块大小），使用文件级去重更高效
        对于大文件，使用块级去重可以提高去重效率
        
        Args:
            file_size: 文件大小（字节）
            chunk_size: 块大小（字节）
        
        Returns:
            是否应该使用块级去重
        """
        if chunk_size is None:
            chunk_size = ChunkingService.DEFAULT_CHUNK_SIZE
        
        # 文件大小超过2倍块大小时，使用块级去重
        return file_size > (chunk_size * 2)
    
    @staticmethod
    def chunk_file_fixed(
        file_obj: BinaryIO,
        chunk_size: int = None
    ) -> List[ChunkInfo]:
        """
        固定大小分块
        
        将文件分割成固定大小的数据块
        最后一个块可能小于chunk_size
        
        Args:
            file_obj: 文件对象（二进制读取模式）
            chunk_size: 块大小（字节），默认4MB
        
        Returns:
            数据块列表
        """
        if chunk_size is None:
            chunk_size = ChunkingService.DEFAULT_CHUNK_SIZE
        
        # 验证块大小
        if chunk_size < ChunkingService.MIN_CHUNK_SIZE:
            logger.warning(f"块大小 {chunk_size} 小于最小值，使用最小值 {ChunkingService.MIN_CHUNK_SIZE}")
            chunk_size = ChunkingService.MIN_CHUNK_SIZE
        elif chunk_size > ChunkingService.MAX_CHUNK_SIZE:
            logger.warning(f"块大小 {chunk_size} 大于最大值，使用最大值 {ChunkingService.MAX_CHUNK_SIZE}")
            chunk_size = ChunkingService.MAX_CHUNK_SIZE
        
        chunks = []
        offset = 0
        index = 0
        
        # 确保从文件开头读取
        file_obj.seek(0)
        
        while True:
            data = file_obj.read(chunk_size)
            if not data:
                break
            
            chunk = ChunkInfo(data, offset, index)
            chunks.append(chunk)
            
            offset += len(data)
            index += 1
        
        logger.info(f"固定大小分块完成: 总块数={len(chunks)}, 块大小={chunk_size / 1024 / 1024:.2f}MB")
        return chunks
    
    @staticmethod
    def chunk_file_rabin(
        file_obj: BinaryIO,
        target_chunk_size: int = None,
        min_chunk_size: int = None,
        max_chunk_size: int = None
    ) -> List[ChunkInfo]:
        """
        基于Rabin fingerprint的内容定义分块（CDC）
        
        根据文件内容特征动态确定分块边界
        相比固定大小分块，CDC对文件修改更鲁棒
        
        Args:
            file_obj: 文件对象（二进制读取模式）
            target_chunk_size: 目标块大小（字节），默认4MB
            min_chunk_size: 最小块大小（字节），默认1MB
            max_chunk_size: 最大块大小（字节），默认16MB
        
        Returns:
            数据块列表
        """
        if target_chunk_size is None:
            target_chunk_size = ChunkingService.DEFAULT_CHUNK_SIZE
        if min_chunk_size is None:
            min_chunk_size = ChunkingService.MIN_CHUNK_SIZE
        if max_chunk_size is None:
            max_chunk_size = ChunkingService.MAX_CHUNK_SIZE
        
        chunks = []
        offset = 0
        index = 0
        
        # 确保从文件开头读取
        file_obj.seek(0)
        
        # 读取整个文件到内存（对于大文件可以优化为流式处理）
        file_data = file_obj.read()
        file_size = len(file_data)
        
        if file_size == 0:
            return chunks
        
        # 计算分块掩码（用于判断分块边界）
        # 目标块大小越大，掩码中1的位数越多
        mask_bits = (target_chunk_size // 1024).bit_length()
        mask = (1 << mask_bits) - 1
        
        current_pos = 0
        chunk_start = 0
        
        # Rabin fingerprint计算
        window = bytearray(ChunkingService.RABIN_WINDOW_SIZE)
        fingerprint = 0
        
        while current_pos < file_size:
            # 更新滑动窗口
            if current_pos < ChunkingService.RABIN_WINDOW_SIZE:
                window[current_pos] = file_data[current_pos]
            else:
                window = window[1:] + bytes([file_data[current_pos]])
            
            # 计算Rabin fingerprint（简化版本）
            fingerprint = (fingerprint << 1) ^ file_data[current_pos]
            
            current_pos += 1
            chunk_size = current_pos - chunk_start
            
            # 判断是否应该分块
            should_split = False
            
            # 条件1：达到最大块大小，强制分块
            if chunk_size >= max_chunk_size:
                should_split = True
            # 条件2：超过最小块大小，且fingerprint匹配分块模式
            elif chunk_size >= min_chunk_size and (fingerprint & mask) == 0:
                should_split = True
            # 条件3：到达文件末尾
            elif current_pos >= file_size:
                should_split = True
            
            if should_split:
                # 创建数据块
                chunk_data = file_data[chunk_start:current_pos]
                chunk = ChunkInfo(chunk_data, chunk_start, index)
                chunks.append(chunk)
                
                # 重置
                chunk_start = current_pos
                index += 1
                fingerprint = 0
        
        logger.info(
            f"Rabin分块完成: 总块数={len(chunks)}, "
            f"平均块大小={file_size / len(chunks) / 1024 / 1024:.2f}MB"
        )
        return chunks
    
    @staticmethod
    def chunk_file(
        file_obj: BinaryIO,
        algorithm: str = "fixed",
        chunk_size: int = None,
        **kwargs
    ) -> List[ChunkInfo]:
        """
        分块文件（统一接口）
        
        Args:
            file_obj: 文件对象（二进制读取模式）
            algorithm: 分块算法，可选值：
                - "fixed": 固定大小分块
                - "rabin": Rabin fingerprint分块
                - "content_defined": 内容定义分块（同rabin）
            chunk_size: 块大小（字节）
            **kwargs: 其他参数
        
        Returns:
            数据块列表
        """
        if algorithm == "fixed":
            return ChunkingService.chunk_file_fixed(file_obj, chunk_size)
        elif algorithm in ["rabin", "content_defined"]:
            return ChunkingService.chunk_file_rabin(
                file_obj,
                target_chunk_size=chunk_size,
                min_chunk_size=kwargs.get('min_chunk_size'),
                max_chunk_size=kwargs.get('max_chunk_size')
            )
        else:
            logger.warning(f"未知的分块算法: {algorithm}，使用固定大小分块")
            return ChunkingService.chunk_file_fixed(file_obj, chunk_size)
    
    @staticmethod
    def calculate_deduplication_stats(chunks: List[ChunkInfo]) -> Dict:
        """
        计算去重统计信息
        
        Args:
            chunks: 数据块列表
        
        Returns:
            统计信息字典
        """
        if not chunks:
            return {
                "total_blocks": 0,
                "unique_blocks": 0,
                "total_size": 0,
                "unique_size": 0,
                "deduplication_ratio": 0
            }
        
        # 统计唯一块
        unique_hashes = set()
        unique_size = 0
        total_size = 0
        
        for chunk in chunks:
            total_size += chunk.size
            if chunk.hash_value not in unique_hashes:
                unique_hashes.add(chunk.hash_value)
                unique_size += chunk.size
        
        dedup_ratio = 0
        if total_size > 0:
            dedup_ratio = int((1 - unique_size / total_size) * 100)
        
        return {
            "total_blocks": len(chunks),
            "unique_blocks": len(unique_hashes),
            "total_size": total_size,
            "unique_size": unique_size,
            "deduplication_ratio": dedup_ratio
        }

