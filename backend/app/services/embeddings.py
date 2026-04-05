import asyncio
from typing import List
import logging
from app.core.config import settings  # pyre-ignore[21]
from sentence_transformers import SentenceTransformer  # pyre-ignore[21]
logger = logging.getLogger(__name__)

# Load embedding model once. We use a local cache folder to avoid repeated downloads or HF Hub checks.
model = SentenceTransformer(settings.EMBEDDING_MODEL, cache_folder="./models")

# In-memory cache for embeddings
embedding_cache = {}


async def get_embedding(text: str) -> List[float]:
    """Get embedding for a single text using local MiniLM model."""

    # Check cache
    if text in embedding_cache:
        return embedding_cache[text]

    try:
        # Run in thread so async server is not blocked
        embedding = await asyncio.to_thread(model.encode, text)

        embedding_list = embedding.tolist()

        embedding_cache[text] = embedding_list

        return embedding_list

    except Exception as e:
        logger.error(f"Embedding error: {str(e)}")
        raise


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for multiple texts."""

    logger.info(f"Generating embeddings for {len(texts)} chunks...")

    try:
        # Batch embedding (much faster)
        embeddings = await asyncio.to_thread(
            model.encode,
            texts,
            batch_size=32,
            show_progress_bar=False
        )

        return [e.tolist() for e in embeddings]

    except Exception as e:
        logger.error(f"Batch embedding error: {str(e)}")
        raise


def clear_cache():
    """Clear embedding cache."""
    global embedding_cache
    embedding_cache.clear()
    logger.info("Embedding cache cleared")


def get_cache_stats():
    """Get cache statistics."""
    return {
        "cachedEmbeddings": len(embedding_cache),
        "model": settings.EMBEDDING_MODEL,
        "dimensions": settings.EMBEDDING_DIM
    }