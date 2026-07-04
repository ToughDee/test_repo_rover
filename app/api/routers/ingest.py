from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import IngestRequest, IngestResponse
from app.services.ingest_service import ingest_repo


router = APIRouter()


from fastapi import HTTPException
import traceback

@router.post("/ingest", response_model=IngestResponse)
def ingest(req: IngestRequest, request: Request):
    neo4j = request.app.state.neo4j
    try:
        res = ingest_repo(
            neo4j=neo4j, 
            repo_id=req.repo_id, 
            source=req.source, 
            branch=req.branch,
            added_or_modified_files=req.added_or_modified_files,
            deleted_files=req.deleted_files
        )
        return IngestResponse(repo_id=res.repo_id, files_indexed=res.files_indexed, symbols_indexed=res.symbols_indexed)
    except Exception as e:
        error_details = traceback.format_exc()
        print("INGEST ERROR:", error_details)
        raise HTTPException(status_code=500, detail=str(e))
