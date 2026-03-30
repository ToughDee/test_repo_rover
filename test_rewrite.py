import asyncio
from app.query.chain import _rewrite_step
import traceback

async def main():
    try:
        # Pass a question asking for backend code.
        state = {"question": "What is the code flow of the login mechanism in the backend?"}
        print("Testing rewrite step...")
        res = await _rewrite_step(state)
        print("Output:", res["plan"].model_dump() if hasattr(res["plan"], "model_dump") else res["plan"])
    except Exception as e:
        print("Crash!")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
