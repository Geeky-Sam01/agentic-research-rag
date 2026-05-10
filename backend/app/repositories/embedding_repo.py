import uuid
from typing import List

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.models import ChatMessage


class EmbeddingRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(self, message_id: str, session_id: str, embedding: List[float]) -> None:
        """Upsert the embedding vector for a given message id."""
        # Using SQLAlchemy update to only modify the embedding
        stmt = (
            update(ChatMessage)
            .where(ChatMessage.id == uuid.UUID(message_id))
            .values(embedding=embedding)
        )
        await self.db.execute(stmt)

    async def search_similar(self, query_embedding: List[float], session_id: str, top_k: int = 3):
        # Only search messages that have embeddings (guard against missing embeddings)
        uid = uuid.UUID(session_id)
        result = await self.db.execute(
            select(ChatMessage)
            .where(
                ChatMessage.session_id == uid,
                ChatMessage.embedding.is_not(None)
            )
            .order_by(ChatMessage.embedding.cosine_distance(query_embedding))
            .limit(top_k)
        )
        return list(result.scalars().all())
