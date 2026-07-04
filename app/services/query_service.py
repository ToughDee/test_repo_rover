from __future__ import annotations

from dataclasses import dataclass

from app.infrastructure.neo4j_client import Neo4jClient
from app.query.agent import run_agent_query

# Keep the old chain import as a fallback
from app.query.chain import run_repo_query_chain, run_repo_query_context_only


@dataclass(frozen=True)
class QueryResult:
    answer: str
    context_items: int


async def answer_question(neo4j: Neo4jClient, repo_id: str, question: str, top_k: int) -> QueryResult:
    """Primary query path: uses the LangGraph agent for dynamic reasoning."""
    answer, tool_calls = await run_agent_query(
        neo4j=neo4j,
        repo_id=repo_id,
        question=question,
    )
    return QueryResult(answer=answer, context_items=tool_calls)


async def answer_question_legacy(neo4j: Neo4jClient, repo_id: str, question: str, top_k: int) -> QueryResult:
    """Legacy query path: uses the old LCEL chain. Kept as fallback."""
    answer, n = await run_repo_query_chain(
        neo4j=neo4j,
        repo_id=repo_id,
        question=question,
        top_k=top_k,
    )
    return QueryResult(answer=answer, context_items=n)


async def get_query_context(neo4j: Neo4jClient, repo_id: str, question: str, top_k: int) -> QueryResult:
    """Context-only path: still uses legacy chain since agent always generates answers."""
    context, n = await run_repo_query_context_only(
        neo4j=neo4j,
        repo_id=repo_id,
        question=question,
        top_k=top_k,
    )
    return QueryResult(answer=context, context_items=n)
