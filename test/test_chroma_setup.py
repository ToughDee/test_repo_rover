import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.infrastructure.neo4j_client import Neo4jClient
from app.services.ingest_service import ingest_repo

async def main():
    neo4j = Neo4jClient.from_settings()
    try:
        res = ingest_repo(
            neo4j=neo4j,
            repo_id="demo",
            source="d:/padhai/cursor-project/repo-rover/test_repo",
            branch=None
        )
        print("Indexed files:", res.files_indexed)
        print("Indexed symbols:", res.symbols_indexed)
    finally:
        neo4j.close()

if __name__ == "__main__":
    asyncio.run(main())
