from fastapi import APIRouter, UploadFile, File, HTTPException
import logging
from pathlib import Path

from app.core.config import settings
from app.services.embeddings import get_embeddings, get_cache_stats
from app.services.faiss_service import faiss_manager
from app.services.document_processor import extract_text_from_file
from app.services.pdr import build_pdr_structure
from app.models.schemas import DocumentUploadResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)) -> DocumentUploadResponse:
    """Upload and index a document using Parent Document Retrieval."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    logger.info(f"\n📄 Processing file: {file.filename}")

    file_path = Path(settings.UPLOAD_PATH) / file.filename

    try:
        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        # Extract text
        logger.info("📖 Extracting text...")
        text = extract_text_from_file(str(file_path))

        if not text or len(text.strip()) == 0:
            raise HTTPException(status_code=400, detail="Could not extract text from file")

        # ---------- PDR PIPELINE ----------
        logger.info("🧠 Building Parent Document Retrieval structure...")

        parent_chunks, child_chunks = build_pdr_structure(text)

        logger.info(f"📦 Parent sections: {len(parent_chunks)}")
        logger.info(f"📚 Child chunks: {len(child_chunks)}")

        # Extract texts for embedding
        child_texts = [c["text"] for c in child_chunks]

        logger.info("🔢 Generating embeddings...")

        embeddings = await get_embeddings(child_texts)

        logger.info(f"✅ Generated {len(embeddings)} embeddings")

        logger.info("💾 Adding to FAISS index...")

        # Metadata mapping
        metadata = [
            {
                "parent_id": c["parent_id"],
                "filename": file.filename
            }
            for c in child_chunks
        ]

        total_indexed = faiss_manager.add_vectors(
            embeddings,
            child_texts,
            metadata,
            parent_chunks
        )

        logger.info(f"✨ Done! Total vectors indexed: {total_indexed}")

        return DocumentUploadResponse(
            success=True,
            message=f"Indexed {len(child_chunks)} chunks from {file.filename}",
            totalIndexed=total_indexed,
            chunksCreated=len(child_chunks),
            embeddingModel=settings.EMBEDDING_MODEL,
            embeddingDimension=settings.EMBEDDING_DIM
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if file_path.exists():
            file_path.unlink()


@router.get("/stats")
async def get_stats():
    """Get knowledge base statistics."""
    try:
        stats = faiss_manager.get_stats()
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
    """Clear the FAISS index."""
    try:
        success = faiss_manager.clear()

        if success:
            return {"success": True, "message": "Index cleared"}

        raise HTTPException(status_code=500, detail="Failed to clear index")

    except Exception as e:
        logger.error(f"Clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 