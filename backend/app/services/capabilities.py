import logging
import re
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

SUPPORTED_CAPABILITIES = {
    "nav": True,
    "historical_returns": True,
    "fund_category": True,
    "sip_calculation": True,
    "fund_holdings": False,
    "fund_manager": False,
    "expense_ratio": False,
    "aum": False,
    "risk_metrics": False,
    "portfolio_overlap": False,
}

QUERY_CAPABILITY_MAP = {
    "expense ratio": "expense_ratio",
    "expense ration": "expense_ratio",
    "exp ratio": "expense_ratio",
    "aum": "aum",
    "total assets": "aum",
    "total asset": "aum",
    "fund size": "aum",
    "nav": "nav",
    "price": "nav",
    "holdings": "fund_holdings",
    "portfolio": "fund_holdings",
    "stocks": "fund_holdings",
    "top 10": "fund_holdings",
    "fund manager": "fund_manager",
    "who manages": "fund_manager",
    "manager name": "fund_manager",
    "category": "fund_category",
    "sip": "sip_calculation",
    "returns": "historical_returns",
    "cagr": "historical_returns",
    "performance": "historical_returns",
    "risk": "risk_metrics",
    "sharpe": "risk_metrics",
    "volatility": "risk_metrics",
    "beta": "risk_metrics",
    "overlap": "portfolio_overlap",
}

UNSUPPORTED_CAPABILITY_RESPONSES = {
    "expense_ratio": "I currently don't have reliable expense ratio data support yet. I'm working on adding more fund detail coverage soon.",
    "aum": "I currently don't have reliable AUM (Assets Under Management) data available yet.",
    "risk_metrics": "Advanced risk metrics like Sharpe ratio or Beta are not available currently. I can help with historical returns instead.",
    "portfolio_overlap": "Portfolio overlap analysis is a planned feature but is not yet supported in the current version.",
    "sip_calculation": "Sip calculation is not supported yet. Coming soon!",
    "fund_holdings": "Fund holdings details are not available yet. Coming soon!",
    "fund_manager": "Fund manager details are not available yet. Coming soon!",
}

TOOL_CAPABILITY_MAP = {
    "get_scheme_quote": ["nav"],
    "get_historical_nav": ["historical_returns"],
    "calculate_historical_sip_returns": ["sip_calculation", "historical_returns"],
    "calculate_projected_sip_returns": ["sip_calculation"],
    "read_factsheet": ["fund_holdings", "fund_manager", "fund_category"],
}


def detect_requested_capability(message: str) -> Optional[str]:
    """Identify the strongest matching capability from a user message."""
    msg_lower = message.lower()

    sorted_patterns = sorted(QUERY_CAPABILITY_MAP.keys(), key=len, reverse=True)

    for pattern in sorted_patterns:
        if pattern in msg_lower:
            capability = QUERY_CAPABILITY_MAP[pattern]
            logger.debug(f"CapabilityGate: detected '{capability}' from pattern '{pattern}'")
            return capability

    return None


def get_unsupported_message(capability: str) -> str:
    """Get the deterministic response for an unsupported capability."""
    return UNSUPPORTED_CAPABILITY_RESPONSES.get(
        capability, "I'm sorry, but that specific analysis is not yet supported in my current version."
    )
