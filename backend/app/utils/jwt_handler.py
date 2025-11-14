"""
JWT Token处理
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from config import get_settings

settings = get_settings()

# HTTP Bearer认证方案
security = HTTPBearer()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    创建访问Token
    
    Args:
        data: 要编码的数据（通常包含用户ID）
        expires_delta: 过期时间增量
        
    Returns:
        JWT Token字符串
    """
    to_encode = data.copy()
    
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)
    
    to_encode.update({"exp": expire})
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    解码Token
    
    Args:
        token: JWT Token字符串
        
    Returns:
        解码后的数据字典
        
    Raises:
        HTTPException: Token无效或过期
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    从Token中获取当前用户ID
    
    Args:
        credentials: HTTP Bearer认证凭证
        
    Returns:
        用户ID
        
    Raises:
        HTTPException: Token无效或用户ID不存在
    """
    token = credentials.credentials
    payload = decode_token(token)
    
    user_id: int = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="无效的认证凭证",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_id


def create_refresh_token(data: dict) -> str:
    """
    创建刷新Token（有效期更长）
    
    Args:
        data: 要编码的数据
        
    Returns:
        刷新Token字符串
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=7)  # 7天有效期
    to_encode.update({"exp": expire, "type": "refresh"})
    
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)
    return encoded_jwt

