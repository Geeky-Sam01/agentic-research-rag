from typing import List, Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import ChatMessage, ChatSession

class MessageRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self, 
        session_id: str, 
        role: str, 
        content: str, 
        metadata: Optional[dict] = None,
        msg_id: Optional[str] = None
    ) -> ChatMessage:
        msg = ChatMessage(
            id=uuid.UUID(msg_id) if msg_id else uuid.uuid4(),
            session_id=uuid.UUID(session_id),
            role=role,
            content=content,
            metadata_=metadata or {}
        )
        self.db.add(msg)
        await self.db.flush()
        return msg

    async def get_by_session(self, session_id: str) -> List[tuple]:
        result = await self.db.execute(
            select(
                ChatMessage.id,
                ChatMessage.role,
                ChatMessage.content,
                ChatMessage.metadata_,
                ChatMessage.created_at
            )
            .where(ChatMessage.session_id == uuid.UUID(session_id))
            .order_by(ChatMessage.created_at.asc())
        )
        return list(result.all())
