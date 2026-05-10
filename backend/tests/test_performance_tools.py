from app.services.agent_tools import get_debt_performance, get_equity_performance, get_hybrid_performance
from tests.fixtures.mock_performance_data import MOCK_DEBT_PERF, MOCK_EQUITY_PERF, MOCK_HYBRID_PERF

# ==============================================================================
# Tests for get_equity_performance
# ==============================================================================

def test_get_equity_performance_success(mock_mf_instance):
    """Test successful fetching of equity performance."""
    response = get_equity_performance.invoke({})
    
    assert response == MOCK_EQUITY_PERF
    mock_mf_instance.get_open_ended_equity_scheme_performance.assert_called()

def test_get_equity_performance_with_date(mock_mf_instance):
    """Test equity performance fetching with a specific date."""
    response = get_equity_performance.invoke({"report_date": "07-May-2026"})
    
    assert response == MOCK_EQUITY_PERF
    mock_mf_instance.get_open_ended_equity_scheme_performance.assert_called_once_with("07-May-2026", as_json=False)

def test_get_equity_performance_cache(mock_mf_instance):
    """Test caching mechanism for equity performance."""
    get_equity_performance.invoke({"report_date": "07-May-2026"})
    get_equity_performance.invoke({"report_date": "07-May-2026"})
    
    mock_mf_instance.get_open_ended_equity_scheme_performance.assert_called_once()

def test_get_equity_performance_exception(mock_mf_instance):
    """Test exception handling for equity performance."""
    mock_mf_instance.get_open_ended_equity_scheme_performance.side_effect = Exception("Service unavailable")
    
    response = get_equity_performance.invoke({})
    assert "error" in response
    assert "currently unavailable" in response["error"]


# ==============================================================================
# Tests for get_debt_performance
# ==============================================================================

def test_get_debt_performance_success(mock_mf_instance):
    """Test successful fetching of debt performance."""
    response = get_debt_performance.invoke({})
    
    assert response == MOCK_DEBT_PERF
    mock_mf_instance.get_open_ended_debt_scheme_performance.assert_called()

def test_get_debt_performance_cache(mock_mf_instance):
    """Test caching mechanism for debt performance."""
    get_debt_performance.invoke({})
    get_debt_performance.invoke({})
    
    mock_mf_instance.get_open_ended_debt_scheme_performance.assert_called_once()

def test_get_debt_performance_exception(mock_mf_instance):
    """Test exception handling for debt performance."""
    mock_mf_instance.get_open_ended_debt_scheme_performance.side_effect = Exception("API limit reached")
    
    response = get_debt_performance.invoke({})
    assert "error" in response
    assert "currently unavailable" in response["error"]


# ==============================================================================
# Tests for get_hybrid_performance
# ==============================================================================

def test_get_hybrid_performance_success(mock_mf_instance):
    """Test successful fetching of hybrid performance."""
    response = get_hybrid_performance.invoke({"report_date": "06-May-2026"})
    
    assert response == MOCK_HYBRID_PERF
    mock_mf_instance.get_open_ended_hybrid_scheme_performance.assert_called_once_with("06-May-2026", as_json=False)

def test_get_hybrid_performance_cache(mock_mf_instance):
    """Test caching mechanism for hybrid performance."""
    get_hybrid_performance.invoke({"report_date": "06-May-2026"})
    get_hybrid_performance.invoke({"report_date": "06-May-2026"})
    
    mock_mf_instance.get_open_ended_hybrid_scheme_performance.assert_called_once()

def test_get_hybrid_performance_exception(mock_mf_instance):
    """Test exception handling for hybrid performance."""
    mock_mf_instance.get_open_ended_hybrid_scheme_performance.side_effect = Exception("Timeout")
    
    response = get_hybrid_performance.invoke({})
    assert "error" in response
    assert "currently unavailable" in response["error"]
