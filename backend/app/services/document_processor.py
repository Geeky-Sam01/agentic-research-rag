import logging
import warnings
from typing import List, Dict, Any, Optional
from pathlib import Path

import fitz  # type: ignore      # PyMuPDF — text extraction & image conversion
import pdfplumber  # type: ignore # pdfplumber — table extraction
import easyocr
import numpy as np
from PIL import Image
import io

# Silence EasyOCR ONNX warnings on Windows
warnings.filterwarnings("ignore", message=".*Unable to load ONNX.*")
warnings.filterwarnings("ignore", category=UserWarning)

logger = logging.getLogger(__name__)

# ---------------- CONFIG ---------------- #
MAX_PAGES = 10
IMAGE_TEXT_THRESHOLD = 50  # If PyMuPDF extracts < 50 chars, treat as image page

# ================================================================
#  EASYOCR LAZY LOADER (Windows Safe)
# ================================================================
_ocr_reader = None

def _get_easyocr_reader():
    """Lazy loads EasyOCR so it doesn't slow down imports or txt file processing."""
    global _ocr_reader
    if _ocr_reader is None:
        logger.info("Initializing EasyOCR (downloads weights on first run)...")
        # gpu=False is safest for Windows. Set to True if you have NVIDIA + CUDA PyTorch.
        _ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
    return _ocr_reader


def init_ocr():
    """Explicitly trigger EasyOCR weight download/initialization."""
    _get_easyocr_reader()

def extract_text_from_file(file_path: str) -> List[Dict[str, Any]]:
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


# ================================================================
#  PDF  (PyMuPDF text  +  pdfplumber tables  +  EasyOCR fallback)
# ================================================================

def _extract_pdf(file_path: str) -> List[Dict[str, Any]]:
    logger.info(f"Extracting PDF: {file_path}")
    document = []

    try:
        fitz_doc    = fitz.open(file_path)
        plumber_doc = pdfplumber.open(file_path)
    except Exception as e:
        logger.error(f"Failed to open PDF: {e}")
        return []

    for i in range(min(len(fitz_doc), MAX_PAGES)):
        page_number  = i + 1
        logger.debug(f"Processing page {page_number}/{len(fitz_doc)}")
        fitz_page    = fitz_doc[i]
        plumber_page = plumber_doc.pages[i]

        # ── 0. IMAGE PAGE DETECTION & FALLBACK ────────────────────────────
        raw_text_check = fitz_page.get_text("text", sort=True).strip()
        if len(raw_text_check) < IMAGE_TEXT_THRESHOLD:
            logger.info(f"Page {page_number} detected as image-based. Using EasyOCR.")
            reader = _get_easyocr_reader()
            ocr_sections = _extract_with_easyocr(fitz_page, reader, page_number)
            
            if ocr_sections:
                document.append({"page": page_number, "sections": ocr_sections})
            continue  # Skip standard extraction for this page

        # ── STANDARD DIGITAL PDF EXTRACTION BELOW ─────────────────────────
        page_height  = fitz_page.rect.height

        # ── 1. Tables via pdfplumber ──────────────────────────────────────
        markdown_tables, table_bboxes = _extract_tables(
            plumber_page, page_height, page_number
        )

        # ── 2. Text via PyMuPDF, skipping table regions ───────────────────
        page_text = _extract_text(fitz_page, table_bboxes)

        # ── 3. Build sections ─────────────────────────────────────────────
        sections: List[Dict[str, Any]] = []

        if page_text:
            logger.debug(f"Page {page_number}: found {len(page_text)} chars of text")
            sections.extend(_build_sections(page_text))
        
        if markdown_tables:
            logger.debug(f"Page {page_number}: found {len(markdown_tables)} tables")

        for idx, md in enumerate(markdown_tables):
            sections.append({
                "heading":  f"Table {idx + 1}",
                "text":     md,
                "is_table": True,
            })

        if sections:
            document.append({"page": page_number, "sections": sections})

    fitz_doc.close()
    plumber_doc.close()
    logger.info(f"Finished PDF extraction. Extracted {len(document)} pages.")
    return document


# ================================================================
#  EASYOCR IMAGE EXTRACTION
# ================================================================

def _extract_with_easyocr(fitz_page: fitz.Page, reader, page_number: int) -> List[Dict[str, Any]]:
    """
    Converts fitz page to image, runs EasyOCR, and formats output to match
    the standard section builder structure.
    """
    try:
        # 1. Convert PyMuPDF page to image array (Fast, no Poppler needed on Windows)
        pix = fitz_page.get_pixmap(dpi=200) 
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        img_array = np.array(img)
        
        # 2. Run OCR. paragraph=True groups text logically instead of line-by-line.
        raw_results = reader.readtext(img_array, paragraph=True, detail=0, batch_size=2)
        
        full_text = "\n".join(raw_results).strip()
        
        if not full_text:
            return []
            
        # 3. Feed into YOUR existing section builder so it catches headings like "FUND FEATURES"
        return _build_sections(full_text)
        
    except Exception as e:
        logger.error(f"EasyOCR failed on page {page_number}: {e}")
        return []


# ================================================================
#  TABLE EXTRACTION  (pdfplumber)
# ================================================================

def _extract_tables(plumber_page, page_height: float, page_number: int):
    """
    Returns (markdown_tables, fitz_rects).
    pdfplumber uses top-left origin; fitz uses bottom-left.
    """
    markdown_tables: List[str]      = []
    table_bboxes:    List[fitz.Rect] = []

    try:
        for tbl in plumber_page.find_tables():
            data = tbl.extract()
            if not data or len(data) < 2:
                continue
            md = _to_markdown(data)
            if not md:
                continue
            markdown_tables.append(md)
            x0, top, x1, bottom = tbl.bbox
            table_bboxes.append(
                fitz.Rect(x0, page_height - bottom, x1, page_height - top)
            )
    except Exception as e:
        logger.warning(f"Table extraction failed on page {page_number}: {e}")

    return markdown_tables, table_bboxes


def _to_markdown(data: List[List]) -> str:
    cleaned: list[list[str]] = [
        [str(cell or "").replace("|", "/").strip() for cell in row]
        for row in data
    ]
    cleaned = [r for r in cleaned if any(r)]
    if len(cleaned) < 2:
        return ""
    header    = "| " + " | ".join(cleaned[0]) + " |"
    separator = "| " + " | ".join(["---"] * len(cleaned[0])) + " |"
    
    # Simple slice for Python type checkers
    footer_data = cleaned[1:]
    rows: List[str] = ["| " + " | ".join(r) + " |" for r in footer_data]
    return "\n".join([header, separator] + rows)


# ================================================================
#  TEXT EXTRACTION  (PyMuPDF)
# ================================================================

def _extract_text(fitz_page: fitz.Page, table_bboxes: List[fitz.Rect]) -> str:
    """
    Extracts text blocks, skipping any that overlap a table region.
    """
    blocks = fitz_page.get_text("blocks", sort=True)
    lines: List[str] = []

    for b in blocks:
        if any(fitz.Rect(b[:4]).intersects(tb) for tb in table_bboxes):
            continue
        txt = _clean(b[4])
        if txt and not _is_noise(txt):
            lines.append(txt)

    return "\n".join(lines)


# ================================================================
#  SECTION BUILDER
# ================================================================

def _build_sections(text: str) -> List[Dict[str, Any]]:
    sections: List[Dict[str, Any]] = []
    current_heading = "General"
    buffer: List[str] = []

    def _flush():
        if buffer:
            sections.append({
                "heading":  current_heading,
                "text":     "\n".join(buffer),
                "is_table": False,
            })
            buffer.clear()

    for line in text.split("\n"):
        if _is_noise(line):
            continue
        if _is_heading(line):
            _flush()
            current_heading = line
        else:
            buffer.append(line)

    _flush()
    return sections


# ---- heuristics ------------------------------------------------- #

_HEADING_KEYWORDS = [
    "Fund Features", "Top Holdings", "Sector Allocation", "Market Cap",
    "Asset Allocation", "Industry Allocation", "Portfolio Disclosure",
    "Performance", "SIP", "About", "Fund Manager", "Load Structure",
    "Investment Objective", "Quantitative Indicators", "Riskometer",
    "Dividend", "Expense Ratio", "Exit Load", "Entry Load", "NAV",
    "Lumpsum", "Rolling Return", "Skin in the Game",
    "Certificate of Deposit", "Treasury Bill", "Debt and Money Market",
    "Core Equity", "Overseas Securities", "Arbitrage",
    "Balance Sheet", "Profit and Loss", "Cash Flow", "Financial Highlights",
    "Our Performance", "Highlights", "Notes to Accounts",
    "Directors Report", "Auditors", "Shareholding Pattern", "Statement of",
    "Summary", "Introduction", "Overview",
]

def _is_heading(text: str) -> bool:
    if not (4 < len(text) < 120):
        return False
    if text.isupper():  # EasyOCR often preserves ALL CAPS headers perfectly
        return True
    if text.endswith(":"):
        return True
    tl = text.lower()
    return any(kw.lower() in tl for kw in _HEADING_KEYWORDS)

def _is_noise(text: str) -> bool:
    t = text.strip()
    if len(t) < 2:
        return True
    if t.isdigit():
        return True
    if all(c in r"-_=*•·|" for c in t):
        return True
    return False

def _clean(text: str) -> str:
    return " ".join(text.split()) if len(text.strip()) >= 2 else ""


# ================================================================
#  CHUNKING
# ================================================================

def chunk_structured_document(
    document:       List[Dict[str, Any]],
    doc_metadata:   Optional[Dict[str, Any]] = None,
    max_chunk_size: int = 1200,
    overlap:        int = 100,
) -> List[Dict[str, Any]]:
    """
    Produces Qdrant-ready chunks. (Your exact original chunking logic)
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
                    # Reset current chunk with overlap if needed
                    # For simplicity, keeping original logic's single-item overlap
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