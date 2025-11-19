"""
文件操作API
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
import os
import tempfile
import shutil
import logging
from datetime import datetime

from app.services.storage import S3StorageService
from app.models.database import get_db
from app.models.file import File as FileModel, FileHistory
from app.models.file_chunk import FileChunk
from app.models.share import Share, SharePermission, ShareLog
from app.models.user import User
from app.utils.jwt_handler import get_current_user_id
from app.utils.compression import CompressionService
from app.utils.deduplication import DeduplicationService
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


# Pydantic模型
class FileInfo(BaseModel):
    """文件信息"""
    id: int
    path: str
    filename: str
    size: int
    content_type: Optional[str]
    hash_value: Optional[str]
    is_directory: bool
    is_compressed: Optional[bool] = False
    compressed_size: Optional[int] = None
    compression_ratio: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    version: int
    
    class Config:
        from_attributes = True


class FileListResponse(BaseModel):
    """文件列表响应"""
    files: List[FileInfo]
    total: int


class UploadResponse(BaseModel):
    """上传响应"""
    success: bool
    message: str
    file_info: Optional[FileInfo] = None


class DeleteResponse(BaseModel):
    """删除响应"""
    success: bool
    message: str

class FileHistoryInfo(BaseModel):
    """文件历史信息"""
    version: int
    size: int
    hash_value: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class RevertResponse(BaseModel):
    """回滚响应"""
    success: bool
    message: str
    file_info: FileInfo

# 依赖注入
def get_storage_service():
    """获取存储服务"""
    return S3StorageService()


def check_file_access(db: Session, file_id: int, user_id: int, required_permission: SharePermission = SharePermission.READ) -> tuple:
    """
    检查用户是否有权限访问文件
    返回: (文件对象, 共享对象或None)
    """
    # 1. 检查文件是否存在
    db_file = db.query(FileModel).filter(FileModel.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    # 2. 检查是否是文件所有者
    if db_file.user_id == user_id:
        return db_file, None
    
    # 3. 检查是否有共享权限
    share = db.query(Share).filter(
        Share.file_id == file_id,
        Share.shared_with_user_id == user_id,
        Share.is_active == True
    ).first()
    
    if not share or not share.is_valid():
        raise HTTPException(status_code=403, detail="无权访问此文件")
    
    # 4. 检查权限级别
    if required_permission == SharePermission.WRITE and share.permission != SharePermission.WRITE:
        raise HTTPException(status_code=403, detail="无写入权限")
    
    return db_file, share


def log_share_action(db: Session, share_id: int, user_id: int, action: str, details: str = None):
    """记录共享操作日志"""
    if share_id:
        log = ShareLog(
            share_id=share_id,
            user_id=user_id,
            action=action,
            details=details
        )
        db.add(log)
        db.commit()


# 用户认证通过JWT实现（已在jwt_handler.py中定义）


@router.post("/update/{file_id}", response_model=UploadResponse)
async def update_file(
    file_id: int,
    file: UploadFile = File(...),
    base_version: Optional[int] = Query(None, description="The file version the update is based on for conflict detection"),
    enable_compression: bool = Query(True, description="是否启用压缩"),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    Update a file's content (uploads a new version).
    - Supports updates by the file owner.
    - Supports updates by shared users with 'write' permission.
    - Handles conflicts by creating a new file if base_version does not match the current version.
    - Supports compression to save storage and bandwidth.
    """
    # 1. Check for file existence and write permission for the user
    existing_file, share = check_file_access(db, file_id, user_id, required_permission=SharePermission.WRITE)
    
    # 2. Conflict Detection
    is_conflict = base_version is not None and base_version != existing_file.version

    temp_file_path = None
    compressed_file_path = None
    
    try:
        # 3. Save the uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
        
        original_size = os.path.getsize(temp_file_path)
        with open(temp_file_path, 'rb') as f:
            hash_value = storage.calculate_file_hash(f)

        # 4. 判断是否需要压缩
        should_compress = (
            enable_compression and 
            CompressionService.should_compress(original_size, file.content_type)
        )
        
        logger.info(
            f"压缩检查: enable_compression={enable_compression}, "
            f"file_size={original_size / 1024 / 1024:.2f} MB, "
            f"content_type={file.content_type}, "
            f"should_compress={should_compress}"
        )
        
        is_compressed = False
        compressed_size = original_size
        compression_ratio = 0
        upload_file_path = temp_file_path
        
        if should_compress:
            compressed_file_path = tempfile.mktemp(suffix='.gz')
            
            with open(temp_file_path, 'rb') as input_f, open(compressed_file_path, 'wb') as output_f:
                compress_result = CompressionService.compress_file(input_f, output_f)
                
                if compress_result['success']:
                    is_compressed = True
                    compressed_size = compress_result['compressed_size']
                    compression_ratio = int(compress_result['compression_ratio'])
                    upload_file_path = compressed_file_path

        # 5. Upload to S3
        timestamp = int(datetime.utcnow().timestamp())
        unique_filename = f"{timestamp}_{file.filename}"
        if is_compressed:
            unique_filename += ".gz"
        
        owner_id = existing_file.user_id
        clean_path = os.path.dirname(existing_file.path).strip('/')
        s3_key = f"users/{owner_id}/{clean_path}/{unique_filename}" if clean_path else f"users/{owner_id}/{unique_filename}"

        upload_size = compressed_size if is_compressed else original_size
        with open(upload_file_path, 'rb') as f:
            result = storage.upload_file(
                f, s3_key, upload_size, 
                'application/gzip' if is_compressed else file.content_type
            )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"Upload to S3 failed: {result.get('error')}")

        # 6. 创建或获取文件块（去重）
        chunk = DeduplicationService.check_duplicate(db, hash_value)
        
        if chunk:
            # 文件块已存在，增加引用计数
            DeduplicationService.increment_reference(db, chunk)
            logger.info(
                f"使用已存在的文件块: chunk_id={chunk.id}, "
                f"hash={hash_value[:16]}..., refs={chunk.reference_count}"
            )
        else:
            # 创建新的文件块
            chunk = DeduplicationService.create_chunk(
                db=db,
                hash_value=hash_value,
                size=original_size,
                s3_key=s3_key,
                s3_etag=result.get('etag'),
                is_compressed=is_compressed,
                compressed_size=compressed_size if is_compressed else None,
                compression_ratio=compression_ratio if is_compressed else None,
                stored_content_type='application/gzip' if is_compressed else file.content_type
            )

        # 7. Handle based on conflict status
        if is_conflict:
            # CONFLICT: Create a new file entry for the conflicted copy
            user = db.query(User).filter(User.id == user_id).first()
            username = user.username if user else "unknown_user"
            name, ext = os.path.splitext(existing_file.filename)
            conflict_filename = f"{name} (conflicted copy from {username} on {datetime.now().strftime('%Y-%m-%d')}){ext}"
            conflict_full_path = os.path.join(os.path.dirname(existing_file.path), conflict_filename)

            new_db_file = FileModel(
                user_id=owner_id,
                path=conflict_full_path,
                filename=conflict_filename,
                size=original_size,
                content_type=file.content_type,
                hash_value=hash_value,
                chunk_id=chunk.id,
                s3_key=s3_key,
                s3_etag=result.get('etag'),
                is_compressed=is_compressed,
                compressed_size=compressed_size if is_compressed else None,
                compression_ratio=compression_ratio if is_compressed else None,
                is_directory=False,
                version=1
            )
            db.add(new_db_file)
            db.commit()
            db.refresh(new_db_file)
            
            message = f"Conflict detected. Your version was saved as '{conflict_filename}'."
            final_file_info = new_db_file
        else:
            # NO CONFLICT: Update the existing file
            old_chunk_id = existing_file.chunk_id
            
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                chunk_id=old_chunk_id,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag,
                is_compressed=existing_file.is_compressed,
                compressed_size=existing_file.compressed_size
            )
            db.add(file_history)
            
            # 如果旧版本有chunk_id，减少其引用计数
            if old_chunk_id and old_chunk_id != chunk.id:
                DeduplicationService.decrement_reference(db, old_chunk_id, storage)
            
            existing_file.size = original_size
            existing_file.content_type = file.content_type
            existing_file.hash_value = hash_value
            existing_file.chunk_id = chunk.id
            existing_file.s3_key = s3_key
            existing_file.s3_etag = result.get('etag')
            existing_file.is_compressed = is_compressed
            existing_file.compressed_size = compressed_size if is_compressed else None
            existing_file.compression_ratio = compression_ratio if is_compressed else None
            existing_file.version += 1
            existing_file.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_file)

            if share:
                log_share_action(db, share.id, user_id, "upload", f"uploaded new version: {file.filename}")
            
            message = "File updated successfully."
            if is_compressed:
                message += f" (compressed, saved {compression_ratio}% space)"
            final_file_info = existing_file

        return UploadResponse(
            success=True,
            message=message,
            file_info=FileInfo.from_orm(final_file_info)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if compressed_file_path and os.path.exists(compressed_file_path):
            os.remove(compressed_file_path)


@router.post("/upload-by-reference", response_model=UploadResponse)
async def upload_file_by_reference(
    filename: str = Query(..., description="文件名"),
    path: str = Query("/", description="上传路径（目录）"),
    chunk_id: int = Query(..., description="已存在的文件块ID"),
    size: int = Query(..., description="文件大小"),
    hash_value: str = Query(..., description="文件哈希值"),
    content_type: Optional[str] = Query(None, description="文件类型"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    通过引用已存在的文件块创建文件（去重上传）
    
    当客户端检测到文件已存在时，调用此接口直接创建文件记录，
    无需重复上传文件内容，节省带宽和存储空间。
    
    Args:
        filename: 文件名
        path: 上传路径
        chunk_id: 已存在的文件块ID
        size: 文件大小
        hash_value: 文件哈希值
        content_type: 文件类型
        
    Returns:
        上传结果
    """
    try:
        # 1. 验证文件块是否存在
        chunk = db.query(FileChunk).filter(FileChunk.id == chunk_id).first()
        if not chunk:
            raise HTTPException(status_code=404, detail="文件块不存在")
        
        # 2. 验证哈希值是否匹配
        if chunk.hash_value != hash_value:
            raise HTTPException(status_code=400, detail="文件哈希值不匹配")
        
        # 3. 构建完整路径
        clean_path = path.strip('/').strip()
        if clean_path:
            full_path = f"/{clean_path}/{filename}"
        else:
            full_path = f"/{filename}"
        
        # 4. 检查文件是否已存在
        existing_file = db.query(FileModel).filter(
            FileModel.user_id == user_id,
            FileModel.path == full_path,
            FileModel.is_directory == False
        ).first()
        
        if existing_file:
            # 文件已存在，保存旧版本到历史记录
            old_chunk_id = existing_file.chunk_id
            
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                chunk_id=old_chunk_id,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag,
                is_compressed=existing_file.is_compressed,
                compressed_size=existing_file.compressed_size
            )
            db.add(file_history)
            
            # 如果旧版本有chunk_id，减少其引用计数
            if old_chunk_id:
                DeduplicationService.decrement_reference(db, old_chunk_id, None)
            
            # 更新现有文件记录
            existing_file.size = size
            existing_file.content_type = content_type
            existing_file.hash_value = hash_value
            existing_file.chunk_id = chunk_id
            existing_file.s3_key = chunk.s3_key
            existing_file.s3_etag = chunk.s3_etag
            existing_file.is_compressed = chunk.is_compressed
            existing_file.compressed_size = chunk.compressed_size
            existing_file.compression_ratio = chunk.compression_ratio
            existing_file.version += 1
            existing_file.updated_at = datetime.utcnow()
            
            # 增加新chunk的引用计数
            DeduplicationService.increment_reference(db, chunk)
            
            db.commit()
            db.refresh(existing_file)
            db_file = existing_file
            
            message = f"文件已更新（版本 {db_file.version}，通过去重）"
        else:
            # 新文件，直接创建引用
            db_file = FileModel(
                user_id=user_id,
                path=full_path,
                filename=filename,
                size=size,
                content_type=content_type,
                hash_value=hash_value,
                chunk_id=chunk_id,
                s3_key=chunk.s3_key,
                s3_etag=chunk.s3_etag,
                is_compressed=chunk.is_compressed,
                compressed_size=chunk.compressed_size,
                compression_ratio=chunk.compression_ratio,
                is_directory=False,
                version=1
            )
            db.add(db_file)
            
            # 增加chunk的引用计数
            DeduplicationService.increment_reference(db, chunk)
            
            db.commit()
            db.refresh(db_file)
            
            message = "文件上传成功（通过去重，无需传输数据）"
        
        logger.info(
            f"用户 {user_id} 通过去重创建文件: {full_path}, "
            f"chunk_id={chunk_id}, refs={chunk.reference_count}"
        )
        
        if chunk.is_compressed:
            message += f"（已压缩，节省 {chunk.compression_ratio}% 空间）"
        
        return UploadResponse(
            success=True,
            message=message,
            file_info=FileInfo.from_orm(db_file)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"通过引用上传文件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    path: str = Query("/", description="上传路径（目录）"),
    enable_compression: bool = Query(True, description="是否启用压缩"),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    上传文件
    
    - 支持多线程上传大文件
    - 自动计算文件哈希
    - 支持自动压缩（GZIP）以节省存储空间和网络流量
    - 支持文件级去重（通过chunk_id）
    
    建议流程：
    1. 客户端先计算文件哈希
    2. 调用 /api/deduplication/check 检查文件是否已存在
    3. 如果存在，调用 /api/files/upload-by-reference 创建引用
    4. 如果不存在，调用此接口上传文件
    """
    temp_file_path = None
    compressed_file_path = None
    
    try:
        # 1. 保存临时文件
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
        
        # 2. 获取原始文件大小
        original_size = os.path.getsize(temp_file_path)
        
        # 3. 计算原始文件哈希值
        with open(temp_file_path, 'rb') as f:
            hash_value = storage.calculate_file_hash(f)
        
        # 4. 判断是否需要压缩
        should_compress = (
            enable_compression and 
            CompressionService.should_compress(original_size, file.content_type)
        )
        
        is_compressed = False
        compressed_size = original_size
        compression_ratio = 0
        upload_file_path = temp_file_path
        
        if should_compress:
            # 压缩文件
            compressed_file_path = tempfile.mktemp(suffix='.gz')
            
            with open(temp_file_path, 'rb') as input_f, open(compressed_file_path, 'wb') as output_f:
                compress_result = CompressionService.compress_file(input_f, output_f)
                
                if compress_result['success']:
                    is_compressed = True
                    compressed_size = compress_result['compressed_size']
                    compression_ratio = int(compress_result['compression_ratio'])
                    upload_file_path = compressed_file_path
                    
                    logger.info(
                        f"文件已压缩: {file.filename}, "
                        f"原始: {original_size / 1024 / 1024:.2f} MB, "
                        f"压缩后: {compressed_size / 1024 / 1024:.2f} MB, "
                        f"压缩率: {compression_ratio}%"
                    )
                else:
                    logger.warning(f"压缩失败，使用原始文件: {compress_result.get('error')}")
        
        # 5. 生成唯一的S3键
        timestamp = int(datetime.utcnow().timestamp())
        unique_filename = f"{timestamp}_{file.filename}"
        if is_compressed:
            unique_filename += ".gz"
        
        clean_path = path.strip('/').strip()
        
        if clean_path:
            s3_key = f"users/{user_id}/{clean_path}/{unique_filename}"
            full_path = f"/{clean_path}/{file.filename}"
        else:
            s3_key = f"users/{user_id}/{unique_filename}"
            full_path = f"/{file.filename}"
        
        # 6. 上传到S3（上传压缩后的文件或原始文件）
        upload_size = compressed_size if is_compressed else original_size
        
        with open(upload_file_path, 'rb') as f:
            result = storage.upload_file(
                f, 
                s3_key, 
                upload_size,
                'application/gzip' if is_compressed else file.content_type
            )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"上传失败: {result.get('error')}")
        
        # 7. 创建或获取文件块（去重）
        chunk = DeduplicationService.check_duplicate(db, hash_value)
        
        if chunk:
            # 文件块已存在，增加引用计数
            DeduplicationService.increment_reference(db, chunk)
            logger.info(
                f"使用已存在的文件块: chunk_id={chunk.id}, "
                f"hash={hash_value[:16]}..., refs={chunk.reference_count}"
            )
        else:
            # 创建新的文件块
            chunk = DeduplicationService.create_chunk(
                db=db,
                hash_value=hash_value,
                size=original_size,
                s3_key=s3_key,
                s3_etag=result.get('etag'),
                is_compressed=is_compressed,
                compressed_size=compressed_size if is_compressed else None,
                compression_ratio=compression_ratio if is_compressed else None,
                stored_content_type='application/gzip' if is_compressed else file.content_type
            )
        
        # 8. 保存元数据到数据库
        existing_file = db.query(FileModel).filter(
            FileModel.user_id == user_id,
            FileModel.path == full_path,
            FileModel.is_directory == False
        ).first()
        
        if existing_file:
            # 文件已存在，保存旧版本到历史记录
            old_chunk_id = existing_file.chunk_id
            
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                chunk_id=old_chunk_id,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag,
                is_compressed=existing_file.is_compressed,
                compressed_size=existing_file.compressed_size
            )
            db.add(file_history)
            
            # 如果旧版本有chunk_id，减少其引用计数
            if old_chunk_id and old_chunk_id != chunk.id:
                DeduplicationService.decrement_reference(db, old_chunk_id, storage)
            
            # 更新现有文件记录
            existing_file.size = original_size
            existing_file.content_type = file.content_type
            existing_file.hash_value = hash_value
            existing_file.chunk_id = chunk.id
            existing_file.s3_key = s3_key
            existing_file.s3_etag = result.get('etag')
            existing_file.is_compressed = is_compressed
            existing_file.compressed_size = compressed_size if is_compressed else None
            existing_file.compression_ratio = compression_ratio if is_compressed else None
            existing_file.version += 1
            existing_file.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_file)
            db_file = existing_file
        else:
            # 新文件
            db_file = FileModel(
                user_id=user_id,
                path=full_path,
                filename=file.filename,
                size=original_size,
                content_type=file.content_type,
                hash_value=hash_value,
                chunk_id=chunk.id,
                s3_key=s3_key,
                s3_etag=result.get('etag'),
                is_compressed=is_compressed,
                compressed_size=compressed_size if is_compressed else None,
                compression_ratio=compression_ratio if is_compressed else None,
                is_directory=False,
                version=1
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
        
        # 8. 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if compressed_file_path and os.path.exists(compressed_file_path):
            os.remove(compressed_file_path)
        
        message = "上传成功"
        if is_compressed:
            message += f"（已压缩，节省 {compression_ratio}% 空间）"
        
        return UploadResponse(
            success=True,
            message=message,
            file_info=FileInfo.from_orm(db_file)
        )
        
    except Exception as e:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        if compressed_file_path and os.path.exists(compressed_file_path):
            os.remove(compressed_file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/download/{file_id}")
async def download_file(
    file_id: int,
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    下载文件
    
    - 支持下载自己的文件
    - 支持下载共享给自己的文件（需要至少有读权限）
    - 自动解压缩文件
    - 支持块级去重文件的组装下载
    """
    from app.utils.block_deduplication import BlockDeduplicationService
    
    # 检查访问权限（支持共享文件）
    db_file, share = check_file_access(db, file_id, user_id, SharePermission.READ)
    
    if db_file.is_directory:
        raise HTTPException(status_code=400, detail="不能下载目录")
    
    compressed_file_path = None
    decompressed_file_path = None
    assembled_file_path = None
    
    try:
        # 检查是否使用块级去重
        metadata = None
        if db_file.chunk_id:
            metadata = BlockDeduplicationService.get_file_block_metadata(db, db_file.chunk_id)
        
        if metadata:
            # 块级去重文件，需要组装
            logger.info(f"下载块级去重文件: {db_file.filename}, blocks={metadata.total_blocks}")
            
            assembled_file_path = tempfile.mktemp(suffix=f"_{db_file.filename}")
            
            # 获取所有数据块
            blocks = BlockDeduplicationService.get_file_blocks(db, db_file.chunk_id)
            
            # 按顺序下载并组装数据块
            with open(assembled_file_path, 'wb') as output_f:
                for block_info in blocks:
                    # 下载数据块
                    block_temp_path = tempfile.mktemp(suffix=".block")
                    
                    result = storage.download_file(block_info['s3_key'], block_temp_path)
                    if not result['success']:
                        raise HTTPException(
                            status_code=500,
                            detail=f"下载数据块失败: {result.get('error')}"
                        )
                    
                    # 如果数据块是压缩的，需要解压
                    if block_info['is_compressed']:
                        decompressed_block_path = tempfile.mktemp(suffix=".block.decompressed")
                        
                        with open(block_temp_path, 'rb') as input_f, open(decompressed_block_path, 'wb') as decomp_f:
                            decompress_result = CompressionService.decompress_file(input_f, decomp_f)
                            
                            if not decompress_result['success']:
                                raise HTTPException(
                                    status_code=500,
                                    detail=f"解压数据块失败: {decompress_result.get('error')}"
                                )
                        
                        # 删除压缩的块文件
                        if os.path.exists(block_temp_path):
                            os.remove(block_temp_path)
                        
                        block_temp_path = decompressed_block_path
                    
                    # 写入组装文件
                    with open(block_temp_path, 'rb') as block_f:
                        output_f.write(block_f.read())
                    
                    # 删除临时块文件
                    if os.path.exists(block_temp_path):
                        os.remove(block_temp_path)
            
            final_file_path = assembled_file_path
            logger.info(f"块级去重文件组装完成: {db_file.filename}")
        else:
            # 常规文件或文件级去重
            # 1. 从S3下载文件（可能是压缩的）
            compressed_file_path = tempfile.mktemp(suffix=".download")
            
            result = storage.download_file(db_file.s3_key, compressed_file_path)
            
            if not result['success']:
                raise HTTPException(status_code=500, detail=f"下载失败: {result.get('error')}")
            
            # 2. 如果文件是压缩的，需要解压
            if db_file.is_compressed:
                decompressed_file_path = tempfile.mktemp(suffix=f"_{db_file.filename}")
                
                with open(compressed_file_path, 'rb') as input_f, open(decompressed_file_path, 'wb') as output_f:
                    decompress_result = CompressionService.decompress_file(input_f, output_f)
                    
                    if not decompress_result['success']:
                        raise HTTPException(status_code=500, detail=f"解压失败: {decompress_result.get('error')}")
                
                # 删除压缩文件，使用解压后的文件
                if os.path.exists(compressed_file_path):
                    os.remove(compressed_file_path)
                
                final_file_path = decompressed_file_path
                logger.info(f"文件已解压: {db_file.filename}")
            else:
                final_file_path = compressed_file_path
        
        # 3. 记录共享文件的下载日志
        if share:
            log_share_action(db, share.id, user_id, "download", f"下载文件: {db_file.filename}")
        
        # 4. 返回文件
        return FileResponse(
            path=final_file_path,
            filename=db_file.filename,
            media_type=db_file.content_type or 'application/octet-stream',
            background=None
        )
        
    except Exception as e:
        # 清理临时文件
        if compressed_file_path and os.path.exists(compressed_file_path):
            os.remove(compressed_file_path)
        if decompressed_file_path and os.path.exists(decompressed_file_path):
            os.remove(decompressed_file_path)
        if assembled_file_path and os.path.exists(assembled_file_path):
            os.remove(assembled_file_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=FileListResponse)
async def list_files(
    path: str = Query("/", description="目录路径"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    列出文件和目录
    """
    clean_path = "/" + path.strip('/').strip()
    
    query = db.query(FileModel).filter(
        FileModel.user_id == user_id
    )
    
    if clean_path != "/":
        query = query.filter(FileModel.path.like(f"{clean_path}%"))
    
    files = query.order_by(FileModel.is_directory.desc(), FileModel.filename).all()
    
    return FileListResponse(
        files=[FileInfo.from_orm(f) for f in files],
        total=len(files)
    )


@router.delete("/delete/{file_id}", response_model=DeleteResponse)
async def delete_file(
    file_id: int,
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    删除文件
    
    - 只有文件所有者可以删除文件
    - 共享用户即使有写权限也不能删除文件
    """
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在或无权删除")
    
    try:
        # S3中的历史版本暂时不删除，可以作为备份
        result = storage.delete_file(db_file.s3_key)
        
        if not result['success']:
            # 即使S3删除失败，也继续删除数据库记录
            pass
        
        # 删除相关的共享记录
        db.query(Share).filter(Share.file_id == file_id).delete()
        
        db.delete(db_file)
        db.commit()
        
        return DeleteResponse(
            success=True,
            message="删除成功"
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/mkdir", response_model=UploadResponse)
async def create_directory(
    path: str = Query(..., description="目录路径"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    创建目录
    """
    clean_path = "/" + path.strip('/').strip()
    
    existing = db.query(FileModel).filter(
        FileModel.user_id == user_id,
        FileModel.path == clean_path,
        FileModel.is_directory == True
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="目录已存在")
    
    dir_name = os.path.basename(clean_path)
    
    db_dir = FileModel(
        user_id=user_id,
        path=clean_path,
        filename=dir_name,
        size=0,
        s3_key=f"users/{user_id}{clean_path}/.keep",
        is_directory=True
    )
    
    db.add(db_dir)
    db.commit()
    db.refresh(db_dir)
    
    return UploadResponse(
        success=True,
        message="目录创建成功",
        file_info=FileInfo.from_orm(db_dir)
    )


@router.get("/info/{file_id}", response_model=FileInfo)
async def get_file_info(
    file_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取文件信息
    
    - 支持查看自己的文件
    - 支持查看共享给自己的文件
    """
    # 检查访问权限（支持共享文件）
    db_file, share = check_file_access(db, file_id, user_id, SharePermission.READ)
    
    # 记录共享文件的访问日志
    if share:
        log_share_action(db, share.id, user_id, "access", f"查看文件信息: {db_file.filename}")
    
    return FileInfo.from_orm(db_file)

@router.get("/history/{file_id}", response_model=List[FileHistoryInfo])
async def get_file_history(
    file_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取文件历史版本
    """
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")

    history = db.query(FileHistory).filter(FileHistory.file_id == file_id).order_by(FileHistory.version.desc()).all()
    
    return [FileHistoryInfo.from_orm(h) for h in history]


@router.post("/revert/{file_id}", response_model=RevertResponse)
async def revert_file_version(
    file_id: int,
    version: int = Query(..., description="要回滚到的版本号"),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    回滚文件到指定版本。此操作与文件去重功能兼容。
    """
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")

    history_version = db.query(FileHistory).filter(
        FileHistory.file_id == file_id,
        FileHistory.version == version
    ).first()
    if not history_version:
        raise HTTPException(status_code=404, detail="历史版本不存在")

    # 获取当前版本和目标历史版本所引用的文件块
    current_chunk_id = db_file.chunk_id
    target_chunk_id = history_version.chunk_id

    try:
        # 1. 将当前版本信息存入历史记录
        current_version_history = FileHistory(
            file_id=db_file.id,
            version=db_file.version,
            size=db_file.size,
            hash_value=db_file.hash_value,
            chunk_id=db_file.chunk_id,
            s3_key=db_file.s3_key, # s3_key and etag are now for metadata purposes
            s3_etag=db_file.s3_etag,
            is_compressed=db_file.is_compressed,
            compressed_size=db_file.compressed_size
        )
        db.add(current_version_history)

        # 2. 更新文件记录以反映历史版本状态
        db_file.size = history_version.size
        db_file.hash_value = history_version.hash_value
        db_file.chunk_id = history_version.chunk_id
        db_file.is_compressed = history_version.is_compressed
        db_file.compressed_size = history_version.compressed_size
        # S3-related info must be restored from the FileChunk, which is the source of truth.
        target_chunk = db.query(FileChunk).filter(FileChunk.id == history_version.chunk_id).first()
        if not target_chunk:
            raise HTTPException(status_code=404, detail=f"Cannot revert: The underlying file chunk for version {version} no longer exists.")

        db_file.s3_key = target_chunk.s3_key
        db_file.s3_etag = target_chunk.s3_etag
        
        db_file.version += 1
        db_file.updated_at = datetime.utcnow()

        # 3. 更新文件块的引用计数
        # 只有当两个版本指向不同的文件块时，才需要调整引用计数
        if current_chunk_id != target_chunk_id:
            # 减少当前版本文件块的引用计数
            if current_chunk_id:
                DeduplicationService.decrement_reference(db, current_chunk_id, storage)
            
            # 增加目标历史版本文件块的引用计数
            if target_chunk_id:
                target_chunk = db.query(FileChunk).filter(FileChunk.id == target_chunk_id).first()
                if target_chunk:
                    DeduplicationService.increment_reference(db, target_chunk)

        # 4. 从历史记录中删除已恢复的版本，因为它现在是当前版本
        db.delete(history_version)
        
        db.commit()
        db.refresh(db_file)

        return RevertResponse(
            success=True,
            message=f"成功回滚到版本 {version}",
            file_info=FileInfo.from_orm(db_file)
        )
    except Exception as e:
        db.rollback()
        logger.error(f"回滚文件失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"回滚操作失败: {str(e)}")
