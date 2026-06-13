"""
数据库连接配置
"""
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from .config import settings


# 创建异步引擎
engine = create_async_engine(
    settings.database_url,
    echo=settings.LOG_LEVEL == "DEBUG",
    pool_size=10,
    max_overflow=20
)


# 创建异步会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)


class Base(DeclarativeBase):
    """SQLAlchemy 声明性基类"""
    pass
