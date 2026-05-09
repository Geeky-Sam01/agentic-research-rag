import asyncio
import asyncpg

async def main():
    try:
        conn = await asyncpg.connect('postgresql://postgres:password@127.0.0.1:5433/finsight_chat')
        print("Success!")
        await conn.close()
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
