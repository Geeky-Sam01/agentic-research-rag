import logging
from datetime import datetime
from typing import Optional

from cachetools import TTLCache

from langchain_core.tools import tool

from app.services.embeddings import model as _embedder
from app.services.mf_instance import mf
from app.services.qdrant_service import get_client
from app.services.rag_pipeline import get_rag_context

logger = logging.getLogger(__name__)

# ============== CACHING SETUP ==============
_nav_cache = TTLCache(maxsize=500, ttl=4 * 3600)
_performance_cache = TTLCache(maxsize=10, ttl=6 * 3600)
_cached_all_schemes: Optional[dict] = None


def _get_all_schemes() -> dict:
    """Get all schemes with caching."""
    global _cached_all_schemes
    if _cached_all_schemes is None:
        logger.info("Loading all schemes into memory...")
        _cached_all_schemes = mf.get_scheme_codes(as_json=False) or {}
        logger.info(f"Loaded {len(_cached_all_schemes)} schemes")
    return _cached_all_schemes


# ============== DATA TOOLS (NAV, History) ==============


@tool
def get_scheme_quote(scheme_code: str) -> dict:
    """Fetch the latest NAV for a mutual fund scheme by its scheme code.

    Args:
        scheme_code: The AMFI scheme code (e.g., "119551").

    Returns:
        Dict with scheme_code, scheme_name, nav, and last_updated.
    """
    logger.info(f"Fetching scheme quote for: {scheme_code}")
    cache_key = f"quote_{scheme_code}"
    if cache_key in _nav_cache:
        return _nav_cache[cache_key]

    try:
        quote = mf.get_scheme_quote(scheme_code, as_json=False)
        if quote and "error" not in quote:
            _nav_cache[cache_key] = quote
        return quote
    except Exception as e:
        logger.error(f"Error fetching quote for {scheme_code}: {str(e)}")
        return {"error": f"Failed to fetch quote: {str(e)}"}


@tool
def get_historical_nav(scheme_code: str) -> dict:
    """Get the full historical NAV data for a mutual fund scheme.

    Args:
        scheme_code: The AMFI scheme code (e.g., "122628").

    Returns:
        Dict with fund_house, scheme_type, scheme_category, scheme_name,
        52_week_high, 52_week_low, and nav data array.
    """
    logger.info(f"Fetching historical NAV for: {scheme_code}")
    cache_key = f"history_{scheme_code}_{datetime.now().strftime('%Y-%m-%d')}"
    if cache_key in _nav_cache:
        return _nav_cache[cache_key]

    try:
        result = mf.get_scheme_historical_nav(scheme_code, as_json=False)
        if result is None:
            return {"error": f"Invalid scheme code or no data: {scheme_code}"}
        _nav_cache[cache_key] = result
        return result
    except Exception as e:
        logger.error(f"Error fetching history for {scheme_code}: {str(e)}")
        return {"error": str(e)}


# ============== PERFORMANCE TOOLS ==============


@tool
def get_equity_performance(report_date: str = None) -> dict:
    """Get daily performance of open-ended equity schemes.

    Args:
        report_date: Optional date in DD-MMM-YYYY format.

    Returns:
        Dict organized by equity sub-category with fund-level performance.
    """
    logger.info(f"Fetching equity performance (date: {report_date})")
    cache_key = f"equity_perf_{report_date or 'latest'}"
    if cache_key in _performance_cache:
        return _performance_cache[cache_key]

    try:
        data = mf.get_open_ended_equity_scheme_performance(report_date, as_json=False)
        _performance_cache[cache_key] = data
        return data
    except Exception as e:
        logger.error(f"Error fetching equity performance: {str(e)}")
        return {"error": str(e)}


@tool
def get_debt_performance(report_date: str = None) -> dict:
    """Get daily performance of open-ended debt schemes."""
    logger.info(f"Fetching debt performance (date: {report_date})")
    cache_key = f"debt_perf_{report_date or 'latest'}"
    if cache_key in _performance_cache:
        return _performance_cache[cache_key]

    try:
        data = mf.get_open_ended_debt_scheme_performance(report_date, as_json=False)
        _performance_cache[cache_key] = data
        return data
    except Exception as e:
        logger.error(f"Error fetching debt performance: {str(e)}")
        return {"error": str(e)}


@tool
def get_hybrid_performance(report_date: str = None) -> dict:
    """Get daily performance of open-ended hybrid schemes."""
    logger.info(f"Fetching hybrid performance (date: {report_date})")
    cache_key = f"hybrid_perf_{report_date or 'latest'}"
    if cache_key in _performance_cache:
        return _performance_cache[cache_key]

    try:
        data = mf.get_open_ended_hybrid_scheme_performance(report_date, as_json=False)
        _performance_cache[cache_key] = data
        return data
    except Exception as e:
        logger.error(f"Error fetching hybrid performance: {str(e)}")
        return {"error": str(e)}


# ============== DISCOVERY TOOLS ==============


@tool
def search_schemes(amc_name: str) -> dict:
    """Find all mutual fund schemes under a given AMC/fund house.

    Args:
        amc_name: Name of the fund house (e.g., "Axis", "ICICI", "HDFC", "SBI").

    Returns:
        Dict mapping scheme codes to scheme names for the AMC.
    """
    logger.info(f"Searching schemes for AMC: {amc_name}")
    amc_normalized = amc_name.strip().upper()

    try:
        all_schemes = _get_all_schemes()
        schemes = {k: v for k, v in all_schemes.items() if amc_normalized in v.upper()}

        if not schemes:
            amc_words = amc_normalized.split()
            schemes = {
                k: v for k, v in all_schemes.items() if any(word in v.upper() for word in amc_words if len(word) > 2)
            }

        if not schemes:
            return {"error": f"No schemes found for AMC: {amc_name}"}

        return dict(list(schemes.items())[:50])
    except Exception as e:
        logger.error(f"Error searching schemes for {amc_name}: {str(e)}")
        return {"error": str(e)}


@tool
def search_scheme_by_name(keyword: str) -> dict:
    """Search for mutual fund schemes by keyword in the scheme name.

    Args:
        keyword: A search term (e.g., "midcap", "bluechip", "tax saver").

    Returns:
        Dict of up to 20 matching scheme codes to scheme names.
    """
    logger.info(f"Searching schemes by keyword: {keyword}")

    try:
        all_schemes = _get_all_schemes()
        keyword_lower = keyword.lower().strip()

        matches = {k: v for k, v in all_schemes.items() if keyword_lower in v.lower()}

        if not matches:
            keywords = keyword_lower.split()
            matches = {
                k: v for k, v in all_schemes.items() if any(word in v.lower() for word in keywords if len(word) > 2)
            }

        if not matches:
            return {"error": f"No schemes found matching: {keyword}"}

        return dict(list(matches.items())[:20])
    except Exception as e:
        logger.error(f"Error searching by keyword {keyword}: {str(e)}")
        return {"error": str(e)}


# ============== CALCULATOR TOOLS ==============


@tool
def calculate_returns(scheme_code: str, balance_units: float, monthly_sip: float, investment_months: int) -> dict:
    """Calculate investment returns for a mutual fund SIP.

    Args:
        scheme_code: The AMFI scheme code.
        balance_units: Current number of units held.
        monthly_sip: Monthly SIP amount in INR.
        investment_months: Total months of investment.

    Returns:
        Dict with total_invested, current_value, profit_loss, returns_pct.
    """
    logger.info(f"Calculating returns for code {scheme_code} over {investment_months} months")

    try:
        balance_units = float(balance_units)
        monthly_sip = float(monthly_sip)
        investment_months = int(investment_months)

        if balance_units < 0 or monthly_sip < 0 or investment_months < 1:
            return {"error": "Invalid input values."}
    except (ValueError, TypeError):
        return {"error": "Invalid input types. Please provide numeric values."}

    try:
        result = mf.calculate_returns(scheme_code, balance_units, monthly_sip, investment_months, as_json=False)
        if result is None:
            return {"error": f"Failed to calculate returns for: {scheme_code}"}
        return result
    except Exception as e:
        logger.error(f"Calculation error for {scheme_code}: {str(e)}")
        return {"error": str(e)}


# ============== DOCUMENT TOOLS ==============


@tool
def read_factsheet(query: str) -> dict:
    """Search uploaded financial documents for qualitative fund details.

    Args:
        query: A specific question about fund strategy, holdings, risk, etc.

    Returns:
        Dict with 'context' (relevant text chunks) and 'sources' (document names).

    USE FOR: Portfolio holdings, sector allocation, fund strategy, risk factors,
    fund manager details, investment objectives.
    """
    logger.info(f"Reading factsheet for: '{query[:100]}...'")

    try:
        client = get_client()
        rag_data = get_rag_context(query, client, _embedder)
        logger.debug(f"Factsheet lookup complete. Found {rag_data.get('raw_results_count', 0)} chunks.")
        return rag_data
    except Exception as e:
        logger.error(f"Error reading factsheet: {str(e)}")
        return {"error": str(e), "context": "", "sources": []}


# ============== TOOL GROUPS FOR AGENTS ==============
DATA_TOOLS = [get_scheme_quote, get_historical_nav]
PERFORMANCE_TOOLS = [get_equity_performance, get_debt_performance, get_hybrid_performance]
DISCOVERY_TOOLS = [search_schemes, search_scheme_by_name]
DOCUMENT_TOOLS = [read_factsheet]
CALCULATOR_TOOLS = [calculate_returns, get_scheme_quote]  # Needs quote for current value

# Legacy: All tools (for backward compatibility if needed)
ALL_MF_TOOLS = DATA_TOOLS + PERFORMANCE_TOOLS + DISCOVERY_TOOLS + DOCUMENT_TOOLS + CALCULATOR_TOOLS
