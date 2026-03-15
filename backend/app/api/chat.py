from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import logging
import json

from app.core.config import settings
from app.services.embeddings import get_embedding
from app.services.faiss_service import faiss_manager
from app.services.llm import generate_answer, generate_answer_stream
from app.models.schemas import QueryRequest, QueryResponse, Source

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/chat", tags=["chat"])

@router.post("/query")
async def query(request: QueryRequest) -> QueryResponse:
    """Query the RAG system."""
    
    if not request.query or not request.query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    
    logger.info(f"\n🔍 Query: \"{request.query}\"")
    
    try:
        # Get query embedding
        query_embedding = await get_embedding(request.query)
        logger.info("✅ Generated query embedding")
        
        # Search FAISS
        results = faiss_manager.search(query_embedding, k=5)
        
        if not results:
            logger.info("⚠️ No relevant documents found")
            return QueryResponse(
                query=request.query,
                answer="I could not find any relevant documents to answer this question. Please upload documents first and ask questions about their content.",
                sources=[],
                resultsFound=0,
                model=settings.LLM_MODEL,
                embedding=settings.EMBEDDING_MODEL
            )
        
        logger.info(f"📚 Found {len(results)} relevant chunks")
        
        # Build context using PDR
        context_parts = []
        for r in results:
            doc = r['document']
            parent_text = faiss_manager.get_parent_text(doc['source'], doc.get('parent_id'))
            
            # Use parent text if available, otherwise fallback to child chunk
            text_to_use = parent_text if parent_text else doc['text']
            context_parts.append(
                f"[Document: {doc['source']} - Similarity: {r['similarity']*100:.1f}%]\n{text_to_use}"
            )
            
        context = "\n\n---\n\n".join(context_parts)
        
        # Generate answer
        logger.info("⏳ Generating answer...")
        answer = await generate_answer(request.query, context)
        
        logger.info("✅ Answer generated")
        
        sources = [
            Source(
                text=r['document']['text'][:150] + "...",
                source=r['document']['source'],
                similarity=f"{r['similarity']*100:.1f}%"
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
async def query_stream(query: str = Query(...)):
    """Stream query response."""
    
    if not query or not query.strip():
        raise HTTPException(status_code=400, detail="Query is required")
    
    logger.info(f"\n🔍 Stream Query: \"{query}\"")
    
    async def event_generator():
        try:
            # Get query embedding
            query_embedding = await get_embedding(query)
            logger.info("✅ Generated query embedding")
            
            # Search FAISS
            results = faiss_manager.search(query_embedding, k=5)
            
            if not results:
                yield f"data: {json.dumps({'content': 'No relevant documents found. Please upload documents first.'})}\n\n"
                return
            
            logger.info(f"📚 Found {len(results)} relevant chunks")
            
            # Build context using PDR
            context_parts = []
            for r in results:
                doc = r['document']
                parent_text = faiss_manager.get_parent_text(doc['source'], doc.get('parent_id'))
                text_to_use = parent_text if parent_text else doc['text']
                context_parts.append(f"[Document: {doc['source']}]\n{text_to_use}")
                
            context = "\n\n---\n\n".join(context_parts)
            
            # Stream answer
            logger.info("⏳ Streaming answer...")
            async for chunk in generate_answer_stream(query, context):
                yield f"data: {json.dumps({'content': chunk})}\n\n"
            
            yield f"data: {json.dumps({'content': '[DONE]'})}\n\n"
            logger.info("✅ Streaming complete")
            
        except Exception as e:
            logger.error(f"Stream error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")
