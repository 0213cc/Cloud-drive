"""
共享模型
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Enum as SQLEnum
from datetime import datetime
from enum import Enum
from .database import Base


class SharePermission(str, Enum):
    """共享权限枚举"""
    READ = "read"      # 只读
    WRITE = "write"    # 可写（包含读权限）


class Share(Base):
    """文件/文件夹共享表"""
    __tablename__ = "shares"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # 共享者和接收者
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    shared_with_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 共享的文件或文件夹
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False, index=True)
    
    # 权限
    permission = Column(SQLEnum(SharePermission), nullable=False, default=SharePermission.READ)
    
    # 共享链接（可选，用于通过链接分享）
    share_token = Column(String(64), unique=True, index=True, nullable=True)
    
    # 是否启用
    is_active = Column(Boolean, default=True, nullable=False)
    
    # 过期时间（可选）
    expires_at = Column(DateTime, nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Share(owner_id={self.owner_id}, shared_with={self.shared_with_user_id}, file_id={self.file_id}, permission={self.permission})>"
    
    def is_expired(self) -> bool:
        """检查共享是否已过期"""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at
    
    def is_valid(self) -> bool:
        """检查共享是否有效（未过期且已启用）"""
        return self.is_active and not self.is_expired()


class ShareLog(Base):
    """共享操作日志表"""
    __tablename__ = "share_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    share_id = Column(Integer, ForeignKey("shares.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 操作类型：access（访问）、download（下载）、upload（上传）、delete（删除）
    action = Column(String(50), nullable=False)
    
    # 操作详情
    details = Column(String(500), nullable=True)
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<ShareLog(share_id={self.share_id}, user_id={self.user_id}, action={self.action})>"

