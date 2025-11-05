import json
from typing import List, Optional
from sqlalchemy import select, desc, or_
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from database import TranscriptionSessionDB
from models import TranscriptionSession


async def create_session(db: AsyncSession, session: TranscriptionSession) -> TranscriptionSessionDB:
    """创建新的转录会话"""
    # 计算统计信息
    word_count = len(session.full_transcript.split()) if session.full_transcript else 0
    speaker_count = len(set(seg.speaker for seg in session.segments))

    # 创建数据库记录
    db_session = TranscriptionSessionDB(
        session_id=session.session_id,
        title=session.title,
        created_at=session.created_at,
        updated_at=datetime.utcnow(),
        status=session.status,
        segments_json=json.dumps([seg.model_dump() for seg in session.segments]),
        full_transcript=session.full_transcript,
        duration_seconds=0.0,  # 可以从最后一个 segment 的时间计算
        speaker_count=speaker_count,
        word_count=word_count
    )

    # 计算持续时间
    if session.segments:
        last_segment = session.segments[-1]
        db_session.duration_seconds = last_segment.end_time / 1000.0

    db.add(db_session)
    await db.commit()
    await db.refresh(db_session)
    return db_session


async def update_session(
    db: AsyncSession,
    session_id: str,
    session: TranscriptionSession
) -> Optional[TranscriptionSessionDB]:
    """更新转录会话"""
    result = await db.execute(
        select(TranscriptionSessionDB).where(TranscriptionSessionDB.session_id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        return None

    # 更新数据
    word_count = len(session.full_transcript.split()) if session.full_transcript else 0
    speaker_count = len(set(seg.speaker for seg in session.segments))

    db_session.title = session.title
    db_session.status = session.status
    db_session.segments_json = json.dumps([seg.model_dump() for seg in session.segments])
    db_session.full_transcript = session.full_transcript
    db_session.word_count = word_count
    db_session.speaker_count = speaker_count
    db_session.updated_at = datetime.utcnow()

    # 更新持续时间
    if session.segments:
        last_segment = session.segments[-1]
        db_session.duration_seconds = last_segment.end_time / 1000.0

    await db.commit()
    await db.refresh(db_session)
    return db_session


async def get_session(db: AsyncSession, session_id: str) -> Optional[TranscriptionSessionDB]:
    """获取单个会话"""
    result = await db.execute(
        select(TranscriptionSessionDB).where(TranscriptionSessionDB.session_id == session_id)
    )
    return result.scalar_one_or_none()


async def get_sessions(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None
) -> List[TranscriptionSessionDB]:
    """获取会话列表"""
    query = select(TranscriptionSessionDB)

    # 搜索功能
    if search:
        query = query.where(
            or_(
                TranscriptionSessionDB.title.contains(search),
                TranscriptionSessionDB.full_transcript.contains(search)
            )
        )

    # 按创建时间倒序
    query = query.order_by(desc(TranscriptionSessionDB.created_at))

    # 分页
    query = query.offset(skip).limit(limit)

    result = await db.execute(query)
    return result.scalars().all()


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    """删除会话"""
    result = await db.execute(
        select(TranscriptionSessionDB).where(TranscriptionSessionDB.session_id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        return False

    await db.delete(db_session)
    await db.commit()
    return True


async def update_ai_summary(
    db: AsyncSession,
    session_id: str,
    summary: str
) -> Optional[TranscriptionSessionDB]:
    """更新 AI 总结"""
    result = await db.execute(
        select(TranscriptionSessionDB).where(TranscriptionSessionDB.session_id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        return None

    db_session.ai_summary = summary
    db_session.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(db_session)
    return db_session


async def update_ai_action_items(
    db: AsyncSession,
    session_id: str,
    action_items: str
) -> Optional[TranscriptionSessionDB]:
    """更新 AI 待办事项"""
    result = await db.execute(
        select(TranscriptionSessionDB).where(TranscriptionSessionDB.session_id == session_id)
    )
    db_session = result.scalar_one_or_none()

    if not db_session:
        return None

    db_session.ai_action_items = action_items
    db_session.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(db_session)
    return db_session


async def get_session_count(db: AsyncSession, search: Optional[str] = None) -> int:
    """获取会话总数"""
    from sqlalchemy import func

    query = select(func.count(TranscriptionSessionDB.id))

    if search:
        query = query.where(
            or_(
                TranscriptionSessionDB.title.contains(search),
                TranscriptionSessionDB.full_transcript.contains(search)
            )
        )

    result = await db.execute(query)
    return result.scalar() or 0
