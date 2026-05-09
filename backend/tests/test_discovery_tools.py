import pytest
from app.services.agent_tools import search_schemes, search_scheme_by_name

# ==============================================================================
# Tests for search_schemes
# ==============================================================================

def test_search_schemes_exact_match(mock_mf_instance):
    """Test searching schemes by exact AMC name match."""
    response = search_schemes.invoke({"amc_name": "Axis"})
    
    # Expect 4 axis funds based on MOCK_ALL_SCHEMES
    assert len(response) == 4
    assert "120465" in response
    assert "120000" in response
    assert response["120465"] == "Axis Bluechip Fund"

def test_search_schemes_fallback_match(mock_mf_instance):
    """Test fallback logic when exact match fails but split words match."""
    # Assuming MOCK_ALL_SCHEMES has "Aditya Birla Sun Life Frontline Equity Fund"
    # If we search for "Aditya Birla Mutual", it fails exact, but "Aditya" matches
    response = search_schemes.invoke({"amc_name": "Aditya Mutual"})
    
    assert len(response) == 1
    assert "119551" in response

def test_search_schemes_no_match(mock_mf_instance):
    """Test searching for an AMC that doesn't exist."""
    response = search_schemes.invoke({"amc_name": "NonExistentAMC"})
    
    assert "error" in response
    assert "No schemes found" in response["error"]

def test_search_schemes_caching(mock_mf_instance):
    """Test that all schemes are cached in memory."""
    search_schemes.invoke({"amc_name": "Axis"})
    search_schemes.invoke({"amc_name": "HDFC"})
    
    # get_scheme_codes should only be called once
    mock_mf_instance.get_scheme_codes.assert_called_once()

def test_search_schemes_exception(mock_mf_instance):
    """Test exception handling."""
    mock_mf_instance.get_scheme_codes.side_effect = Exception("Memory error")
    
    response = search_schemes.invoke({"amc_name": "Axis"})
    assert "error" in response
    assert "Memory error" in response["error"]

# ==============================================================================
# Tests for search_scheme_by_name
# ==============================================================================

def test_search_scheme_by_name_exact(mock_mf_instance):
    """Test searching scheme by exact keyword."""
    response = search_scheme_by_name.invoke({"keyword": "Bluechip"})
    
    assert len(response) == 2
    assert "120465" in response  # Axis Bluechip
    assert "112345" in response  # ICICI Bluechip

def test_search_scheme_by_name_case_insensitive(mock_mf_instance):
    """Test case insensitivity."""
    response = search_scheme_by_name.invoke({"keyword": "bluechip"})
    
    assert len(response) == 2

def test_search_scheme_by_name_fallback(mock_mf_instance):
    """Test fallback splitting logic."""
    response = search_scheme_by_name.invoke({"keyword": "Axis Liquid Extra"})
    
    # "axis liquid extra" as exact string won't match, 
    # but split words "axis" and "liquid" will match Axis Liquid Fund.
    assert len(response) >= 1
    assert "120000" in response

def test_search_scheme_by_name_no_match(mock_mf_instance):
    """Test with a keyword that yields no results."""
    response = search_scheme_by_name.invoke({"keyword": "Blockchain"})
    
    assert "error" in response
    assert "No schemes found" in response["error"]

def test_search_scheme_by_name_exception(mock_mf_instance):
    """Test exception handling."""
    mock_mf_instance.get_scheme_codes.side_effect = Exception("Failed to load")
    
    response = search_scheme_by_name.invoke({"keyword": "Fund"})
    assert "error" in response
    assert "Failed to load" in response["error"]
