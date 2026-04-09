import asyncio
import logging
import os
from pathlib import Path
from typing import List, Union

import numpy as np
import onnxruntime as ort
from transformers import AutoTokenizer

from app.core.config import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  ONNX EMBEDDER (Direct ONNX Runtime + NumPy)
# ------------------------------------------------------------------ #

class ONNXEmbedder:
    """
    Lightweight ONNX Runtime-based embedder.
    Uses onnxruntime and numpy directly (No PyTorch/Optimum).
    """

    def __init__(self, model_path: str):
        """
        Args:
            model_path: Path to the local ONNX model directory.
        """
        logger.info(f"Loading ONNX embedder from: {model_path}")
        
        # Verify model path exists
        if not os.path.exists(model_path):
            error_msg = f"CRITICAL ERROR: ONNX model directory NOT FOUND at {model_path}."
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)
            
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        
        # Load ONNX session with CPU provider (optimal for lean Docker)
        onnx_file = os.path.join(model_path, "model.onnx")
        self.session = ort.InferenceSession(onnx_file, providers=["CPUExecutionProvider"])
        
        logger.info("ONNX embedder (torch-free) loaded successfully")

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True,
    ) -> np.ndarray:
        """
        Encode text(s) into embedding vectors using standard ONNX + NumPy.
        """
        single_input = isinstance(texts, str)
        if single_input:
            texts = [texts]

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]

            # Tokenize to NumPy arrays
            encoded = self.tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="np",
            )

            # Prepare ONNX inputs (ensure int64 as expected by the model)
            inputs = {k: v.astype(np.int64) for k, v in encoded.items()}
            
            # Run ONNX inference
            outputs = self.session.run(None, inputs)
            
            # last_hidden_state is usually the first output (index 0)
            token_embeddings = outputs[0]
            
            # Manual Mean Pooling in NumPy
            attention_mask = encoded["attention_mask"]
            mask = np.expand_dims(attention_mask, axis=-1).astype(float)
            masked_embeddings = token_embeddings * mask
            
            summed = np.sum(masked_embeddings, axis=1)
            counts = np.clip(np.sum(mask, axis=1), a_min=1e-9, a_max=None)
            mean_pooled = summed / counts

            all_embeddings.append(mean_pooled)

        embeddings = np.vstack(all_embeddings).astype(np.float32)

        # L2 normalization in NumPy
        if normalize_embeddings:
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms = np.clip(norms, a_min=1e-9, a_max=None)
            embeddings = embeddings / norms

        if single_input:
            return embeddings[0]

        return embeddings


# ------------------------------------------------------------------ #
#  MODULE-LEVEL SINGLETON
# ------------------------------------------------------------------ #

# Resolve ONNX model path:
# 1. Environment variable ONNX_MODEL_PATH (for custom deployments)
# 2. backend/models/onnx/ (shipped with the repo)
# 3. Fallback to HF model ID (downloads at runtime — not recommended for prod)
_onnx_model_path = (
    Path(__file__).resolve().parent.parent.parent / "models" / "onnx"
)

# Allow override via env var
if os.environ.get("ONNX_MODEL_PATH"):
    _onnx_model_path = Path(os.environ["ONNX_MODEL_PATH"])

model = ONNXEmbedder(str(_onnx_model_path))

# In-memory cache for embeddings
embedding_cache = {}


async def get_embedding(text: str) -> List[float]:
    """Get embedding for a single text using local ONNX model."""

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