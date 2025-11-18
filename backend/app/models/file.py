"""
文件模型
"""
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, ForeignKey, Boolean
from datetime import datetime
from .database import Base


class File(Base):
    """文件元数据表"""
    __tablename__ = "files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 文件路径（用户空间内的虚拟路径）
    path = Column(String(500), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    
    # 文件信息
    size = Column(BigInteger, nullable=False)  # 原始大小（未压缩）
    content_type = Column(String(100))
    hash_value = Column(String(64), index=True)  # SHA-256（原始文件的哈希）
    
    # 文件去重 - 指向实际存储的文件块
    chunk_id = Column(Integer, ForeignKey("file_chunks.id"), nullable=True, index=True)
    
    # 压缩信息（从chunk_id引用的FileChunk获取，这里保留用于快速查询）
    is_compressed = Column(Boolean, default=False)  # 是否压缩存储
    compressed_size = Column(BigInteger)  # 压缩后大小
    compression_ratio = Column(Integer)  # 压缩率（百分比）
    
    # S3存储信息（从chunk_id引用的FileChunk获取，这里保留用于快速查询）
    s3_key = Column(String(500), nullable=False)  # S3对象键
    s3_etag = Column(String(100))  # S3 ETag
    
    # 文件类型
    is_directory = Column(Boolean, default=False)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    version = Column(Integer, default=1, nullable=False)
    
    def __repr__(self):
        return f"<File(path='{self.path}', filename='{self.filename}')>"

class FileHistory(Base):
    """文件历史版本表"""
    __tablename__ = "file_history"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    version = Column(Integer, nullable=False)
    
    # 文件信息
    size = Column(BigInteger, nullable=False)
    hash_value = Column(String(64), index=True)
    
    # 文件去重 - 指向实际存储的文件块
    chunk_id = Column(Integer, ForeignKey("file_chunks.id"), nullable=True, index=True)
    
    # 压缩信息
    is_compressed = Column(Boolean, default=False)
    compressed_size = Column(BigInteger)
    
    # S3存储信息
    s3_key = Column(String(500), nullable=False)
    s3_etag = Column(String(100))
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FileHistory(file_id='{self.file_id}', version='{self.version}')>"
