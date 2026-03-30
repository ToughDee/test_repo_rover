from __future__ import annotations

from fastapi import APIRouter, Request


router = APIRouter()


@router.get("/health")
def health(request: Request):
    neo4j = getattr(request.app.state, "neo4j", None)
    return {"ok": True, "neo4j": neo4j is not None}
