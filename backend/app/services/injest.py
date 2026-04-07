import uuid
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.services.embeddings import model as _embedder
from app.services.document_processor import extract_text_from_file, chunk_structured_document
from app.services.qdrant_service import (
    get_client, 
    ensure_collection, 
    delete_document, 
    clear_collection, 
    get_collection_stats,
    COLLECTION_NAME
)

logger = logging.getLogger(__name__)

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