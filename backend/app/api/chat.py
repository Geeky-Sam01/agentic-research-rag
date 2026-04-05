from fastapi import APIRouter, HTTPException, Query  # type: ignore
from fastapi.responses import StreamingResponse  # type: ignore
import logging
import json
from typing import Optional
from sentence_transformers import SentenceTransformer  # type: ignore

from app.core.config import settings  # type: ignore
from app.services.injest import get_client, query_qdrant  # type: ignore
from app.services.embeddings import model as _embedder  # type: ignore
from app.services.llm import generate_answer, generate_answer_stream  # type: ignore
from app.models.schemas import QueryRequest, QueryResponse, Source  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])


# ── Shared clients (initialised once at import time) ─────────────────────────
_qdrant_client = get_client()
# _embedder is now imported from embeddings service


@router.post("/query")
async def query(request: QueryRequest) -> QueryResponse:
    """Query the RAG system."""
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    
    logger.info(f"\n🔍 Query: \"{request.query}\"")
    
    try:
        # 🔹 Step 1: Search Qdrant
        results = query_qdrant(
            query    = request.query,
            client   = _qdrant_client,
            embedder = _embedder,
            top_k    = 5
        )
        
        if not results:
            logger.info("⚠️ No relevant documents found")
            return QueryResponse(
                query=request.query,
                answer="I could not find any relevant documents in the knowledge base. Please upload documents first.",
                sources=[],
                resultsFound=0,
                model=settings.LLM_MODEL,
                embedding=settings.EMBEDDING_MODEL
            )
        
        logger.info(f"📚 Found {len(results)} relevant chunks")
        
        # 🔹 Step 2: Build Context
        # Every chunk already contains "Heading\n\nBody" so context is self-contained.
        context = "\n\n---\n\n".join([r["text"] for r in results])
        
        # 🔹 Step 3: Generate answer
        logger.info("⏳ Generating answer...")
        answer = await generate_answer(request.query, context)
        logger.info("✅ Answer generated")
        
        sources = [
            Source(
                text=r['text'][:200] + ("..." if len(r['text']) > 200 else ""),
                source=f"{r['file']} - p.{r['page']}" if r.get('page') else str(r['file']),
                similarity=f"{r['score']*100:.1f}%"
            )
            for r in results
        ]
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources,
            resultsFound=len(results),
            model=settings.LLM_MODEL,
            embedding=settings.EMBEDDING_MODEL
        )
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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