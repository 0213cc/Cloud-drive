"""
数据库连接配置
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import get_settings

settings = get_settings()

# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {},
    echo=True  # 开发时显示SQL语句
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()


def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """初始化数据库，如果表不存在则创建表"""
    # 在这里导入所有模型，以便Base有正确的元数据
    # 否则，如果其他地方没有导入模型，create_all将不知道要创建什么表
    from app.models import user, file, share  # noqa

    # checkfirst=True 会在创建表之前检查表是否存在
    Base.metadata.create_all(bind=engine, checkfirst=True)

