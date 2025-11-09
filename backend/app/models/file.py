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
    
    def __repr__(self):
        return f"<File(path='{self.path}', filename='{self.filename}')>"

