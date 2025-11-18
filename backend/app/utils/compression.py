"""
数据压缩工具模块
支持GZIP压缩和解压，用于网络流量优化
"""
import gzip
import io
import os
import logging
from typing import BinaryIO, Dict, Optional

logger = logging.getLogger(__name__)


class CompressionService:
    """压缩服务类"""
    
    # 压缩级别 (1-9, 9为最高压缩率但最慢)
    DEFAULT_COMPRESSION_LEVEL = 6
    
    # 小于此大小的文件不压缩（避免压缩开销大于收益）
    MIN_COMPRESS_SIZE = 1024  # 1KB
    
    # 这些文件类型通常已经压缩过，不需要再压缩
    SKIP_COMPRESS_TYPES = {
        'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp',
        'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
        'audio/mpeg', 'audio/mp4', 'audio/wav',
        'application/zip', 'application/x-zip-compressed',
        'application/x-rar-compressed', 'application/x-7z-compressed',
        'application/gzip', 'application/x-gzip'
    }
    
    @staticmethod
    def should_compress(file_size: int, content_type: Optional[str] = None) -> bool:
        """
        判断文件是否应该压缩
        
        Args:
            file_size: 文件大小（字节）
            content_type: 文件MIME类型
            
        Returns:
            是否应该压缩
        """
        # 文件太小，不值得压缩
        if file_size < CompressionService.MIN_COMPRESS_SIZE:
            return False
        
        # 已经是压缩格式，不需要再压缩
        if content_type and content_type.lower() in CompressionService.SKIP_COMPRESS_TYPES:
            return False
        
        return True
    
    @staticmethod
    def compress_file(
        input_file: BinaryIO,
        output_file: BinaryIO,
        compression_level: int = DEFAULT_COMPRESSION_LEVEL
    ) -> Dict:
        """
        压缩文件
        
        Args:
            input_file: 输入文件对象
            output_file: 输出文件对象
            compression_level: 压缩级别 (1-9)
            
        Returns:
            压缩结果字典，包含原始大小、压缩后大小、压缩率等信息
        """
        try:
            input_file.seek(0)
            original_size = 0
            
            # 使用GZIP压缩
            with gzip.GzipFile(fileobj=output_file, mode='wb', compresslevel=compression_level) as gz:
                chunk_size = 8192
                while True:
                    chunk = input_file.read(chunk_size)
                    if not chunk:
                        break
                    gz.write(chunk)
                    original_size += len(chunk)
            
            # 获取压缩后大小
            output_file.seek(0, 2)  # 移动到文件末尾
            compressed_size = output_file.tell()
            output_file.seek(0)  # 重置到开始
            
            # 计算压缩率
            compression_ratio = (1 - compressed_size / original_size) * 100 if original_size > 0 else 0
            
            logger.info(
                f"压缩完成: {original_size / 1024 / 1024:.2f} MB -> "
                f"{compressed_size / 1024 / 1024:.2f} MB "
                f"(压缩率: {compression_ratio:.1f}%)"
            )
            
            return {
                'success': True,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'compression_level': compression_level
            }
            
        except Exception as e:
            logger.error(f"压缩失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def decompress_file(
        input_file: BinaryIO,
        output_file: BinaryIO
    ) -> Dict:
        """
        解压文件
        
        Args:
            input_file: 压缩的输入文件对象
            output_file: 解压后的输出文件对象
            
        Returns:
            解压结果字典
        """
        try:
            input_file.seek(0)
            compressed_size = 0
            decompressed_size = 0
            
            # 使用GZIP解压
            with gzip.GzipFile(fileobj=input_file, mode='rb') as gz:
                chunk_size = 8192
                while True:
                    chunk = gz.read(chunk_size)
                    if not chunk:
                        break
                    output_file.write(chunk)
                    decompressed_size += len(chunk)
            
            # 获取压缩文件大小
            input_file.seek(0, 2)
            compressed_size = input_file.tell()
            input_file.seek(0)
            
            output_file.seek(0)  # 重置到开始
            
            logger.info(
                f"解压完成: {compressed_size / 1024 / 1024:.2f} MB -> "
                f"{decompressed_size / 1024 / 1024:.2f} MB"
            )
            
            return {
                'success': True,
                'compressed_size': compressed_size,
                'decompressed_size': decompressed_size
            }
            
        except Exception as e:
            logger.error(f"解压失败: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    @staticmethod
    def compress_data(data: bytes, compression_level: int = DEFAULT_COMPRESSION_LEVEL) -> bytes:
        """
        压缩字节数据
        
        Args:
            data: 原始字节数据
            compression_level: 压缩级别
            
        Returns:
            压缩后的字节数据
        """
        return gzip.compress(data, compresslevel=compression_level)
    
    @staticmethod
    def decompress_data(data: bytes) -> bytes:
        """
        解压字节数据
        
        Args:
            data: 压缩的字节数据
            
        Returns:
            解压后的字节数据
        """
        return gzip.decompress(data)

