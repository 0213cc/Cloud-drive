"""
文件块模型 - 用于文件级去重
"""
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Boolean
from datetime import datetime
from .database import Base


class FileChunk(Base):
    """
    文件块表 - 存储实际的文件内容引用
    
    多个用户的文件如果内容相同（哈希值相同），会共享同一个FileChunk记录
    实现文件级去重，节省存储空间
    """
    __tablename__ = "file_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 文件内容标识
    hash_value = Column(String(64), unique=True, nullable=False, index=True)  # SHA-256哈希值
    
    # 文件信息
    size = Column(BigInteger, nullable=False)  # 原始文件大小
    
    # 压缩信息
    is_compressed = Column(Boolean, default=False)  # 是否压缩存储
    compressed_size = Column(BigInteger)  # 压缩后大小
    compression_ratio = Column(Integer)  # 压缩率（百分比）
    
    # S3存储信息
    s3_key = Column(String(500), nullable=False, unique=True)  # S3对象键
    s3_etag = Column(String(100))  # S3 ETag
    stored_content_type = Column(String(100))  # 存储时的content_type（如果压缩则为application/gzip）
    
    # 引用计数
    reference_count = Column(Integer, default=1, nullable=False)  # 有多少个文件引用此chunk
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)  # 最后访问时间
    
    def __repr__(self):
        return f"<FileChunk(hash='{self.hash_value[:16]}...', refs={self.reference_count})>"

