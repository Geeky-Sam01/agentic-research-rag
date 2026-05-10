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

    async def get_graph_messages(self, session_id: str) -> List[dict]:
        from app.services.langchain_agents import get_pipeline
        from langchain_core.messages import AIMessage, HumanMessage
        import uuid
        from datetime import datetime

        graph = get_pipeline()
        config = {"configurable": {"thread_id": session_id}}
        try:
            state = await graph.aget_state(config)
            if not state or not state.values:
                return []
            
            messages = state.values.get("messages", [])
            formatted = []
            for m in messages:
                # Skip SystemMessages and ToolMessages for UI
                if not isinstance(m, (AIMessage, HumanMessage)):
                    continue
                
                role = "assistant" if isinstance(m, AIMessage) else "user"
                
                # Check for sources if it's an AI message
                sources = []
                if isinstance(m, AIMessage):
                    # We might have stored sources in a different way, but for now we just return empty list
                    # if it's not present. The frontend expects them in metadata.sources
                    sources = []

                formatted.append({
                    "id": m.id or str(uuid.uuid4()),
                    "role": role,
                    "content": str(m.content) if m.content else "",
                    "metadata": {"sources": sources},
                    "created_at": datetime.utcnow().isoformat()
                })
            return formatted
        except Exception as e:
            logger.error(f"Failed to fetch graph messages: {e}", exc_info=True)
            return []
            
    async def update_session_title(self, session_id: str, title: str) -> None:
        async with AsyncSessionFactory() as db:
            session_repo = SessionRepository(db)
            session = await session_repo.get(session_id)
            if session and session.title == "New Chat":
                session.title = title[:40] + ("..." if len(title) > 40 else "")
                await db.commit()
