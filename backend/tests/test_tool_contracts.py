import pytest

from app.services.agent_tools import ALL_MF_TOOLS

# ==============================================================================
# Tests for general tool contracts (Schema & Error Handling)
# ==============================================================================

def test_all_tools_are_callable():
    """Ensure all tools exported have an invoke method (Langchain tool)."""
    for tool in ALL_MF_TOOLS:
        assert hasattr(tool, "invoke"), f"Tool {tool.name} is missing 'invoke' method."
        assert hasattr(tool, "name"), "Tool is missing a name attribute."
        assert hasattr(tool, "description"), f"Tool {tool.name} is missing a description."

@pytest.mark.parametrize("tool", ALL_MF_TOOLS)
def test_tools_handle_exceptions_gracefully(tool, mock_mf_instance, mock_rag_services):
    """
    Ensure no tool raises unhandled exceptions when dependencies fail.
    Instead, they must return a dictionary containing an 'error' key.
    """
    # Force all mock methods to raise exceptions
    mock_mf_instance.get_scheme_quote.side_effect = Exception("General Mock Error")
    mock_mf_instance.get_scheme_historical_nav.side_effect = Exception("General Mock Error")
    mock_mf_instance.get_open_ended_equity_scheme_performance.side_effect = Exception("General Mock Error")
    mock_mf_instance.get_open_ended_debt_scheme_performance.side_effect = Exception("General Mock Error")
    mock_mf_instance.get_open_ended_hybrid_scheme_performance.side_effect = Exception("General Mock Error")
    mock_mf_instance.get_scheme_codes.side_effect = Exception("General Mock Error")
    mock_mf_instance.calculate_returns.side_effect = Exception("General Mock Error")
    mock_rag_services["get_rag_context"].side_effect = Exception("General Mock Error")
    
    # We need to construct dummy inputs based on tool name/schema to invoke them
    dummy_input = {}
    if "scheme_code" in tool.description.lower() or "quote" in tool.name or "returns" in tool.name:
        dummy_input["scheme_code"] = "119551"
    if "keyword" in tool.description.lower():
        dummy_input["keyword"] = "test"
    if "amc_name" in tool.description.lower() or "search_schemes" == tool.name:
        dummy_input["amc_name"] = "test"
    if "returns" in tool.name:
        dummy_input.update({
            "balance_units": 100,
            "monthly_sip": 1000,
            "investment_months": 12
        })
    if "factsheet" in tool.name:
        dummy_input["query"] = "test query"
        
    response = tool.invoke(dummy_input)
    
    # Contract checks
    assert isinstance(response, dict), f"Tool {tool.name} must return a dictionary even on error."
    assert "error" in response, f"Tool {tool.name} must include an 'error' key when an exception occurs."
    assert "General Mock Error" in response["error"] or "error" in response["error"].lower(), \
        f"Tool {tool.name} error message does not contain the exception details or standard error text."

@pytest.mark.parametrize("tool", ALL_MF_TOOLS)
def test_tools_return_dictionary_on_success(tool, mock_mf_instance, mock_rag_services):
    """
    Ensure all tools return dictionaries on successful execution.
    """
    dummy_input = {}
    if "scheme_code" in tool.description.lower() or "quote" in tool.name or "returns" in tool.name:
        dummy_input["scheme_code"] = "119551"
    if "keyword" in tool.description.lower():
        dummy_input["keyword"] = "bluechip"
    if "amc_name" in tool.description.lower() or "search_schemes" == tool.name:
        dummy_input["amc_name"] = "Axis"
    if "returns" in tool.name:
        dummy_input.update({
            "balance_units": 100,
            "monthly_sip": 1000,
            "investment_months": 12
        })
    if "factsheet" in tool.name:
        dummy_input["query"] = "test query"
        
    response = tool.invoke(dummy_input)
    
    # Contract check
    assert isinstance(response, dict), f"Tool {tool.name} must return a dictionary on success."
