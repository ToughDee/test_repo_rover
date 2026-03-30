from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    repo_id: str = Field(..., description="Stable id to reference this repo later")
    source: str = Field(..., description="Local path or remote git URL")
    branch: str | None = Field(None, description="Optional branch for remote repos")


class IngestResponse(BaseModel):
    repo_id: str
    files_indexed: int
    symbols_indexed: int


class QueryRequest(BaseModel):
    repo_id: str
    question: str
    top_k: int = 8


class QueryResponse(BaseModel):
    answer: str
    context_items: int


class GraphExploreRequest(BaseModel):
    repo_id: str
    qualified_name: str
    depth: int = 1


class GraphExploreResponse(BaseModel):
    nodes: list[dict]
    edges: list[dict]
