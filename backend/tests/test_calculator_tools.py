import pytest
from pydantic import ValidationError

from app.services.agent_tools import calculate_historical_sip_returns

# ==============================================================================
# Tests for calculate_historical_sip_returns
# ==============================================================================

def test_calculate_historical_sip_returns_success(mock_mf_instance):
    """Test successful calculation of returns."""
    params = {
        "scheme_code": "119551",
        "balance_units": 1000.5,
        "monthly_sip": 5000,
        "investment_months": 24
    }
    response = calculate_historical_sip_returns.invoke(params)
    
    assert "total_invested" in response
    assert response["total_invested"] == 120000.0




def test_calculate_historical_sip_returns_invalid_types(mock_mf_instance):
    """Test handling of invalid input types."""
    params = {
        "scheme_code": "119551",
        "balance_units": "not_a_number",
        "monthly_sip": 5000,
        "investment_months": 24
    }
    with pytest.raises(ValidationError):
        calculate_historical_sip_returns.invoke(params)

def test_calculate_historical_sip_returns_negative_values(mock_mf_instance):
    """Test handling of negative input values."""
    params = {
        "scheme_code": "119551",
        "balance_units": -100,
        "monthly_sip": 5000,
        "investment_months": 24
    }
    response = calculate_historical_sip_returns.invoke(params)
    
    assert "error" in response
    assert "Invalid input values" in response["error"]

def test_calculate_historical_sip_returns_zero_months(mock_mf_instance):
    """Test handling of zero investment months."""
    params = {
        "scheme_code": "119551",
        "balance_units": 100,
        "monthly_sip": 5000,
        "investment_months": 0
    }
    response = calculate_historical_sip_returns.invoke(params)
    
    assert "error" in response
    assert "Invalid input values" in response["error"]

def test_calculate_historical_sip_returns_none_returned(mock_mf_instance):
    """Test behavior when the underlying calculator returns None."""
    params = {
        "scheme_code": "999999",
        "balance_units": 100,
        "monthly_sip": 5000,
        "investment_months": 12
    }
    # If quote fails, tool returns the quote error
    mock_mf_instance.get_scheme_quote.return_value = {"error": "Scheme code not found"}
    response = calculate_historical_sip_returns.invoke(params)
    
    assert "error" in response
    assert "Scheme code not found" in response["error"]

    mock_mf_instance.get_scheme_quote.side_effect = Exception("Calculation error")
    
    params = {
        "scheme_code": "119551",
        "balance_units": 100,
        "monthly_sip": 5000,
        "investment_months": 12
    }
    response = calculate_historical_sip_returns.invoke(params)
    
    assert "error" in response
    assert "Calculation error" in response["error"]
