import asyncio
import json
from app.api.chat import query_structured
from app.models.schemas import QueryRequest

async def run_test():
    req = QueryRequest(query="Find the NAV of SBI Bluechip Fund.", stream=False)
    try:
        response = await query_structured(req)
        # response is a JSONResponse. We can decode its body
        body = json.loads(response.body)
        print("Response:", body)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(run_test())
