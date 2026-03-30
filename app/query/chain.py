from __future__ import annotations

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnableSequence

from app.core.settings import settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.vector_store import VectorStore
from app.ingestion.text_scan import extract_identifiers
from app.llm.chat_model import get_chat_model
from app.query.graph_context import files_mentioning_symbol, graph_expand_neighbors, snip_around_text
from app.repos.registry import get_repo_root


async def _retrieve_step(state: dict) -> dict:
    repo_id = state["repo_id"]
    question = state["question"]
    top_k = state["top_k"]
    vs = VectorStore.from_settings(repo_id)
    retriever = vs.as_retriever(top_k)
    docs = await retriever.ainvoke(question)
    hits: list[dict] = []
    for d in docs:
        md = d.metadata or {}
        hits.append(
            {
                "id": getattr(d, "id", None) or "",
                "document": d.page_content,
                "metadata": md,
                "distance": 0.0,
            }
        )
    seed_qns = [h["metadata"]["qualified_name"] for h in hits if h.get("metadata")]
    context_parts = [h["document"][:2500] for h in hits]
    return {
        **state,
        "hits": hits,
        "seed_qns": seed_qns,
        "context_parts": context_parts,
    }


def _enrich_step(state: dict) -> dict:
    neo4j: Neo4jClient = state["neo4j"]
    repo_id = state["repo_id"]
    question = state["question"]
    hits: list[dict] = state["hits"]
    context_parts = list(state["context_parts"])

    expanded = graph_expand_neighbors(neo4j, repo_id=repo_id, qualified_names=state["seed_qns"], depth=1)

    ql = question.lower()
    if "where" in ql and ("used" in ql or "usage" in ql or "import" in ql):
        q_idents = extract_identifiers(question)
        symbol_name = None
        if hits:
            m0 = hits[0].get("metadata") or {}
            cand = m0.get("name")
            if cand and cand in q_idents:
                symbol_name = cand
        if symbol_name is None:
            for ident in q_idents:
                if ident[0].isalpha() and any(c.isupper() for c in ident[1:]):
                    symbol_name = ident
                    break
        if symbol_name is None and hits and hits[0].get("metadata"):
            symbol_name = hits[0]["metadata"].get("name")
        if symbol_name:
            paths = files_mentioning_symbol(neo4j, repo_id=repo_id, symbol_name=symbol_name)
            repo_root = get_repo_root(repo_id)
            if paths:
                context_parts.append(f"Files mentioning `{symbol_name}`:\n" + "\n".join(paths))
            if repo_root:
                for p in paths[:5]:
                    fp = (repo_root / p).resolve()
                    if fp.exists():
                        try:
                            txt = fp.read_text(encoding="utf-8", errors="ignore")
                            context_parts.append(f"{p}\n\n{snip_around_text(txt, symbol_name)}")
                        except Exception:
                            pass

    if expanded:
        context_parts.append("Graph-expanded symbols:\n" + "\n".join(expanded[:50]))

    return {**state, "context_parts": context_parts}


def _assemble_step(state: dict) -> dict:
    context = "\n\n---\n\n".join(state["context_parts"])
    return {
        **state,
        "context": context,
        "context_items": len(state["context_parts"]),
    }


SYSTEM = (
    "You are RepoRover, an assistant that answers questions about a codebase. "
    "Use ONLY the provided context. If unsure, say what is missing."
)

_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM),
        ("human", "Question:\n{question}\n\nContext:\n{context}"),
    ]
)


async def _llm_step(state: dict) -> dict:
    if not settings.llm_api_key:
        return {**state, "answer": "LLM_API_KEY is missing. Set it in repo-rover/.env to enable answers."}
    try:
        answer = await (_PROMPT | get_chat_model() | StrOutputParser()).ainvoke(
            {"question": state["question"], "context": state["context"]}
        )
    except Exception as e:
        answer = f"LLM error: {e}"
    return {**state, "answer": answer}


def _build_retrieval_sequence() -> RunnableSequence:
    return (
        RunnableLambda(_retrieve_step)
        | RunnableLambda(_enrich_step)
        | RunnableLambda(_assemble_step)
    )


def build_repo_query_chain() -> Runnable:
    """LCEL: retrieve + enrich + assemble context → prompt → chat model → text."""
    return _build_retrieval_sequence() | RunnableLambda(_llm_step)


async def run_repo_query_chain(
    neo4j: Neo4jClient,
    repo_id: str,
    question: str,
    top_k: int,
) -> tuple[str, int]:
    chain = build_repo_query_chain()
    out = await chain.ainvoke(
        {
            "neo4j": neo4j,
            "repo_id": repo_id,
            "question": question,
            "top_k": top_k,
        }
    )
    return out["answer"], int(out["context_items"])
