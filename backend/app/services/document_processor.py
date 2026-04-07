import logging
import re
import io
from typing import List, Dict, Any, Optional
from pathlib import Path

import pdfplumber
import fitz  # PyMuPDF
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

MAX_PAGES = 10


def init_ocr():
    try:
        pytesseract.get_tesseract_version()
        logger.info("Tesseract OCR ready")
    except Exception:
        logger.warning("Tesseract not found. OCR fallback may fail.")


def extract_text_from_file(file_path: str) -> List[Dict[str, Any]]:
    doc_path = Path(file_path)
    if doc_path.suffix.lower() == ".pdf":
        return _extract_pdf(str(doc_path))
    return _extract_txt(str(doc_path))



def _extract_txt(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except:
        with open(file_path, "r", encoding="latin-1") as f:
            text = f.read()

    return [{
        "page": 1,
        "sections": [{"heading": "Document", "text": text, "is_table": False}]
    }]


def _extract_pdf(file_path: str) -> List[Dict[str, Any]]:
    pages = []

    try:
        with pdfplumber.open(file_path) as pdf, fitz.open(file_path) as doc:
            n = min(len(doc), MAX_PAGES)

            for i in range(n):
                p0 = pdf.pages[i]
                text = (p0.extract_text() or "").strip()

                # OCR fallback
                if len(text) < 50:
                    try:
                        pix = doc[i].get_pixmap(dpi=300)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        text = pytesseract.image_to_string(img).strip()
                    except:
                        pass

                sections = []

                # 1. TABLE EXTRACTION
                try:
                    tables = p0.extract_tables()
                except:
                    tables = []

                for tbl in tables:
                    if not tbl or len(tbl) < 2:
                        continue

                    heading = "Top Holdings" if _is_holdings_table(tbl) else "Table"

                    md = _table_to_json(tbl)

                    sections.append({
                        "heading": heading,
                        "text": md,
                        "is_table": True
                    })

                # 2. TEXT SECTIONS
                text_sections = _split_into_sections(text)
                sections.extend(text_sections)

                pages.append({
                    "page": i + 1,
                    "sections": sections
                })

    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        return []

    return pages


# ================================================================
#  TABLE HELPERS
# ================================================================

def _table_to_json(table: List[List[Any]]) -> Dict[str, Any]:
    if not table or len(table) < 2:
        return {}

    headers = [str(c or "").strip() for c in table[0]]
    rows = [
        [str(c or "").strip() for c in r]
        for r in table[1:20]  # limit rows
    ]

    return {
        "headers": headers,
        "rows": rows
    }

def _is_holdings_table(table: List[List[Any]]) -> bool:
    header = [str(c).lower() for c in table[0]]

    header_str = " ".join(header)

    return (
        "name" in header_str and
        ("%" in header_str or "net assets" in header_str)
    )


# ================================================================
#  SECTION SPLIT
# ================================================================

_HEADING_PATTERNS = re.compile(
    r"(portfolio|allocation|holdings|equity|debt|performance|risk|overview)",
    re.IGNORECASE,
)


def _split_into_sections(text: str) -> List[Dict[str, Any]]:
    if not text:
        return []

    lines = text.split("\n")
    sections = []

    current_heading = "General"
    buffer = []

    def flush():
        if buffer:
            sections.append({
                "heading": current_heading,
                "text": "\n".join(buffer),
                "is_table": False
            })
            buffer.clear()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        if _is_heading(line):
            flush()
            current_heading = line
        else:
            buffer.append(line)

    flush()
    return sections


def _is_heading(line: str) -> bool:
    if len(line) > 80:
        return False

    if _HEADING_PATTERNS.search(line):
        return True

    if line.isupper() and len(line.split()) >= 2:
        return True

    return False


# ================================================================
#  CHUNKING (UNCHANGED)
# ================================================================

def chunk_structured_document(
    document: List[Dict[str, Any]],
    doc_metadata: Optional[Dict[str, Any]] = None,
    max_chunk_size: int = 1200,
    overlap: int = 100,
) -> List[Dict[str, Any]]:

    doc_metadata = doc_metadata or {}
    raw_chunks = []

    for page in document:
        for section in page["sections"]:
            heading = section["heading"]
            text = section["text"]
            is_table = section.get("is_table", False)

            raw_chunks.append({
                "text": f"{heading}\n\n{text}",
                "page": page["page"],
                "heading": heading,
                "is_table": is_table,
            })

    return [
        {**doc_metadata, **chunk, "chunk_index": i}
        for i, chunk in enumerate(raw_chunks)
    ]