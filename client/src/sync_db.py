"""
同步状态数据库 - 记录文件同步状态
"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import os

Base = declarative_base()


class SyncFile(Base):
    """同步文件记录"""
    __tablename__ = 'sync_files'
    
    id = Column(Integer, primary_key=True)
    local_path = Column(String(500), unique=True, nullable=False, index=True)
    remote_path = Column(String(500), nullable=False)
    remote_id = Column(Integer)  # 服务器端文件ID
    
    # 状态
    status = Column(String(20), default='synced')  # synced, pending, uploading, error
    
    # 时间戳
    local_modified = Column(DateTime)
    remote_modified = Column(DateTime)
    last_sync = Column(DateTime, default=datetime.utcnow)
    
    # 文件信息
    size = Column(Integer)
    hash_value = Column(String(64))  # SHA-256
    
    # 标记
    is_directory = Column(Boolean, default=False)
    deleted = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncDatabase:
    """同步数据库管理"""
    
    def __init__(self, db_path='sync.db'):
        """初始化数据库"""
        self.db_path = db_path
        self.engine = create_engine(f'sqlite:///{db_path}')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def get_session(self):
        """获取数据库会话"""
        return self.Session()
    
    def add_file(self, local_path, remote_path, remote_id=None, 
                 local_modified=None, size=0, hash_value='', is_directory=False):
        """添加或更新文件记录"""
        session = self.get_session()
        try:
            # 查找是否存在
            record = session.query(SyncFile).filter_by(local_path=local_path).first()
            
            if record:
                # 更新
                record.remote_path = remote_path
                record.remote_id = remote_id
                record.local_modified = local_modified
                record.size = size
                record.hash_value = hash_value
                record.status = 'synced'
                record.last_sync = datetime.utcnow()
                record.deleted = False
            else:
                # 新建
                record = SyncFile(
                    local_path=local_path,
                    remote_path=remote_path,
                    remote_id=remote_id,
                    local_modified=local_modified,
                    size=size,
                    hash_value=hash_value,
                    is_directory=is_directory,
                    status='synced'
                )
                session.add(record)
            
            session.commit()
            return record
        finally:
            session.close()
    
    def get_file(self, local_path):
        """获取文件记录"""
        session = self.get_session()
        try:
            return session.query(SyncFile).filter_by(local_path=local_path).first()
        finally:
            session.close()
    
    def mark_deleted(self, local_path):
        """标记文件已删除"""
        session = self.get_session()
        try:
            record = session.query(SyncFile).filter_by(local_path=local_path).first()
            if record:
                record.deleted = True
                record.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()
    
    def get_all_files(self, include_deleted=False):
        """获取所有文件记录"""
        session = self.get_session()
        try:
            query = session.query(SyncFile)
            if not include_deleted:
                query = query.filter_by(deleted=False)
            return query.all()
        finally:
            session.close()
    
    def update_status(self, local_path, status):
        """更新文件状态"""
        session = self.get_session()
        try:
            record = session.query(SyncFile).filter_by(local_path=local_path).first()
            if record:
                record.status = status
                record.updated_at = datetime.utcnow()
                session.commit()
        finally:
            session.close()
    
    def delete_record(self, local_path):
        """删除记录"""
        session = self.get_session()
        try:
            record = session.query(SyncFile).filter_by(local_path=local_path).first()
            if record:
                session.delete(record)
                session.commit()
        finally:
            session.close()
    
    def clear_all(self):
        """清空所有记录（调试用）"""
        session = self.get_session()
        try:
            session.query(SyncFile).delete()
            session.commit()
        finally:
            session.close()

