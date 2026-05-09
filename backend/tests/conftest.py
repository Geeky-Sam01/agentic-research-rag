import pytest
from unittest.mock import Mock, patch

# Clear caches for isolation
from app.services.agent_tools import cache
import app.services.agent_tools as agent_tools

from tests.fixtures.mock_nav_data import MOCK_SCHEME_QUOTE, MOCK_HISTORICAL_NAV
from tests.fixtures.mock_performance_data import MOCK_EQUITY_PERF, MOCK_DEBT_PERF, MOCK_HYBRID_PERF
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
    mock_mf.calculate_returns.return_value = {
        "total_invested": 120000.0,
        "current_value": 150000.0,
        "profit_loss": 30000.0,
        "returns_pct": 25.0
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
