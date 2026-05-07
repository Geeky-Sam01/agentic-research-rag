import json
import logging

from fastapi import APIRouter, HTTPException, Query  # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse  # type: ignore
from langchain_core.messages import AIMessage, HumanMessage

from app.models.schemas import QueryRequest
from app.services.ingest_pipeline import get_client
from app.services.langchain_agents import run_agent_query, stream_agent_query
from app.services.llm import generate_answer_structured  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Shared clients ──────────────────────────────────────────────────────────
_qdrant_client = get_client()

@router.get("/query-stream")
async def query_stream(query: str = Query(...), history: str = Query(default="[]")):
    """
    Stream query response. Pass prior conversation as JSON in 'history' param:
    [{"role": "user", "content": "..."},  {"role": "assistant", "content": "..."}]
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query is required")

    # Parse chat history from JSON query param
    chat_history = []
    try:
        raw_history = json.loads(history)
        for msg in raw_history[-10:]:  # Last 10 messages max
            role = msg.get("role", "")
            content = msg.get("content", "").strip()
            if not content:
                continue
            if role == "user":
                chat_history.append(HumanMessage(content=content))
            elif role == "assistant":
                chat_history.append(AIMessage(content=content))
    except (json.JSONDecodeError, TypeError, AttributeError):
        chat_history = []  # Ignore malformed history

    logger.info(f"Agentic Stream Query: \"{query}\" (history: {len(chat_history)} msgs)")

    async def event_generator():
        try:
            accumulated_sources = []
            async for event in stream_agent_query(query, chat_history=chat_history or None):
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

            yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"
            logger.info("Agentic stream complete")

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/query-structured")
async def query_structured(request: QueryRequest):
    """
    Wait for and return a structured JSON response via the research agent.
    """
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
        
    logger.info(f"Agentic Structured Query: \"{request.query}\"")
    
    try:
        # Step 1: Run the autonomous agent to get the ground truth / analysis
        agent_res = await run_agent_query(request.query)
        
        # Step 2: Use the structured parser to transform raw analysis into UI-friendly blocks
        # We pass the agent's output as 'context' to the formatting chain
        structured_data = await generate_answer_structured(
            request.query, 
            context=agent_res["output"],
            model_override="openrouter/free"
        )
        
        return JSONResponse(content={
            "query": request.query,
            "structuredPayload": structured_data,
            "sources": agent_res["sources"]
        })
        
    except Exception as e:
        logger.error(f"Structured Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))