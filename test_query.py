import asyncio
from app.infrastructure.neo4j_client import Neo4jClient
from app.services.query_service import get_query_context

async def main():
    neo4j = Neo4jClient.from_settings()
    try:
        res = await get_query_context(
            neo4j=neo4j,
            repo_id="test_repo_rover",
            question="What is the backend login flow?",
            top_k=8
        )
        # Ensure safe printing on Windows CLI
        safe_res = str(res).encode('utf-8', errors='replace').decode('utf-8')
        print("CONTEXT:", safe_res)
    finally:
        neo4j.close()

if __name__ == "__main__":
    asyncio.run(main())
