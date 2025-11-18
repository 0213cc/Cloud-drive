"""
配置文件
"""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """应用配置"""
    
    # AWS配置
    # 如果EC2有IAM角色，这些可以为空，boto3会自动使用IAM角色
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "ap-northeast-1"
    aws_s3_bucket: str
    aws_s3_endpoint_url: Optional[str] = None  # 新增：支持MinIO的端点URL
    
    # 数据库配置
    database_url: str = "sqlite:///./cloud_drive.db"
    
    # JWT配置
    secret_key: str  # 必须在.env中配置，否则会报错
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    
    # 服务器配置
    host: str = "0.0.0.0"
    port: int = 8000
    
    # 文件上传配置
    max_file_size: int = 5368709120  # 5GB
    chunk_size: int = 8388608  # 8MB
    multipart_threshold: int = 104857600  # 100MB
    max_concurrency: int = 10
    
    class Config:
        env_file = ".env"
        case_sensitive = False  # 注意：这里会忽略环境变量的大小写，建议保持一致


@lru_cache()
def get_settings() -> Settings:
    """获取配置（单例模式）"""
    return Settings()