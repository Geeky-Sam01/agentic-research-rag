
with open('app/services/agent_tools.py', 'r') as f:
    content = f.read()

# Replace Imports
content = content.replace("from cachetools import TTLCache", "from cachetools import TTLCache\nfrom pydantic import BaseModel, Field")

# Replace Caching Setup & Schemas
cache_orig = """# ============== CACHING SETUP ==============
_nav_cache = TTLCache(maxsize=500, ttl=4 * 3600)
_performance_cache = TTLCache(maxsize=10, ttl=6 * 3600)
_cached_all_schemes: Optional[dict] = None


def _get_all_schemes() -> dict:
    \"\"\"Get all schemes with caching.\"\"\"
    global _cached_all_schemes
    if _cached_all_schemes is None:
        logger.info("Loading all schemes into memory...")
        _cached_all_schemes = mf.get_scheme_codes(as_json=False) or {}
        logger.info(f"Loaded {len(_cached_all_schemes)} schemes")
    return _cached_all_schemes"""

cache_new = """# ============== CACHING SETUP ==============
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

def _get_all_schemes() -> dict:
    \"\"\"Get all schemes with caching.\"\"\"
    if cache.all_schemes is None:
        logger.info("Loading all schemes into memory...")
        cache.all_schemes = mf.get_scheme_codes(as_json=False) or {}
        logger.info(f"Loaded {len(cache.all_schemes)} schemes")
    return cache.all_schemes

# ============== INPUT SCHEMAS ==============

class SchemeCodeInput(BaseModel):
    scheme_code: str = Field(..., description="The AMFI scheme code (e.g., '119551').")

class PerformanceInput(BaseModel):
    report_date: Optional[str] = Field(None, description="Optional date in DD-MMM-YYYY format.")

class SearchSchemesInput(BaseModel):
    amc_name: str = Field(..., description="Name of the fund house (e.g., 'Axis', 'ICICI', 'HDFC', 'SBI').")

class SearchSchemeByNameInput(BaseModel):
    keyword: str = Field(..., description="A search term (e.g., 'midcap', 'bluechip', 'tax saver').")

class CalculateReturnsInput(BaseModel):
    scheme_code: str = Field(..., description="The AMFI scheme code.")
    balance_units: float = Field(..., description="Current number of units held.")
    monthly_sip: float = Field(..., description="Monthly SIP amount in INR.")
    investment_months: int = Field(..., description="Total months of investment.")

class ReadFactsheetInput(BaseModel):
    query: str = Field(..., description="A specific question about fund strategy, holdings, risk, etc.")"""

content = content.replace(cache_orig, cache_new)

# Replace cache vars
content = content.replace("_nav_cache", "cache.nav_cache")
content = content.replace("_performance_cache", "cache.performance_cache")

# Apply tools
content = content.replace("@tool\ndef get_scheme_quote", "@tool(args_schema=SchemeCodeInput)\ndef get_scheme_quote")
content = content.replace("@tool\ndef get_historical_nav", "@tool(args_schema=SchemeCodeInput)\ndef get_historical_nav")
content = content.replace("@tool\ndef get_equity_performance", "@tool(args_schema=PerformanceInput)\ndef get_equity_performance")
content = content.replace("@tool\ndef get_debt_performance", "@tool(args_schema=PerformanceInput)\ndef get_debt_performance")
content = content.replace("@tool\ndef get_hybrid_performance", "@tool(args_schema=PerformanceInput)\ndef get_hybrid_performance")
content = content.replace("@tool\ndef search_schemes", "@tool(args_schema=SearchSchemesInput)\ndef search_schemes")
content = content.replace("@tool\ndef search_scheme_by_name", "@tool(args_schema=SearchSchemeByNameInput)\ndef search_scheme_by_name")
content = content.replace("@tool\ndef calculate_returns", "@tool(args_schema=CalculateReturnsInput)\ndef calculate_returns")
content = content.replace("@tool\ndef read_factsheet", "@tool(args_schema=ReadFactsheetInput)\ndef read_factsheet")

# Remove calculate returns try except since Pydantic does validation
calc_orig = """    try:
        balance_units = float(balance_units)
        monthly_sip = float(monthly_sip)
        investment_months = int(investment_months)

        if balance_units < 0 or monthly_sip < 0 or investment_months < 1:
            return {"error": "Invalid input values."}
    except (ValueError, TypeError):
        return {"error": "Invalid input types. Please provide numeric values."}"""

calc_new = """    if balance_units < 0 or monthly_sip < 0 or investment_months < 1:
        return {"error": "Invalid input values."}"""

content = content.replace(calc_orig, calc_new)

with open('app/services/agent_tools.py', 'w') as f:
    f.write(content)
