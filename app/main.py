from __future__ import annotations

import os
import warnings
from contextlib import asynccontextmanager

from fastapi import FastAPI

# Suppress annoying console noise from dependencies (Chroma telemetry, LangChain deprecations, Tree-sitter futures)
# os.environ["CHROMA_TELEMETRY_DISABLED"] = "1"
# warnings.filterwarnings("ignore", category=DeprecationWarning)
# warnings.filterwarnings("ignore", category=FutureWarning)
# warnings.filterwarnings("ignore", category=UserWarning)


from app.api.routers.health import router as health_router
from app.api.routers.ingest import router as ingest_router
from app.api.routers.query import router as query_router
from app.infrastructure.neo4j_client import Neo4jClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    neo4j = Neo4jClient.from_settings()
    try:
        neo4j.init_schema()
    except Exception as e:
        raise RuntimeError(
            "Neo4j is unreachable at startup. Common causes: (1) NEO4J_URI in .env does not "
            "match the Connection URI in the Neo4j Aura console (copy the full host); "
            "(2) no internet, VPN, or DNS blocking *.databases.neo4j.io; "
            "(3) for local Neo4j, use bolt://localhost:7687 and run the database first."
        ) from e
    app.state.neo4j = neo4j
    try:
        yield
    finally:
        neo4j.close()


app = FastAPI(title="RepoRover API", version="0.1.0", lifespan=lifespan)

app.include_router(health_router)
app.include_router(ingest_router)
app.include_router(query_router)
