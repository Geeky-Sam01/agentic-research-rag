import logging
from datetime import datetime
from typing import Optional

from cachetools import TTLCache
from pydantic import BaseModel, Field

from langchain_core.tools import tool

from app.services.embeddings import model as _embedder
from app.services.mf_instance import mf
from app.services.qdrant_service import get_client
from app.services.rag_pipeline import get_rag_context
from app.services.dateHelper import is_trading_day, prev_trading_day

logger = logging.getLogger(__name__)


# ============== CACHING SETUP ==============
class AgentCache:
    def __init__(self):
        self.nav_cache = TTLCache(maxsize=500, ttl=4 * 3600)
        self.performance_cache = TTLCache(maxsize=10, ttl=6 * 3600)
        self.all_schemes: Optional[dict] = None

    def clear(self):
        self.nav_cache.clear()
        self.performance_cache.clear()
        self.all_schemes = None


cache = AgentCache()

# Track latest working date PER performance type — not globally.
# AMFI publishes equity/debt/hybrid on slightly different schedules.
_latest_date_found: dict[str, str] = {}


def _check_has_data(res: object) -> bool:
    """Check if the performance response has actual fund data (not just empty category keys)."""
    if not isinstance(res, dict):
        return False
    if "error" in res:
        return False

    # Count categories that actually have fund entries
    categories_with_data = 0
    for v in res.values():
        if isinstance(v, list) and len(v) > 0:
            categories_with_data += 1

    return categories_with_data > 0


def _count_funds(res: dict) -> int:
    """Count total funds across all categories in a performance response."""
    if not isinstance(res, dict):
        return 0
    return sum(len(v) for v in res.values() if isinstance(v, list))


def _filter_performance_results(res: dict, category_filter: str = None, keyword: str = None) -> dict:
    """Prune massive AMFI performance datasets to prevent token overflow."""
    if not isinstance(res, dict):
        return res

    filtered = {}
    keyword_lower = keyword.lower() if keyword else None
    cat_lower = category_filter.lower() if category_filter else None

    for cat_name, funds in res.items():
        # 1. Category Filter
        if cat_lower and cat_lower not in cat_name.lower():
            continue

        if not isinstance(funds, list):
            filtered[cat_name] = funds
            continue

        # 2. Keyword Filter
        matching_funds = funds
        if keyword_lower:
            matching_funds = [f for f in funds if keyword_lower in str(f.get("scheme_name", "")).lower()]

        # 3. Safety Truncation: Limit to top 15 funds per category to save tokens
        # If the user didn't provide a keyword, they likely want a 'top funds' overview.
        if not keyword_lower and len(matching_funds) > 15:
            matching_funds = matching_funds[:15]
            filtered[f"{cat_name} (Top 15)"] = matching_funds
        else:
            filtered[cat_name] = matching_funds

    return filtered


def _get_all_schemes() -> dict:
    """Get all schemes with caching."""
    if cache.all_schemes is None:
        logger.info("Loading all schemes into memory...")
        cache.all_schemes = mf.get_scheme_codes(as_json=False) or {}
        logger.info(f"Loaded {len(cache.all_schemes)} schemes")
    return cache.all_schemes


def _fetch_performance_with_fallback(
    func,
    report_date: str = None,
    category_type: str = "unknown",
) -> dict:
    """Fetch AMFI performance data with date fallback and smart caching."""
    from datetime import datetime, timedelta

    func_name = func.__name__

    # ── Case 1: Explicit date requested ──
    if report_date:
        cache_key = f"{func_name}_{report_date}"
        if cache_key in cache.performance_cache:
            return cache.performance_cache[cache_key]
        try:
            res = func(report_date, as_json=False)
            cache.performance_cache[cache_key] = res
            return res
        except Exception as e:
            logger.warning(f"Performance fetch failed for explicit date {report_date}: {e}")
            return {"error": f"Failed to fetch performance data for {report_date}: {str(e)}"}

    # ── Case 2: Auto-detect latest date ──
    now = datetime.now()
    # AMFI publishes around 10-11 PM IST. If before 11 PM, start from yesterday.
    if now.hour < 23:
        start_date = now - timedelta(days=1)
    else:
        start_date = now

    start_date = prev_trading_day(start_date)

    # Check if we already know the latest working date for this category type
    known_date = _latest_date_found.get(category_type)
    if known_date:
        cache_key = f"{func_name}_{known_date}"
        if cache_key in cache.performance_cache:
            cached = cache.performance_cache[cache_key]
            if _check_has_data(cached):
                return cached

    # ── Case 3: Walk backwards through trading days ──
    probe_date = start_date
    final_res = {"error": f"Performance data for {category_type} is currently unavailable."}
    
    for i in range(5):  # 5 trading days covers a full week
        date_str = probe_date.strftime("%d-%b-%Y")
        cache_key = f"{func_name}_{date_str}"

        # Check cache
        if cache_key in cache.performance_cache:
            res = cache.performance_cache[cache_key]
            if _check_has_data(res):
                logger.info(f"Performance ({category_type}): cache hit for {date_str}")
                _latest_date_found[category_type] = date_str
                final_res = res
                break
            # Cached but empty — skip
            logger.debug(f"Performance ({category_type}): cache skip (empty) for {date_str}")
            probe_date = prev_trading_day(probe_date - timedelta(days=1))
            continue

        # Fetch from AMFI
        try:
            logger.info(f"Performance ({category_type}): probing AMFI for {date_str}...")
            res = func(date_str, as_json=False)
            cache.performance_cache[cache_key] = res

            if _check_has_data(res):
                fund_count = _count_funds(res)
                logger.info(f"Performance ({category_type}): found {fund_count} funds for {date_str}")
                _latest_date_found[category_type] = date_str
                final_res = res
                break

            if i == 0 and isinstance(res, dict) and not _check_has_data(res):
                logger.warning(f"Performance ({category_type}): AMFI returned empty for {date_str}.")

        except Exception as e:
            logger.warning(f"Performance ({category_type}): fetch failed for {date_str}: {e}")

        # Move to previous trading day
        probe_date = prev_trading_day(probe_date - timedelta(days=1))
    
    # Apply context filtering before returning to the Agent
    return final_res

    logger.error(f"Performance ({category_type}): no data found after 5 trading days.")
    return {
        "error": f"Performance data for {category_type} is currently unavailable.",
        "_diagnostic": {
            "category_type": category_type,
            "known_latest": known_date,
        },
    }


# ============== INPUT SCHEMAS ==============


class SchemeCodeInput(BaseModel):
    scheme_code: str = Field(..., description="The AMFI scheme code (e.g., '119551').")


class PerformanceInput(BaseModel):
    report_date: Optional[str] = Field(None, description="Optional date in DD-MMM-YYYY format.")
    category: Optional[str] = Field(None, description="Optional category filter (e.g., 'Large Cap', 'Mid Cap').")
    filter_keyword: Optional[str] = Field(None, description="Optional keyword to filter fund names (e.g., 'ICICI', 'SBI').")


class SearchSchemesInput(BaseModel):
    amc_name: str = Field(..., description="Name of the fund house (e.g., 'Axis', 'ICICI', 'HDFC', 'SBI').")


class SearchSchemeByNameInput(BaseModel):
    keyword: str = Field(..., description="A search term (e.g., 'midcap', 'bluechip', 'tax saver').")


class CalculateReturnsInput(BaseModel):
    scheme_code: str = Field(..., description="The AMFI scheme code.")
    monthly_sip: float = Field(..., description="Monthly SIP amount in INR.")
    investment_months: int = Field(..., description="Total months of investment.")
    balance_units: Optional[float] = Field(
        None,
        description="Optional. Current number of units held. If not provided, will be estimated based on historical NAV.",
    )


class ProjectedSIPReturnsInput(BaseModel):
    monthly_sip: float = Field(..., description="Monthly SIP amount in INR.")
    annual_return_rate: float = Field(..., description="Expected annual return percentage (e.g. 12 for 12%).")
    investment_years: int = Field(..., description="Total investment duration in years.")
    yearly_step_up_pct: float = Field(
        0.0, description="Optional annual SIP increase percentage (e.g. 10 for a 10% yearly top-up)."
    )


class ReadFactsheetInput(BaseModel):
    query: str = Field(..., description="A specific question about fund strategy, holdings, risk, etc.")


# ============== DATA TOOLS (NAV, History) ==============


@tool(args_schema=SchemeCodeInput)
def get_scheme_quote(scheme_code: str) -> dict:
    """Fetch the latest NAV for a mutual fund scheme by its scheme code.

    Args:
        scheme_code: The AMFI scheme code (e.g., "119551").

    Returns:
        Dict with scheme_code, scheme_name, nav, and last_updated.
    """
    logger.info(f"Fetching scheme quote for: {scheme_code}")
    cache_key = f"quote_{scheme_code}"
    if cache_key in cache.nav_cache:
        return cache.nav_cache[cache_key]

    try:
        quote = mf.get_scheme_quote(scheme_code, as_json=False)
        if quote and "error" not in quote:
            cache.nav_cache[cache_key] = quote
        return quote
    except Exception as e:
        logger.error(f"Error fetching quote for {scheme_code}: {str(e)}")
        return {"error": f"Failed to fetch quote: {str(e)}"}


@tool(args_schema=SchemeCodeInput)
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
    if cache_key in cache.nav_cache:
        return cache.nav_cache[cache_key]

    try:
        result = mf.get_scheme_historical_nav(scheme_code, as_json=False)
        if result is None:
            return {"error": f"Invalid scheme code or no data: {scheme_code}"}
        cache.nav_cache[cache_key] = result
        return result
    except Exception as e:
        logger.error(f"Error fetching history for {scheme_code}: {str(e)}")
        return {"error": str(e)}


@tool(args_schema=SchemeCodeInput)
def get_scheme_details(scheme_code: str) -> dict:
    """Fetch full details for a mutual fund scheme including expense ratio, exit load, etc.

    Args:
        scheme_code: The AMFI scheme code (e.g., "119551").

    Returns:
        Dict with fund_house, scheme_name, scheme_type, scheme_category,
        scheme_code, expense_ratio, exit_load, etc.
    """
    logger.info(f"Fetching scheme details for: {scheme_code}")
    cache_key = f"details_{scheme_code}"
    if cache_key in cache.nav_cache:
        return cache.nav_cache[cache_key]

    try:
        details = mf.get_scheme_details(scheme_code, as_json=False)
        if details and "error" not in details:
            # Note: mftool's get_scheme_details is very limited.
            # We add placeholders to inform the Agent to look elsewhere for these.
            details["expense_ratio"] = "Not available in live API. Use 'read_factsheet' for this data."
            details["exit_load"] = "Not available in live API. Use 'read_factsheet' for this data."
            details["sharpe_ratio"] = "Not available in live API. Use 'read_factsheet' for this data."
            cache.nav_cache[cache_key] = details
        return details
    except Exception as e:
        logger.error(f"Error fetching details for {scheme_code}: {str(e)}")
        return {"error": f"Failed to fetch details: {str(e)}"}


# ============== PERFORMANCE TOOLS ==============


@tool(args_schema=PerformanceInput)
def get_equity_performance(
    report_date: Optional[str] = None,
    category: Optional[str] = None,
    filter_keyword: Optional[str] = None,
) -> dict:
    """Get daily performance of open-ended equity mutual fund schemes.

    Returns performance data organized by equity sub-category:
    Large Cap, Large & Mid Cap, Flexi Cap, Multi Cap, Mid Cap, Small Cap,
    Value, ELSS, Contra, Dividend Yield, Focused, Sectoral/Thematic.

    Each category contains a list of funds with their 1-day, 1-week, 1-month,
    3-month, 6-month, 1-year, 2-year, 3-year, 5-year, and inception returns.

    Args:
        report_date: Optional date in DD-MMM-YYYY format (e.g., "08-May-2026").
                     Defaults to the latest available trading day.
        category: Optional filter for sub-category (e.g., "Mid Cap").
        filter_keyword: Optional keyword to search within fund names (e.g., "ICICI").

    Use when the user asks about: best equity funds, top large-cap/mid-cap funds,
    fund performance comparison, category-wise returns, or top performers.
    """
    raw_res = _fetch_performance_with_fallback(
        mf.get_open_ended_equity_scheme_performance,
        report_date,
        category_type="equity",
    )
    return _filter_performance_results(raw_res, category, filter_keyword)


@tool(args_schema=PerformanceInput)
def get_debt_performance(
    report_date: Optional[str] = None,
    category: Optional[str] = None,
    filter_keyword: Optional[str] = None,
) -> dict:
    """Get daily performance of open-ended debt mutual fund schemes.

    Returns performance data organized by debt sub-category:
    Long Duration, Medium to Long Duration, Medium Duration, Short Duration,
    Low Duration, Ultra Short Duration, Liquid, Money Market, Overnight,
    Dynamic Bond, Corporate Bond, Credit Risk, Banking and PSU, Floater,
    FMP, Gilt, Gilt with 10 year constant duration.

    Args:
        report_date: Optional date in DD-MMM-YYYY format (e.g., "08-May-2026").
                     Defaults to the latest available trading day.

    Use when the user asks about: best debt funds, liquid fund returns,
    banking & PSU fund performance, or short-term fund comparisons.
    """
    return _fetch_performance_with_fallback(
        mf.get_open_ended_debt_scheme_performance,
        report_date,
        category_type="debt",
    )


@tool(args_schema=PerformanceInput)
def get_hybrid_performance(
    report_date: Optional[str] = None,
    category: Optional[str] = None,
    filter_keyword: Optional[str] = None,
) -> dict:
    """Get daily performance of open-ended hybrid mutual fund schemes.

    Returns performance data organized by hybrid sub-category:
    Aggressive Hybrid, Balanced Hybrid, Conservative Hybrid, Equity Savings,
    Arbitrage, Multi Asset Allocation.

    Args:
        report_date: Optional date in DD-MMM-YYYY format (e.g., "08-May-2026").
                     Defaults to the latest available trading day.

    Use when the user asks about: balanced fund performance, hybrid fund returns,
    arbitrage fund yields, or conservative/aggressive hybrid comparisons.
    """
    return _fetch_performance_with_fallback(
        mf.get_open_ended_hybrid_scheme_performance,
        report_date,
        category_type="hybrid",
    )


# ============== DISCOVERY TOOLS ==============


@tool(args_schema=SearchSchemesInput)
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


@tool(args_schema=SearchSchemeByNameInput)
def search_scheme_by_name(keyword: str) -> dict:
    """Search for mutual fund schemes by keyword or colloquial name.

    Args:
        keyword: A search term (e.g., "SBI Bluechip", "midcap", "tax saver").

    Returns:
        Dict of up to 20 matching scheme codes to scheme names.
    """
    logger.info(f"Searching schemes by keyword: {keyword}")

    try:
        from app.services.fund_resolver import resolve_fund

        # 1. Smart Resolution (Handles Aliases and exact matches)
        res = resolve_fund(keyword)
        if res.resolved and res.best_match:
            logger.info(f"Discovery Tool: smartly resolved '{keyword}' to '{res.best_match.scheme_name}'")
            return {str(res.best_match.scheme_code): res.best_match.scheme_name}

        # 2. Fallback to basic keyword matching
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


@tool(args_schema=CalculateReturnsInput)
def calculate_historical_sip_returns(
    scheme_code: str, monthly_sip: float, investment_months: int, balance_units: Optional[float] = None
) -> dict:
    """Calculate investment returns for a mutual fund SIP.

    Args:
        scheme_code: The AMFI scheme code.
        monthly_sip: Monthly SIP amount in INR.
        investment_months: Total months of investment.
        balance_units: Optional. Current units. If None, we simulate based on historical NAV.

    Returns:
        Dict with total_invested, current_value, profit_loss, returns_pct.
    """
    logger.info(f"Calculating returns for code {scheme_code} over {investment_months} months")

    if monthly_sip < 0 or investment_months < 1:
        return {"error": "Invalid input values."}

    try:
        # 1. Get current NAV
        quote = get_scheme_quote.invoke({"scheme_code": scheme_code})
        if "error" in quote:
            return quote
        current_nav = float(quote["nav"])

        # 2. If units not provided, simulate SIP to estimate them
        if balance_units is None or balance_units <= 0:
            logger.info("Units not provided. Simulating SIP from historical data...")
            history = get_historical_nav.invoke({"scheme_code": scheme_code})
            if "error" in history or "data" not in history:
                return {"error": "Could not fetch history to simulate SIP. Please provide balance_units."}

            nav_data = history["data"]  # Expected to be [ {date, nav}, ... ] in descending order
            nav_data_sorted = sorted(nav_data, key=lambda x: datetime.strptime(x["date"], "%d-%m-%Y"))

            # Simulate monthly SIP (approx 30 days)
            simulated_units = 0.0
            total_invested = 0.0

            # We want to look back investment_months from the latest date
            # We'll pick one NAV every ~30 days
            step = max(1, len(nav_data_sorted) // investment_months)
            selected_navs = nav_data_sorted[::step][-investment_months:]

            for entry in selected_navs:
                try:
                    nav_val = float(entry["nav"])
                    if nav_val > 0:
                        simulated_units += monthly_sip / nav_val
                        total_invested += monthly_sip
                except:
                    continue

            balance_units = simulated_units
            actual_investment = total_invested
        else:
            actual_investment = monthly_sip * investment_months

        # 3. Calculate final values
        current_value = balance_units * current_nav
        profit_loss = current_value - actual_investment
        absolute_return = (profit_loss / actual_investment) * 100 if actual_investment > 0 else 0

        # Simple CAGR estimation for SIP (XIRR would be better but this is more robust than mftool's math)
        # For SIP, effective duration is approx half of total duration
        years = investment_months / 12
        annualised_return = (
            (((current_value / actual_investment) ** (1 / (years / 2))) - 1) * 100
            if years > 0 and actual_investment > 0
            else 0
        )

        return {
            "scheme_code": scheme_code,
            "scheme_name": quote.get("scheme_name"),
            "total_invested": round(actual_investment, 2),
            "current_value": round(current_value, 2),
            "profit_loss": round(profit_loss, 2),
            "absolute_return_pct": f"{round(absolute_return, 2)} %",
            "annualised_return_pct": f"{round(annualised_return, 2)} %",
            "estimated_units": round(balance_units, 3),
            "method": "SIP Simulation" if "selected_navs" in locals() else "Lump Sum Estimate",
        }
    except Exception as e:
        logger.error(f"Calculation error for {scheme_code}: {str(e)}")
        return {"error": str(e)}


@tool(args_schema=ProjectedSIPReturnsInput)
def calculate_projected_sip_returns(
    monthly_sip: float,
    annual_return_rate: float,
    investment_years: int,
    yearly_step_up_pct: float = 0.0,
) -> dict:
    """
    Calculate projected future SIP corpus using industry-standard CAGR compounding.

    Supports:
    - Normal SIP projection
    - Step-up SIP projection

    Args:
        monthly_sip: Monthly SIP amount in INR.
        annual_return_rate: Expected annual CAGR return percentage.
        investment_years: Total investment duration in years.
        yearly_step_up_pct: Optional yearly SIP increase percentage.

    Returns:
        Dict with invested amount, projected corpus, and estimated gains.
    """

    logger.info(
        f"Projected SIP calculation | "
        f"SIP={monthly_sip}, "
        f"Return={annual_return_rate}%, "
        f"Years={investment_years}, "
        f"StepUp={yearly_step_up_pct}%"
    )

    try:
        # ─────────────────────────────────────────────
        # Validation
        # ─────────────────────────────────────────────
        if monthly_sip <= 0:
            return {"error": "monthly_sip must be greater than 0"}

        if annual_return_rate <= 0:
            return {"error": "annual_return_rate must be greater than 0"}

        if investment_years <= 0:
            return {"error": "investment_years must be greater than 0"}

        if yearly_step_up_pct < 0:
            return {"error": "yearly_step_up_pct cannot be negative"}

        # ─────────────────────────────────────────────
        # CAGR → Effective Monthly Rate
        # Example:
        # 12% annual CAGR
        # → ~0.9489% monthly compounded
        # ─────────────────────────────────────────────
        monthly_rate = (1 + (annual_return_rate / 100)) ** (1 / 12) - 1

        total_months = investment_years * 12

        # ─────────────────────────────────────────────
        # FAST PATH:
        # Standard SIP without yearly step-up
        # Uses exact closed-form formula
        # ─────────────────────────────────────────────
        if yearly_step_up_pct == 0:
            future_value = monthly_sip * (((1 + monthly_rate) ** total_months - 1) / monthly_rate) * (1 + monthly_rate)

            invested_amount = monthly_sip * total_months

        # ─────────────────────────────────────────────
        # STEP-UP SIP:
        # Uses yearly iterative simulation
        # ─────────────────────────────────────────────
        else:
            invested_amount = 0.0
            future_value = 0.0
            current_monthly_sip = monthly_sip

            for month in range(1, total_months + 1):
                # Apply yearly SIP increase
                if month > 1 and (month - 1) % 12 == 0:
                    current_monthly_sip *= 1 + yearly_step_up_pct / 100

                # Add SIP contribution
                future_value += current_monthly_sip
                invested_amount += current_monthly_sip

                # Apply monthly compounding
                future_value *= 1 + monthly_rate

        # ─────────────────────────────────────────────
        # Final Metrics
        # ─────────────────────────────────────────────
        gains = future_value - invested_amount

        absolute_return_pct = (gains / invested_amount) * 100 if invested_amount > 0 else 0

        return {
            "monthly_sip": round(monthly_sip, 2),
            "investment_years": investment_years,
            "annual_return_assumption_pct": annual_return_rate,
            "yearly_step_up_pct": yearly_step_up_pct,
            "total_invested": round(invested_amount, 2),
            "projected_corpus": round(future_value, 2),
            "estimated_gains": round(gains, 2),
            "absolute_return_pct": round(absolute_return_pct, 2),
            "projection_type": ("Step-Up SIP Projection" if yearly_step_up_pct > 0 else "Future SIP Projection"),
            "assumption": (f"Projection assumes {annual_return_rate}% annual compounded return"),
        }

    except Exception as e:
        logger.exception("Projected SIP calculation failed")
        return {"error": str(e)}  # ============== DOCUMENT TOOLS ==============


@tool(args_schema=ReadFactsheetInput)
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
DATA_TOOLS = [get_scheme_quote, get_historical_nav, get_scheme_details]
PERFORMANCE_TOOLS = [get_equity_performance, get_debt_performance, get_hybrid_performance]
DISCOVERY_TOOLS = [search_schemes, search_scheme_by_name]
DOCUMENT_TOOLS = [read_factsheet]
CALCULATOR_TOOLS = [
    calculate_historical_sip_returns,
    calculate_projected_sip_returns,
    get_scheme_quote,
]

# Legacy: All tools (for backward compatibility if needed)
ALL_MF_TOOLS = list(
    {t.name: t for t in (DATA_TOOLS + PERFORMANCE_TOOLS + DISCOVERY_TOOLS + DOCUMENT_TOOLS + CALCULATOR_TOOLS)}.values()
)
