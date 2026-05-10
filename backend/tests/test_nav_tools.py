import pytest
from pydantic import ValidationError

from app.services.agent_tools import get_historical_nav, get_scheme_quote
from tests.fixtures.mock_nav_data import MOCK_HISTORICAL_NAV, MOCK_SCHEME_QUOTE

# ==============================================================================
# Tests for get_scheme_quote
# ==============================================================================

def test_get_scheme_quote_success(mock_mf_instance):
    """Test successful fetching of scheme quote."""
    response = get_scheme_quote.invoke({"scheme_code": "119551"})
    
    assert response == MOCK_SCHEME_QUOTE
    mock_mf_instance.get_scheme_quote.assert_called_once_with("119551", as_json=False)

def test_get_scheme_quote_cache_hit(mock_mf_instance):
    """Test that subsequent calls use cache and avoid redundant API calls."""
    # First call
    get_scheme_quote.invoke({"scheme_code": "119551"})
    # Second call (should hit cache)
    response = get_scheme_quote.invoke({"scheme_code": "119551"})
    
    assert response == MOCK_SCHEME_QUOTE
    # The underlying method should only be called once
    mock_mf_instance.get_scheme_quote.assert_called_once()

def test_get_scheme_quote_mf_error(mock_mf_instance):
    """Test handling of explicit error dictionaries from the MF library."""
    mock_mf_instance.get_scheme_quote.return_value = {"error": "Scheme code not found"}
    
    response = get_scheme_quote.invoke({"scheme_code": "999999"})
    assert "error" in response
    assert response["error"] == "Scheme code not found"

def test_get_scheme_quote_exception(mock_mf_instance):
    """Test handling of unhandled exceptions raised during fetching."""
    mock_mf_instance.get_scheme_quote.side_effect = Exception("Network timeout")
    
    response = get_scheme_quote.invoke({"scheme_code": "119551"})
    assert "error" in response
    assert "Network timeout" in response["error"]




@pytest.mark.parametrize("invalid_input", [
    None, 12345, [], {}
])
def test_get_scheme_quote_invalid_input(mock_mf_instance, invalid_input):
    """Test handling of various invalid input types or empty values via Pydantic validation."""
    with pytest.raises(ValidationError):
        get_scheme_quote.invoke({"scheme_code": invalid_input})


# ==============================================================================
# Tests for get_historical_nav
# ==============================================================================

def test_get_historical_nav_success(mock_mf_instance):
    """Test successful fetching of historical NAV."""
    response = get_historical_nav.invoke({"scheme_code": "119551"})
    
    assert response == MOCK_HISTORICAL_NAV
    mock_mf_instance.get_scheme_historical_nav.assert_called_once_with("119551", as_json=False)

def test_get_historical_nav_cache_hit(mock_mf_instance):
    """Test that historical NAV requests are cached."""
    get_historical_nav.invoke({"scheme_code": "119551"})
    response = get_historical_nav.invoke({"scheme_code": "119551"})
    
    assert response == MOCK_HISTORICAL_NAV
    mock_mf_instance.get_scheme_historical_nav.assert_called_once()

def test_get_historical_nav_returns_none(mock_mf_instance):
    """Test behavior when the underlying library returns None."""
    mock_mf_instance.get_scheme_historical_nav.return_value = None
    
    response = get_historical_nav.invoke({"scheme_code": "invalid_code"})
    assert "error" in response
    assert "invalid_code" in response["error"]

def test_get_historical_nav_exception(mock_mf_instance):
    """Test behavior when an exception is raised."""
    mock_mf_instance.get_scheme_historical_nav.side_effect = ValueError("Invalid data format")
    
    response = get_historical_nav.invoke({"scheme_code": "119551"})
    assert "error" in response
    assert "Invalid data format" in response["error"]
