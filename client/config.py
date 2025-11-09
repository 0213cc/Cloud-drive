"""
客户端配置
"""
import os
from dotenv import load_dotenv

load_dotenv()


class ClientConfig:
    """客户端配置"""
    
    # 服务器地址
    API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    # 用户ID（临时mock）
    USER_ID = int(os.getenv("USER_ID", "1"))
    
    # 上传配置
    CHUNK_SIZE = 8 * 1024 * 1024  # 8MB
    MAX_RETRIES = 3
    
    # 下载配置
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "./downloads")


config = ClientConfig()

