import json
import logging

from fastapi import APIRouter, HTTPException, Query  # type: ignore
from fastapi.responses import JSONResponse, StreamingResponse  # type: ignore

from app.models.schemas import QueryRequest
from app.services.ingest_pipeline import get_client
from app.services.langchain_agents import run_agent_query, stream_agent_query
from app.services.llm import generate_answer_structured  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

# ── Shared clients ──────────────────────────────────────────────────────────
_qdrant_client = get_client()

@router.get("/query-stream")
async def query_stream(query: str = Query(...)):
    """
    Stream query response using the autonomous research agent.
    The agent dynamically decides between RAG (Factsheets) and live MF API.
    """
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query is required")

    logger.info(f"Agentic Stream Query: \"{query}\"")

    async def event_generator():
        try:
            async for event in stream_agent_query(query):
                kind = event["event"]
                
                # 1. Text chunks from the model
                if kind == "on_chat_model_stream":
                    content = event["data"]["chunk"].content
                    if content:
                        yield f"data: {json.dumps({'content': content})}\n\n"
                
                # 2. Tool calls (Start of action)
                elif kind == "on_tool_start":
                    yield f"data: {json.dumps({
                        'type': 'toolcall', 
                        'tool': event['name'], 
                        'input': event['data'].get('input')
                    })}\n\n"
                
                # 3. Tool outputs (End of action - Intercept 'read_factsheet' to emit sources)
                elif kind == "on_tool_end":
                    if event["name"] == "read_factsheet":
                        output = event["data"]["output"]
                        if isinstance(output, dict) and "sources" in output:
                            sources = output["sources"]
                            yield f"data: {json.dumps({'type': 'sources', 'sources': sources})}\n\n"
                            logger.info(f"Agent consulted documents: {len(sources)} sources emitted")

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