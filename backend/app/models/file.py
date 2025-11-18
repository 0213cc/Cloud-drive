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
    size = Column(BigInteger, nullable=False)  # 原始大小
    content_type = Column(String(100))
    hash_value = Column(String(64), index=True)  # SHA-256
    
    # S3存储信息
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
    
    # S3存储信息
    s3_key = Column(String(500), nullable=False)
    s3_etag = Column(String(100))
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FileHistory(file_id='{self.file_id}', version='{self.version}')>"


class FileChunk(Base):
    """文件块元数据"""
    __tablename__ = "file_chunks"

    id = Column(Integer, primary_key=True, index=True)
    hash_value = Column(String(64), unique=True, nullable=False, index=True)
    size = Column(BigInteger, nullable=False)
    s3_key = Column(String(500), nullable=False, unique=True)
    compression = Column(String(20), default="none")
    ref_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<FileChunk(hash='{self.hash_value}', size='{self.size}')>"


class FileChunkUsage(Base):
    """文件块使用记录"""
    __tablename__ = "file_chunk_usage"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    chunk_id = Column(Integer, ForeignKey("file_chunks.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    size = Column(BigInteger, nullable=False)

    def __repr__(self):
        return f"<FileChunkUsage(file_id='{self.file_id}', chunk_id='{self.chunk_id}', index='{self.chunk_index}')>"
