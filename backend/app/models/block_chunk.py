"""
块级去重模型 - 用于块级数据去重

与文件级去重(FileChunk)的区别：
- FileChunk: 整个文件作为一个单位进行去重
- BlockChunk: 将文件分割成多个块，每个块独立去重
"""
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Boolean, ForeignKey, Index
from datetime import datetime
from .database import Base


class BlockChunk(Base):
    """
    数据块表 - 存储文件的数据块
    
    大文件会被分割成多个固定或可变大小的数据块
    每个数据块通过哈希值进行去重
    多个文件可以共享相同的数据块
    """
    __tablename__ = "block_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 数据块标识
    hash_value = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256哈希值
    
    # 数据块信息
    size = Column(BigInteger, nullable=False)  # 数据块大小（字节）
    
    # 压缩信息
    is_compressed = Column(Boolean, default=False)  # 是否压缩存储
    compressed_size = Column(BigInteger)  # 压缩后大小
    compression_ratio = Column(Integer)  # 压缩率（百分比）
    
    # S3存储信息
    s3_key = Column(String(500), nullable=False, unique=True)  # S3对象键
    s3_etag = Column(String(100))  # S3 ETag
    stored_content_type = Column(String(100))  # 存储时的content_type
    
    # 引用计数
    reference_count = Column(Integer, default=1, nullable=False)  # 有多少个文件块引用此数据块
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)  # 最后访问时间
    
    def __repr__(self):
        return f"<BlockChunk(hash='{self.hash_value[:16]}...', size={self.size}, refs={self.reference_count})>"


class FileBlockMap(Base):
    """
    文件-数据块映射表
    
    记录文件由哪些数据块组成，以及数据块的顺序
    支持块级去重：多个文件可以共享相同的数据块
    """
    __tablename__ = "file_block_maps"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联的文件块（FileChunk）
    file_chunk_id = Column(Integer, ForeignKey("file_chunks.id"), nullable=False, index=True)
    
    # 关联的数据块（BlockChunk）
    block_chunk_id = Column(Integer, ForeignKey("block_chunks.id"), nullable=False, index=True)
    
    # 数据块在文件中的位置
    block_index = Column(Integer, nullable=False)  # 数据块序号（从0开始）
    block_offset = Column(BigInteger, nullable=False)  # 数据块在文件中的偏移量（字节）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<FileBlockMap(file_chunk={self.file_chunk_id}, block={self.block_chunk_id}, index={self.block_index})>"
    
    # 创建复合索引以提高查询性能
    __table_args__ = (
        Index('idx_file_chunk_block_index', 'file_chunk_id', 'block_index'),
    )


class FileBlockMetadata(Base):
    """
    文件块元数据表
    
    扩展FileChunk表，添加块级去重相关的元数据
    记录文件的分块策略和块组成信息
    """
    __tablename__ = "file_block_metadata"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 关联的文件块
    file_chunk_id = Column(Integer, ForeignKey("file_chunks.id"), unique=True, nullable=False, index=True)
    
    # 分块策略
    chunking_algorithm = Column(String(50), nullable=False)  # 分块算法：fixed, rabin, content_defined
    chunk_size = Column(Integer, nullable=False)  # 目标块大小（字节）
    
    # 块统计信息
    total_blocks = Column(Integer, nullable=False)  # 总块数
    unique_blocks = Column(Integer, nullable=False)  # 唯一块数（去重后）
    deduplication_ratio = Column(Integer)  # 去重率（百分比）
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<FileBlockMetadata(file_chunk={self.file_chunk_id}, blocks={self.total_blocks}, unique={self.unique_blocks})>"

