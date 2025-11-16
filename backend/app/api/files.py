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
from app.models.file import File as FileModel, FileHistory
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
        # 检查是否已存在同名文件
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
            existing_file.size = file_size
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
                size=file_size,
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

@router.get("/history/{file_id}", response_model=List[FileHistoryInfo])
async def get_file_history(
    file_id: int,
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取文件历史版本
    """
    # 检查文件是否存在
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
    user_id: int = Depends(get_current_user_id)
):
    """
    回滚文件到指定版本
    """
    # 1. 查找当前文件
    db_file = db.query(FileModel).filter(
        FileModel.id == file_id,
        FileModel.user_id == user_id
    ).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="文件不存在")

    # 2. 查找目标历史版本
    history_version = db.query(FileHistory).filter(
        FileHistory.file_id == file_id,
        FileHistory.version == version
    ).first()
    if not history_version:
        raise HTTPException(status_code=404, detail="历史版本不存在")

    try:
        # 3. 将当前版本存入历史记录
        current_version_history = FileHistory(
            file_id=db_file.id,
            version=db_file.version,
            size=db_file.size,
            hash_value=db_file.hash_value,
            s3_key=db_file.s3_key,
            s3_etag=db_file.s3_etag
        )
        db.add(current_version_history)

        # 4. 用历史版本覆盖当前文件记录
        db_file.size = history_version.size
        db_file.hash_value = history_version.hash_value
        db_file.s3_key = history_version.s3_key
        db_file.s3_etag = history_version.s3_etag
        db_file.version += 1  # 版本号增加
        db_file.updated_at = datetime.utcnow()

        # 5. 从历史记录中删除已恢复的版本
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
