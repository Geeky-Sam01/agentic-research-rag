import asyncio
import logging

from app.services.langchain_agents import run_agent_query

logging.basicConfig(level=logging.INFO)

async def test_chain():
    print("Running DISCOVERY -> DATA test...")
    # This query requires discovering the scheme code first, then fetching the NAV data
    result = await run_agent_query("Find the NAV of SBI Bluechip Fund.", chat_history=[])
    print("\nResult output:")
    print(result.get("output"))
    print("\nSources:")
    print(result.get("sources"))

if __name__ == "__main__":
    asyncio.run(test_chain())
