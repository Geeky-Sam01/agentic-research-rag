from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from app.core.config import settings
from app.api.documents import router as documents_router
from app.api.chat import router as chat_router
from app.services.document_processor import init_ocr

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Agentic Research RAG API",
    description="Python FastAPI RAG system with Qdrant, BGE, and OpenRouter",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.on_event("startup")
async def startup_event():
    """Tasks to run on startup: pre-load models, connect DBs, etc."""
    logger.info("Starting up Agentic Research RAG API...")
    # Pre-load EasyOCR weights so they're ready for image PDFs instantly
    init_ocr()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.CORS_ORIGIN] if settings.CORS_ORIGIN != "*" else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(documents_router)
app.include_router(chat_router)

@app.get("/")
async def root():
    return {
        "message": "Welcome to Agentic Research RAG API",
        "docs": "/docs",
        "health": "/health",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "RAG Backend",
        "embedding_model": settings.EMBEDDING_MODEL,
        "embedding_dimension": settings.EMBEDDING_DIM,
        "llm_model": settings.LLM_MODEL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app", 
        host=settings.HOST, 
        port=settings.PORT, 
        reload=True
    )
