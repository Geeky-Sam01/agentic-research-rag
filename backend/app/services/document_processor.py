import logging
from typing import List
from pathlib import Path
from PyPDF2 import PdfReader  # pyre-ignore[21]

logger = logging.getLogger(__name__)

def extract_text_from_file(file_path: str) -> str:
    """Extract text from PDF or TXT file."""
    
    file_path = Path(file_path)
    
    if file_path.suffix.lower() == '.pdf':
        return extract_text_from_pdf(str(file_path))
    else:
        return extract_text_from_txt(str(file_path))

def extract_text_from_txt(file_path: str) -> str:
    """Extract text from TXT file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        with open(file_path, 'r', encoding='latin-1') as f:
            return f.read()

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF file."""
    try:
        text = []
        with open(file_path, 'rb') as f:
            pdf_reader = PdfReader(f)
            for page in pdf_reader.pages:
                text.append(page.extract_text())
        return '\n'.join(text)
    except Exception as e:
        logger.error(f"PDF extraction error: {e}")
        return ""

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> List[str]:
    """Split text into overlapping chunks."""
    
    if not text or len(text.strip()) == 0:
        return []
    
    chunks = []
    for i in range(0, len(text), chunk_size - overlap):
        chunk = text[i:i + chunk_size]
        if chunk.strip():
            chunks.append(chunk)
    
    return chunks
