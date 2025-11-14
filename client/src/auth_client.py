"""
客户端认证模块 - Token管理
"""
import requests
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class AuthClient:
    """认证客户端 - 管理Token"""
    
    def __init__(self, api_base_url):
        """
        初始化认证客户端
        
        Args:
            api_base_url: API基础URL
        """
        self.api_base_url = api_base_url.rstrip('/')
        self.session = requests.Session()
        
        # Token存储文件
        self.token_file = Path.home() / '.cloud_drive_token.json'
        
        # 当前Token
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self.username = None
        self.token_expires = None
        
        # 加载已保存的Token
        self._load_tokens()
    
    def register(self, username: str, email: str, password: str) -> dict:
        """
        用户注册
        
        Args:
            username: 用户名
            email: 邮箱
            password: 密码
            
        Returns:
            注册结果字典
        """
        try:
            url = f"{self.api_base_url}/api/auth/register"
            data = {
                "username": username,
                "email": email,
                "password": password
            }
            
            response = self.session.post(url, json=data)
            
            if response.status_code == 201:
                result = response.json()
                self._save_tokens(result)
                logger.info(f"注册成功: {username}")
                return {"success": True, **result}
            else:
                error = response.json().get('detail', '注册失败')
                logger.error(f"注册失败: {error}")
                return {"success": False, "error": error}
                
        except Exception as e:
            logger.error(f"注册异常: {e}")
            return {"success": False, "error": str(e)}
    
    def login(self, username: str, password: str) -> dict:
        """
        用户登录
        
        Args:
            username: 用户名
            password: 密码
            
        Returns:
            登录结果字典
        """
        try:
            url = f"{self.api_base_url}/api/auth/login"
            data = {
                "username": username,
                "password": password
            }
            
            response = self.session.post(url, json=data)
            
            if response.status_code == 200:
                result = response.json()
                self._save_tokens(result)
                logger.info(f"登录成功: {username}")
                return {"success": True, **result}
            else:
                error = response.json().get('detail', '登录失败')
                logger.error(f"登录失败: {error}")
                return {"success": False, "error": error}
                
        except Exception as e:
            logger.error(f"登录异常: {e}")
            return {"success": False, "error": str(e)}
    
    def refresh_access_token(self) -> bool:
        """
        刷新访问Token
        
        Returns:
            是否刷新成功
        """
        if not self.refresh_token:
            return False
        
        try:
            url = f"{self.api_base_url}/api/auth/refresh"
            data = {"refresh_token": self.refresh_token}
            
            response = self.session.post(url, json=data)
            
            if response.status_code == 200:
                result = response.json()
                self._save_tokens(result)
                logger.info("Token刷新成功")
                return True
            else:
                logger.error("Token刷新失败")
                return False
                
        except Exception as e:
            logger.error(f"Token刷新异常: {e}")
            return False
    
    def logout(self):
        """退出登录"""
        self.access_token = None
        self.refresh_token = None
        self.user_id = None
        self.username = None
        self.token_expires = None
        
        # 删除Token文件
        if self.token_file.exists():
            self.token_file.unlink()
        
        logger.info("已退出登录")
    
    def is_authenticated(self) -> bool:
        """
        检查是否已认证
        
        Returns:
            是否已登录
        """
        if not self.access_token:
            return False
        
        # 检查Token是否过期
        if self.token_expires:
            if datetime.now() >= self.token_expires:
                # Token已过期，尝试刷新
                logger.info("Token已过期，尝试刷新")
                return self.refresh_access_token()
        
        return True
    
    def get_auth_header(self) -> dict:
        """
        获取认证请求头
        
        Returns:
            包含Authorization的请求头字典
        """
        if not self.is_authenticated():
            raise Exception("未登录或Token已过期")
        
        return {
            "Authorization": f"Bearer {self.access_token}"
        }
    
    def get_user_info(self) -> dict:
        """
        获取当前用户信息
        
        Returns:
            用户信息字典
        """
        try:
            url = f"{self.api_base_url}/api/auth/me"
            headers = self.get_auth_header()
            
            response = self.session.get(url, headers=headers)
            
            if response.status_code == 200:
                return {"success": True, **response.json()}
            else:
                error = response.json().get('detail', '获取用户信息失败')
                return {"success": False, "error": error}
                
        except Exception as e:
            logger.error(f"获取用户信息异常: {e}")
            return {"success": False, "error": str(e)}
    
    def _save_tokens(self, token_data: dict):
        """
        保存Token到本地文件
        
        Args:
            token_data: Token数据
        """
        self.access_token = token_data.get('access_token')
        self.refresh_token = token_data.get('refresh_token')
        self.user_id = token_data.get('user_id')
        self.username = token_data.get('username')
        
        # 计算Token过期时间（默认30分钟）
        self.token_expires = datetime.now() + timedelta(minutes=25)  # 提前5分钟刷新
        
        # 保存到文件
        try:
            data = {
                'access_token': self.access_token,
                'refresh_token': self.refresh_token,
                'user_id': self.user_id,
                'username': self.username,
                'expires': self.token_expires.isoformat()
            }
            
            with open(self.token_file, 'w') as f:
                json.dump(data, f)
            
            # 设置文件权限（仅所有者可读写）
            os.chmod(self.token_file, 0o600)
            
        except Exception as e:
            logger.error(f"保存Token失败: {e}")
    
    def _load_tokens(self):
        """从本地文件加载Token"""
        if not self.token_file.exists():
            return
        
        try:
            with open(self.token_file, 'r') as f:
                data = json.load(f)
            
            self.access_token = data.get('access_token')
            self.refresh_token = data.get('refresh_token')
            self.user_id = data.get('user_id')
            self.username = data.get('username')
            
            expires_str = data.get('expires')
            if expires_str:
                self.token_expires = datetime.fromisoformat(expires_str)
            
            logger.info(f"已加载保存的Token: 用户 {self.username}")
            
        except Exception as e:
            logger.error(f"加载Token失败: {e}")
            # 加载失败，删除损坏的Token文件
            if self.token_file.exists():
                self.token_file.unlink()

