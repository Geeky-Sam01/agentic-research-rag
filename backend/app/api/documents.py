from fastapi import APIRouter, UploadFile, File, Form, HTTPException  # type: ignore
import logging
from pathlib import Path

from app.core.config import settings  # type: ignore
from app.services.embeddings import get_embeddings, get_cache_stats, model as _embedder  # type: ignore
from app.services.document_processor import extract_text_from_file, chunk_structured_document  # type: ignore
from app.models.schemas import DocumentUploadResponse  # type: ignore
from app.services.qdrant_service import (
    get_client, ensure_collection, delete_document, 
    get_collection_stats, clear_collection
)
from app.services.injest import ingest_file
from sentence_transformers import SentenceTransformer  # type: ignore

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


# ── Shared clients (initialised once at import time) ─────────────────────────
_qdrant_client = get_client()

 
ensure_collection(_qdrant_client)
 
 

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file:      UploadFile = File(...),
    fund_name: str        = Form("Unknown Fund"),                          
    doc_type:  str        = Form("other"),                  
    period:    str        = Form("Unknown Period"),                          
    overwrite: bool       = Form(False),                        
) -> DocumentUploadResponse:
    """
    Upload and index a financial document (PDF or TXT) into Qdrant.
 
    Form fields
    -----------
    fund_name   Fund this document belongs to.
    doc_type    "factsheet" | "annual_report" | "other"
    period      Month/year string: "2025-01" for a January factsheet,
                "2025" for an annual report.
    overwrite   If True, existing Qdrant points for this filename are
                deleted before ingestion (safe re-upload).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")
 
    logger.info(f"📄 Received: {file.filename}  [{doc_type} / {fund_name} / {period}]")
 
    file_path = Path(settings.UPLOAD_PATH) / file.filename
 
    try:
        
        content = await file.read()
        logger.debug(f"Saving {len(content)} bytes to {file_path}")
        with open(file_path, "wb") as f:
            f.write(content)  # type: ignore
        logger.info(f"Successfully saved {file.filename} to disk.")
 
        
        if overwrite:
            logger.info(f"🗑️  Overwrite=True — deleting existing points for {file.filename}")
            delete_document(file.filename, _qdrant_client)
 
        
        #       extract → chunk → embed → upsert
        logger.info("🚀 Running ingest pipeline...")
        total_indexed, extracted_doc = ingest_file(
            file_path = str(file_path),
            fund_name = fund_name,
            doc_type  = doc_type,
            period    = period,
            client    = _qdrant_client,
            embedder  = _embedder,
        )

        if total_indexed == 0:
            raise HTTPException(
                status_code=400,
                detail="No content could be extracted or indexed from the file.",
            )

        
        from app.services.smart_questions import generate_smart_questions
        suggested_qs = generate_smart_questions(extracted_doc, fund_name)

        logger.info(f"✅ Indexed {total_indexed} chunks from {file.filename}")

        return DocumentUploadResponse(
            success            = True,
            message            = f"Indexed {total_indexed} chunks from {file.filename}",
            totalIndexed       = total_indexed,
            chunksCreated      = total_indexed,
            embeddingModel     = settings.EMBEDDING_MODEL,
            embeddingDimension = settings.EMBEDDING_DIM,
            suggested_questions = suggested_qs
        )
 
    except HTTPException:
        raise
 
    except Exception as e:
        logger.error(f"Upload error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
 
    finally:
        # Always clean up the temp file
        if file_path.exists():
            logger.debug(f"Cleaning up temporary file: {file_path}")
            file_path.unlink()

@router.get("/stats")
async def get_stats():
    """Get knowledge base statistics from Qdrant."""
    try:
        stats = get_collection_stats(_qdrant_client)
        cache_stats = get_cache_stats()

        return {
            **stats,
            "cache": cache_stats
        }

    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/clear")
async def clear_index():
    """Clear the Qdrant collection."""
    try:
        success = clear_collection(_qdrant_client)

        if success:
            return {"success": True, "message": "Collection cleared"}

        raise HTTPException(status_code=500, detail="Failed to clear collection")

    except Exception as e:
        logger.error(f"Clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 