import asyncio
import logging
from typing import List, Optional, Tuple
import uuid

from app.db.connection import AsyncSessionFactory
from app.repositories.session_repo import SessionRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.embedding_repo import EmbeddingRepository
from app.services.embeddings import get_embedding

logger = logging.getLogger(__name__)

class HistoryService:
    async def create_session(self, session_id: str, title: str = "New Chat") -> str:
        async with AsyncSessionFactory() as db:
            repo = SessionRepository(db)
            session = await repo.get_or_create(session_id, title)
            await db.commit()
            return str(session.id)

    async def get_session(self, session_id: str) -> Optional[dict]:
        async with AsyncSessionFactory() as db:
            repo = SessionRepository(db)
            session = await repo.get(session_id)
            if not session:
                return None
            return {
                "id": str(session.id),
                "title": session.title,
                "metadata": session.metadata_,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat()
            }

    async def get_all_sessions(self, limit: int = 20) -> List[dict]:
        async with AsyncSessionFactory() as db:
            repo = SessionRepository(db)
            sessions = await repo.get_all(limit)
            return [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat()
                }
                for s in sessions
            ]

    async def delete_session(self, session_id: str) -> None:
        async with AsyncSessionFactory() as db:
            repo = SessionRepository(db)
            await repo.delete(session_id)
            await db.commit()

    async def get_messages(self, session_id: str) -> List[dict]:
        async with AsyncSessionFactory() as db:
            repo = MessageRepository(db)
            messages = await repo.get_by_session(session_id)
            return [
                {
                    "id": str(m[0]),
                    "role": m[1],
                    "content": m[2],
                    "metadata": m[3],
                    "created_at": m[4].isoformat()
                }
                for m in messages
            ]

    async def add_message(
        self, session_id: str, role: str, content: str, metadata: Optional[dict] = None
    ) -> str:
        async with AsyncSessionFactory() as db:
            repo = MessageRepository(db)
            msg = await repo.create(session_id, role, content, metadata)
            
            # If this is a user message and session title is "New Chat", update it
            if role == 'user':
                session_repo = SessionRepository(db)
                session = await session_repo.get(session_id)
                if session and session.title == "New Chat":
                    session.title = content[:40] + ("..." if len(content) > 40 else "")
            
            await db.commit()
            return str(msg.id)

    async def _embed_messages(
        self,
        session_id: str,
        human_msg_id: str,
        human_content: str,
        ai_msg_id: str,
        ai_content: str,
    ) -> None:
        """Background task: embed and store both turns."""
        try:
            # get_embedding is already async — call directly, no to_thread wrapper needed
            human_emb, ai_emb = await asyncio.gather(
                get_embedding(human_content),
                get_embedding(ai_content),
            )

            async with AsyncSessionFactory() as db:
                emb_repo = EmbeddingRepository(db)
                await emb_repo.upsert(human_msg_id, session_id, human_emb)
                await emb_repo.upsert(ai_msg_id, session_id, ai_emb)
                await db.commit()

        except Exception as e:
            logger.error(f"Embedding background task failed: {e}", exc_info=True)

    def trigger_embedding_task(
        self,
        session_id: str,
        human_msg_id: str,
        human_content: str,
        ai_msg_id: str,
        ai_content: str,
    ):
        """Helper to fire off the background task."""
        asyncio.create_task(
            self._embed_messages(
                session_id=session_id,
                human_msg_id=human_msg_id,
                human_content=human_content,
                ai_msg_id=ai_msg_id,
                ai_content=ai_content,
            )
        )
