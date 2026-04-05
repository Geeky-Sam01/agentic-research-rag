from fastapi import APIRouter, HTTPException, Query  # type: ignore
from fastapi.responses import StreamingResponse, JSONResponse  # type: ignore
import logging
import json
from typing import Optional
from sentence_transformers import SentenceTransformer  # type: ignore

from app.core.config import settings  # type: ignore
from app.services.injest import get_client, query_qdrant  # type: ignore
from app.services.embeddings import model as _embedder  # type: ignore
from app.services.llm import generate_answer_stream, generate_answer_structured  # type: ignore
from app.models.schemas import QueryRequest, QueryResponse, Source  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Shared clients (initialised once at import time) ─────────────────────────
_qdrant_client = get_client()
# _embedder is now imported from embeddings service


@router.get("/query-stream")
async def query_stream(query: str = Query(...), model: Optional[str] = None):
    """Stream query response with proper PDR context."""

    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query is required")

    logger.info(f"\n Stream Query: \"{query}\"")

    async def event_generator():
        try:
            # 🔹 Step 1: SEARCH QDRANT
            results = query_qdrant(
                query    = query,
                client   = _qdrant_client,
                embedder = _embedder,
                top_k    = 8
            )

            if not results:
                yield f"data: {json.dumps({'content': 'No relevant documents found.'})}\n\n"
                return

            logger.info(f"📚 Found {len(results)} relevant chunks")

            # 🔹 Step 2: Build context
            context = "\n\n---\n\n".join([r["text"] for r in results])

            # 🔹 Step 3: Format Sources (Deduplicated for UI tags)
            sources_payload = []
            seen_sources = set()
            for r in results:
                source_label = f"{r['file']} - p.{r['page']}" if r.get('page') else str(r['file'])
                
                # We still want to show the full list of chunks in the evidence panel if needed,
                # but for the citations list (sources_payload), deduplication is better.
                if source_label not in seen_sources:
                    sources_payload.append({
                        "text":    r["text"][:200] + ("..." if len(r["text"]) > 200 else ""),
                        "source":  source_label,
                        "similarity": f"{r['score']*100:.1f}%"
                    })
                    seen_sources.add(source_label)

            # 🔹 Step 5: Emit sources first
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources_payload})}\n\n"
            logger.info(f" Emitted deduplicated sources: {len(sources_payload)} items")

            # 🔹 Step 6: Stream answer using CLEAN context and optional model override
            logger.info(f"⏳ Streaming answer (override={model})...")

            async for chunk in generate_answer_stream(query, context, model_override=model):
                yield f"data: {json.dumps({'content': chunk})}\n\n"

            yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"
            logger.info("✅ Streaming complete")

        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/query-structured")
async def query_structured(request: QueryRequest):
    """Wait for and return a structured JSON response."""
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
        
    logger.info(f"\n Structured Query: \"{request.query}\"")
    
    try:
        # Step 1: SEARCH QDRANT
        results = query_qdrant(
            query    = request.query,
            client   = _qdrant_client,
            embedder = _embedder,
            top_k    = 8
        )
        
        sources_payload = []
        if results:
            # Build context
            context = "\n\n---\n\n".join([r["text"] for r in results])
            
            # Format Sources (Deduplicated for UI tags)
            seen_sources = set()
            for r in results:
                source_label = f"{r['file']} - p.{r['page']}" if r.get('page') else str(r['file'])
                if source_label not in seen_sources:
                    sources_payload.append({
                        "text":    r["text"][:200] + ("..." if len(r["text"]) > 200 else ""),
                        "source":  source_label,
                        "similarity": f"{r['score']*100:.1f}%"
                    })
                    seen_sources.add(source_label)
        else:
            context = "No relevant context found."

        # Step 2: Generate Answer
        logger.info(f"⏳ Generating structured answer (override=openrouter/free)...")
        structured_data = await generate_answer_structured(
            request.query, 
            context,
            model_override="openrouter/free"
        )
        
        # We return the structured payload, plus the sources that the frontend expects
        return JSONResponse(content={
            "query": request.query,
            "structuredPayload": structured_data,
            "sources": sources_payload
        })
        
    except Exception as e:
        logger.error(f"Structured Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))