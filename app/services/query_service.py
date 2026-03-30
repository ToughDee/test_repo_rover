from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.neo4j_client import Neo4jClient
from app.query.chain import run_repo_query_chain


@dataclass(frozen=True)
class QueryResult:
    answer: str
    context_items: int


async def answer_question(neo4j: Neo4jClient, repo_id: str, question: str, top_k: int) -> QueryResult:
    answer, n = await run_repo_query_chain(
        neo4j=neo4j,
        repo_id=repo_id,
        question=question,
        top_k=top_k,
    )
    return QueryResult(answer=answer, context_items=n)
