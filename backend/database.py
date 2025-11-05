from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean
from datetime import datetime
import os

# 数据库配置
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./transcriptions.db")

# 创建异步引擎
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    future=True
)

# 创建会话工厂
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# 基础模型
Base = declarative_base()


class TranscriptionSessionDB(Base):
    """转录会话数据库模型"""
    __tablename__ = "transcription_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(36), unique=True, index=True, nullable=False)
    title = Column(String(200), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    status = Column(String(20), default="active", nullable=False)

    # 转录内容（JSON 格式存储）
    segments_json = Column(Text, nullable=False, default="[]")
    full_transcript = Column(Text, nullable=False, default="")

    # 元数据
    duration_seconds = Column(Float, default=0.0)
    speaker_count = Column(Integer, default=0)
    word_count = Column(Integer, default=0)

    # AI 分析结果（可选）
    ai_summary = Column(Text, nullable=True)
    ai_action_items = Column(Text, nullable=True)


# 数据库依赖
async def get_db():
    """获取数据库会话"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """初始化数据库"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
