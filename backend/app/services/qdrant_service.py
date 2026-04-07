import logging
import uuid
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance, VectorParams,
    PointStruct, Filter, FieldCondition, MatchValue,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  CONFIG
# ------------------------------------------------------------------ #

COLLECTION_NAME = "financial_docs"

# ------------------------------------------------------------------ #
#  CLIENT + COLLECTION SETUP
# ------------------------------------------------------------------ #

_client_instance: Optional[QdrantClient] = None

def get_client() -> QdrantClient:
    """Initializes and returns a singleton Qdrant client."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance
        
    logger.info("Initializing SINGLETON Qdrant client (local mode)")
    _client_instance = QdrantClient(path="qdrant_db")
    return _client_instance


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )
        print(f"Created collection: {COLLECTION_NAME}")
    else:
        print(f"Collection already exists: {COLLECTION_NAME}")


# ------------------------------------------------------------------ #
#  RETRIEVAL
# ------------------------------------------------------------------ #

def query_qdrant(
    query:     str,
    client:    QdrantClient,
    embedder:  Any,
    fund_name: Optional[str]  = None,
    doc_type:  Optional[str]  = None,
    period:    Optional[str]  = None,
    top_k:     int  = 8,
) -> List[Dict[str, Any]]:
    """
    Vector search with optional metadata filters.
    """
    # BGE query prefix improves retrieval quality
    query_vector = embedder.encode(f"Represent this sentence for searching relevant passages: {query}").tolist()

    # Build payload filter from whichever fields are provided
    must_conditions = []
    if fund_name:
        must_conditions.append(FieldCondition(key="fund_name", match=MatchValue(value=fund_name)))
    if doc_type:
        must_conditions.append(FieldCondition(key="doc_type",  match=MatchValue(value=doc_type)))
    if period:
        must_conditions.append(FieldCondition(key="period",    match=MatchValue(value=period)))

    search_filter = Filter(must=must_conditions) if must_conditions else None

    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        ).points
    except AttributeError:
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        )

    return [
        {
            "score":   r.score,
            "text":    r.payload.get("text", ""),
            "page":    r.payload.get("page"),
            "heading": r.payload.get("heading"),
            "is_table":r.payload.get("is_table"),
            "fund":    r.payload.get("fund_name"),
            "period":  r.payload.get("period"),
            "file":    r.payload.get("source_file"),
        }
        for r in results
    ]


# ------------------------------------------------------------------ #
#  MANAGEMENT ( Stats, Clear, Delete )
# ------------------------------------------------------------------ #

def delete_document(file_name: str, client: QdrantClient) -> None:
    """Deletes all points for a given source_file before re-ingesting."""
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="source_file", match=MatchValue(value=file_name))]
        ),
    )
    print(f"Deleted all points for {file_name}")


def clear_collection(client: QdrantClient) -> bool:
    """Definitively wipes the entire collection from Qdrant."""
    try:
        logger.info(f"REQUESTED FULL CLEAR for collection: {COLLECTION_NAME}")
        
        try:
            client.delete_collection(collection_name=COLLECTION_NAME)
            logger.info(f"Dropped collection: {COLLECTION_NAME}")
        except Exception as e:
            logger.warning(f"Could not drop collection '{COLLECTION_NAME}': {e}. Trying scroll-delete.")
            
        import time
        time.sleep(0.5)
        ensure_collection(client)
            
        logger.info(f"Successfully cleared {COLLECTION_NAME}")
        return True
    except Exception as e:
        logger.error(f"DEEP CLEAR FAILED: {e}")
        return False


def get_collection_stats(client: QdrantClient) -> Dict[str, Any]:
    """Retrieves basic stats and unique source files from Qdrant."""
    try:
        info = client.get_collection(collection_name=COLLECTION_NAME)
        count = info.points_count if hasattr(info, 'points_count') else 0
        
        sources = set()
        scroll_results, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        for point in scroll_results:
            if point.payload:
                fname = (
                    point.payload.get("source_file") or 
                    point.payload.get("file") or 
                    point.payload.get("source") or
                    point.payload.get("filename")
                )
                if fname:
                    sources.add(fname)

        return {
            "vectors": count,
            "sources": sorted(list(sources)),
            "status":  str(info.status),
        }
    except Exception as e:
        print(f"Failed to get stats: {e}")
        return {"vectors": 0, "sources": [], "status": "error"}
