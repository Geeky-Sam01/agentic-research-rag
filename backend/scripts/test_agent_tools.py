import sys
import os
import json
import traceback
from pathlib import Path

# Add backend directory to Python path so we can import app modules
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.services.agent_tools import (
    get_scheme_quote,
    get_historical_nav,
    get_equity_performance,
    get_debt_performance,
    get_hybrid_performance,
    search_schemes,
    search_scheme_by_name,
    calculate_returns,
    read_factsheet
)

def format_data(data):
    """Safely format data for printing, truncating if too long."""
    try:
        data_str = json.dumps(data, indent=2, default=str)
    except Exception:
        data_str = str(data)
        
    if len(data_str) > 1500:
        return data_str[:1500] + f"\n... [Truncated {len(data_str) - 1500} more characters]"
    return data_str

def run_test(tool, kwargs):
    print(f"\n{'='*30} Testing: {tool.name} {'='*30}")
    print(f"📥 INPUTS:")
    print(format_data(kwargs))
    print("-" * 75)
    
    try:
        result = tool.invoke(kwargs)
        
        if isinstance(result, dict) and "error" in result:
            print(f"❌ RESULT: ERROR")
            print(f"Error Message: {result['error']}")
        else:
            print(f"✅ RESULT: SUCCESS")
            print(f"Output Type: {type(result).__name__}")
            print(f"📤 OUTPUT:")
            print(format_data(result))
    except Exception as e:
        print(f"💥 FATAL EXCEPTION")
        traceback.print_exc()
        
    print("=" * 75)

def main():
    print("🚀 Starting Agent Tools Test Suite...")
    
    # Example constants
    test_scheme_code = "119551"
    test_amc = "SBI"
    test_keyword = "bluechip"
    
    # ============== 1. DATA TOOLS ==============
    run_test(get_scheme_quote, {"scheme_code": test_scheme_code})
    run_test(get_historical_nav, {"scheme_code": test_scheme_code})
    
    # ============== 2. PERFORMANCE TOOLS ==============
    # Testing with a specific historical date because 'latest' might be failing 
    # if today is a weekend/holiday or if AMFI data is delayed.
    test_date = "01-Mar-2024"
    run_test(get_equity_performance, {"report_date": test_date})
    run_test(get_debt_performance, {"report_date": test_date})
    run_test(get_hybrid_performance, {"report_date": test_date})
    
    # ============== 3. DISCOVERY TOOLS ==============
    run_test(search_schemes, {"amc_name": test_amc})
    run_test(search_scheme_by_name, {"keyword": test_keyword})
    
    # ============== 4. CALCULATOR TOOLS ==============
    run_test(calculate_returns, {
        "scheme_code": test_scheme_code,
        "balance_units": 100.0,
        "monthly_sip": 5000.0,
        "investment_months": 12
    })
    
    # ============== 5. DOCUMENT TOOLS ==============
    run_test(read_factsheet, {"query": "What are the top 10 stock holdings?"})

if __name__ == "__main__":
    main()
