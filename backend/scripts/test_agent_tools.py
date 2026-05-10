import os
import sys
import json
import asyncio
from datetime import datetime

# Add the backend directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.agent_tools import (
    get_scheme_quote,
    get_historical_nav,
    get_scheme_details,
    get_equity_performance,
    get_debt_performance,
    get_hybrid_performance,
    search_schemes,
    search_scheme_by_name,
    calculate_returns,
    read_factsheet
)

OUTPUT_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "artifacts", "tool_test_results.md"))

# Sample inputs
SAMPLE_SCHEME_CODE = "119551"  # SBI Bluechip Fund - Direct - Growth
SAMPLE_AMC = "HDFC"
SAMPLE_KEYWORD = "midcap"
SAMPLE_FACTSHEET_QUERY = "What are the top holdings of HDFC Top 100 fund?"

async def test_tool(tool_func, **kwargs):
    print(f"Testing {tool_func.name}...")
    try:
        # tool_func is a LangChain tool, call .invoke()
        result = tool_func.invoke(kwargs)
        return {
            "name": tool_func.name,
            "inputs": kwargs,
            "output": result
        }
    except Exception as e:
        return {
            "name": tool_func.name,
            "inputs": kwargs,
            "error": str(e)
        }

async def run_tests():
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    
    results = []
    
    # 1. DATA TOOLS
    results.append(await test_tool(get_scheme_quote, scheme_code=SAMPLE_SCHEME_CODE))
    results.append(await test_tool(get_historical_nav, scheme_code=SAMPLE_SCHEME_CODE))
    results.append(await test_tool(get_scheme_details, scheme_code=SAMPLE_SCHEME_CODE))
    
    # 2. PERFORMANCE TOOLS
    results.append(await test_tool(get_equity_performance))
    results.append(await test_tool(get_debt_performance))
    results.append(await test_tool(get_hybrid_performance))
    
    # 3. DISCOVERY TOOLS
    results.append(await test_tool(search_schemes, amc_name=SAMPLE_AMC))
    results.append(await test_tool(search_scheme_by_name, keyword=SAMPLE_KEYWORD))
    
    # 4. CALCULATOR TOOLS
    results.append(await test_tool(calculate_returns, 
                                  scheme_code=SAMPLE_SCHEME_CODE, 
                                  balance_units=100.5, 
                                  monthly_sip=5000.0, 
                                  investment_months=36))
    
    # 5. DOCUMENT TOOLS
    results.append(await test_tool(read_factsheet, query=SAMPLE_FACTSHEET_QUERY))

    # Generate Markdown Report
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("# Agent Tool Test Results\n")
        f.write(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        
        for res in results:
            f.write(f"## Tool: `{res['name']}`\n")
            f.write("### Inputs\n")
            f.write("```json\n")
            f.write(json.dumps(res['inputs'], indent=2))
            f.write("\n```\n")
            
            f.write("### Output\n")
            if "error" in res:
                f.write(f"**Error**: {res['error']}\n")
            else:
                f.write("```json\n")
                # Truncate very long outputs (like historical NAV or many schemes)
                output_str = json.dumps(res['output'], indent=2)
                if len(output_str) > 2000:
                    f.write(output_str[:2000] + "\n... [TRUNCATED] ...")
                else:
                    f.write(output_str)
                f.write("\n```\n")
            f.write("\n---\n\n")
            
    print(f"Results written to {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(run_tests())
