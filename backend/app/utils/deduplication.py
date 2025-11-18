"""
文件去重服务模块
实现基于哈希值的文件级去重
"""
import logging
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.file_chunk import FileChunk

logger = logging.getLogger(__name__)


class DeduplicationService:
    """文件去重服务类"""
    
    @staticmethod
    def check_duplicate(
        db: Session,
        hash_value: str
    ) -> Optional[FileChunk]:
        """
        检查文件是否已存在（基于哈希值）
        
        Args:
            db: 数据库会话
            hash_value: 文件的SHA-256哈希值
            
        Returns:
            如果文件已存在，返回对应的FileChunk对象；否则返回None
        """
        chunk = db.query(FileChunk).filter(
            FileChunk.hash_value == hash_value
        ).first()
        
        if chunk:
            logger.info(f"发现重复文件: hash={hash_value[:16]}..., refs={chunk.reference_count}")
        
        return chunk
    
    @staticmethod
    def create_chunk(
        db: Session,
        hash_value: str,
        size: int,
        s3_key: str,
        s3_etag: Optional[str] = None,
        is_compressed: bool = False,
        compressed_size: Optional[int] = None,
        compression_ratio: Optional[int] = None,
        stored_content_type: Optional[str] = None
    ) -> FileChunk:
        """
        创建新的文件块记录
        
        Args:
            db: 数据库会话
            hash_value: 文件哈希值
            size: 原始文件大小
            s3_key: S3存储键
            s3_etag: S3 ETag
            is_compressed: 是否压缩
            compressed_size: 压缩后大小
            compression_ratio: 压缩率
            stored_content_type: 存储的内容类型
            
        Returns:
            创建的FileChunk对象
        """
        chunk = FileChunk(
            hash_value=hash_value,
            size=size,
            s3_key=s3_key,
            s3_etag=s3_etag,
            is_compressed=is_compressed,
            compressed_size=compressed_size,
            compression_ratio=compression_ratio,
            stored_content_type=stored_content_type,
            reference_count=1
        )
        
        db.add(chunk)
        db.flush()  # 获取ID但不提交
        
        logger.info(
            f"创建新文件块: chunk_id={chunk.id}, "
            f"hash={hash_value[:16]}..., "
            f"size={size / 1024 / 1024:.2f} MB"
        )
        
        return chunk
    
    @staticmethod
    def increment_reference(
        db: Session,
        chunk: FileChunk
    ) -> None:
        """
        增加文件块的引用计数
        
        Args:
            db: 数据库会话
            chunk: 文件块对象
        """
        chunk.reference_count += 1
        chunk.last_accessed_at = datetime.utcnow()
        
        logger.info(
            f"增加引用计数: chunk_id={chunk.id}, "
            f"hash={chunk.hash_value[:16]}..., "
            f"refs={chunk.reference_count}"
        )
    
    @staticmethod
    def decrement_reference(
        db: Session,
        chunk_id: int,
        storage_service=None
    ) -> Tuple[bool, Optional[str]]:
        """
        减少文件块的引用计数
        如果引用计数降为0，删除文件块和S3对象
        
        Args:
            db: 数据库会话
            chunk_id: 文件块ID
            storage_service: S3存储服务（可选）
            
        Returns:
            (是否删除了文件块, S3键)
        """
        chunk = db.query(FileChunk).filter(FileChunk.id == chunk_id).first()
        
        if not chunk:
            logger.warning(f"文件块不存在: chunk_id={chunk_id}")
            return False, None
        
        chunk.reference_count -= 1
        
        logger.info(
            f"减少引用计数: chunk_id={chunk.id}, "
            f"hash={chunk.hash_value[:16]}..., "
            f"refs={chunk.reference_count}"
        )
        
        # 如果引用计数降为0，删除文件块
        if chunk.reference_count <= 0:
            s3_key = chunk.s3_key
            
            # 从数据库删除
            db.delete(chunk)
            
            logger.info(
                f"删除文件块: chunk_id={chunk.id}, "
                f"hash={chunk.hash_value[:16]}..., "
                f"s3_key={s3_key}"
            )
            
            # 从S3删除（如果提供了storage_service）
            if storage_service:
                try:
                    result = storage_service.delete_file(s3_key)
                    if result.get('success'):
                        logger.info(f"从S3删除文件: {s3_key}")
                    else:
                        logger.warning(f"从S3删除文件失败: {s3_key}, {result.get('error')}")
                except Exception as e:
                    logger.error(f"从S3删除文件异常: {s3_key}, {e}")
            
            return True, s3_key
        
        return False, None
    
    @staticmethod
    def get_deduplication_stats(db: Session) -> Dict:
        """
        获取去重统计信息
        
        Args:
            db: 数据库会话
            
        Returns:
            统计信息字典
        """
        from app.models.file import File
        
        # 总文件块数
        total_chunks = db.query(FileChunk).count()
        
        # 总文件记录数（不包括目录）
        total_files = db.query(File).filter(
            File.is_directory == False,
            File.chunk_id.isnot(None)
        ).count()
        
        # 被去重的文件块数（引用次数>1）
        deduplicated_chunks = db.query(FileChunk).filter(
            FileChunk.reference_count > 1
        ).count()
        
        # 去重的文件副本数
        from sqlalchemy import func
        result = db.query(
            func.sum(FileChunk.reference_count - 1)
        ).filter(
            FileChunk.reference_count > 1
        ).scalar()
        duplicate_count = result or 0
        
        # 平均引用次数
        avg_refs = db.query(
            func.avg(FileChunk.reference_count)
        ).scalar() or 0
        
        # 计算节省的存储空间
        # 获取所有被去重的文件块的总大小
        result = db.query(
            func.sum(FileChunk.size * (FileChunk.reference_count - 1))
        ).filter(
            FileChunk.reference_count > 1
        ).scalar()
        saved_space = result or 0
        
        # 实际存储的总大小
        result = db.query(
            func.sum(
                func.coalesce(FileChunk.compressed_size, FileChunk.size)
            )
        ).scalar()
        actual_storage = result or 0
        
        # 如果没有去重，需要的存储空间
        result = db.query(
            func.sum(File.size)
        ).filter(
            File.is_directory == False,
            File.chunk_id.isnot(None)
        ).scalar()
        total_size_without_dedup = result or 0
        
        # 去重率
        dedup_ratio = 0
        if total_size_without_dedup > 0:
            dedup_ratio = (saved_space / total_size_without_dedup) * 100
        
        return {
            'total_chunks': total_chunks,
            'total_files': total_files,
            'deduplicated_chunks': deduplicated_chunks,
            'duplicate_count': int(duplicate_count),
            'average_references': float(avg_refs),
            'saved_space_bytes': int(saved_space),
            'saved_space_mb': saved_space / 1024 / 1024,
            'actual_storage_bytes': int(actual_storage),
            'actual_storage_mb': actual_storage / 1024 / 1024,
            'total_size_without_dedup_bytes': int(total_size_without_dedup),
            'total_size_without_dedup_mb': total_size_without_dedup / 1024 / 1024,
            'deduplication_ratio': dedup_ratio
        }
    
    @staticmethod
    def update_chunk_access_time(
        db: Session,
        chunk_id: int
    ) -> None:
        """
        更新文件块的最后访问时间
        
        Args:
            db: 数据库会话
            chunk_id: 文件块ID
        """
        chunk = db.query(FileChunk).filter(FileChunk.id == chunk_id).first()
        if chunk:
            chunk.last_accessed_at = datetime.utcnow()

