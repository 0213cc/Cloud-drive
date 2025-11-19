"""
断点续传会话模型
"""
import json
from sqlalchemy import Column, Integer, String, BigInteger, DateTime, Text, Enum as SQLAlchemyEnum
from sqlalchemy.types import TypeDecorator
from datetime import datetime
from enum import Enum
from .database import Base

class UploadStatus(Enum):
    """上传状态枚举"""
    PENDING = "pending"      # 待处理
    UPLOADING = "uploading"  # 上传中
    COMPLETED = "completed"  # 已完成
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消

class JSONEncodedList(TypeDecorator):
    """将Python列表编码为JSON字符串以便存入数据库"""
    impl = Text

    def process_bind_param(self, value, dialect):
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return json.loads(value)
        return None

class UploadSession(Base):
    """
    上传会话表 - 用于跟踪大文件的断点续传状态
    """
    __tablename__ = "upload_sessions"

    id = Column(Integer, primary_key=True, index=True)
    upload_id = Column(String(128), unique=True, nullable=False, index=True)  # 唯一的会话ID

    # 关联用户和文件信息
    user_id = Column(Integer, nullable=False, index=True)
    file_hash = Column(String(64), nullable=False, index=True)  # 完整文件的哈希值
    filename = Column(String(255), nullable=False)
    path = Column(String(500), nullable=False)

    # 文件和分块元数据
    total_size = Column(BigInteger, nullable=False)
    chunk_size = Column(Integer, nullable=False)
    total_chunks = Column(Integer, nullable=False)

    # 上传进度
    uploaded_chunks = Column(JSONEncodedList, default=lambda: [])  # 已上传的块索引列表
    status = Column(SQLAlchemyEnum(UploadStatus), default=UploadStatus.PENDING, nullable=False)

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # 会话过期时间

    def __repr__(self):
        return f"<UploadSession(upload_id='{self.upload_id}', status='{self.status.value}')>"

