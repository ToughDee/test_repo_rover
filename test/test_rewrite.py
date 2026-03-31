import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.query.chain import _rewrite_step
import traceback

async def main():
    try:
        state = {"question": "What is the code flow for when an image is uploaded, how is it tagged?"}
        print("Testing rewrite step...")
        res = await _rewrite_step(state)
        print("Output:", res["plan"].model_dump() if hasattr(res["plan"], "model_dump") else res["plan"])
    except Exception as e:
        print("Crash!")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
