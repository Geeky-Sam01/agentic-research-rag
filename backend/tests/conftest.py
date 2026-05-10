import os
from unittest.mock import Mock

import pytest

# ── Set required env vars before importing app modules ────────────────────────
os.environ.setdefault("OPENROUTER_API_KEY", "test-key")
os.environ.setdefault("PORT", "8000")
os.environ.setdefault("HOST", "0.0.0.0")
os.environ.setdefault("DEBUG", "false")
os.environ.setdefault("CORS_ORIGIN", "*")
os.environ.setdefault("INDEX_PATH", "/tmp/test_indices")
os.environ.setdefault("UPLOAD_PATH", "/tmp/test_uploads")
os.environ.setdefault("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
os.environ.setdefault("EMBEDDING_DIM", "384")
os.environ.setdefault("LLM_MODEL", "openrouter/free")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")

import app.services.agent_tools as agent_tools

# Clear caches for isolation
from app.services.agent_tools import cache
from tests.fixtures.mock_nav_data import MOCK_HISTORICAL_NAV, MOCK_SCHEME_QUOTE
from tests.fixtures.mock_performance_data import MOCK_DEBT_PERF, MOCK_EQUITY_PERF, MOCK_HYBRID_PERF
from tests.fixtures.mock_rag_data import MOCK_RAG_RESPONSE
from tests.fixtures.mock_scheme_data import MOCK_ALL_SCHEMES


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear caches before and after each test to ensure isolation."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def mock_mf_instance(monkeypatch):
    """Mocks the mutual fund instance 'mf' used in agent_tools."""
    mock_mf = Mock()
    
    # Default successful mock responses
    mock_mf.get_scheme_quote.return_value = MOCK_SCHEME_QUOTE
    mock_mf.get_scheme_historical_nav.return_value = MOCK_HISTORICAL_NAV
    mock_mf.get_open_ended_equity_scheme_performance.return_value = MOCK_EQUITY_PERF
    mock_mf.get_open_ended_debt_scheme_performance.return_value = MOCK_DEBT_PERF
    mock_mf.get_open_ended_hybrid_scheme_performance.return_value = MOCK_HYBRID_PERF
    mock_mf.get_scheme_codes.return_value = MOCK_ALL_SCHEMES
    mock_mf.calculate_historical_sip_returns.return_value = {
        "total_invested": 120000.0,
        "current_value": 150000.0,
        "profit_loss": 30000.0,
        "returns_pct": 25.0
    }
    mock_mf.calculate_projected_sip_returns.return_value = {
        "total_invested": 120000.0,
        "projected_corpus": 150000.0,
        "estimated_gains": 30000.0
    }
    
    monkeypatch.setattr(agent_tools, "mf", mock_mf)
    return mock_mf


@pytest.fixture
def mock_rag_services(monkeypatch):
    """Mocks the RAG services including qdrant, embeddings, and context retrieval."""
    mock_client = Mock()
    mock_get_client = Mock(return_value=mock_client)
    mock_get_rag_context = Mock(return_value=MOCK_RAG_RESPONSE)
    mock_embedder = Mock()
    
    monkeypatch.setattr(agent_tools, "get_client", mock_get_client)
    monkeypatch.setattr(agent_tools, "get_rag_context", mock_get_rag_context)
    monkeypatch.setattr(agent_tools, "_embedder", mock_embedder)
    
    return {
        "client": mock_client,
        "get_client": mock_get_client,
        "get_rag_context": mock_get_rag_context,
        "embedder": mock_embedder
    }
