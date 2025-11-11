"""
同步API - 支持客户端同步
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from datetime import datetime

from app.models.database import get_db
from app.models.file import File as FileModel

router = APIRouter(prefix="/api/sync", tags=["sync"])


# 模拟用户认证
def get_current_user_id() -> int:
    """获取当前用户ID（临时mock）"""
    return 1


class FileChangeInfo(BaseModel):
    """文件变更信息"""
    file_id: int
    path: str
    filename: str
    size: int
    hash_value: str
    updated_at: datetime
    action: str  # created, modified, deleted
    
    class Config:
        from_attributes = True


class SyncStatusResponse(BaseModel):
    """同步状态响应"""
    total_files: int
    last_update: datetime
    changes: List[FileChangeInfo]


@router.get("/changes", response_model=SyncStatusResponse)
async def get_changes(
    since: datetime = None,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取服务器端的文件变更
    
    - since: 从哪个时间点开始的变更（可选）
    - 返回自指定时间以来的所有文件变更
    """
    query = db.query(FileModel).filter(
        FileModel.user_id == user_id
    )
    
    if since:
        # 只返回since之后更新的文件
        query = query.filter(FileModel.updated_at > since)
    
    files = query.order_by(FileModel.updated_at.desc()).all()
    
    changes = []
    for file in files:
        changes.append(FileChangeInfo(
            file_id=file.id,
            path=file.path,
            filename=file.filename,
            size=file.size,
            hash_value=file.hash_value or '',
            updated_at=file.updated_at,
            action='modified'  # 简化处理，都标记为modified
        ))
    
    return SyncStatusResponse(
        total_files=len(files),
        last_update=datetime.utcnow(),
        changes=changes
    )


@router.get("/status")
async def get_sync_status(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取同步状态统计
    """
    total_files = db.query(FileModel).filter(
        FileModel.user_id == user_id,
        FileModel.is_directory == False
    ).count()
    
    total_size = db.query(FileModel).filter(
        FileModel.user_id == user_id,
        FileModel.is_directory == False
    ).with_entities(FileModel.size).all()
    
    total_size_bytes = sum(s[0] for s in total_size if s[0])
    
    return {
        'total_files': total_files,
        'total_size': total_size_bytes,
        'total_size_mb': round(total_size_bytes / 1024 / 1024, 2),
        'last_check': datetime.utcnow()
    }


@router.post("/notify")
async def notify_client_update():
    """
    通知客户端有更新（WebSocket可选实现）
    """
    # 简化实现，实际可以用WebSocket推送
    return {'message': 'Notification sent'}

