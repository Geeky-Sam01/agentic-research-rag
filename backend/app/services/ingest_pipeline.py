import argparse
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pdfplumber
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from app.services.document_processor import chunk_structured_document, extract_text_from_file
from app.services.embeddings import model as _embedder
from app.services.qdrant_service import (
    COLLECTION_NAME,
    delete_document,
    ensure_collection,
    get_client,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  KNOWN FUND HOUSES  (lowercase keyword → canonical name)
# ------------------------------------------------------------------ #
_FUND_HOUSE_MAP = {
    "parag parikh": "PPFAS",
    "ppfas":        "PPFAS",
    "hdfc":         "HDFC",
    "sbi":          "SBI",
    "icici":        "ICICI Prudential",
    "axis":         "Axis",
    "kotak":        "Kotak",
    "nippon":       "Nippon India",
    "dsp":          "DSP",
    "mirae":        "Mirae Asset",
    "tata":         "Tata",
    "aditya birla": "Aditya Birla Sun Life",
    "uti":          "UTI",
    "franklin":     "Franklin Templeton",
    "motilal":      "Motilal Oswal",
    "canara":       "Canara Robeco",
    "invesco":      "Invesco",
    "bandhan":      "Bandhan",
    "quant":        "Quant",
    "edelweiss":    "Edelweiss",
    "sundaram":     "Sundaram",
    "baroda":       "Baroda BNP Paribas",
    "quantum":      "Quantum",
    "mahindra":     "Mahindra Manulife",
    "hsbc":         "HSBC",
    "pgim":         "PGIM India",
    "groww":        "Groww",
}

# Filename patterns that hint at document type
_DOC_TYPE_PATTERNS = {
    "factsheet":     ["factsheet", "fact_sheet", "fact-sheet"],
    "annual_report": ["annual", "annual_report", "annual-report"],
    "monthly":       ["monthly"],
    "kim":           ["kim", "key_information"],
    "sid":           ["sid", "scheme_information"],
    "sai":           ["sai", "additional_information"],
}

# Date regex: "March 2025", "31 March 2025", "March 31, 2025"
_DATE_RE = re.compile(
    r"(\d{1,2}\s+)?"
    r"(January|February|March|April|May|June|July|August|September"
    r"|October|November|December)"
    r"\s+(\d{4})",
    re.IGNORECASE,
)

# Month name → number
_MONTH_MAP = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}


def _infer_doc_type_from_filename(filename: str) -> str:
    """Try to guess doc_type from the filename. Falls back to 'factsheet'."""
    name_lower = filename.lower()
    for doc_type, keywords in _DOC_TYPE_PATTERNS.items():
        if any(kw in name_lower for kw in keywords):
            return doc_type
    # Most uploaded financial PDFs are factsheets
    return "factsheet"


def extract_header_metadata(file_path: str) -> dict:
    """
    Extract fund house name and date from the first page of a PDF.
    Returns {fund_name, period, doc_type} with best-effort values.
    """
    path = Path(file_path)
    result = {
        "fund_name": None,
        "period":    None,
        "doc_type":  _infer_doc_type_from_filename(path.name),
    }

    if path.suffix.lower() != ".pdf":
        return result

    try:
        with pdfplumber.open(file_path) as pdf:
            if not pdf.pages:
                return result
            first_page_text = pdf.pages[0].extract_text() or ""
    except Exception as e:
        logger.warning(f"Could not read first page of {path.name}: {e}")
        return result

    text_lower = first_page_text.lower()

    # ── Fund house detection ──────────────────────────────────────
    for keyword, canonical in _FUND_HOUSE_MAP.items():
        if keyword in text_lower:
            result["fund_name"] = canonical
            break

    # ── Date / period detection ───────────────────────────────────
    date_match = _DATE_RE.search(first_page_text)
    if date_match:
        month_name = date_match.group(2).lower()
        year = date_match.group(3)
        month_num = _MONTH_MAP.get(month_name)
        if month_num:
            result["period"] = f"{year}-{month_num}"  # e.g. "2025-03"
        else:
            result["period"] = year

    return result


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
        logger.warning(f"No content extracted from {path.name}")
        return 0, []

    # ── 1b. Auto-fill missing metadata from PDF content ──────────────
    defaults = {"Unknown Fund", "Unknown Period", "other", "", None}
    needs_enrichment = (
        fund_name in defaults or doc_type in defaults or period in defaults
    )

    if needs_enrichment:
        header_meta = extract_header_metadata(file_path)
        logger.info(f"Auto-detected metadata for {path.name}: {header_meta}")

        if fund_name in defaults and header_meta["fund_name"]:
            fund_name = header_meta["fund_name"]
        if period in defaults and header_meta["period"]:
            period = header_meta["period"]
        if doc_type in defaults and header_meta["doc_type"]:
            doc_type = header_meta["doc_type"]

    # ── 2. Build doc-level metadata ──────────────────────────────────
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
        logger.warning(f"No chunks produced from {path.name}")
        return 0, document

    logger.info(f"{path.name}  ->  {len(chunks)} chunks")

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

    logger.info(f"Upserted {len(points)} points for {path.name}")
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