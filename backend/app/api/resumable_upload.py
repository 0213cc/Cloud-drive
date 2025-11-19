"""
断点续传API

支持大文件的断点续传
"""
from fastapi import APIRouter, HTTPException, Depends, Body
from pydantic import BaseModel
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
import uuid
import logging
from datetime import datetime, timedelta

from app.models.database import get_db
from app.models.upload_session import UploadSession, UploadStatus
from app.utils.jwt_handler import get_current_user_id
from app.api.block_upload import assemble_file as block_assemble_file, AssembleFileRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resumable", tags=["resumable-upload"])


# Pydantic模型
class StartUploadRequest(BaseModel):
    """开始上传请求"""
    filename: str
    path: str
    total_size: int
    file_hash: str
    chunk_size: int
    total_chunks: int


class StartUploadResponse(BaseModel):
    """开始上传响应"""
    upload_id: str
    status: str
    uploaded_chunks: List[int]
    message: str


class UploadStatusResponse(BaseModel):
    """上传状态响应"""
    upload_id: str
    status: str
    uploaded_chunks: List[int]
    total_chunks: int
    is_complete: bool


@router.post("/start", response_model=StartUploadResponse)
async def start_upload_session(
    request: StartUploadRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    开始或恢复一个上传会話

    如果文件哈希已存在，则恢复之前的会话
    否则，创建一个新的上传会话
    """
    # 检查是否已存在相同的上传会话（基于文件哈希）
    session = db.query(UploadSession).filter(
        UploadSession.user_id == user_id,
        UploadSession.file_hash == request.file_hash,
        UploadSession.status.in_([UploadStatus.PENDING, UploadStatus.UPLOADING])
    ).first()

    if session:
        # 恢复现有会话
        session.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(session)

        logger.info(f"恢复上传会话: upload_id={session.upload_id}, user_id={user_id}")
        return StartUploadResponse(
            upload_id=session.upload_id,
            status=session.status.value,
            uploaded_chunks=session.uploaded_chunks or [],
            message="已恢复上传会话"
        )
    else:
        # 创建新会话
        upload_id = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(days=7)  # 会话有效期7天

        new_session = UploadSession(
            upload_id=upload_id,
            user_id=user_id,
            file_hash=request.file_hash,
            filename=request.filename,
            path=request.path,
            total_size=request.total_size,
            chunk_size=request.chunk_size,
            total_chunks=request.total_chunks,
            uploaded_chunks=[],
            status=UploadStatus.PENDING,
            expires_at=expires_at
        )

        db.add(new_session)
        db.commit()
        db.refresh(new_session)

        logger.info(f"创建新上传会话: upload_id={upload_id}, user_id={user_id}")
        return StartUploadResponse(
            upload_id=upload_id,
            status=new_session.status.value,
            uploaded_chunks=[],
            message="已创建新的上传会话"
        )


@router.get("/status/{upload_id}", response_model=UploadStatusResponse)
async def get_upload_status(
    upload_id: str,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    查询上传会话的状态
    """
    session = db.query(UploadSession).filter(
        UploadSession.upload_id == upload_id,
        UploadSession.user_id == user_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="上传会话不存在")

    is_complete = len(session.uploaded_chunks) == session.total_chunks

    return UploadStatusResponse(
        upload_id=session.upload_id,
        status=session.status.value,
        uploaded_chunks=session.uploaded_chunks or [],
        total_chunks=session.total_chunks,
        is_complete=is_complete
    )


@router.post("/complete/{upload_id}")
async def complete_upload_session(
    upload_id: str,
    request: AssembleFileRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    完成上传会话并组装文件

    调用现有的块级上传组装逻辑
    """
    session = db.query(UploadSession).filter(
        UploadSession.upload_id == upload_id,
        UploadSession.user_id == user_id
    ).first()

    if not session:
        raise HTTPException(status_code=404, detail="上传会话不存在")

    if session.status == UploadStatus.COMPLETED:
        return {"success": True, "message": "文件已组装"}

    # 验证请求是否与会话匹配
    if session.file_hash != request.file_hash:
        raise HTTPException(status_code=400, detail="文件哈希不匹配")

    # 调用现有的组装函数
    try:
        result = await block_assemble_file(request, db, user_id)

        # 更新会话状态
        session.status = UploadStatus.COMPLETED
        session.updated_at = datetime.utcnow()
        db.commit()

        logger.info(f"上传会话完成: upload_id={upload_id}")
        return result

    except Exception as e:
        session.status = UploadStatus.FAILED
        db.commit()
        logger.error(f"组装失败: upload_id={upload_id}, error={e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"组装失败: {str(e)}")

