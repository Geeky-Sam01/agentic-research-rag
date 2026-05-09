"""Mock data for RAG related tools."""

MOCK_RAG_RESPONSE = {
    "context": "The fund primarily invests in large-cap stocks, focusing on market leaders with strong balance sheets. It has a conservative risk profile suitable for long-term investors.",
    "sources": ["Axis_Bluechip_Factsheet_May2026.pdf"],
    "raw_results_count": 3
}

MOCK_RAG_EMPTY_RESPONSE = {
    "context": "No relevant information found in the documents.",
    "sources": [],
    "raw_results_count": 0
}
