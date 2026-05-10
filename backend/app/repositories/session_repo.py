import uuid
from typing import List, Optional

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import ChatSession


class SessionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_or_create(self, session_id: str, title: str = "New Chat") -> ChatSession:
        uid = uuid.UUID(session_id)
        stmt = pg_insert(ChatSession).values(id=uid, title=title).on_conflict_do_nothing()
        await self.db.execute(stmt)
        await self.db.flush()
        result = await self.db.execute(
            select(ChatSession).where(ChatSession.id == uid)
        )
        return result.scalars().first()

    async def get(self, session_id: str) -> Optional[ChatSession]:
        result = await self.db.execute(select(ChatSession).where(ChatSession.id == uuid.UUID(session_id)))
        return result.scalars().first()

    async def get_all(self, limit: int = 20) -> List[ChatSession]:
        result = await self.db.execute(
            select(ChatSession).order_by(ChatSession.updated_at.desc()).limit(limit)
        )
        return list(result.scalars().all())

    async def delete(self, session_id: str) -> None:
        await self.db.execute(delete(ChatSession).where(ChatSession.id == uuid.UUID(session_id)))
        await self.db.flush()
