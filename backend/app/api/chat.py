import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query  # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse  # type: ignore
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.db.connection import get_db
from app.db.models import ChatSession
from app.models.schemas import QueryRequest
from app.services.history_service import HistoryService
from app.services.langchain_agents import run_agent_query, stream_agent_query
from app.services.llm import generate_answer_structured  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Shared clients ──────────────────────────────────────────────────────────
_history_service = HistoryService()


def _infer_last_response_mode(chat_history: list) -> Optional[str]:
    """Infer last_response_mode from the prior AI turn.

    This avoids requiring the client to store and echo back the mode.
    Concise responses are short (<=3 lines). Analytical ones contain bullet
    points or tables. Everything else is detailed.
    """
    for msg in reversed(chat_history):
        if isinstance(msg, AIMessage) and msg.content:
            text = msg.content.strip()
            lines = [line for line in text.splitlines() if line.strip()]
            # Concise: short deterministic format (NAV card = <=5 lines)
            if len(lines) <= 5:
                return "concise"
            # Analytical: structured bullet/table output
            if any(line.lstrip().startswith(("- ", "* ", "|", "#")) for line in lines):
                return "analytical"
            return "detailed"
    return None

@router.get("/sessions")
async def get_sessions():
    """List recent sessions."""
    sessions = await _history_service.get_all_sessions(limit=20)
    return JSONResponse(content={"sessions": sessions})

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(session_id: str):
    """Get full message history for a session."""
    messages = await _history_service.get_graph_messages(session_id)
    return JSONResponse(content={"messages": messages})

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a session and all its messages."""
    try:
        uid = uuid.UUID(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session ID format")
        
    result = await db.execute(select(ChatSession).where(ChatSession.id == uid))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    await _history_service.delete_session(session_id)
    return JSONResponse(content={"success": True})


@router.get("/query-stream")
async def query_stream(
    background_tasks: BackgroundTasks,
    query: str = Query(...), 
    session_id: Optional[str] = Query(default=None)
):
    """
    Stream query response. Uses database session for history.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query is required")

    # Retrieve chat history from LangGraph purely for response mode inference
    chat_history = []
    if session_id:
        db_messages = await _history_service.get_graph_messages(session_id)
        for msg in db_messages:
            if msg["role"] == "user":
                chat_history.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                chat_history.append(AIMessage(content=msg["content"]))
    else:
        session_id = str(uuid.uuid4())
        await _history_service.create_session(session_id=session_id, title=query)
    
    # Update title immediately
    await _history_service.update_session_title(session_id, query)

    logger.info(f"Agentic Stream Query: \"{query}\" (history: {len(chat_history)} msgs)")

    # Infer last_response_mode from prior AI turn (server-side, no client cooperation needed)
    last_response_mode = _infer_last_response_mode(chat_history)

    async def event_generator():
        try:
            accumulated_sources = []
            async for event in stream_agent_query(
                query,
                last_response_mode=last_response_mode,
                session_id=session_id,
            ):
                event_type = event.get("type")

                # 1. Text chunks
                if event_type == "token":
                    content = event.get("content", "")
                    if content:
                        yield f"data: {json.dumps({'content': content})}\n\n"

                # 2. Tool calls
                elif event_type == "tool_start":
                    yield f"data: {json.dumps({'type': 'toolcall', 'tool': event.get('tool')})}\n\n"

                # 3. Agent routing/status updates
                elif event_type == "node_start":
                    yield f"data: {json.dumps({'type': 'status', 'status': event.get('display', 'Thinking...')})}\n\n"

                # 4. Collect sources (don't close stream yet)
                elif event_type == "done":
                    sources = event.get("sources", [])
                    if sources:
                        accumulated_sources.extend(sources)

                # 5. Errors
                elif event_type == "error":
                    error_msg = event.get("message", "Unknown error")
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"

            # Emit sources and [DONE] AFTER the generator is fully exhausted
            if accumulated_sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': accumulated_sources})}\n\n"
                logger.info(f"Agent consulted documents: {len(accumulated_sources)} sources emitted")

            # Wait for assistant response to finish, then save
            # For streaming, the final answer was incrementally sent. We could reconstruct it
            # But the agent `done` event should technically provide it, or we rely on the state?
            # Actually, `event` inside `isDone` checking is from the stream.
            # In LangGraph streaming, we typically just need the final AI content.
            # I will store the assistant message inside the `event_generator` after the loop.
            pass

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    # We need a wrapper to save the AI message after stream ends.
    # FastAPI StreamingResponse accepts a generator, but doesn't easily let us run async code after it yields.
    # We can wrap the generator to capture the emitted tokens.
    async def wrapped_event_generator():
        full_content = ""
        accumulated_sources = []
        try:
            async for event in stream_agent_query(
                query,
                last_response_mode=last_response_mode,
                session_id=session_id,
            ):
                event_type = event.get("type")
                if event_type == "token":
                    content = event.get("content", "")
                    if content:
                        full_content += content
                        yield f"data: {json.dumps({'content': content})}\n\n"
                elif event_type == "tool_start":
                    yield f"data: {json.dumps({'type': 'toolcall', 'tool': event.get('tool')})}\n\n"
                elif event_type == "node_start":
                    yield f"data: {json.dumps({'type': 'status', 'status': event.get('display', 'Thinking...')})}\n\n"
                elif event_type == "done":
                    sources = event.get("sources", [])
                    if sources:
                        accumulated_sources.extend(sources)
                elif event_type == "error":
                    error_msg = event.get("message", "Unknown error")
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"

            if accumulated_sources:
                yield f"data: {json.dumps({'type': 'sources', 'sources': accumulated_sources})}\n\n"
            yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"
            
            # Stream is fully done, LangGraph already saved the state natively!
            pass

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(wrapped_event_generator(), media_type="text/event-stream")


@router.post("/query-structured")
async def query_structured(request: QueryRequest):
    """
    Wait for and return a structured JSON response via the research agent.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
        
    logger.info(f"Agentic Structured Query: \"{request.query}\"")
    
    try:
        session_id = request.session_id if hasattr(request, 'session_id') else None
        
        # Load history from DB purely for context mode
        chat_history = []
        if session_id:
            db_messages = await _history_service.get_graph_messages(session_id)
            for msg in db_messages:
                if msg["role"] == "user":
                    chat_history.append(HumanMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    chat_history.append(AIMessage(content=msg["content"]))
        else:
            session_id = str(uuid.uuid4())
            await _history_service.create_session(session_id=session_id, title=request.query)

        await _history_service.update_session_title(session_id, request.query)
    except Exception as e:
        import traceback
        with open("error.log", "w") as f:
            f.write(traceback.format_exc())
        raise e
    
    try:
        # Step 1: Run the autonomous agent to get the ground truth / analysis
        last_response_mode = _infer_last_response_mode(chat_history)
        agent_res = await run_agent_query(
            request.query,
            last_response_mode=last_response_mode,
            session_id=session_id,
        )
        
        # Step 2: Use the structured parser to transform raw analysis into UI-friendly blocks
        # We pass the agent's output as 'context' to the formatting chain
        structured_data = await generate_answer_structured(
            request.query, 
            context=agent_res["output"],
            model_override="openrouter/free"
        )
        
        return {
            "answer": structured_data.answer,
            "data": structured_data.data,
            "sources": agent_res["sources"],
            "pipeline_meta": {
                "tasks_run": len(agent_res.get("query_plan", {}).get("tasks", [])),
                "confidence": agent_res.get("confidence_score", 0.8),
                "mode": last_response_mode
            }
        }
    except Exception as e:
        import traceback
        with open("error.log", "a") as f:
            f.write(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))