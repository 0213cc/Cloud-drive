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
from datetime import datetime

from app.services.storage import S3StorageService
from app.models.database import get_db
from app.models.file import File as FileModel
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


# 依赖注入
def get_storage_service():
    """获取存储服务"""
    return S3StorageService()

# 用户认证通过JWT实现（已在jwt_handler.py中定义）


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
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
    try:
        # 1. 保存临时文件
        temp_file_path = None
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
        
        # 2. 获取文件大小
        file_size = os.path.getsize(temp_file_path)
        
        # 3. 计算哈希值
        with open(temp_file_path, 'rb') as f:
            hash_value = storage.calculate_file_hash(f)
        
        # 4. 生成S3键
        # 格式: users/{user_id}/{path}/{filename}
        clean_path = path.strip('/').strip()
        if clean_path:
            s3_key = f"users/{user_id}/{clean_path}/{file.filename}"
            full_path = f"/{clean_path}/{file.filename}"
        else:
            s3_key = f"users/{user_id}/{file.filename}"
            full_path = f"/{file.filename}"
        
        # 5. 上传到S3
        with open(temp_file_path, 'rb') as f:
            result = storage.upload_file(
                f, 
                s3_key, 
                file_size,
                file.content_type
            )
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"上传失败: {result.get('error')}")
        
        # 6. 保存元数据到数据库
        db_file = FileModel(
            user_id=user_id,
            path=full_path,
            filename=file.filename,
            size=file_size,
            content_type=file.content_type,
            hash_value=hash_value,
            s3_key=s3_key,
            s3_etag=result.get('etag'),
            is_directory=False
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        
        # 7. 删除临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        
        return UploadResponse(
            success=True,
            message="上传成功",
            file_info=FileInfo.from_orm(db_file)
        )
        
    except Exception as e:
        # 清理临时文件
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
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
    
    - 支持多线程下载大文件
    """
    # 1. 查询文件元数据
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    if db_file.is_directory:
        raise HTTPException(status_code=400, detail="不能下载目录")
    
    # 2. 创建临时文件
    temp_file_path = tempfile.mktemp(suffix=f"_{db_file.filename}")
    
    try:
        # 3. 从S3下载
        result = storage.download_file(db_file.s3_key, temp_file_path)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"下载失败: {result.get('error')}")
        
        # 4. 返回文件
        return FileResponse(
            path=temp_file_path,
            filename=db_file.filename,
            media_type=db_file.content_type or 'application/octet-stream',
            background=None  # 手动清理
        )
        
    except Exception as e:
        # 清理临时文件
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
    # 规范化路径
    clean_path = "/" + path.strip('/').strip()
    
    # 查询指定路径下的文件
    query = db.query(FileModel).filter(
        FileModel.user_id == user_id
    )
    
    # 如果不是根目录，过滤路径
    if clean_path != "/":
        # 查询该路径下的直接子项
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
    """
    # 1. 查询文件
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    try:
        # 2. 从S3删除
        result = storage.delete_file(db_file.s3_key)
        
        if not result['success']:
            raise HTTPException(status_code=500, detail=f"删除失败: {result.get('error')}")
        
        # 3. 从数据库删除
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
    
    注意：S3本身没有目录概念，这里只在数据库中创建记录
    """
    # 规范化路径
    clean_path = "/" + path.strip('/').strip()
    
    # 检查是否已存在
    existing = db.query(FileModel).filter(
        FileModel.user_id == user_id,
        FileModel.path == clean_path,
        FileModel.is_directory == True
    ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="目录已存在")
    
    # 创建目录记录
    dir_name = os.path.basename(clean_path)
    parent_path = os.path.dirname(clean_path)
    
    db_dir = FileModel(
        user_id=user_id,
        path=clean_path,
        filename=dir_name,
        size=0,
        s3_key=f"users/{user_id}{clean_path}/.keep",  # 占位符
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
    """
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")
    
    return FileInfo.from_orm(db_file)

