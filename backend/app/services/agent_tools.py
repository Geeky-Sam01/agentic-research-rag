import logging

from langchain_core.tools import tool

from app.services.embeddings import model as _embedder
from app.services.mf_instance import mf
from app.services.qdrant_service import get_client
from app.services.rag_pipeline import get_rag_context

logger = logging.getLogger(__name__)

@tool
def get_scheme_quote(scheme_code: str) -> dict:
    """Fetch the latest NAV for a mutual fund scheme by its scheme code.
    Args:
        scheme_code: The AMFI scheme code (e.g., "119551").
    Returns:
        Dict with scheme_code, scheme_name, nav, and last_updated.
    Use this when the user asks for current NAV, latest price,
    or today's mutual fund value.
    """
    logger.info(f"Fetching scheme quote for: {scheme_code}")
    try:
        quote = mf.get_scheme_quote(scheme_code, as_json=False)
        logger.debug(f"Successfully fetched quote for {scheme_code}")
        return quote
    except Exception as e:
        logger.error(f"Error fetching quote for {scheme_code}: {str(e)}")
        return {"error": f"Failed to fetch quote: {str(e)}"}

@tool
def search_schemes(amc_name: str) -> dict:
    """Find all mutual fund schemes under a given AMC/fund house.
    Args:
        amc_name: Name of the fund house (e.g., "Axis", "ICICI", "HDFC", "SBI").
    Returns:
        Dict mapping scheme codes to scheme names for the AMC.
    Use when the user wants to list or discover funds
    from a specific fund house.
    """
    logger.info(f"Searching schemes for AMC: {amc_name}")
    try:
        schemes = mf.get_available_schemes(amc_name)
        if not schemes:
            logger.warning(f"No schemes found for AMC: {amc_name}")
            return {"error": f"No schemes found for AMC: {amc_name}"}
        logger.debug(f"Found {len(schemes)} schemes for {amc_name}")
        return schemes
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
    Use when the user describes a fund type or partial name
    but does not know the specific scheme code.
    """
    logger.info(f"Searching schemes by keyword: {keyword}")
    try:
        all_schemes = mf.get_scheme_codes(as_json=False)
        matches = {k: v for k, v in all_schemes.items()
                   if keyword.lower() in v.lower()}
        if not matches:
            logger.warning(f"No matches found for keyword: {keyword}")
            return {"error": f"No schemes found matching: {keyword}"}
        
        display_matches = dict(list(matches.items())[:20])
        logger.debug(f"Found {len(matches)} matches, returning top {len(display_matches)}")
        return display_matches
    except Exception as e:
        logger.error(f"Error searching by keyword {keyword}: {str(e)}")
        return {"error": str(e)}

@tool
def get_historical_nav(scheme_code: str) -> dict:
    """Get the full historical NAV data for a mutual fund scheme.
    Args:
        scheme_code: The AMFI scheme code (e.g., "122628").
    Returns:
        Dict with fund_house, scheme_type, scheme_category,
        scheme_name, 52_week_high, 52_week_low, and nav data array.
    Use when the user asks about NAV history, historical
    performance, or 52-week high/low of a fund.
    """
    logger.info(f"Fetching historical NAV for: {scheme_code}")
    try:
        result = mf.get_scheme_historical_nav(scheme_code, as_json=False)
        if result is None:
            logger.warning(f"No historical data (None returned) for: {scheme_code}")
            return {"error": f"Invalid scheme code or no data: {scheme_code}"}
        logger.debug(f"Successfully fetched historical NAV for {scheme_code}")
        return result
    except Exception as e:
        logger.error(f"Error fetching history for {scheme_code}: {str(e)}")
        return {"error": str(e)}

@tool
def calculate_returns(
    scheme_code: str,
    balance_units: float,
    monthly_sip: float,
    investment_months: int
) -> dict:
    """Calculate investment returns for a mutual fund SIP.
    Args:
        scheme_code: The AMFI scheme code.
        balance_units: Current number of units held.
        monthly_sip: Monthly SIP amount in INR.
        investment_months: Total months of investment.
    Returns:
        Dict with total_invested, current_value, profit_loss, returns_pct.
    Use when the user wants to calculate their mutual fund
    investment returns or profit/loss.
    """
    logger.info(f"Calculating returns for code {scheme_code} over {investment_months} months")
    try:
        result = mf.calculate_returns(
            scheme_code, balance_units, monthly_sip,
            investment_months, as_json=False
        )
        if result is None:
            logger.warning(f"Returns calculation failed for: {scheme_code}")
            return {"error": f"Failed to calculate returns for: {scheme_code}"}
        logger.debug(f"Calculation complete for {scheme_code}")
        return result
    except Exception as e:
        logger.error(f"Calculation error for {scheme_code}: {str(e)}")
        return {"error": str(e)}

@tool
def get_equity_performance(report_date: str = None) -> dict:
    """Get daily performance of open-ended equity schemes.
    Args:
        report_date: Optional date in DD-MMM-YYYY format.
        Defaults to the last working day.
    Returns:
        Dict organized by equity sub-category with fund-level
        performance (1Y/3Y/5Y returns, regular and direct).
    Use when the user asks about equity fund performance,
    best-performing funds, or category-level comparisons.
    """
    logger.info(f"Fetching equity performance (date: {report_date})")
    try:
        data = mf.get_open_ended_equity_scheme_performance(report_date, as_json=False)
        logger.debug("Equity performance data fetched successfully")
        return data
    except Exception as e:
        logger.error(f"Error fetching equity performance: {str(e)}")
        return {"error": str(e)}

@tool
def get_debt_performance(report_date: str = None) -> dict:
    """Get daily performance of open-ended debt schemes.
    Args:
        report_date: Optional date in DD-MMM-YYYY format.
    Returns:
        Dict of debt fund performance metrics.
    """
    logger.info(f"Fetching debt performance (date: {report_date})")
    try:
        data = mf.get_open_ended_debt_scheme_performance(report_date, as_json=False)
        logger.debug("Debt performance data fetched successfully")
        return data
    except Exception as e:
        logger.error(f"Error fetching debt performance: {str(e)}")
        return {"error": str(e)}

@tool
def get_hybrid_performance(report_date: str = None) -> dict:
    """Get daily performance of open-ended hybrid schemes.
    Args:
        report_date: Optional date in DD-MMM-YYYY format.
    Returns:
        Dict of hybrid fund performance metrics.
    """
    logger.info(f"Fetching hybrid performance (date: {report_date})")
    try:
        data = mf.get_open_ended_hybrid_scheme_performance(report_date, as_json=False)
        logger.debug("Hybrid performance data fetched successfully")
        return data
    except Exception as e:
        logger.error(f"Error fetching hybrid performance: {str(e)}")
        return {"error": str(e)}

@tool
def read_factsheet(query: str) -> dict:
    """
    Search the uploaded financial documents (factsheets, annual reports, legal docs) 
    for specific details about a fund's strategy, risk factors, or historical holdings.
    Use this when the user asks about the 'how' and 'why' of a fund, 
    or anything defined in its official documentation.
    """
    logger.info(f"Agent Tool - Reading factsheet for: '{query}'")
    try:
        client = get_client()
        rag_data = get_rag_context(query, client, _embedder)
        logger.debug(f"Factsheet lookup complete. Found {rag_data.get('raw_results_count', 0)} chunks.")
        return rag_data
    except Exception as e:
        logger.error(f"Error reading factsheet: {str(e)}")
        return {"error": str(e)}

# List of all tools for the agent
ALL_MF_TOOLS = [
    get_scheme_quote,
    search_schemes,
    search_scheme_by_name,
    get_historical_nav,
    calculate_returns,
    get_equity_performance,
    get_debt_performance,
    get_hybrid_performance,
    read_factsheet,
]