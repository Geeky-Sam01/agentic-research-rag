import pytest
from app.services.agent_tools import read_factsheet
from tests.fixtures.mock_rag_data import MOCK_RAG_RESPONSE, MOCK_RAG_EMPTY_RESPONSE

# ==============================================================================
# Tests for read_factsheet
# ==============================================================================

def test_read_factsheet_success(mock_rag_services):
    """Test successful retrieval of factsheet data via RAG."""
    query = "What is the investment strategy of Axis Bluechip?"
    response = read_factsheet.invoke({"query": query})
    
    assert response == MOCK_RAG_RESPONSE
    mock_rag_services["get_client"].assert_called_once()
    mock_rag_services["get_rag_context"].assert_called_once_with(
        query, mock_rag_services["client"], mock_rag_services["embedder"]
    )

def test_read_factsheet_empty_results(mock_rag_services):
    """Test behavior when RAG returns no relevant documents."""
    mock_rag_services["get_rag_context"].return_value = MOCK_RAG_EMPTY_RESPONSE
    
    query = "What is the secret recipe?"
    response = read_factsheet.invoke({"query": query})
    
    assert response == MOCK_RAG_EMPTY_RESPONSE
    assert response["raw_results_count"] == 0
    assert len(response["sources"]) == 0

def test_read_factsheet_exception(mock_rag_services):
    """Test exception handling during RAG process."""
    mock_rag_services["get_rag_context"].side_effect = Exception("Vector DB connection failed")
    
    query = "What is the investment strategy?"
    response = read_factsheet.invoke({"query": query})
    
    assert "error" in response
    assert "Vector DB connection failed" in response["error"]
    assert response["context"] == ""
    assert response["sources"] == []

@pytest.mark.parametrize("invalid_query", [
    "", "   ", "a"*1000  # Very long string
])
def test_read_factsheet_edge_cases(mock_rag_services, invalid_query):
    """Test read_factsheet with edge case queries."""
    # The current implementation passes whatever string to the RAG pipeline.
    # We ensure it doesn't crash our tool wrapper.
    response = read_factsheet.invoke({"query": invalid_query})
    
    assert "error" not in response  # Assuming the mock returns a successful response
    mock_rag_services["get_rag_context"].assert_called_once_with(
        invalid_query, mock_rag_services["client"], mock_rag_services["embedder"]
    )
