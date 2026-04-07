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

# ---------------- CONFIG ---------------- #
MAX_PAGES = 10

# Heading patterns for factsheet section detection
_HEADING_PATTERNS = re.compile(
    r"^(?:"
    r"FACT SHEET|"
    r"Fund (?:Overview|Details|Performance|Returns?|Highlights?)|"
    r"Portfolio (?:Overview|Allocation|Composition|Holdings?)|"
    r"Top (?:\d+ )?(?:Holdings?|Equity|Debt)|"
    r"Sector(?:al)? (?:Allocation|Breakdown)|"
    r"Asset Allocation|"
    r"Risk(?:ometer)?|"
    r"Quantitative Indicators|"
    r"Scheme (?:Information|Returns?|Details)|"
    r"(?:Monthly|Quarterly|Annual) (?:Returns?|Performance)|"
    r"NAV|AUM|"
    r" benchmark(?:\s+index)?|"
    r"Expense Ratio|"
    r"Exit Load|"
    r"Standard Deviation|"
    r"Sharpe Ratio|"
    r"Beta|"
    r"(?:Net )?Asset Value|"
    r"(?:Additional |Tier \d )?Benchmark|"
    r"Key (?:Metrics|Indicators)|"
    r"(?:Fund )?Manager|"
    r"Investment (?:Strategy|Objective|Philosophy)|"
    r"Debt and Money Market|"
    r"Equity and Equity Related|"
    r"Government securities|"
    r"About the Fund|"
    r"Performance (?:Summary|Snapshot)|"
    r"Risk (?:Metrics|Statistics)|"
    r"Portfolio Turnover|"
    r"Core Equity|"
    r"Parag Parikh \w+.*Fund"  # fund name headings
    r")",
    re.IGNORECASE | re.DOTALL,
)


def init_ocr():
    """Verify pytesseract is available on the system."""
    try:
        version = pytesseract.get_tesseract_version()
        logger.info(f"Document processor ready (tesseract {version})")
    except EnvironmentError:
        logger.warning(
            "tesseract not found in PATH — OCR fallback will fail for scanned pages. "
            "Install it via: apt install tesseract-ocr"
        )


def extract_text_from_file(file_path: str) -> List[Dict[str, Any]]:
    """Main entry point — returns per-page sections with headings."""
    doc_path = Path(file_path)
    if doc_path.suffix.lower() == ".pdf":
        return _extract_pdf(str(doc_path))
    return _extract_txt(str(doc_path))


# ================================================================
#  TXT
# ================================================================

def _extract_txt(file_path: str) -> List[Dict[str, Any]]:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(file_path, "r", encoding="latin-1") as f:
            text = f.read()
    return [{"page": 1, "sections": [{"heading": "Document", "text": text, "is_table": False}]}]


import time

# ================================================================
#  PDF — Integrated 3-layer extraction (plumber -> fitz -> tesseract)
# ================================================================

def _extract_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Optimized 3-layer extraction loop:
    For each page, attempts the following until meaningful text is found:
      1. pdfplumber  (Highest fidelity for native text)
      2. PyMuPDF     (Fast layout extraction)
      3. pytesseract (OCR for scanned pages)

    Opening docs once and processing page-by-page is 2-3x faster than sequential fallbacks.
    """
    start_time = time.time()
    logger.info(f"🚀 Starting optimized extraction for: {Path(file_path).name}")
    
    pages: List[Dict[str, Any]] = []
    
    try:
        # Open both handlers once
        with pdfplumber.open(file_path) as pdf, fitz.open(file_path) as doc:
            num_pages = min(len(doc), MAX_PAGES)
            
            for i in range(num_pages):
                page_start = time.time()
                engine_used = "none"
                text = ""
                
                # Layer 1: pdfplumber (Text)
                try:
                    p0 = pdf.pages[i]
                    text = (p0.extract_text() or "").strip()
                    if len(text) > 100:
                        engine_used = "pdfplumber"
                except Exception as e:
                    logger.debug(f"Page {i+1}: pdfplumber error: {e}")

                # Layer 2: PyMuPDF (Fallback Text)
                if len(text) < 100:
                    try:
                        text = doc[i].get_text("text").strip()
                        if len(text) > 100:
                            engine_used = "PyMuPDF"
                    except Exception as e:
                        logger.debug(f"Page {i+1}: PyMuPDF error: {e}")

                # Layer 3: Tesseract (OCR Fallback)
                if len(text) < 50:
                    try:
                        pix = doc[i].get_pixmap(dpi=200)
                        img = Image.open(io.BytesIO(pix.tobytes("png")))
                        text = pytesseract.image_to_string(img).strip()
                        if len(text) > 20:
                            engine_used = "pytesseract (OCR)"
                    except Exception as e:
                        logger.error(f"Page {i+1}: OCR failed: {e}")

                # Process the best text found
                sections = _split_into_sections(text)
                pages.append({
                    "page": i + 1,
                    "sections": sections,
                    "engine": engine_used
                })
                
                elapsed = time.time() - page_start
                logger.info(f"  📄 Page {i+1}/{num_pages} processed in {elapsed:.2f}s | Engine: {engine_used}")

    except Exception as e:
        logger.error(f"❌ Critical failure during PDF extraction: {e}")
        return []

    total_duration = time.time() - start_time
    logger.info(f"✅ Extraction complete for {len(pages)} pages in {total_duration:.2f}s")
    return pages


# ================================================================
#  SECTION SPLITTING  (replaces unstructured element categorisation)
# ================================================================

def _split_into_sections(text: str) -> List[Dict[str, Any]]:
    """
    Splits raw page text into headed sections.

    Replaces unstructured's ML-based Title/Table/NarrativeText classification
    with lightweight regex heuristics tuned for mutual fund factsheets.

    Returns:
        [{"heading": str, "text": str, "is_table": bool}]
    """
    if not text:
        return []

    lines = text.split("\n")
    sections: List[Dict[str, Any]] = []
    current_heading = "General"
    buffer: List[str] = []

    def flush():
        if buffer:
            combined = "\n".join(buffer).strip()
            if combined:
                sections.append({
                    "heading": current_heading,
                    "text": combined,
                    "is_table": False,
                })
            buffer.clear()

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Check if this line is a heading
        if _is_heading(stripped):
            flush()
            current_heading = stripped
            continue

        buffer.append(stripped)

    flush()
    return sections


def _is_heading(line: str) -> bool:
    """
    Determines if a line is likely a section heading.

    Uses multiple signals rather than a single heuristic:
      - Regex match against known factsheet section titles
      - Short line (< 80 chars)
      - Doesn't end with typical sentence punctuation
    """
    if len(line) > 80:
        return False

    # Definite heading: matches known section patterns
    if _HEADING_PATTERNS.match(line.strip()):
        # But not if it's a long sentence that happens to start with a keyword
        if line.endswith((".", "!", "?", ";")):
            return False
        return True

    # Heuristic: short, ALL CAPS line (factsheet section headers are usually caps)
    if len(line) < 60 and line.isupper() and len(line.split()) >= 2:
        return True

    return False


# ================================================================
#  CHUNKING  (unchanged — your original logic)
# ================================================================

def chunk_structured_document(
    document:       List[Dict[str, Any]],
    doc_metadata:   Optional[Dict[str, Any]] = None,
    max_chunk_size: int = 1200,
    overlap:        int = 100,
) -> List[Dict[str, Any]]:
    """
    Produces Qdrant-ready chunks.
    """
    doc_metadata = doc_metadata or {}
    raw_chunks:  List[Dict[str, Any]] = []
    logger.info(f"Starting chunking for {len(document)} pages...")

    for page in document:
        page_num = page["page"]

        for section in page["sections"]:
            heading  = section["heading"]
            text     = section["text"]
            is_table = section.get("is_table", False)

            if is_table:
                raw_chunks.append({
                    "text":     f"{heading}\n\n{text}",
                    "page":     page_num,
                    "heading":  heading,
                    "is_table": True,
                })
                continue

            if len(text) <= max_chunk_size:
                raw_chunks.append({
                    "text":     f"{heading}\n\n{text}",
                    "page":     page_num,
                    "heading":  heading,
                    "is_table": False,
                })
                continue

            paragraphs: List[str] = text.split("\n")
            current_chunk: List[str] = []
            current_len = 0

            for para in paragraphs:
                para_len = len(para) + 1

                if current_len + para_len > max_chunk_size and current_chunk:
                    raw_chunks.append({
                        "text":     f"{heading}\n\n" + "\n".join(current_chunk),
                        "page":     page_num,
                        "heading":  heading,
                        "is_table": False,
                    })
                    current_chunk = [current_chunk[-1]] if current_chunk else []
                    if current_chunk:
                        current_len = len(current_chunk[0]) + 1
                    else:
                        current_len = 0

                current_chunk.append(para)
                current_len += para_len

            if current_chunk:
                raw_chunks.append({
                    "text":     f"{heading}\n\n" + "\n".join(current_chunk),
                    "page":     page_num,
                    "heading":  heading,
                    "is_table": False,
                })

    total = len(raw_chunks)
    chunks: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(raw_chunks):
        chunks.append({
            **doc_metadata,
            **chunk,
            "chunk_index":  idx,
            "total_chunks": total,
        })

    logger.info(f"Chunking complete. Created {len(chunks)} chunks.")
    return chunks
