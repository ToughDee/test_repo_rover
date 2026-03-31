from fastapi import APIRouter, Request
from pydantic import BaseModel
import shutil
from pathlib import Path

from app.core.settings import settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.vector_store import VectorStore

router = APIRouter(prefix="/test", tags=["test"])

class PeekResponse(BaseModel):
    repo_id: str
    symbol_count: int

@router.get("/peek/{repo_id}", response_model=PeekResponse)
def peek_chroma(repo_id: str):
    """Peek into the ChromaDB collection for a specific repo to see how many symbols are indexed."""
    try:
        vs = VectorStore.from_settings(repo_id)
        # We access the underlying chromadb collection
        count = vs._chroma._collection.count()
        return PeekResponse(repo_id=repo_id, symbol_count=count)
    except Exception as e:
        return PeekResponse(repo_id=repo_id, symbol_count=-1)

@router.post("/reset")
def reset_database(request: Request):
    """
    WARNING: Wipes the entire Neo4j database and deletes ChromaDB & Work folders.
    Use this to start fresh during development.
    """
    # 1. Wipe Neo4j
    neo4j: Neo4jClient = request.app.state.neo4j
    try:
        with neo4j.driver.session() as s:
            s.run("MATCH (n) DETACH DELETE n")
        neo4j.init_schema()
    except Exception as e:
        return {"status": "error", "message": f"Failed to reset Neo4j: {str(e)}"}

    # 2. Wipe Local Folders (Chroma & Work)
    # Note: On Windows, ChromaDB might hold file locks if the server is actively using it.
    dirs_to_delete = [
        Path(settings.chroma_dir),
        Path(settings.work_dir)
    ]
    
    deleted = []
    failed = []
    for d in dirs_to_delete:
        if d.exists() and d.is_dir():
            try:
                shutil.rmtree(d, ignore_errors=True)
                deleted.append(str(d))
            except Exception as e:
                failed.append(str(d))
                
    return {
        "status": "success", 
        "message": "Neo4j wiped. Local folders cleared.",
        "directories_deleted": deleted,
        "directories_failed_locks": failed
    }
