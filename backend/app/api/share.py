"""
文件共享API
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime
import secrets

from app.models.database import get_db
from app.models.file import File as FileModel
from app.models.share import Share, SharePermission, ShareLog
from app.models.user import User
from app.utils.jwt_handler import get_current_user_id
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/share", tags=["share"])


# Pydantic模型
class CreateShareRequest(BaseModel):
    """创建共享请求"""
    file_id: int
    shared_with_username: str
    permission: SharePermission
    expires_at: Optional[datetime] = None


class UpdateShareRequest(BaseModel):
    """更新共享请求"""
    permission: Optional[SharePermission] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class ShareInfo(BaseModel):
    """共享信息"""
    id: int
    owner_id: int
    owner_username: str
    shared_with_user_id: int
    shared_with_username: str
    file_id: int
    file_path: str
    filename: str
    permission: SharePermission
    share_token: Optional[str]
    is_active: bool
    expires_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    is_expired: bool
    is_valid: bool
    
    class Config:
        from_attributes = True


class ShareListResponse(BaseModel):
    """共享列表响应"""
    shares: List[ShareInfo]
    total: int


class ShareResponse(BaseModel):
    """共享操作响应"""
    success: bool
    message: str
    share_info: Optional[ShareInfo] = None


class ShareLogInfo(BaseModel):
    """共享日志信息"""
    id: int
    share_id: int
    user_id: int
    username: str
    action: str
    details: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


def check_file_access(db: Session, file_id: int, user_id: int, required_permission: SharePermission = SharePermission.READ) -> tuple[FileModel, Optional[Share]]:
    """
    检查用户是否有权限访问文件
    返回: (文件对象, 共享对象或None)
    """
    # 1. 检查是否是文件所有者
    db_file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if db_file.user_id == user_id:
        return db_file, None
    
    # 2. 检查是否有共享权限
    share = db.query(Share).filter(
        Share.file_id == file_id,
        Share.shared_with_user_id == user_id,
        Share.is_active == True
    ).first()
    
    if not share or not share.is_valid():
        raise HTTPException(status_code=403, detail="无权访问此文件")
    
    # 3. 检查权限级别
    if required_permission == SharePermission.WRITE and share.permission != SharePermission.WRITE:
        raise HTTPException(status_code=403, detail="无写入权限")
    
    return db_file, share


@router.post("/create", response_model=ShareResponse)
async def create_share(
    request: CreateShareRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    创建文件/文件夹共享
    
    - 只有文件所有者可以创建共享
    - 可以设置权限（只读/可写）
    - 可以设置过期时间
    """
    # 1. 验证文件是否存在且属于当前用户
    db_file = db.query(FileModel).filter(
        FileModel.id == request.file_id,
        FileModel.user_id == user_id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在或无权分享")
    
    # 2. 查找要分享给的用户
    target_user = db.query(User).filter(User.username == request.shared_with_username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail=f"用户 '{request.shared_with_username}' 不存在")
    
    # 3. 不能分享给自己
    if target_user.id == user_id:
        raise HTTPException(status_code=400, detail="不能分享给自己")
    
    # 4. 检查是否已经存在共享
    existing_share = db.query(Share).filter(
        Share.owner_id == user_id,
        Share.shared_with_user_id == target_user.id,
        Share.file_id == request.file_id
    ).first()
    
    if existing_share:
        raise HTTPException(status_code=400, detail="已经分享给该用户")
    
    # 5. 创建共享
    share_token = secrets.token_urlsafe(32)
    
    new_share = Share(
        owner_id=user_id,
        shared_with_user_id=target_user.id,
        file_id=request.file_id,
        permission=request.permission,
        share_token=share_token,
        expires_at=request.expires_at,
        is_active=True
    )
    
    db.add(new_share)
    db.commit()
    db.refresh(new_share)
    
    # 6. 记录日志
    log = ShareLog(
        share_id=new_share.id,
        user_id=user_id,
        action="create",
        details=f"分享给 {request.shared_with_username}，权限: {request.permission.value}"
    )
    db.add(log)
    db.commit()
    
    # 7. 构造响应
    owner = db.query(User).filter(User.id == user_id).first()
    share_info = ShareInfo(
        id=new_share.id,
        owner_id=new_share.owner_id,
        owner_username=owner.username,
        shared_with_user_id=new_share.shared_with_user_id,
        shared_with_username=target_user.username,
        file_id=new_share.file_id,
        file_path=db_file.path,
        filename=db_file.filename,
        permission=new_share.permission,
        share_token=new_share.share_token,
        is_active=new_share.is_active,
        expires_at=new_share.expires_at,
        created_at=new_share.created_at,
        updated_at=new_share.updated_at,
        is_expired=new_share.is_expired(),
        is_valid=new_share.is_valid()
    )
    
    return ShareResponse(
        success=True,
        message="共享创建成功",
        share_info=share_info
    )


@router.get("/my-shares", response_model=ShareListResponse)
async def list_my_shares(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    列出我创建的所有共享
    """
    shares = db.query(Share).filter(Share.owner_id == user_id).all()
    
    share_infos = []
    for share in shares:
        owner = db.query(User).filter(User.id == share.owner_id).first()
        target_user = db.query(User).filter(User.id == share.shared_with_user_id).first()
        db_file = db.query(FileModel).filter(FileModel.id == share.file_id).first()
        
        if owner and target_user and db_file:
            share_infos.append(ShareInfo(
                id=share.id,
                owner_id=share.owner_id,
                owner_username=owner.username,
                shared_with_user_id=share.shared_with_user_id,
                shared_with_username=target_user.username,
                file_id=share.file_id,
                file_path=db_file.path,
                filename=db_file.filename,
                permission=share.permission,
                share_token=share.share_token,
                is_active=share.is_active,
                expires_at=share.expires_at,
                created_at=share.created_at,
                updated_at=share.updated_at,
                is_expired=share.is_expired(),
                is_valid=share.is_valid()
            ))
    
    return ShareListResponse(
        shares=share_infos,
        total=len(share_infos)
    )


@router.get("/shared-with-me", response_model=ShareListResponse)
async def list_shared_with_me(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    列出分享给我的所有文件
    """
    shares = db.query(Share).filter(
        Share.shared_with_user_id == user_id,
        Share.is_active == True
    ).all()
    
    share_infos = []
    for share in shares:
        if not share.is_valid():
            continue
            
        owner = db.query(User).filter(User.id == share.owner_id).first()
        target_user = db.query(User).filter(User.id == share.shared_with_user_id).first()
        db_file = db.query(FileModel).filter(FileModel.id == share.file_id).first()
        
        if owner and target_user and db_file:
            share_infos.append(ShareInfo(
                id=share.id,
                owner_id=share.owner_id,
                owner_username=owner.username,
                shared_with_user_id=share.shared_with_user_id,
                shared_with_username=target_user.username,
                file_id=share.file_id,
                file_path=db_file.path,
                filename=db_file.filename,
                permission=share.permission,
                share_token=share.share_token,
                is_active=share.is_active,
                expires_at=share.expires_at,
                created_at=share.created_at,
                updated_at=share.updated_at,
                is_expired=share.is_expired(),
                is_valid=share.is_valid()
            ))
    
    return ShareListResponse(
        shares=share_infos,
        total=len(share_infos)
    )


@router.get("/info/{share_id}", response_model=ShareInfo)
async def get_share_info(
    share_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取共享详情
    
    - 只有共享的所有者或接收者可以查看
    """
    share = db.query(Share).filter(Share.id == share_id).first()
    
    if not share:
        raise HTTPException(status_code=404, detail="共享不存在")
    
    # 验证权限
    if share.owner_id != user_id and share.shared_with_user_id != user_id:
        raise HTTPException(status_code=403, detail="无权查看此共享")
    
    owner = db.query(User).filter(User.id == share.owner_id).first()
    target_user = db.query(User).filter(User.id == share.shared_with_user_id).first()
    db_file = db.query(FileModel).filter(FileModel.id == share.file_id).first()
    
    if not owner or not target_user or not db_file:
        raise HTTPException(status_code=404, detail="共享数据不完整")
    
    return ShareInfo(
        id=share.id,
        owner_id=share.owner_id,
        owner_username=owner.username,
        shared_with_user_id=share.shared_with_user_id,
        shared_with_username=target_user.username,
        file_id=share.file_id,
        file_path=db_file.path,
        filename=db_file.filename,
        permission=share.permission,
        share_token=share.share_token,
        is_active=share.is_active,
        expires_at=share.expires_at,
        created_at=share.created_at,
        updated_at=share.updated_at,
        is_expired=share.is_expired(),
        is_valid=share.is_valid()
    )


@router.put("/update/{share_id}", response_model=ShareResponse)
async def update_share(
    share_id: int,
    request: UpdateShareRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    更新共享设置
    
    - 只有共享的所有者可以更新
    - 可以修改权限、启用状态、过期时间
    """
    share = db.query(Share).filter(
        Share.id == share_id,
        Share.owner_id == user_id
    ).first()
    
    if not share:
        raise HTTPException(status_code=404, detail="共享不存在或无权修改")
    
    # 更新字段
    if request.permission is not None:
        share.permission = request.permission
    if request.is_active is not None:
        share.is_active = request.is_active
    if request.expires_at is not None:
        share.expires_at = request.expires_at
    
    share.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(share)
    
    # 记录日志
    log = ShareLog(
        share_id=share.id,
        user_id=user_id,
        action="update",
        details=f"更新共享设置"
    )
    db.add(log)
    db.commit()
    
    # 构造响应
    owner = db.query(User).filter(User.id == share.owner_id).first()
    target_user = db.query(User).filter(User.id == share.shared_with_user_id).first()
    db_file = db.query(FileModel).filter(FileModel.id == share.file_id).first()
    
    share_info = ShareInfo(
        id=share.id,
        owner_id=share.owner_id,
        owner_username=owner.username,
        shared_with_user_id=share.shared_with_user_id,
        shared_with_username=target_user.username,
        file_id=share.file_id,
        file_path=db_file.path,
        filename=db_file.filename,
        permission=share.permission,
        share_token=share.share_token,
        is_active=share.is_active,
        expires_at=share.expires_at,
        created_at=share.created_at,
        updated_at=share.updated_at,
        is_expired=share.is_expired(),
        is_valid=share.is_valid()
    )
    
    return ShareResponse(
        success=True,
        message="共享更新成功",
        share_info=share_info
    )


@router.delete("/delete/{share_id}", response_model=ShareResponse)
async def delete_share(
    share_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    删除共享
    
    - 只有共享的所有者可以删除
    """
    share = db.query(Share).filter(
        Share.id == share_id,
        Share.owner_id == user_id
    ).first()
    
    if not share:
        raise HTTPException(status_code=404, detail="共享不存在或无权删除")
    
    # 记录日志
    log = ShareLog(
        share_id=share.id,
        user_id=user_id,
        action="delete",
        details=f"删除共享"
    )
    db.add(log)
    
    # 删除共享
    db.delete(share)
    db.commit()
    
    return ShareResponse(
        success=True,
        message="共享删除成功"
    )


@router.get("/logs/{share_id}", response_model=List[ShareLogInfo])
async def get_share_logs(
    share_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取共享操作日志
    
    - 只有共享的所有者可以查看日志
    """
    share = db.query(Share).filter(
        Share.id == share_id,
        Share.owner_id == user_id
    ).first()
    
    if not share:
        raise HTTPException(status_code=404, detail="共享不存在或无权查看")
    
    logs = db.query(ShareLog).filter(ShareLog.share_id == share_id).order_by(ShareLog.created_at.desc()).all()
    
    log_infos = []
    for log in logs:
        user = db.query(User).filter(User.id == log.user_id).first()
        if user:
            log_infos.append(ShareLogInfo(
                id=log.id,
                share_id=log.share_id,
                user_id=log.user_id,
                username=user.username,
                action=log.action,
                details=log.details,
                created_at=log.created_at
            ))
    
    return log_infos

