# --- Stage 1: Builder ---
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uv/bin/uv

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1
ENV PATH="/uv/bin:${PATH}"

# Install compilers (only for building wheels)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml uv.lock ./

# Use 'uv pip install' to force installation into system site-packages (easy to copy)
RUN uv pip install -r pyproject.toml

# --- Stage 2: Final Runtime ---
FROM python:3.12-slim

WORKDIR /app

# Install ONLY runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages and binaries from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application last
COPY . .

EXPOSE 8000

# Use direct uvicorn (now correctly in the system path)
CMD ["/bin/sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]