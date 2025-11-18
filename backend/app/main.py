"""
Cloud Drive Backend - 主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from contextlib import asynccontextmanager

from app.api.files import router as files_router
from app.api.sync import router as sync_router
from app.api.auth import router as auth_router
from app.api.share import router as share_router
from app.api.deduplication import router as dedup_router
from app.models.database import init_db

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化数据库
    logger.info("初始化数据库...")
    init_db()
    logger.info("数据库初始化完成")
    yield
    # 关闭时清理资源
    logger.info("应用关闭")


# 创建FastAPI应用
app = FastAPI(
    title="Cloud Drive API",
    description="云盘服务API - 支持多线程上传下载、用户认证、自动同步",
    version="0.2.0",
    lifespan=lifespan
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(files_router)
app.include_router(sync_router)
app.include_router(share_router)
app.include_router(dedup_router)


@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "Cloud Drive API",
        "version": "0.1.0",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "service": "cloud-drive-backend"
    }


if __name__ == "__main__":
    import uvicorn
    from config import get_settings
    
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=True,  # 开发模式
        log_level="info"
    )

