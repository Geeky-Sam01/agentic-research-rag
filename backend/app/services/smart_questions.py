import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

TEMPLATES = {
    "nav": "What is the NAV of {fund_name}?",
    "expense_ratio": "What is the expense ratio?",
    "performance": "How has the fund performed over 5 years?",
    "holdings": "What are the top holdings?",
    "risk": "How risky is this fund?",
    "benchmark": "Compare this fund with its benchmark",
    "sharpe": "What is the Sharpe ratio?",
    "sectors": "What sectors does this fund invest in?",
    "aum": "What is the AUM of the fund?",
}

PRIORITY = ["nav", "performance", "risk", "holdings", "expense_ratio"]

def generate_smart_questions(document: List[Dict[str, Any]], fund_name: str) -> List[str]:
    """
    Generates a list of suggested questions based on the presence of key sections 
    in the extracted document.
    """
    found_signals = set()
    
    # 1. Scan for signals in section headings
    for page in document:
        for section in page.get("sections", []):
            heading = section.get("heading", "").lower()
            
            if "nav" in heading:
                found_signals.add("nav")
            if "expense" in heading:
                found_signals.add("expense_ratio")
            if "performance" in heading or "return" in heading:
                found_signals.add("performance")
            if "holding" in heading or "portfolio" in heading:
                found_signals.add("holdings")
            if "risk" in heading or "quant" in heading:
                found_signals.add("risk")
            if "benchmark" in heading:
                found_signals.add("benchmark")
            if "sharpe" in heading:
                found_signals.add("sharpe")
            if "sector" in heading or "industry" in heading:
                found_signals.add("sectors")
            if "aum" in heading or "asset under management" in heading or "market cap" in heading:
                found_signals.add("aum")

    # 2. Map signals to questions
    suggested = []
    
    # Add priority questions if signals found
    for signal in PRIORITY:
        if signal in found_signals and signal in TEMPLATES:
            question = TEMPLATES[signal].format(fund_name=fund_name)
            suggested.append(question)
            
    # Add remaining if we have space (limit to 5 total)
    for signal, question_tpl in TEMPLATES.items():
        if len(suggested) >= 5:
            break
        if signal not in PRIORITY and signal in found_signals:
            question = question_tpl.format(fund_name=fund_name)
            suggested.append(question)
            
    # Fallback if no specific signals found
    if not suggested:
        suggested = [
            f"Summarize the {fund_name} document",
            "What are the key highlights?",
            "What is the investment objective?",
            "Who are the fund managers?",
            "What is the exit load?"
        ]

    return suggested[:5]
