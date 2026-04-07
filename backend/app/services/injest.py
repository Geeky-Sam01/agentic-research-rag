"""
ingest.py — Qdrant ingestion pipeline for financial factsheets.

Usage:
    python ingest.py --file ppfas-factsheet-jan-2025.pdf \
                     --fund "Parag Parikh Flexi Cap Fund"  \
                     --doc-type factsheet                  \
                     --period 2025-01
"""

import uuid
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from qdrant_client import QdrantClient  # type: ignore
from qdrant_client.models import (  # type: ignore
    Distance, VectorParams,
    PointStruct, Filter, FieldCondition, MatchValue,
)
from app.services.embeddings import model as _embedder  # type: ignore

from app.services.document_processor import extract_text_from_file, chunk_structured_document  # type: ignore

from app.core.config import settings  # type: ignore

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
        
    # Use Local by default:
    logger = logging.getLogger(__name__)
    logger.info("Initializing SINGLETON Qdrant client (local mode)")
    _client_instance = QdrantClient(path="qdrant_db")
    return _client_instance


def ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    
    # Check if the collection exists but has wrong dimension? We assume correct dimension for now.
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=settings.EMBEDDING_DIM, distance=Distance.COSINE),
        )
        print(f"✅ Created collection: {COLLECTION_NAME}")
    else:
        print(f"ℹ️  Collection already exists: {COLLECTION_NAME}")


# ------------------------------------------------------------------ #
#  INGESTION
# ------------------------------------------------------------------ #

def ingest_file(
    file_path:  str,
    fund_name:  str,
    doc_type:   str,   # "factsheet" | "annual_report" | "other"
    period:     str,   # "2025-01" for Jan 2025 factsheet, "2025" for annual report
    client:     QdrantClient,
    embedder:   Any,
) -> tuple[int, List[Dict[str, Any]]]:
    """
    Full pipeline:  file → extract → chunk → embed → upsert.
    Returns (number of points upserted, extracted document).
    """
    path = Path(file_path)

    # ── 1. Extract structured document ───────────────────────────────
    document = extract_text_from_file(file_path)
    if not document:
        print(f"⚠️  No content extracted from {path.name}")
        return 0, []

    # ── 2. Build doc-level metadata (passed in from caller) ───────────
    doc_metadata: Dict[str, Any] = {
        "source_file": path.name,
        "file_type":   path.suffix.lstrip(".").lower(),  # "pdf" | "txt"
        "fund_name":   fund_name,
        "doc_type":    doc_type,
        "period":      period,
    }

    # ── 3. Chunk — metadata gets merged into every chunk here ─────────
    chunks = chunk_structured_document(document, doc_metadata=doc_metadata)
    if not chunks:
        print(f"⚠️  No chunks produced from {path.name}")
        return 0, document

    print(f"📄 {path.name}  →  {len(chunks)} chunks")

    # ── 4. Embed ──────────────────────────────────────────────────────
    texts  = [c["text"] for c in chunks]
    vectors = embedder.encode(texts, batch_size=32, show_progress_bar=True).tolist()

    # ── 5. Build Qdrant points ────────────────────────────────────────
    points: List[PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        payload = {k: v for k, v in chunk.items()}  # full chunk as payload
        points.append(
            PointStruct(
                id=str(uuid.uuid4()),   # stable UUID per chunk
                vector=vector,
                payload=payload,
            )
        )

    # ── 6. Upsert in batches ──────────────────────────────────────────
    batch_size = 64
    for i in range(0, len(points), batch_size):
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=points[i : i + batch_size],  # type: ignore
        )

    print(f"✅ Upserted {len(points)} points for {path.name}")
    return len(points), document


# ------------------------------------------------------------------ #
#  RETRIEVAL EXAMPLE
#  (put this in your rag.py / query pipeline, not here in prod)
# ------------------------------------------------------------------ #

def query_qdrant(
    query:     str,
    client:    QdrantClient,
    embedder:  Any,
    fund_name: Optional[str]  = None,   # optional filter
    doc_type:  Optional[str]  = None,   # optional filter
    period:    Optional[str]  = None,   # optional filter
    top_k:     int  = 5,
) -> List[Dict[str, Any]]:
    """
    Vector search with optional metadata filters.

    Examples:
        # All chunks about NAV across all funds
        search("what is the NAV", ...)

        # Only PPFCF January 2025 chunks
        search("top holdings", fund_name="Parag Parikh Flexi Cap Fund", period="2025-01")

        # Only table chunks (for precise financial data)
        search("HDFC Bank allocation percentage", ...)
        # then filter results: [r for r in results if r["payload"]["is_table"]]
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

    # Use query_points (the modern endpoint in 1.1x series) or fallback to search
    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        ).points
    except AttributeError:
        # Fallback to search if query_points is missing (highly unlikely for 1.17)
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
#  DELETE BY DOCUMENT  (re-ingest a single factsheet cleanly)
# ------------------------------------------------------------------ #

def delete_document(file_name: str, client: QdrantClient) -> None:
    """Deletes all points for a given source_file before re-ingesting."""
    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(
            must=[FieldCondition(key="source_file", match=MatchValue(value=file_name))]
        ),
    )
    print(f"🗑️  Deleted all points for {file_name}")


def clear_collection(client: QdrantClient) -> bool:
    """Definitively wipes the entire collection from Qdrant."""
    try:
        logger = logging.getLogger(__name__)
        logger.info(f"💣 REQUESTED FULL CLEAR for collection: {COLLECTION_NAME}")
        
        # 1. Attempt to drop the collection entirely (requires Admin/Manage perms)
        can_drop = True
        try:
            client.delete_collection(collection_name=COLLECTION_NAME)
            logger.info(f"✅ Dropped collection: {COLLECTION_NAME}")
        except Exception as e:
            if "403" in str(e) or "Forbidden" in str(e):
                logger.warning(f"⚠️ Permission Denied (403) to drop collection. Falling back to point-deletion. Error: {e}")
                can_drop = False
            else:
                logger.warning(f"⚠️ Could not drop collection '{COLLECTION_NAME}': {e}")
        
        if can_drop:
            # Re-create it if it was dropped
            import time
            time.sleep(0.5)
            ensure_collection(client)
        else:
            # SOFT WIPE (Delete all points but keep collection because we lack drop perms)
            logger.info(f"🧹 Attempting Point-level wipe for {COLLECTION_NAME} because Drop failed...")
            try:
                # Use empty Filter() which matches ALL points in most Qdrant versions
                client.delete(
                    collection_name=COLLECTION_NAME,
                    points_selector=Filter(),
                    wait=True
                )
            except Exception as e:
                 logger.warning(f"⚠️ Simple Filter() wipe failed: {e}. Moving to exhaustive scroll-delete.")
            
        # 2. Final check and fallback: Scroll and Delete by ID
        info = client.get_collection(collection_name=COLLECTION_NAME)
        if info.points_count and info.points_count > 0:
            logger.info(f"🔍 Collection still has {info.points_count} points. Executing deep scroll-delete...")
            # If everything else fails, scroll all points and delete by ID list
            scroll_results, next_page = client.scroll(collection_name=COLLECTION_NAME, limit=1000, with_payload=False)
            while scroll_results:
                point_ids = [r.id for r in scroll_results]
                client.delete(collection_name=COLLECTION_NAME, points_selector=point_ids, wait=True)
                if not next_page: break
                scroll_results, next_page = client.scroll(collection_name=COLLECTION_NAME, limit=1000, with_payload=False, offset=next_page)
            
        logger.info(f"✨ Successfully cleared {COLLECTION_NAME}")
        return True
    except Exception as e:
        logger.error(f"❌ DEEP CLEAR FAILED: {e}")
        return False


def get_collection_stats(client: QdrantClient) -> Dict[str, Any]:
    """Retrieves basic stats and unique source files from Qdrant."""
    try:
        # 1. Get system-level points count
        info = client.get_collection(collection_name=COLLECTION_NAME)
        count = info.points_count if hasattr(info, 'points_count') else 0
        
        # 2. Get unique source files from payloads
        # We scroll a sufficient number of points (Qdrant doesn't have a native 'unique' query)
        # For a small/medium KB, scrolling 1000 items is usually enough to find all unique filenames.
        sources = set()
        scroll_results, _ = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=1000,
            with_payload=True,
            with_vectors=False
        )
        for point in scroll_results:
            if point.payload:
                # Check multiple potential keys for the filename
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
        print(f"❌ Failed to get stats: {e}")
        return {"vectors": 0, "sources": [], "status": "error"}



# ------------------------------------------------------------------ #
#  CLI
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file",     required=True,  help="Path to PDF or TXT")
    parser.add_argument("--fund",     required=True,  help="Fund name")
    parser.add_argument("--doc-type", default="factsheet", choices=["factsheet", "annual_report", "other"])
    parser.add_argument("--period",   required=True,  help="e.g. 2025-01 or 2025")
    parser.add_argument("--delete-first", action="store_true", help="Delete existing points for this file before ingesting")
    args = parser.parse_args()

    client   = get_client()
    embedder = _embedder

    ensure_collection(client)

    if args.delete_first:
        delete_document(Path(args.file).name, client)

    ingest_file(
        file_path = args.file,
        fund_name = args.fund,
        doc_type  = args.doc_type,
        period    = args.period,
        client    = client,
        embedder  = embedder,
    )