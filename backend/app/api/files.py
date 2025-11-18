"""
文件操作API
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, Request
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, List
from pydantic import BaseModel
import os
import tempfile
import shutil
from datetime import datetime
import gzip

from app.services.storage import S3StorageService
from app.models.database import get_db
from app.models.file import File as FileModel, FileHistory, FileChunk, FileChunkUsage
from app.models.share import Share, SharePermission, ShareLog
from app.models.user import User
from app.utils.jwt_handler import get_current_user_id
from sqlalchemy.orm import Session

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

class HashCheckRequest(BaseModel):
    """去重校验请求"""
    hash_value: str

class HashCheckResponse(BaseModel):
    """去重校验结果"""
    exists: bool
    size: Optional[int] = None
    content_type: Optional[str] = None
    filename: Optional[str] = None

class DedupUploadRequest(BaseModel):
    """去重上传请求"""
    hash_value: str
    path: str = "/"
    filename: str
    content_type: Optional[str] = None

class DedupUpdateRequest(BaseModel):
    """去重更新请求"""
    hash_value: str
    content_type: Optional[str] = None

class ChunkInfo(BaseModel):
    """块信息"""
    hash_value: str
    size: int

class ChunkCheckRequest(BaseModel):
    """块检查请求"""
    chunks: List[ChunkInfo]

class ChunkCheckResponse(BaseModel):
    """块检查响应"""
    missing: List[str]
    existing: List[str]

class ChunkAssembleRequest(BaseModel):
    """块级组装请求"""
    path: str
    filename: str
    chunks: List[ChunkInfo]
    file_hash: Optional[str] = None
    content_type: Optional[str] = None
    file_id: Optional[int] = None
    base_version: Optional[int] = None

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


def detect_compression_type(header_value: Optional[str], file_path: str) -> Optional[str]:
    """根据请求头和文件魔数检测压缩算法"""
    if header_value:
        normalized = header_value.strip().lower()
    else:
        normalized = None
    if normalized in (None, '', 'none'):
        normalized = None
    elif normalized not in ('gzip',):
        raise HTTPException(status_code=400, detail=f"不支持的压缩算法: {header_value}")

    if normalized:
        return normalized

    # 尝试通过文件魔数检测gzip
    try:
        with open(file_path, 'rb') as temp_file:
            magic = temp_file.read(2)
            if magic == b'\x1f\x8b':
                return 'gzip'
    except OSError:
        pass
    return None


def decompress_uploaded_file(source_path: str, compression: Optional[str]) -> str:
    """
    根据压缩方式解压到临时文件，返回解压后的路径。
    如果未压缩则直接返回原路径。
    """
    if not compression:
        return source_path

    if compression == 'gzip':
        target_temp = tempfile.NamedTemporaryFile(delete=False)
        target_temp.close()
        try:
            with gzip.open(source_path, 'rb') as src, open(target_temp.name, 'wb') as dst:
                shutil.copyfileobj(src, dst)
        except OSError as exc:
            os.remove(target_temp.name)
            raise HTTPException(status_code=400, detail=f"解压失败: {exc}")
        return target_temp.name

    raise HTTPException(status_code=400, detail=f"当前不支持的压缩格式: {compression}")


def normalize_hash_value(hash_value: Optional[str]) -> Optional[str]:
    """规范化哈希值便于查询"""
    if not hash_value:
        return None
    return hash_value.strip().lower()


def find_existing_file_by_hash(db: Session, hash_value: Optional[str]) -> Optional[FileModel]:
    """根据哈希值查找已存在的文件记录"""
    normalized = normalize_hash_value(hash_value)
    if not normalized:
        return None
    return db.query(FileModel).filter(
        FileModel.hash_value == normalized,
        FileModel.is_directory == False
    ).order_by(FileModel.updated_at.desc()).first()


def release_file_chunks(db: Session, file_id: int, storage: S3StorageService):
    """释放文件引用的块"""
    usages = db.query(FileChunkUsage).filter(FileChunkUsage.file_id == file_id).all()
    for usage in usages:
        chunk = db.query(FileChunk).filter(FileChunk.id == usage.chunk_id).first()
        if chunk:
            chunk.ref_count = max(0, (chunk.ref_count or 0) - 1)
            if chunk.ref_count == 0:
                storage.delete_file(chunk.s3_key)
                db.delete(chunk)
        db.delete(usage)


def assign_chunks_to_file(db: Session, file_id: int, chunks: List[FileChunk]):
    """为文件记录块使用情况"""
    for idx, chunk in enumerate(chunks):
        usage = FileChunkUsage(
            file_id=file_id,
            chunk_id=chunk.id,
            chunk_index=idx,
            size=chunk.size
        )
        chunk.ref_count = (chunk.ref_count or 0) + 1
        db.add(usage)


@router.post("/hash/check", response_model=HashCheckResponse)
async def check_file_hash(
    payload: HashCheckRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    根据哈希值检查服务器是否已存在相同文件内容
    """
    existing = find_existing_file_by_hash(db, payload.hash_value)
    if not existing:
        return HashCheckResponse(exists=False)
    
    return HashCheckResponse(
        exists=True,
        size=existing.size,
        content_type=existing.content_type,
        filename=existing.filename
    )


@router.post("/chunks/check", response_model=ChunkCheckResponse)
async def check_chunks(
    payload: ChunkCheckRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """检查哪些块已存在"""
    normalized_hashes = []
    for chunk in payload.chunks:
        normalized = normalize_hash_value(chunk.hash_value)
        if normalized:
            normalized_hashes.append(normalized)
    normalized_hashes = list(dict.fromkeys(normalized_hashes))
    existing = []
    if normalized_hashes:
        db_chunks = db.query(FileChunk.hash_value).filter(FileChunk.hash_value.in_(normalized_hashes)).all()
        existing = [row[0] for row in db_chunks]
    missing = [h for h in normalized_hashes if h not in existing]
    return ChunkCheckResponse(existing=existing, missing=missing)


# 用户认证通过JWT实现（已在jwt_handler.py中定义）


@router.post("/update/{file_id}", response_model=UploadResponse)
async def update_file(
    file_id: int,
    request: Request,
    file: UploadFile = File(...),
    base_version: Optional[int] = Query(None, description="The file version the update is based on for conflict detection"),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    Update a file's content (uploads a new version).
    - Supports updates by the file owner.
    - Supports updates by shared users with 'write' permission.
    - Handles conflicts by creating a new file if base_version does not match the current version.
    """
    # 1. Check for file existence and write permission for the user
    existing_file, share = check_file_access(db, file_id, user_id, required_permission=SharePermission.WRITE)
    
    # 2. Conflict Detection
    is_conflict = base_version is not None and base_version != existing_file.version

    temp_file_path = None
    cleanup_paths = set()
    try:
        # 3. Save the uploaded file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            cleanup_paths.add(temp_file_path)
            shutil.copyfileobj(file.file, temp_file)

        # Detect compression and decompress for hashing/size calculation
        compression = detect_compression_type(
            request.headers.get('X-Compression') if request else None,
            temp_file_path
        )
        decompressed_path = decompress_uploaded_file(temp_file_path, compression)
        if decompressed_path != temp_file_path:
            cleanup_paths.add(decompressed_path)
        
        original_file_size = os.path.getsize(decompressed_path)
        compressed_size = os.path.getsize(temp_file_path)
        with open(decompressed_path, 'rb') as f:
            hash_value = normalize_hash_value(storage.calculate_file_hash(f))

        # 4. Upload to S3
        timestamp = int(datetime.utcnow().timestamp())
        unique_filename = f"{timestamp}_{file.filename}"
        owner_id = existing_file.user_id
        clean_path = os.path.dirname(existing_file.path).strip('/')
        s3_key = f"users/{owner_id}/{clean_path}/{unique_filename}" if clean_path else f"users/{owner_id}/{unique_filename}"

        metadata = {
            'compression': (compression or 'none'),
            'original_size': str(original_file_size)
        }
        content_encoding = 'gzip' if compression == 'gzip' else None

        with open(temp_file_path, 'rb') as f:
            result = storage.upload_file(
                f, 
                s3_key, 
                compressed_size, 
                file.content_type,
                metadata=metadata,
                content_encoding=content_encoding
            )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"Upload to S3 failed: {result.get('error')}")

        # 5. Handle based on conflict status
        if is_conflict:
            # CONFLICT: Create a new file entry for the conflicted copy
            user = db.query(User).filter(User.id == user_id).first()
            username = user.username if user else "unknown_user"
            name, ext = os.path.splitext(existing_file.filename)
            conflict_filename = f"{name} (conflicted copy from {username} on {datetime.now().strftime('%Y-%m-%d')}){ext}"
            conflict_full_path = os.path.join(os.path.dirname(existing_file.path), conflict_filename)

            new_db_file = FileModel(
                user_id=owner_id, # The original owner still owns the conflicted copy
                path=conflict_full_path,
                filename=conflict_filename,
                size=original_file_size,
                content_type=file.content_type,
                hash_value=hash_value,
                s3_key=s3_key,
                s3_etag=result.get('etag'),
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
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag
            )
            db.add(file_history)
            
            existing_file.size = original_file_size
            existing_file.content_type = file.content_type
            existing_file.hash_value = hash_value
            existing_file.s3_key = s3_key
            existing_file.s3_etag = result.get('etag')
            existing_file.version += 1
            existing_file.updated_at = datetime.utcnow()
            
            db.commit()
            db.refresh(existing_file)

            if share:
                log_share_action(db, share.id, user_id, "upload", f"uploaded new version: {file.filename}")
            
            message = "File updated successfully."
            final_file_info = existing_file

        return UploadResponse(
            success=True,
            message=message,
            file_info=FileInfo.from_orm(final_file_info)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for temp_path in cleanup_paths:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


@router.post("/dedup/update/{file_id}", response_model=UploadResponse)
async def dedup_update_file(
    file_id: int,
    payload: DedupUpdateRequest,
    base_version: Optional[int] = Query(None, description="The file version the update is based on for conflict detection"),
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    基于已有文件内容更新文件版本（复用已有S3对象，避免重新上传）
    """
    normalized_hash = normalize_hash_value(payload.hash_value)
    if not normalized_hash:
        raise HTTPException(status_code=400, detail="无效的哈希值")

    existing_file, share = check_file_access(db, file_id, user_id, required_permission=SharePermission.WRITE)
    is_conflict = base_version is not None and base_version != existing_file.version

    source_file = find_existing_file_by_hash(db, normalized_hash)
    if not source_file:
        raise HTTPException(status_code=404, detail="未找到可复用的文件内容")

    content_type = payload.content_type or source_file.content_type or existing_file.content_type

    if is_conflict:
        user = db.query(User).filter(User.id == user_id).first()
        username = user.username if user else "unknown_user"
        name, ext = os.path.splitext(existing_file.filename)
        conflict_filename = f"{name} (conflicted copy from {username} on {datetime.now().strftime('%Y-%m-%d')}){ext}"
        conflict_full_path = os.path.join(os.path.dirname(existing_file.path), conflict_filename)

        new_db_file = FileModel(
            user_id=existing_file.user_id,
            path=conflict_full_path,
            filename=conflict_filename,
            size=source_file.size,
            content_type=content_type,
            hash_value=normalized_hash,
            s3_key=source_file.s3_key,
            s3_etag=source_file.s3_etag,
            is_directory=False,
            version=1
        )
        db.add(new_db_file)
        db.commit()
        db.refresh(new_db_file)

        return UploadResponse(
            success=True,
            message=f"Conflict detected. Your version was saved as '{conflict_filename}'.",
            file_info=FileInfo.from_orm(new_db_file)
        )

    file_history = FileHistory(
        file_id=existing_file.id,
        version=existing_file.version,
        size=existing_file.size,
        hash_value=existing_file.hash_value,
        s3_key=existing_file.s3_key,
        s3_etag=existing_file.s3_etag
    )
    db.add(file_history)

    existing_file.size = source_file.size
    existing_file.content_type = content_type
    existing_file.hash_value = normalized_hash
    existing_file.s3_key = source_file.s3_key
    existing_file.s3_etag = source_file.s3_etag
    existing_file.version += 1
    existing_file.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(existing_file)

    if share:
        log_share_action(db, share.id, user_id, "upload", f"uploaded dedup version: {existing_file.filename}")

    return UploadResponse(
        success=True,
        message="File updated successfully via deduplication.",
        file_info=FileInfo.from_orm(existing_file)
    )


@router.post("/chunks/upload")
async def upload_chunk(
    request: Request,
    hash_value: str = Query(..., description="块哈希"),
    size: int = Query(..., description="块大小"),
    chunk: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """上传单个数据块"""
    normalized_hash = normalize_hash_value(hash_value)
    if not normalized_hash:
        raise HTTPException(status_code=400, detail="无效的哈希值")

    existing = db.query(FileChunk).filter(FileChunk.hash_value == normalized_hash).first()
    if existing:
        return {"success": True, "message": "块已存在"}

    cleanup_paths = set()
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            cleanup_paths.add(temp_file_path)
            shutil.copyfileobj(chunk.file, temp_file)

        compression = detect_compression_type(
            request.headers.get('X-Compression') if request else None,
            temp_file_path
        )
        decompressed_path = decompress_uploaded_file(temp_file_path, compression)
        if decompressed_path != temp_file_path:
            cleanup_paths.add(decompressed_path)

        actual_size = os.path.getsize(decompressed_path)
        if actual_size != size:
            raise HTTPException(status_code=400, detail="块大小与声明不一致")

        s3_key = f"chunks/{normalized_hash}"

        with open(decompressed_path, 'rb') as f:
            result = storage.upload_file(
                f,
                s3_key,
                actual_size,
                'application/octet-stream'
            )

        if not result['success']:
            raise HTTPException(status_code=500, detail="块上传失败")

        chunk_record = FileChunk(
            hash_value=normalized_hash,
            size=actual_size,
            s3_key=s3_key,
            compression='none',
            ref_count=0
        )
        db.add(chunk_record)
        db.commit()

        return {"success": True, "message": "块上传成功"}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        for temp_path in cleanup_paths:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    path: str = Query("/", description="上传路径（目录）"),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    上传文件
    
    - 支持多线程上传大文件
    - 自动计算文件哈希
    """
    cleanup_paths = set()
    try:
        # 1. 保存临时文件
        temp_file_path = None
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            cleanup_paths.add(temp_file_path)
            shutil.copyfileobj(file.file, temp_file)
        
        # 2. 检测压缩类型并解压用于计算
        compression = detect_compression_type(
            request.headers.get('X-Compression') if request else None,
            temp_file_path
        )
        decompressed_path = decompress_uploaded_file(temp_file_path, compression)
        if decompressed_path != temp_file_path:
            cleanup_paths.add(decompressed_path)
        
        # 3. 获取原始/压缩大小
        original_file_size = os.path.getsize(decompressed_path)
        compressed_size = os.path.getsize(temp_file_path)
        
        # 4. 计算哈希值（基于原始数据）
        with open(decompressed_path, 'rb') as f:
            hash_value = normalize_hash_value(storage.calculate_file_hash(f))
        
        # 4. 生成唯一的S3键
        timestamp = int(datetime.utcnow().timestamp())
        unique_filename = f"{timestamp}_{file.filename}"
        clean_path = path.strip('/').strip()
        
        if clean_path:
            s3_key = f"users/{user_id}/{clean_path}/{unique_filename}"
            full_path = f"/{clean_path}/{file.filename}"
        else:
            s3_key = f"users/{user_id}/{unique_filename}"
            full_path = f"/{file.filename}"
        
        metadata = {
            'compression': (compression or 'none'),
            'original_size': str(original_file_size)
        }
        content_encoding = 'gzip' if compression == 'gzip' else None
        
        # 5. 上传到S3
        with open(temp_file_path, 'rb') as f:
            result = storage.upload_file(
                f, 
                s3_key, 
                compressed_size,
                file.content_type,
                metadata=metadata,
                content_encoding=content_encoding
            )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"上传失败: {result.get('error')}")
        
        # 6. 保存元数据到数据库
        existing_file = db.query(FileModel).filter(
            FileModel.user_id == user_id,
            FileModel.path == full_path,
            FileModel.is_directory == False
        ).first()
        
        if existing_file:
            # 文件已存在，保存旧版本到历史记录
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag
            )
            db.add(file_history)
            
            # 更新现有文件记录
            existing_file.size = original_file_size
            existing_file.content_type = file.content_type
            existing_file.hash_value = hash_value
            existing_file.s3_key = s3_key
            existing_file.s3_etag = result.get('etag')
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
                size=original_file_size,
                content_type=file.content_type,
                hash_value=hash_value,
                s3_key=s3_key,
                s3_etag=result.get('etag'),
                is_directory=False,
                version=1
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
        
        # 7. 删除临时文件
        for temp_path in cleanup_paths:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        
        return UploadResponse(
            success=True,
            message="上传成功",
            file_info=FileInfo.from_orm(db_file)
        )
        
    except Exception as e:
        for temp_path in cleanup_paths:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/dedup/upload", response_model=UploadResponse)
async def dedup_upload_file(
    payload: DedupUploadRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    基于去重结果，在服务器端复用现有文件内容创建/更新文件
    """
    normalized_hash = normalize_hash_value(payload.hash_value)
    if not normalized_hash:
        raise HTTPException(status_code=400, detail="无效的哈希值")

    source_file = find_existing_file_by_hash(db, normalized_hash)
    if not source_file:
        raise HTTPException(status_code=404, detail="未找到可复用的文件内容")

    clean_path = payload.path.strip('/').strip()
    if clean_path:
        full_path = f"/{clean_path}/{payload.filename}"
    else:
        full_path = f"/{payload.filename}"
    content_type = payload.content_type or source_file.content_type

    existing_file = db.query(FileModel).filter(
        FileModel.user_id == user_id,
        FileModel.path == full_path,
        FileModel.is_directory == False
    ).first()

    if existing_file:
        file_history = FileHistory(
            file_id=existing_file.id,
            version=existing_file.version,
            size=existing_file.size,
            hash_value=existing_file.hash_value,
            s3_key=existing_file.s3_key,
            s3_etag=existing_file.s3_etag
        )
        db.add(file_history)

        existing_file.size = source_file.size
        existing_file.content_type = content_type
        existing_file.hash_value = normalized_hash
        existing_file.s3_key = source_file.s3_key
        existing_file.s3_etag = source_file.s3_etag
        existing_file.version += 1
        existing_file.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(existing_file)

        return UploadResponse(
            success=True,
            message="上传成功（复用现有文件内容）",
            file_info=FileInfo.from_orm(existing_file)
        )

    db_file = FileModel(
        user_id=user_id,
        path=full_path,
        filename=payload.filename,
        size=source_file.size,
        content_type=content_type,
        hash_value=normalized_hash,
        s3_key=source_file.s3_key,
        s3_etag=source_file.s3_etag,
        is_directory=False,
        version=1
    )
    db.add(db_file)
    db.commit()
    db.refresh(db_file)

    return UploadResponse(
        success=True,
        message="上传成功（复用现有文件内容）",
        file_info=FileInfo.from_orm(db_file)
    )


@router.post("/chunks/assemble", response_model=UploadResponse)
async def assemble_file_from_chunks(
    payload: ChunkAssembleRequest,
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """根据块组合生成文件"""
    if not payload.chunks:
        raise HTTPException(status_code=400, detail="缺少块信息")

    chunk_hashes = [normalize_hash_value(c.hash_value) for c in payload.chunks]
    if any(not h for h in chunk_hashes):
        raise HTTPException(status_code=400, detail="存在无效的块哈希")

    chunk_records = db.query(FileChunk).filter(FileChunk.hash_value.in_(chunk_hashes)).all()
    if len(chunk_records) != len(chunk_hashes):
        existing_hashes = {c.hash_value for c in chunk_records}
        missing = [h for h in chunk_hashes if h not in existing_hashes]
        raise HTTPException(status_code=404, detail=f"缺少块: {', '.join(missing)}")

    # 保持顺序
    hash_to_chunk = {c.hash_value: c for c in chunk_records}
    ordered_chunks = [hash_to_chunk[h] for h in chunk_hashes]
    total_size = sum(chunk.size for chunk in ordered_chunks)

    assembled_path = tempfile.NamedTemporaryFile(delete=False)
    assembled_path.close()
    merged_path = assembled_path.name
    compressed_path = None

    try:
        # 合并块
        with open(merged_path, 'wb') as merged_file:
            for chunk in ordered_chunks:
                response = storage.s3_client.get_object(
                    Bucket=storage.bucket_name,
                    Key=chunk.s3_key
                )
                body = response['Body']
                while True:
                    data = body.read(1024 * 1024)
                    if not data:
                        break
                    merged_file.write(data)

        # 计算哈希并校验
        with open(merged_path, 'rb') as merged_file:
            calculated_hash = normalize_hash_value(storage.calculate_file_hash(merged_file))
        if payload.file_hash and normalize_hash_value(payload.file_hash) != calculated_hash:
            raise HTTPException(status_code=400, detail="文件哈希校验失败")

        # 压缩后上传
        compressed_temp = tempfile.NamedTemporaryFile(delete=False)
        compressed_temp.close()
        compressed_path = compressed_temp.name
        with open(merged_path, 'rb') as src, gzip.open(compressed_path, 'wb') as dst:
            shutil.copyfileobj(src, dst)

        compressed_size = os.path.getsize(compressed_path)
        content_type = payload.content_type or 'application/octet-stream'

        if payload.file_id:
            # 更新已有文件
            existing_file, share = check_file_access(
                db, payload.file_id, user_id, required_permission=SharePermission.WRITE
            )
            is_conflict = payload.base_version is not None and payload.base_version != existing_file.version

            if is_conflict:
                user = db.query(User).filter(User.id == user_id).first()
                username = user.username if user else "unknown_user"
                name, ext = os.path.splitext(existing_file.filename)
                conflict_filename = f"{name} (conflicted copy from {username} on {datetime.now().strftime('%Y-%m-%d')}){ext}"
                conflict_full_path = os.path.join(os.path.dirname(existing_file.path), conflict_filename)
                new_s3_key = f"users/{existing_file.user_id}/{int(datetime.utcnow().timestamp())}_{conflict_filename}"

                with open(compressed_path, 'rb') as f:
                    result = storage.upload_file(
                        f,
                        new_s3_key,
                        compressed_size,
                        content_type,
                        metadata={
                            'compression': 'gzip',
                            'original_size': str(total_size)
                        },
                        content_encoding='gzip'
                    )

                if not result['success']:
                    raise HTTPException(status_code=500, detail="文件合并上传失败")

                new_file = FileModel(
                    user_id=existing_file.user_id,
                    path=conflict_full_path,
                    filename=conflict_filename,
                    size=total_size,
                    content_type=content_type,
                    hash_value=calculated_hash,
                    s3_key=new_s3_key,
                    s3_etag=result.get('etag'),
                    is_directory=False,
                    version=1
                )
                db.add(new_file)
                db.commit()
                db.refresh(new_file)
                assign_chunks_to_file(db, new_file.id, ordered_chunks)
                db.commit()

                return UploadResponse(
                    success=True,
                    message=f"Conflict detected. Your version was saved as '{conflict_filename}'.",
                    file_info=FileInfo.from_orm(new_file)
                )

            # 更新当前文件
            release_file_chunks(db, existing_file.id, storage)
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag
            )
            db.add(file_history)

            new_s3_key = f"users/{existing_file.user_id}/{int(datetime.utcnow().timestamp())}_{existing_file.filename}"
            with open(compressed_path, 'rb') as f:
                result = storage.upload_file(
                    f,
                    new_s3_key,
                    compressed_size,
                    content_type,
                    metadata={
                        'compression': 'gzip',
                        'original_size': str(total_size)
                    },
                    content_encoding='gzip'
                )
            if not result['success']:
                raise HTTPException(status_code=500, detail="文件合并上传失败")

            existing_file.size = total_size
            existing_file.content_type = content_type
            existing_file.hash_value = calculated_hash
            existing_file.s3_key = new_s3_key
            existing_file.s3_etag = result.get('etag')
            existing_file.version += 1
            existing_file.updated_at = datetime.utcnow()
            db.commit()
            assign_chunks_to_file(db, existing_file.id, ordered_chunks)
            db.commit()
            db.refresh(existing_file)

            return UploadResponse(
                success=True,
                message="块级去重上传成功",
                file_info=FileInfo.from_orm(existing_file)
            )

        # 新文件
        clean_path = payload.path.strip('/').strip()
        if clean_path:
            full_path = f"/{clean_path}/{payload.filename}"
        else:
            full_path = f"/{payload.filename}"
        unique_s3_key = f"users/{user_id}/{int(datetime.utcnow().timestamp())}_{payload.filename}"

        with open(compressed_path, 'rb') as f:
            result = storage.upload_file(
                f,
                unique_s3_key,
                compressed_size,
                content_type,
                metadata={
                    'compression': 'gzip',
                    'original_size': str(total_size)
                },
                content_encoding='gzip'
            )
        if not result['success']:
            raise HTTPException(status_code=500, detail="文件合并上传失败")

        existing_file = db.query(FileModel).filter(
            FileModel.user_id == user_id,
            FileModel.path == full_path,
            FileModel.is_directory == False
        ).first()

        if existing_file:
            release_file_chunks(db, existing_file.id, storage)
            file_history = FileHistory(
                file_id=existing_file.id,
                version=existing_file.version,
                size=existing_file.size,
                hash_value=existing_file.hash_value,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag
            )
            db.add(file_history)

            existing_file.size = total_size
            existing_file.content_type = content_type
            existing_file.hash_value = calculated_hash
            existing_file.s3_key = unique_s3_key
            existing_file.s3_etag = result.get('etag')
            existing_file.version += 1
            existing_file.updated_at = datetime.utcnow()
            db.commit()
            assign_chunks_to_file(db, existing_file.id, ordered_chunks)
            db.commit()
            db.refresh(existing_file)
            target_file = existing_file
        else:
            new_db_file = FileModel(
                user_id=user_id,
                path=full_path,
                filename=payload.filename,
                size=total_size,
                content_type=content_type,
                hash_value=calculated_hash,
                s3_key=unique_s3_key,
                s3_etag=result.get('etag'),
                is_directory=False,
                version=1
            )
            db.add(new_db_file)
            db.commit()
            db.refresh(new_db_file)
            assign_chunks_to_file(db, new_db_file.id, ordered_chunks)
            db.commit()
            target_file = new_db_file

        return UploadResponse(
            success=True,
            message="块级去重上传成功",
            file_info=FileInfo.from_orm(target_file)
        )

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(merged_path):
            os.remove(merged_path)
        if compressed_path and os.path.exists(compressed_path):
            os.remove(compressed_path)


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
    """
    # 检查访问权限（支持共享文件）
    db_file, share = check_file_access(db, file_id, user_id, SharePermission.READ)
    
    if db_file.is_directory:
        raise HTTPException(status_code=400, detail="不能下载目录")
    
    temp_file_path = tempfile.mktemp(suffix=f"_{db_file.filename}")
    
    try:
        result = storage.download_file(db_file.s3_key, temp_file_path)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"下载失败: {result.get('error')}")
        
        # 记录共享文件的下载日志
        if share:
            log_share_action(db, share.id, user_id, "download", f"下载文件: {db_file.filename}")
        
        metadata = result.get('metadata') or {}
        compression_value = result.get('content_encoding') or metadata.get('compression') or 'none'
        headers = {
            'X-Compression': compression_value
        }
        original_size_header = metadata.get('original_size') or (db_file.size and str(db_file.size))
        if original_size_header:
            headers['X-Original-Size'] = str(original_size_header)
        
        return FileResponse(
            path=temp_file_path,
            filename=db_file.filename,
            media_type=db_file.content_type or 'application/octet-stream',
            background=None,
            headers=headers
        )
        
    except Exception as e:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
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
        release_file_chunks(db, db_file.id, storage)
        
        other_refs = db.query(FileModel).filter(
            FileModel.s3_key == db_file.s3_key,
            FileModel.id != db_file.id
        ).count()

        if other_refs == 0:
            result = storage.delete_file(db_file.s3_key)
            if not result['success']:
                pass
        else:
            logger.info(f"跳过底层对象删除，仍有 {other_refs} 个文件引用 {db_file.s3_key}")
        
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
    回滚文件到指定版本
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

    try:
        # 1. 将当前版本存入历史记录
        current_version_history = FileHistory(
            file_id=db_file.id,
            version=db_file.version,
            size=db_file.size,
            hash_value=db_file.hash_value,
            s3_key=db_file.s3_key,
            s3_etag=db_file.s3_etag
        )
        db.add(current_version_history)

        # 2. 从S3复制历史版本文件作为新文件
        clean_path = os.path.dirname(db_file.path).strip('/')
        timestamp = int(datetime.utcnow().timestamp())
        new_s3_key = f"users/{user_id}/{clean_path}/{timestamp}_{db_file.filename}" if clean_path else f"users/{user_id}/{timestamp}_{db_file.filename}"
        
        copy_result = storage.copy_file(history_version.s3_key, new_s3_key)
        if not copy_result['success']:
            raise HTTPException(status_code=500, detail="S3文件复制失败")

        # 3. 用历史版本元数据和新的S3信息覆盖当前文件记录
        db_file.size = history_version.size
        db_file.hash_value = history_version.hash_value
        db_file.s3_key = new_s3_key
        db_file.s3_etag = copy_result.get('etag')
        db_file.version += 1
        db_file.updated_at = datetime.utcnow()

        # 4. 从历史记录中删除已恢复的版本
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
        raise HTTPException(status_code=500, detail=str(e))
