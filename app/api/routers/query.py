from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.schemas import QueryRequest, QueryResponse, QueryContextResponse
from app.services.query_service import answer_question, get_query_context


router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest, request: Request):
    neo4j = request.app.state.neo4j
    res = await answer_question(neo4j=neo4j, repo_id=req.repo_id, question=req.question, top_k=req.top_k)
    return QueryResponse(answer=res.answer, context_items=res.context_items)

@router.post("/query/context", response_model=QueryContextResponse)
async def query_context(req: QueryRequest, request: Request):
    neo4j = request.app.state.neo4j
    res = await get_query_context(neo4j=neo4j, repo_id=req.repo_id, question=req.question, top_k=req.top_k)
    return QueryContextResponse(context=res.answer, context_items=res.context_items)
