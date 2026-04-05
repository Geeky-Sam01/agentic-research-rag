import logging
import os
from typing import List, Dict, Any
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader

logger = logging.getLogger(__name__)

# ---------------- ENV ---------------- #

os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
os.environ["OMP_NUM_THREADS"] = "1"

# ---------------- CONFIG ---------------- #

MAX_PAGES = 10
MAX_IMAGE_SIZE = (1500, 1500)

ocr = None


# ---------------- OCR INIT ---------------- #

def get_ocr():
    global ocr
    if ocr is None:
        from paddleocr import PaddleOCR
        logger.info("🔧 Initializing PaddleOCR...")
        ocr = PaddleOCR(
            lang="en",
            ocr_version="PP-OCRv4",
            enable_mkldnn=False,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False
        )
    return ocr


# ---------------- ENTRY ---------------- #

def extract_text_from_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Returns structured document:
    [
        {
            "page": int,
            "sections": [
                {"heading": str, "text": str}
            ]
        }
    ]
    """
    file_path = Path(file_path)

    if file_path.suffix.lower() == '.pdf':
        return extract_pdf_smart(str(file_path))
    else:
        return extract_txt_structured(str(file_path))


# ---------------- TXT ---------------- #

def extract_txt_structured(file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            text = f.read()

    return [{
        "page": 1,
        "sections": [{"heading": "Document", "text": text}]
    }]


# ---------------- SMART PDF ROUTER ---------------- #

def extract_pdf_smart(file_path: str):
    """
    Try native (pypdf) extraction first.
    If the result looks invalid/garbage → fallback to PaddleOCR.
    """
    logger.info("🧪 Trying native PDF extraction...")
    native_text = extract_native_pdf(file_path)

    if is_text_valid(native_text):
        logger.info("✅ Using native PDF extraction (FAST + CLEAN)")
        return convert_native_to_structured(native_text)

    logger.info("⚠️ Native extraction failed → falling back to OCR...")
    return extract_pdf_ocr(file_path)


# ---------------- NATIVE EXTRACTION ---------------- #

def extract_native_pdf(file_path: str) -> str:
    try:
        reader = PdfReader(file_path)
        text = []

        for page in reader.pages[:MAX_PAGES]:
            page_text = page.extract_text()
            if page_text:
                text.append(page_text)

        full_text = "\n".join(text).strip()
        logger.info(f"📏 Native extraction length: {len(full_text)} chars")
        return full_text

    except Exception as e:
        logger.warning(f"⚠️ Native extraction exception: {e}")
        return ""


def is_text_valid(text: str) -> bool:
    """Detect garbage or near-empty native extraction."""
    if not text or len(text) < 200:
        return False

    lines = text.split("\n")
    short_lines = sum(1 for l in lines if len(l.strip()) <= 2)

    # Too many single-character lines → likely garbage from a scanned PDF
    if short_lines > len(lines) * 0.4:
        logger.info(f"🚫 Text quality check failed ({short_lines}/{len(lines)} short lines)")
        return False

    return True


def convert_native_to_structured(text: str):
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    sections = []
    current_heading = "General"
    buffer = []

    for line in lines:
        if is_heading(line):
            if buffer:
                sections.append({
                    "heading": current_heading,
                    "text": "\n".join(buffer)
                })
                buffer = []
            current_heading = line
        else:
            buffer.append(line)

    if buffer:
        sections.append({
            "heading": current_heading,
            "text": "\n".join(buffer)
        })

    return [{
        "page": 1,
        "sections": sections
    }]


# ---------------- OCR FALLBACK ---------------- #

def pdf_to_images(file_path: str):
    pdf = pdfium.PdfDocument(file_path)
    images = []

    for i, page in enumerate(pdf):
        if i >= MAX_PAGES:
            break

        img = page.render(scale=2).to_pil()
        img.thumbnail(MAX_IMAGE_SIZE)
        images.append((i + 1, img))  # (page_number, PIL image)

    return images


def extract_pdf_ocr(file_path: str):
    try:
        pages = pdf_to_images(file_path)
        document = []

        ocr_engine = get_ocr()
        import numpy as np

        for page_number, img in pages:
            logger.info(f"📄 OCR Processing page {page_number}...")

            img_np = np.array(img)
            result = ocr_engine.ocr(img_np)

            if not result or not result[0]:
                logger.warning(f"⚠️ No OCR result on page {page_number}")
                continue

            lines = [
                line[1][0].strip()
                for line in result[0]
                if line[1][0].strip()
            ]

            logger.info(f"📝 Page {page_number}: {len(lines)} lines extracted")
            sections = build_sections(lines)
            document.append({
                "page": page_number,
                "sections": sections
            })

        return document

    except Exception as e:
        logger.error(f"❌ OCR extraction error: {e}")
        return []


# ---------------- SECTION BUILDER ---------------- #

def build_sections(lines: List[str]) -> List[Dict[str, str]]:
    sections = []
    current_heading = "General"
    buffer = []

    for line in lines:
        if is_heading(line):
            if buffer:
                sections.append({
                    "heading": current_heading,
                    "text": "\n".join(buffer)
                })
                buffer = []
            current_heading = line
        else:
            buffer.append(line)

    if buffer:
        sections.append({
            "heading": current_heading,
            "text": "\n".join(buffer)
        })

    return sections


def is_heading(text: str) -> bool:
    return (
        len(text) < 100 and (
            text.isupper() or
            text.startswith("Module") or
            text.endswith(":") or
            "TIU-" in text or
            "Credit" in text
        )
    )


# ---------------- CHUNKING ---------------- #

def chunk_structured_document(
    document: List[Dict[str, Any]],
    chunk_size: int = 500,
    overlap: int = 100
) -> List[Dict[str, Any]]:
    """
    Splits structured document pages/sections into overlapping text chunks.
    Returns:
    [
        {
            "text": str,
            "page": int,
            "heading": str
        }
    ]
    """
    chunks = []

    for page in document:
        page_num = page["page"]
        logger.debug(f"✂️ Chunking page {page_num}...")

        for section in page["sections"]:
            heading = section["heading"]
            text = section["text"]

            start = 0
            while start < len(text):
                chunk_text = text[start:start + chunk_size]
                chunks.append({
                    "text": chunk_text,
                    "page": page_num,
                    "heading": heading
                })
                start += chunk_size - overlap

    return chunks