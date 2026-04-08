FROM python:3.12-slim

# Install uv binary
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv

WORKDIR /app

# Environment
ENV UV_SYSTEM_PYTHON=1
ENV PATH="/uv/bin:${PATH}"
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache/huggingface/sentence_transformers

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install CPU-only PyTorch explicitly before uv sync
RUN uv pip install \
    torch==2.11.0 \
    torchvision==0.26.0 \
    --index-url https://download.pytorch.org/whl/cpu

# Install remaining dependencies
COPY pyproject.toml uv.lock ./
RUN uv pip install -r pyproject.toml

# Pre-download embedding model at build time (cache path now matches runtime)
RUN python -c "\
from sentence_transformers import SentenceTransformer; \
SentenceTransformer('BAAI/bge-small-en-v1.5')"

# Copy application code last (best layer caching)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]