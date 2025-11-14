"""
认证服务
"""
from sqlalchemy.orm import Session
from app.models.user import User
from app.utils.password import hash_password, verify_password
from app.utils.jwt_handler import create_access_token, create_refresh_token
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


class AuthService:
    """认证服务"""
    
    @staticmethod
    def register_user(db: Session, username: str, email: str, password: str) -> User:
        """
        注册新用户
        
        Args:
            db: 数据库会话
            username: 用户名
            email: 邮箱
            password: 密码
            
        Returns:
            创建的用户对象
            
        Raises:
            ValueError: 用户名或邮箱已存在
        """
        # 检查用户名是否已存在
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            raise ValueError("用户名已存在")
        
        # 检查邮箱是否已存在
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise ValueError("邮箱已被注册")
        
        # 创建新用户
        hashed_password = hash_password(password)
        new_user = User(
            username=username,
            email=email,
            hashed_password=hashed_password
        )
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"新用户注册成功: {username}")
        return new_user
    
    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User:
        """
        认证用户
        
        Args:
            db: 数据库会话
            username: 用户名
            password: 密码
            
        Returns:
            认证成功的用户对象
            
        Raises:
            ValueError: 认证失败
        """
        # 查找用户
        user = db.query(User).filter(User.username == username).first()
        if not user:
            raise ValueError("用户名或密码错误")
        
        # 验证密码
        if not verify_password(password, user.hashed_password):
            raise ValueError("用户名或密码错误")
        
        logger.info(f"用户登录成功: {username}")
        return user
    
    @staticmethod
    def create_tokens(user_id: int, username: str) -> dict:
        """
        为用户创建访问Token和刷新Token
        
        Args:
            user_id: 用户ID
            username: 用户名
            
        Returns:
            包含access_token和refresh_token的字典
        """
        token_data = {
            "user_id": user_id,
            "username": username
        }
        
        access_token = create_access_token(data=token_data)
        refresh_token = create_refresh_token(data=token_data)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
    
    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> User:
        """
        根据ID获取用户
        
        Args:
            db: 数据库会话
            user_id: 用户ID
            
        Returns:
            用户对象或None
        """
        return db.query(User).filter(User.id == user_id).first()
    
    @staticmethod
    def get_user_by_username(db: Session, username: str) -> User:
        """
        根据用户名获取用户
        
        Args:
            db: 数据库会话
            username: 用户名
            
        Returns:
            用户对象或None
        """
        return db.query(User).filter(User.username == username).first()

