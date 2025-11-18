"""
文件去重API
提供文件去重相关的接口
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
import logging

from app.models.database import get_db
from app.utils.jwt_handler import get_current_user_id
from app.utils.deduplication import DeduplicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/deduplication", tags=["deduplication"])


class CheckDuplicateRequest(BaseModel):
    """检查重复文件请求"""
    hash_value: str
    size: int


class CheckDuplicateResponse(BaseModel):
    """检查重复文件响应"""
    exists: bool
    chunk_id: Optional[int] = None
    is_compressed: Optional[bool] = None
    compressed_size: Optional[int] = None
    compression_ratio: Optional[int] = None
    s3_key: Optional[str] = None
    reference_count: Optional[int] = None
    message: str


class DeduplicationStatsResponse(BaseModel):
    """去重统计响应"""
    total_chunks: int
    total_files: int
    deduplicated_chunks: int
    duplicate_count: int
    average_references: float
    saved_space_mb: float
    actual_storage_mb: float
    total_size_without_dedup_mb: float
    deduplication_ratio: float


@router.post("/check", response_model=CheckDuplicateResponse)
async def check_duplicate(
    request: CheckDuplicateRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    检查文件是否已存在（基于哈希值）
    
    客户端在上传前调用此接口，如果文件已存在，可以跳过上传直接创建引用
    
    Args:
        request: 包含文件哈希值和大小的请求
        
    Returns:
        文件是否存在及相关信息
    """
    try:
        # 检查是否存在相同哈希的文件块
        chunk = DeduplicationService.check_duplicate(db, request.hash_value)
        
        if chunk:
            # 文件已存在
            logger.info(
                f"用户 {user_id} 查询到重复文件: "
                f"hash={request.hash_value[:16]}..., "
                f"chunk_id={chunk.id}, "
                f"refs={chunk.reference_count}"
            )
            
            return CheckDuplicateResponse(
                exists=True,
                chunk_id=chunk.id,
                is_compressed=chunk.is_compressed,
                compressed_size=chunk.compressed_size,
                compression_ratio=chunk.compression_ratio,
                s3_key=chunk.s3_key,
                reference_count=chunk.reference_count,
                message=f"文件已存在，可以跳过上传（已被引用{chunk.reference_count}次）"
            )
        else:
            # 文件不存在，需要上传
            return CheckDuplicateResponse(
                exists=False,
                message="文件不存在，需要上传"
            )
            
    except Exception as e:
        logger.error(f"检查重复文件失败: {e}")
        raise HTTPException(status_code=500, detail=f"检查失败: {str(e)}")


@router.get("/stats", response_model=DeduplicationStatsResponse)
async def get_deduplication_stats(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取去重统计信息
    
    Returns:
        去重统计数据
    """
    try:
        stats = DeduplicationService.get_deduplication_stats(db)
        
        return DeduplicationStatsResponse(
            total_chunks=stats['total_chunks'],
            total_files=stats['total_files'],
            deduplicated_chunks=stats['deduplicated_chunks'],
            duplicate_count=stats['duplicate_count'],
            average_references=stats['average_references'],
            saved_space_mb=stats['saved_space_mb'],
            actual_storage_mb=stats['actual_storage_mb'],
            total_size_without_dedup_mb=stats['total_size_without_dedup_mb'],
            deduplication_ratio=stats['deduplication_ratio']
        )
        
    except Exception as e:
        logger.error(f"获取去重统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取统计失败: {str(e)}")

