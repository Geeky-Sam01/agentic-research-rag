import logging
import os
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    VectorParams,
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
_collection_ensured: bool = False


def get_client() -> QdrantClient:
    """Initializes and returns a singleton Qdrant client."""
    global _client_instance, _collection_ensured
    if _client_instance is not None:
        if not _collection_ensured:
            ensure_collection(_client_instance)
            _collection_ensured = True
        return _client_instance

    # Option 1: Qdrant Cloud (preferred for prod if set)
    if settings.QDRANT_API_KEY and settings.QDRANT_END_POINT:
        logger.info(f"Initializing Qdrant Cloud client (endpoint: {settings.QDRANT_END_POINT})")
        _client_instance = QdrantClient(
            url=settings.QDRANT_END_POINT,
            api_key=settings.QDRANT_API_KEY,
        )
    # Option 2: Local persistent storage (standard for Railway Volume)
    else:
        # Default path is qdrant_db (matches Railway Volume mount point suggestion)
        qdrant_path = os.environ.get("QDRANT_PATH", "qdrant_db")
        logger.info(f"Initializing persistent local Qdrant client at: {qdrant_path}")
        _client_instance = QdrantClient(path=qdrant_path)

    if not _collection_ensured:
        ensure_collection(_client_instance)
        _collection_ensured = True

    return _client_instance


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )
        logger.info(f"Created collection: {COLLECTION_NAME}")
    else:
        logger.info(f"Collection already exists: {COLLECTION_NAME}")


# ------------------------------------------------------------------ #
#  RETRIEVAL
# ------------------------------------------------------------------ #


def query_qdrant(
    query: str,
    client: QdrantClient,
    embedder: Any,
    fund_name: Optional[str] = None,
    doc_type: Optional[str] = None,
    period: Optional[str] = None,
    top_k: int = 8,
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
        must_conditions.append(FieldCondition(key="doc_type", match=MatchValue(value=doc_type)))
    if period:
        must_conditions.append(FieldCondition(key="period", match=MatchValue(value=period)))

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
            "score": r.score,
            "text": r.payload.get("text", ""),
            "page": r.payload.get("page"),
            "heading": r.payload.get("heading"),
            "is_table": r.payload.get("is_table"),
            "fund": r.payload.get("fund_name"),
            "period": r.payload.get("period"),
            "file": r.payload.get("source_file"),
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
        points_selector=Filter(must=[FieldCondition(key="source_file", match=MatchValue(value=file_name))]),
    )
    logger.info(f"Deleted all points for {file_name}")


def clear_collection(client: QdrantClient) -> bool:
    """Wipe all points from the collection.

    Strategy:
      1. Try drop + recreate (works for local / admin-scoped keys).
      2. If that fails (scoped Cloud API key), fall back to scroll-all
         point IDs and batch-delete them (only requires rw access).
    """
    import time

    try:
        logger.info(f"REQUESTED FULL CLEAR for collection: {COLLECTION_NAME}")

        # ── Attempt 1: drop + recreate (fastest, needs admin rights) ──
        try:
            client.delete_collection(collection_name=COLLECTION_NAME)
            logger.info(f"Dropped collection: {COLLECTION_NAME}")
            time.sleep(0.5)
            ensure_collection(client)
            logger.info(f"Successfully cleared and recreated {COLLECTION_NAME}")
            return True
        except Exception as drop_err:
            logger.warning(
                f"drop_collection failed (likely scoped API key): {drop_err}. "
                "Falling back to scroll-delete."
            )

        # ── Attempt 2: scroll all IDs and delete in batches ──────────
        deleted_total = 0
        offset = None

        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=500,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            points, next_offset = scroll_result
            if not points:
                break

            ids = [p.id for p in points]
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=PointIdsList(points=ids),
            )
            deleted_total += len(ids)
            logger.info(f"Deleted batch of {len(ids)} points ({deleted_total} total)")

            if next_offset is None:
                break
            offset = next_offset

        logger.info(f"Scroll-delete finished — removed {deleted_total} points from {COLLECTION_NAME}")
        return True

    except Exception as e:
        logger.error(f"DEEP CLEAR FAILED: {e}")
        return False


def get_collection_stats(client: QdrantClient) -> Dict[str, Any]:
    """Retrieves basic stats and unique source files from Qdrant."""
    try:
        info = client.get_collection(collection_name=COLLECTION_NAME)
        count = info.points_count if hasattr(info, "points_count") else 0

        sources = set()
        scroll_results, _ = client.scroll(
            collection_name=COLLECTION_NAME, limit=1000, with_payload=True, with_vectors=False
        )
        for point in scroll_results:
            if point.payload:
                fname = (
                    point.payload.get("source_file")
                    or point.payload.get("file")
                    or point.payload.get("source")
                    or point.payload.get("filename")
                )
                if fname:
                    sources.add(fname)

        return {
            "vectors": count,
            "sources": sorted(list(sources)),
            "status": str(info.status),
        }
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        return {"vectors": 0, "sources": [], "status": "error"}
