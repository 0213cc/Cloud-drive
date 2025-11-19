"""
块级去重服务

管理数据块的创建、查询和引用计数
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List, Dict
from datetime import datetime
import logging

from app.models.block_chunk import BlockChunk, FileBlockMap, FileBlockMetadata
from app.models.file_chunk import FileChunk

logger = logging.getLogger(__name__)


class BlockDeduplicationService:
    """块级去重服务"""
    
    @staticmethod
    def check_block_duplicate(db: Session, hash_value: str) -> Optional[BlockChunk]:
        """
        检查数据块是否已存在
        
        Args:
            db: 数据库会话
            hash_value: 数据块哈希值
        
        Returns:
            如果存在返回BlockChunk对象，否则返回None
        """
        return db.query(BlockChunk).filter(
            BlockChunk.hash_value == hash_value
        ).first()
    
    @staticmethod
    def create_block_chunk(
        db: Session,
        hash_value: str,
        size: int,
        s3_key: str,
        s3_etag: str = None,
        is_compressed: bool = False,
        compressed_size: int = None,
        compression_ratio: int = None,
        stored_content_type: str = None
    ) -> BlockChunk:
        """
        创建新的数据块记录
        
        Args:
            db: 数据库会话
            hash_value: 数据块哈希值
            size: 数据块大小（字节）
            s3_key: S3对象键
            s3_etag: S3 ETag
            is_compressed: 是否压缩
            compressed_size: 压缩后大小
            compression_ratio: 压缩率
            stored_content_type: 存储的内容类型
        
        Returns:
            创建的BlockChunk对象
        """
        block_chunk = BlockChunk(
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
        
        db.add(block_chunk)
        db.commit()
        db.refresh(block_chunk)
        
        logger.info(
            f"创建数据块: block_id={block_chunk.id}, "
            f"hash={hash_value[:16]}..., size={size}, "
            f"compressed={is_compressed}"
        )
        
        return block_chunk
    
    @staticmethod
    def increment_block_reference(db: Session, block_chunk: BlockChunk) -> None:
        """
        增加数据块引用计数
        
        Args:
            db: 数据库会话
            block_chunk: 数据块对象
        """
        block_chunk.reference_count += 1
        block_chunk.last_accessed_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            f"增加数据块引用: block_id={block_chunk.id}, "
            f"hash={block_chunk.hash_value[:16]}..., "
            f"refs={block_chunk.reference_count}"
        )
    
    @staticmethod
    def decrement_block_reference(
        db: Session,
        block_chunk_id: int,
        storage_service = None
    ) -> bool:
        """
        减少数据块引用计数
        
        当引用计数降为0时，删除数据块记录和S3对象
        
        Args:
            db: 数据库会话
            block_chunk_id: 数据块ID
            storage_service: 存储服务（用于删除S3对象）
        
        Returns:
            是否删除了数据块
        """
        block_chunk = db.query(BlockChunk).filter(
            BlockChunk.id == block_chunk_id
        ).first()
        
        if not block_chunk:
            logger.warning(f"数据块不存在: block_id={block_chunk_id}")
            return False
        
        block_chunk.reference_count -= 1
        
        if block_chunk.reference_count <= 0:
            # 删除S3对象
            if storage_service:
                try:
                    storage_service.delete_file(block_chunk.s3_key)
                    logger.info(f"删除S3对象: {block_chunk.s3_key}")
                except Exception as e:
                    logger.error(f"删除S3对象失败: {block_chunk.s3_key}, error={e}")
            
            # 删除数据库记录
            db.delete(block_chunk)
            db.commit()
            
            logger.info(
                f"删除数据块: block_id={block_chunk.id}, "
                f"hash={block_chunk.hash_value[:16]}..."
            )
            return True
        else:
            db.commit()
            logger.info(
                f"减少数据块引用: block_id={block_chunk.id}, "
                f"hash={block_chunk.hash_value[:16]}..., "
                f"refs={block_chunk.reference_count}"
            )
            return False
    
    @staticmethod
    def create_file_block_map(
        db: Session,
        file_chunk_id: int,
        block_chunk_id: int,
        block_index: int,
        block_offset: int
    ) -> FileBlockMap:
        """
        创建文件-数据块映射
        
        Args:
            db: 数据库会话
            file_chunk_id: 文件块ID
            block_chunk_id: 数据块ID
            block_index: 数据块序号
            block_offset: 数据块偏移量
        
        Returns:
            创建的FileBlockMap对象
        """
        file_block_map = FileBlockMap(
            file_chunk_id=file_chunk_id,
            block_chunk_id=block_chunk_id,
            block_index=block_index,
            block_offset=block_offset
        )
        
        db.add(file_block_map)
        db.commit()
        db.refresh(file_block_map)
        
        return file_block_map
    
    @staticmethod
    def get_file_blocks(
        db: Session,
        file_chunk_id: int
    ) -> List[Dict]:
        """
        获取文件的所有数据块（按顺序）
        
        Args:
            db: 数据库会话
            file_chunk_id: 文件块ID
        
        Returns:
            数据块信息列表
        """
        maps = db.query(FileBlockMap, BlockChunk).join(
            BlockChunk,
            FileBlockMap.block_chunk_id == BlockChunk.id
        ).filter(
            FileBlockMap.file_chunk_id == file_chunk_id
        ).order_by(
            FileBlockMap.block_index
        ).all()
        
        blocks = []
        for map_obj, block_chunk in maps:
            blocks.append({
                "block_index": map_obj.block_index,
                "block_offset": map_obj.block_offset,
                "block_chunk_id": block_chunk.id,
                "hash_value": block_chunk.hash_value,
                "size": block_chunk.size,
                "s3_key": block_chunk.s3_key,
                "is_compressed": block_chunk.is_compressed,
                "compressed_size": block_chunk.compressed_size
            })
        
        return blocks
    
    @staticmethod
    def create_file_block_metadata(
        db: Session,
        file_chunk_id: int,
        chunking_algorithm: str,
        chunk_size: int,
        total_blocks: int,
        unique_blocks: int,
        deduplication_ratio: int = None
    ) -> FileBlockMetadata:
        """
        创建文件块元数据
        
        Args:
            db: 数据库会话
            file_chunk_id: 文件块ID
            chunking_algorithm: 分块算法
            chunk_size: 块大小
            total_blocks: 总块数
            unique_blocks: 唯一块数
            deduplication_ratio: 去重率
        
        Returns:
            创建的FileBlockMetadata对象
        """
        metadata = FileBlockMetadata(
            file_chunk_id=file_chunk_id,
            chunking_algorithm=chunking_algorithm,
            chunk_size=chunk_size,
            total_blocks=total_blocks,
            unique_blocks=unique_blocks,
            deduplication_ratio=deduplication_ratio
        )
        
        db.add(metadata)
        db.commit()
        db.refresh(metadata)
        
        logger.info(
            f"创建文件块元数据: file_chunk_id={file_chunk_id}, "
            f"algorithm={chunking_algorithm}, blocks={total_blocks}, "
            f"unique={unique_blocks}, dedup_ratio={deduplication_ratio}%"
        )
        
        return metadata
    
    @staticmethod
    def get_file_block_metadata(
        db: Session,
        file_chunk_id: int
    ) -> Optional[FileBlockMetadata]:
        """
        获取文件块元数据
        
        Args:
            db: 数据库会话
            file_chunk_id: 文件块ID
        
        Returns:
            FileBlockMetadata对象或None
        """
        return db.query(FileBlockMetadata).filter(
            FileBlockMetadata.file_chunk_id == file_chunk_id
        ).first()
    
    @staticmethod
    def delete_file_blocks(
        db: Session,
        file_chunk_id: int,
        storage_service = None
    ) -> int:
        """
        删除文件的所有数据块映射，并减少数据块引用计数
        
        Args:
            db: 数据库会话
            file_chunk_id: 文件块ID
            storage_service: 存储服务
        
        Returns:
            删除的映射数量
        """
        # 获取所有映射
        maps = db.query(FileBlockMap).filter(
            FileBlockMap.file_chunk_id == file_chunk_id
        ).all()
        
        deleted_count = 0
        
        for map_obj in maps:
            # 减少数据块引用计数
            BlockDeduplicationService.decrement_block_reference(
                db, map_obj.block_chunk_id, storage_service
            )
            
            # 删除映射
            db.delete(map_obj)
            deleted_count += 1
        
        # 删除元数据
        metadata = db.query(FileBlockMetadata).filter(
            FileBlockMetadata.file_chunk_id == file_chunk_id
        ).first()
        
        if metadata:
            db.delete(metadata)
        
        db.commit()
        
        logger.info(
            f"删除文件块映射: file_chunk_id={file_chunk_id}, "
            f"deleted_maps={deleted_count}"
        )
        
        return deleted_count
    
    @staticmethod
    def get_deduplication_stats(db: Session) -> Dict:
        """
        获取块级去重统计信息
        
        Args:
            db: 数据库会话
        
        Returns:
            统计信息字典
        """
        # 统计数据块
        total_blocks = db.query(BlockChunk).count()
        total_size = db.query(func.sum(BlockChunk.size)).scalar() or 0
        total_compressed_size = db.query(
            func.sum(BlockChunk.compressed_size)
        ).filter(
            BlockChunk.is_compressed == True
        ).scalar() or 0
        
        # 统计引用
        total_references = db.query(
            func.sum(BlockChunk.reference_count)
        ).scalar() or 0
        
        # 计算节省的空间
        saved_space = total_size * (total_references - total_blocks) if total_blocks > 0 else 0
        
        # 计算去重率
        dedup_ratio = 0
        if total_references > 0:
            dedup_ratio = int((1 - total_blocks / total_references) * 100)
        
        return {
            "total_blocks": total_blocks,
            "total_references": total_references,
            "total_size_bytes": total_size,
            "total_size_mb": total_size / 1024 / 1024,
            "saved_space_bytes": saved_space,
            "saved_space_mb": saved_space / 1024 / 1024,
            "deduplication_ratio": dedup_ratio,
            "compressed_blocks": db.query(BlockChunk).filter(
                BlockChunk.is_compressed == True
            ).count(),
            "total_compressed_size_mb": total_compressed_size / 1024 / 1024
        }

