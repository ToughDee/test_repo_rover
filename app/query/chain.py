from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableLambda, RunnableSequence

from app.core.settings import settings
from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.vector_store import VectorStore
from app.ingestion.text_scan import extract_identifiers
from app.llm.chat_model import get_chat_model
from app.query.graph_context import files_mentioning_symbol, graph_expand_neighbors, snip_around_text, graph_get_call_flows
from app.repos.registry import get_repo_root


class QueryPlan(BaseModel):
    search_vector: str = Field(description="The semantic keywords for vector search. Do NOT include path filters here.")
    intent: Literal["flow", "usage", "general"] = Field(description="The structural intent of the query.")
    include_paths: list[str] = Field(description="Substrings that must be present in the file path (e.g., '.py', 'backend', 'src/'). Empty means all.")
    exclude_paths: list[str] = Field(description="Substrings that must NOT be present in the file path (e.g., '.tsx', 'frontend', 'tests/').")
    target_symbol: str | None = Field(None, description="If intent is usage, the symbol being asked about (e.g. 'authenticate_user').")

from langchain_core.output_parsers import PydanticOutputParser

_PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are a query optimizer. Analyze the user's codebase query to extract the intent and target file paths.\n"
               "1. If they ask about 'code flow', 'execution path', 'mechanism', or 'how X works', set intent to 'flow'.\n"
               "2. If they ask 'where is X used' or 'who calls X', set it to 'usage' and extract the symbol name to target_symbol.\n"
               "3. Use clues like 'frontend', 'backend', 'client', or 'server'. For 'backend', add common server folders/extensions to 'include_paths' (e.g., 'server/', 'api/', 'backend/', '.py', '.java', '.go') and exclude client code in 'exclude_paths' (e.g., 'frontend/', 'client/', '.tsx', '.jsx'). For 'frontend', do the reverse. If no specific area is requested, leave them empty.\n\n"
               "{format_instructions}"),
    ("human", "{question}")
])

async def _rewrite_step(state: dict) -> dict:
    question = state["question"]
    if not settings.llm_api_key:
        plan = QueryPlan(search_vector=question, intent="general", include_paths=[], exclude_paths=[], target_symbol=None)
        return {**state, "plan": plan}
        
    try:
        model = get_chat_model()
        parser = PydanticOutputParser(pydantic_object=QueryPlan)
        prompt = _PLANNER_PROMPT.partial(format_instructions=parser.get_format_instructions())
        
        output = await (prompt | model).ainvoke({"question": question})
        plan = parser.invoke(output)
    except Exception as e:
        import traceback
        traceback.print_exc()
        plan = QueryPlan(search_vector=question, intent="general", include_paths=[], exclude_paths=[], target_symbol=None)
        
    return {**state, "plan": plan}


async def _retrieve_step(state: dict) -> dict:
    repo_id = state["repo_id"]
    top_k = state["top_k"]
    plan: QueryPlan = state["plan"]
    
    vs = VectorStore.from_settings(repo_id)
    retriever = vs.as_retriever(top_k * 3)
    docs = await retriever.ainvoke(plan.search_vector)
    
    hits: list[dict] = []
    for d in docs:
        if len(hits) >= top_k:
            break
            
        md = d.metadata or {}
        fp = md.get("file_path", "").replace("\\", "/")
        
        if plan.exclude_paths and any(excl in fp for excl in plan.exclude_paths):
            continue
        if plan.include_paths and not any(incl in fp for incl in plan.include_paths):
            continue
            
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
    hits: list[dict] = state["hits"]
    context_parts = list(state["context_parts"])
    plan: QueryPlan = state["plan"]

    expanded = graph_expand_neighbors(neo4j, repo_id=repo_id, qualified_names=state["seed_qns"], depth=1)

    if plan.intent == "usage":
        symbol_name = plan.target_symbol
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

    if plan.intent == "flow":
        flows = graph_get_call_flows(neo4j, repo_id=repo_id, qualified_names=state["seed_qns"], max_depth=4)
        if flows:
            context_parts.append("Function Call Flows:\n" + "\n".join(flows[:20]))

    if expanded:
        context_parts.append("Graph-expanded symbols:\n" + "\n".join(expanded[:50]))
        vs = VectorStore.from_settings(repo_id)
        neighbor_docs = vs.get_documents_by_qns(expanded[:5])
        if neighbor_docs:
            context_parts.append("Source code for key neighbors:\n" + "\n\n---\n\n".join(neighbor_docs))

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
        RunnableLambda(_rewrite_step)
        | RunnableLambda(_retrieve_step)
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

async def run_repo_query_context_only(
    neo4j: Neo4jClient,
    repo_id: str,
    question: str,
    top_k: int,
) -> tuple[str, int]:
    chain = _build_retrieval_sequence()
    out = await chain.ainvoke(
        {
            "neo4j": neo4j,
            "repo_id": repo_id,
            "question": question,
            "top_k": top_k,
        }
    )
    return out["context"], int(out["context_items"])
