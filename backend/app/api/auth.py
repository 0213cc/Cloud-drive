"""
认证API
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime

from app.models.database import get_db
from app.services.auth_service import AuthService
from app.utils.jwt_handler import get_current_user_id, decode_token

router = APIRouter(prefix="/api/auth", tags=["authentication"])


# Pydantic模型
class UserRegister(BaseModel):
    """用户注册请求"""
    username: str
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """用户登录请求"""
    username: str
    password: str


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    refresh_token: str
    token_type: str
    user_id: int
    username: str


class UserInfo(BaseModel):
    """用户信息"""
    id: int
    username: str
    email: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """
    用户注册
    
    - 创建新用户账户
    - 返回访问Token
    """
    try:
        # 注册用户
        new_user = AuthService.register_user(
            db=db,
            username=user_data.username,
            email=user_data.email,
            password=user_data.password
        )
        
        # 创建Token
        tokens = AuthService.create_tokens(
            user_id=new_user.id,
            username=new_user.username
        )
        
        return TokenResponse(
            **tokens,
            user_id=new_user.id,
            username=new_user.username
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """
    用户登录
    
    - 验证用户凭证
    - 返回访问Token
    """
    try:
        # 认证用户
        user = AuthService.authenticate_user(
            db=db,
            username=credentials.username,
            password=credentials.password
        )
        
        # 创建Token
        tokens = AuthService.create_tokens(
            user_id=user.id,
            username=user.username
        )
        
        return TokenResponse(
            **tokens,
            user_id=user.id,
            username=user.username
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    刷新访问Token
    
    - 使用刷新Token获取新的访问Token
    """
    try:
        # 解码刷新Token
        payload = decode_token(request.refresh_token)
        
        # 验证Token类型
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的刷新Token"
            )
        
        user_id = payload.get("user_id")
        username = payload.get("username")
        
        if not user_id or not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的Token数据"
            )
        
        # 验证用户是否存在
        user = AuthService.get_user_by_id(db, user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在"
            )
        
        # 创建新Token
        tokens = AuthService.create_tokens(
            user_id=user.id,
            username=user.username
        )
        
        return TokenResponse(
            **tokens,
            user_id=user.id,
            username=user.username
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="刷新Token失败"
        )


@router.get("/me", response_model=UserInfo)
async def get_current_user(
    db: Session = Depends(get_db),
    user_id: int = Depends(get_current_user_id)
):
    """
    获取当前登录用户信息
    
    - 需要提供有效的访问Token
    """
    user = AuthService.get_user_by_id(db, user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    return UserInfo.from_orm(user)


@router.get("/test")
async def test_auth(user_id: int = Depends(get_current_user_id)):
    """
    测试认证
    
    - 验证Token是否有效
    """
    return {
        "message": "认证成功",
        "user_id": user_id
    }

