"""
块级上传API

支持文件分块上传和块级去重
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Query, Body
from typing import Optional, List, Dict
from pydantic import BaseModel
from sqlalchemy.orm import Session
import tempfile
import os
import logging
from datetime import datetime

from app.services.storage import S3StorageService
from app.models.database import get_db
from app.models.file import File as FileModel, FileHistory
from app.models.file_chunk import FileChunk
from app.utils.jwt_handler import get_current_user_id
from app.utils.chunking import ChunkingService, ChunkInfo
from app.utils.block_deduplication import BlockDeduplicationService
from app.utils.compression import CompressionService
from app.utils.deduplication import DeduplicationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/block-upload", tags=["block-upload"])


# Pydantic模型
class CheckBlockRequest(BaseModel):
    """检查数据块请求"""
    hash_values: List[str]  # 数据块哈希值列表


class CheckBlockResponse(BaseModel):
    """检查数据块响应"""
    existing_blocks: Dict[str, int]  # 已存在的数据块：hash -> block_chunk_id
    missing_blocks: List[str]  # 需要上传的数据块哈希值


class AssembleFileRequest(BaseModel):
    """组装文件请求"""
    filename: str
    path: str = "/"
    content_type: Optional[str] = None
    total_size: int
    file_hash: str
    chunking_algorithm: str = "fixed"
    chunk_size: int
    blocks: List[Dict]  # [{"hash": "...", "index": 0, "offset": 0, "size": 1024}, ...]


class AssembleFileResponse(BaseModel):
    """组装文件响应"""
    success: bool
    message: str
    file_id: Optional[int] = None
    version: Optional[int] = None
    deduplication_stats: Optional[Dict] = None


def get_storage_service():
    """获取存储服务"""
    return S3StorageService()


@router.post("/check-blocks", response_model=CheckBlockResponse)
async def check_blocks(
    request: CheckBlockRequest,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    检查哪些数据块已存在
    
    客户端在上传前调用此接口，获取需要上传的数据块列表
    """
    existing_blocks = {}
    missing_blocks = []
    
    for hash_value in request.hash_values:
        block_chunk = BlockDeduplicationService.check_block_duplicate(db, hash_value)
        if block_chunk:
            existing_blocks[hash_value] = block_chunk.id
        else:
            missing_blocks.append(hash_value)
    
    logger.info(
        f"检查数据块: user_id={user_id}, "
        f"total={len(request.hash_values)}, "
        f"existing={len(existing_blocks)}, "
        f"missing={len(missing_blocks)}"
    )
    
    return CheckBlockResponse(
        existing_blocks=existing_blocks,
        missing_blocks=missing_blocks
    )


@router.post("/upload-block")
async def upload_block(
    block_hash: str = Query(..., description="数据块哈希值"),
    block_index: int = Query(..., description="数据块序号"),
    enable_compression: bool = Query(True, description="是否启用压缩"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    上传单个数据块
    
    Args:
        block_hash: 数据块哈希值（用于验证和去重）
        block_index: 数据块序号
        enable_compression: 是否启用压缩
        file: 数据块文件
    
    Returns:
        上传结果
    """
    temp_file_path = None
    compressed_file_path = None
    
    try:
        # 1. 检查数据块是否已存在
        existing_block = BlockDeduplicationService.check_block_duplicate(db, block_hash)
        if existing_block:
            logger.info(
                f"数据块已存在: hash={block_hash[:16]}..., "
                f"block_id={existing_block.id}, refs={existing_block.reference_count}"
            )
            return {
                "success": True,
                "message": "数据块已存在",
                "block_chunk_id": existing_block.id,
                "deduplicated": True
            }
        
        # 2. 保存上传的数据块到临时文件
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            content = await file.read()
            temp_file.write(content)
        
        # 3. 验证哈希值
        import hashlib
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash != block_hash:
            raise HTTPException(
                status_code=400,
                detail=f"数据块哈希值不匹配: expected={block_hash[:16]}..., actual={actual_hash[:16]}..."
            )
        
        original_size = len(content)
        
        # 4. 判断是否需要压缩
        should_compress = (
            enable_compression and
            CompressionService.should_compress(original_size, "application/octet-stream")
        )
        
        is_compressed = False
        compressed_size = original_size
        compression_ratio = 0
        upload_file_path = temp_file_path
        stored_content_type = "application/octet-stream"
        
        if should_compress:
            compressed_file_path = tempfile.mktemp(suffix='.gz')
            
            with open(temp_file_path, 'rb') as input_f, open(compressed_file_path, 'wb') as output_f:
                compress_result = CompressionService.compress_file(input_f, output_f)
                
                if compress_result['success']:
                    is_compressed = True
                    compressed_size = compress_result['compressed_size']
                    compression_ratio = int(compress_result['compression_ratio'])
                    upload_file_path = compressed_file_path
                    stored_content_type = 'application/gzip'
        
        # 5. 生成S3键
        timestamp = int(datetime.utcnow().timestamp())
        s3_key = f"blocks/{user_id}/{block_hash[:2]}/{block_hash}"
        if is_compressed:
            s3_key += ".gz"
        
        # 6. 上传到S3
        upload_size = compressed_size if is_compressed else original_size
        
        with open(upload_file_path, 'rb') as f:
            result = storage.upload_file(
                f,
                s3_key,
                upload_size,
                stored_content_type
            )
        
        if not result['success']:
            raise HTTPException(
                status_code=500,
                detail=f"上传失败: {result.get('error')}"
            )
        
        # 7. 创建数据块记录
        block_chunk = BlockDeduplicationService.create_block_chunk(
            db=db,
            hash_value=block_hash,
            size=original_size,
            s3_key=s3_key,
            s3_etag=result.get('etag'),
            is_compressed=is_compressed,
            compressed_size=compressed_size if is_compressed else None,
            compression_ratio=compression_ratio if is_compressed else None,
            stored_content_type=stored_content_type
        )
        
        logger.info(
            f"上传数据块成功: block_id={block_chunk.id}, "
            f"hash={block_hash[:16]}..., size={original_size}, "
            f"compressed={is_compressed}"
        )
        
        return {
            "success": True,
            "message": "上传成功",
            "block_chunk_id": block_chunk.id,
            "deduplicated": False,
            "compressed": is_compressed,
            "compression_ratio": compression_ratio
        }
    
    finally:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        if compressed_file_path and os.path.exists(compressed_file_path):
            os.unlink(compressed_file_path)


@router.post("/assemble", response_model=AssembleFileResponse)
async def assemble_file(
    request: AssembleFileRequest,
    db: Session = Depends(get_db),
    storage: S3StorageService = Depends(get_storage_service),
    user_id: int = Depends(get_current_user_id)
):
    """
    组装文件
    
    客户端上传完所有数据块后，调用此接口组装文件
    创建FileChunk和File记录，建立文件-数据块映射
    
    Args:
        request: 组装文件请求
    
    Returns:
        组装结果
    """
    try:
        timestamp = int(datetime.utcnow().timestamp())
        # 1. 验证所有数据块都已上传
        block_chunk_ids = []
        for block_info in request.blocks:
            block_hash = block_info['hash']
            block_chunk = BlockDeduplicationService.check_block_duplicate(db, block_hash)
            
            if not block_chunk:
                raise HTTPException(
                    status_code=400,
                    detail=f"数据块不存在: hash={block_hash[:16]}..."
                )
            
            block_chunk_ids.append(block_chunk.id)
        
        # 2. 检查文件是否已存在（文件级去重）
        existing_file_chunk = DeduplicationService.check_duplicate(db, request.file_hash)
        
        if existing_file_chunk:
            # 文件已存在，直接复用
            file_chunk_id = existing_file_chunk.id
            DeduplicationService.increment_reference(db, existing_file_chunk)
            
            logger.info(
                f"文件已存在（文件级去重）: file_chunk_id={file_chunk_id}, "
                f"hash={request.file_hash[:16]}..., refs={existing_file_chunk.reference_count}"
            )
            
            is_file_deduplicated = True
        else:
            # 3. 创建FileChunk记录
            # 注意：对于块级去重的文件，s3_key指向一个虚拟路径（不实际存储完整文件）
            timestamp = int(datetime.utcnow().timestamp())
            s3_key = f"files/{user_id}/{timestamp}_{request.filename}.chunked"
            
            file_chunk = FileChunk(
                hash_value=request.file_hash,
                size=request.total_size,
                s3_key=s3_key,
                is_compressed=False,  # 块级去重时，压缩在块级别进行
                reference_count=1
            )
            
            db.add(file_chunk)
            db.commit()
            db.refresh(file_chunk)
            
            file_chunk_id = file_chunk.id
            is_file_deduplicated = False
            
            logger.info(
                f"创建文件块: file_chunk_id={file_chunk_id}, "
                f"hash={request.file_hash[:16]}..., size={request.total_size}"
            )
            
            # 4. 创建文件-数据块映射
            for i, block_info in enumerate(request.blocks):
                block_hash = block_info['hash']
                block_chunk = BlockDeduplicationService.check_block_duplicate(db, block_hash)
                
                # 增加数据块引用计数
                BlockDeduplicationService.increment_block_reference(db, block_chunk)
                
                # 创建映射
                BlockDeduplicationService.create_file_block_map(
                    db=db,
                    file_chunk_id=file_chunk_id,
                    block_chunk_id=block_chunk.id,
                    block_index=block_info['index'],
                    block_offset=block_info['offset']
                )
            
            # 5. 创建文件块元数据
            unique_hashes = set(block_info['hash'] for block_info in request.blocks)
            dedup_ratio = 0
            if len(request.blocks) > 0:
                dedup_ratio = int((1 - len(unique_hashes) / len(request.blocks)) * 100)
            
            BlockDeduplicationService.create_file_block_metadata(
                db=db,
                file_chunk_id=file_chunk_id,
                chunking_algorithm=request.chunking_algorithm,
                chunk_size=request.chunk_size,
                total_blocks=len(request.blocks),
                unique_blocks=len(unique_hashes),
                deduplication_ratio=dedup_ratio
            )
        
        # 6. 创建或更新File记录
        clean_path = request.path.strip('/').strip()
        if clean_path:
            full_path = f"/{clean_path}/{request.filename}"
        else:
            full_path = f"/{request.filename}"
        
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
                chunk_id=existing_file.chunk_id,
                s3_key=existing_file.s3_key,
                s3_etag=existing_file.s3_etag,
                is_compressed=existing_file.is_compressed,
                compressed_size=existing_file.compressed_size
            )
            db.add(file_history)
            
            # 如果旧版本也有chunk_id，需要减少其引用计数
            if existing_file.chunk_id and existing_file.chunk_id != file_chunk_id:
                # 检查旧版本是否使用块级去重
                old_metadata = BlockDeduplicationService.get_file_block_metadata(
                    db, existing_file.chunk_id
                )
                
                if old_metadata:
                    # 旧版本使用块级去重，需要删除块映射
                    BlockDeduplicationService.delete_file_blocks(
                        db, existing_file.chunk_id, storage
                    )
                
                # 减少文件块引用计数
                DeduplicationService.decrement_reference(
                    db, existing_file.chunk_id, storage
                )
            
            # 更新现有文件记录
            existing_file.size = request.total_size
            existing_file.content_type = request.content_type
            existing_file.hash_value = request.file_hash
            existing_file.chunk_id = file_chunk_id
            existing_file.s3_key = f"files/{user_id}/{timestamp}_{request.filename}.chunked"
            existing_file.is_compressed = False
            existing_file.compressed_size = None
            existing_file.compression_ratio = None
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
                filename=request.filename,
                size=request.total_size,
                content_type=request.content_type,
                hash_value=request.file_hash,
                chunk_id=file_chunk_id,
                s3_key=f"files/{user_id}/{timestamp}_{request.filename}.chunked",
                is_compressed=False,
                is_directory=False,
                version=1
            )
            db.add(db_file)
            db.commit()
            db.refresh(db_file)
        
        # 7. 计算去重统计
        metadata = BlockDeduplicationService.get_file_block_metadata(db, file_chunk_id)
        dedup_stats = None
        
        if metadata:
            dedup_stats = {
                "total_blocks": metadata.total_blocks,
                "unique_blocks": metadata.unique_blocks,
                "deduplication_ratio": metadata.deduplication_ratio,
                "chunking_algorithm": metadata.chunking_algorithm
            }
        
        message = "文件组装成功"
        if is_file_deduplicated:
            message += "（文件级去重）"
        elif dedup_stats and dedup_stats['deduplication_ratio'] > 0:
            message += f"（块级去重率: {dedup_stats['deduplication_ratio']}%）"
        
        logger.info(
            f"文件组装成功: file_id={db_file.id}, "
            f"file_chunk_id={file_chunk_id}, "
            f"version={db_file.version}, "
            f"file_dedup={is_file_deduplicated}"
        )
        
        return AssembleFileResponse(
            success=True,
            message=message,
            file_id=db_file.id,
            version=db_file.version,
            deduplication_stats=dedup_stats
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"文件组装失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"文件组装失败: {str(e)}")


@router.get("/stats")
async def get_block_deduplication_stats(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取块级去重统计信息
    """
    stats = BlockDeduplicationService.get_deduplication_stats(db)
    
    return {
        "success": True,
        "stats": stats
    }

