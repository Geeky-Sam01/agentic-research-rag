import logging
import json
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient

from app.services.qdrant_service import query_qdrant

logger = logging.getLogger(__name__)

def get_rag_context(
    query: str,
    client: QdrantClient,
    embedder: Any,
    top_k: int = 8
) -> Dict[str, Any]:
    """
    Consolidated RAG retrieval pipeline (Steps 1, 2, 3).
    Returns context string and formatted sources.
    """
    # 🔹 Step 1: SEARCH QDRANT
    results = query_qdrant(
        query=query,
        client=client,
        embedder=embedder,
        top_k=top_k
    )

    if not results:
        return {
            "context": "No relevant documents found.",
            "sources": [],
            "raw_results_count": 0
        }

    # 🔹 Step 2: Build context (Combining table metadata with text for the LLM)
    context_parts = []
    for r in results:
        part = f"Source: {r['file']} (Page {r['page']})\nSection: {r['heading']}\n"
        if r.get('is_table'):
             part += f"[DATA-TABLE]: {r['text']}"
        else:
             part += r['text']
        context_parts.append(part)

    context = "\n\n---\n\n".join(context_parts)

    # 🔹 Step 3: Format Citations (Deduplicated for UI tags)
    sources_payload = []
    seen_sources = set()
    for r in results:
        source_label = f"{r['file']} - p.{r['page']}" if r.get('page') else str(r['file'])
        if source_label not in seen_sources:
            sources_payload.append({
                "text": r["text"][:200] + ("..." if len(r["text"]) > 200 else ""),
                "source": source_label,
                "similarity": f"{r['score']*100:.1f}%"
            })
            seen_sources.add(source_label)

    return {
        "context": context,
        "sources": sources_payload,
        "raw_results_count": len(results)
    }
