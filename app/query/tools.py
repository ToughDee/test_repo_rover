"""
LangGraph Agent Tools for RepoRover.

Each tool wraps a graph/vector operation that the agent can invoke
dynamically during reasoning. Tools are pure functions that accept
structured input and return string context for the LLM.
"""
from __future__ import annotations

from typing import Annotated
from langchain_core.tools import tool

from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.vector_store import VectorStore
from app.query.graph_context import (
    graph_expand_neighbors,
    files_mentioning_symbol,
    graph_get_call_flows,
    snip_around_text,
)
from app.repos.registry import get_repo_root


# ---------------------------------------------------------------------------
# Helper: we stash neo4j + repo_id in a closure so tool signatures stay clean
# ---------------------------------------------------------------------------

def build_tools(neo4j: Neo4jClient, repo_id: str):
    """Returns a list of LangChain tools bound to a specific repo context."""

    @tool
    def search_codebase(query: str) -> str:
        """Search the codebase using semantic vector similarity.
        Use this when you need to find code related to a concept, feature, or keyword.
        Input should be a detailed technical description of what you're looking for.
        """
        vs = VectorStore.from_settings(repo_id)
        retriever = vs.as_retriever(top_k=8)
        # LangChain retriever is async-first but we call sync here
        import asyncio
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                docs = pool.submit(lambda: retriever.invoke(query)).result()
        else:
            docs = retriever.invoke(query)

        if not docs:
            return "No results found for this query."

        parts = []
        for d in docs[:8]:
            md = d.metadata or {}
            header = md.get("qualified_name", "unknown")
            parts.append(f"### {header}\n```\n{d.page_content[:1500]}\n```")
        return "\n\n".join(parts)

    @tool
    def find_symbol_usages(symbol_name: str) -> str:
        """Find all files that use/reference a specific symbol (function, class, variable).
        Use this when the user asks 'where is X used?' or 'who calls X?'.
        Input should be the exact symbol name (e.g., 'authenticate_user').
        """
        paths = files_mentioning_symbol(neo4j, repo_id=repo_id, symbol_name=symbol_name)
        if not paths:
            return f"No files found mentioning '{symbol_name}'."

        result = f"Files mentioning `{symbol_name}`:\n"
        repo_root = get_repo_root(repo_id)

        for p in paths[:10]:
            result += f"- {p}\n"
            if repo_root:
                fp = (repo_root / p).resolve()
                if fp.exists():
                    try:
                        txt = fp.read_text(encoding="utf-8", errors="ignore")
                        snippet = snip_around_text(txt, symbol_name, max_len=600)
                        result += f"```\n{snippet}\n```\n"
                    except Exception:
                        pass
        return result

    @tool
    def get_call_chain(function_name: str) -> str:
        """Trace the call chain of a function to see what it calls and what calls it.
        Use this to understand execution flow, e.g., 'how does the login flow work?'.
        Input should be a qualified name or function name.
        """
        # First, try to find the function in the vector store to get its qualified name
        vs = VectorStore.from_settings(repo_id)
        retriever = vs.as_retriever(top_k=3)
        docs = retriever.invoke(function_name)

        seed_qns = []
        for d in docs:
            md = d.metadata or {}
            qn = md.get("qualified_name")
            if qn:
                seed_qns.append(qn)

        if not seed_qns:
            return f"Could not find function '{function_name}' in the codebase."

        flows = graph_get_call_flows(neo4j, repo_id=repo_id, qualified_names=seed_qns, max_depth=4)
        if not flows:
            return f"No call chains found starting from '{function_name}'."

        result = f"Call chains from `{function_name}`:\n"
        for flow in flows[:15]:
            result += f"  {flow}\n"
        return result

    @tool
    def expand_graph_neighborhood(qualified_name: str) -> str:
        """Explore the graph neighborhood of a symbol to find related functions, classes, and files.
        Use this to discover what other code is structurally connected to a given symbol.
        Input should be a qualified name (e.g., 'app/auth.py::verify_token').
        """
        neighbors = graph_expand_neighbors(
            neo4j, repo_id=repo_id, qualified_names=[qualified_name], depth=2
        )
        if not neighbors:
            return f"No graph neighbors found for '{qualified_name}'."

        result = f"Graph neighbors of `{qualified_name}`:\n"
        for n in neighbors[:20]:
            result += f"- {n}\n"

        # Fetch source code for the top neighbors
        vs = VectorStore.from_settings(repo_id)
        neighbor_docs = vs.get_documents_by_qns(neighbors[:5])
        if neighbor_docs:
            result += "\nSource code for key neighbors:\n"
            for doc in neighbor_docs:
                result += f"```\n{doc[:800]}\n```\n"

        return result

    @tool
    def read_file(file_path: str) -> str:
        """Read the contents of a specific file from the repository.
        Use this when you need to examine the full source code of a file.
        Input should be the relative path (e.g., 'app/core/settings.py').
        """
        repo_root = get_repo_root(repo_id)
        if not repo_root:
            return f"Repository root not found for repo '{repo_id}'."

        fp = (repo_root / file_path).resolve()
        if not fp.exists():
            return f"File not found: {file_path}"

        try:
            txt = fp.read_text(encoding="utf-8", errors="ignore")
            if len(txt) > 4000:
                txt = txt[:4000] + "\n\n... [truncated]"
            return f"Contents of `{file_path}`:\n```\n{txt}\n```"
        except Exception as e:
            return f"Error reading file: {e}"

    @tool
    def get_definition(symbol_name: str) -> str:
        """Look up the definition of a symbol (function, class) by its exact name.
        Returns the symbol's qualified name, type, file location, and source code.
        Use this as the FIRST tool when the user asks 'what does X do?' or 'show me X'.
        Input should be the symbol name (e.g., 'verify_token', 'Neo4jClient').
        """
        results = neo4j.find_symbol(repo_id, symbol_name)
        if not results:
            return f"No symbol named '{symbol_name}' found in the graph."

        parts = []
        repo_root = get_repo_root(repo_id)
        for r in results:
            qn = r.get("qualified_name", "unknown")
            kind = r.get("kind", "unknown")
            fpath = r.get("file_path", "unknown")
            header = f"**{kind}** `{qn}` in `{fpath}`"
            parts.append(header)

            # Try to read the source code
            if repo_root and fpath:
                fp = (repo_root / fpath).resolve()
                if fp.exists():
                    try:
                        txt = fp.read_text(encoding="utf-8", errors="ignore")
                        snippet = snip_around_text(txt, symbol_name, max_len=1200)
                        parts.append(f"```\n{snippet}\n```")
                    except Exception:
                        pass

        return "\n\n".join(parts)

    @tool
    def get_callers(function_name: str) -> str:
        """Find all functions that CALL a given function (reverse call graph).
        Use this when the user asks 'who calls X?' or 'what depends on X?'.
        Input should be the function name or qualified name.
        """
        # First resolve the name to a qualified name
        symbols = neo4j.find_symbol(repo_id, function_name)
        qn = function_name
        if symbols:
            qn = symbols[0].get("qualified_name", function_name)

        callers = neo4j.get_callers(repo_id, qn)
        if not callers:
            return f"No callers found for '{function_name}'."

        result = f"Functions that call `{function_name}`:\n"
        for c in callers:
            caller_name = c.get("caller_name", "unknown")
            caller_qn = c.get("caller_qn", "unknown")
            fpath = c.get("file_path", "unknown")
            result += f"- `{caller_name}` ({caller_qn}) in `{fpath}`\n"
        return result

    @tool
    def get_file_dependencies(file_path: str) -> str:
        """Show what a file imports (its dependencies) and what other files import it.
        Use this to understand the dependency graph around a specific file.
        Input should be the relative file path (e.g., 'app/core/settings.py').
        """
        deps = neo4j.get_file_dependencies(repo_id, file_path)

        result = f"Dependencies for `{file_path}`:\n\n"

        imports = deps.get("imports", [])
        if imports:
            result += "**This file imports:**\n"
            for imp in imports:
                target = imp.get("target_qn") or imp.get("target_path") or "unknown"
                kind = imp.get("target_kind", "")
                result += f"- {target} ({kind})\n"
        else:
            result += "**This file imports:** (no resolved imports found)\n"

        imported_by = deps.get("imported_by", [])
        if imported_by:
            result += "\n**Imported by:**\n"
            for dep in imported_by:
                result += f"- {dep.get('source_path', 'unknown')}\n"
        else:
            result += "\n**Imported by:** (no dependents found)\n"

        return result

    @tool
    def list_files(path_filter: str = "") -> str:
        """List all indexed files in the repository, optionally filtered by a path substring.
        Use this when the user asks 'show me the project structure' or 'what files are in the auth module?'.
        Input should be a path substring to filter by (e.g., 'auth', 'test') or empty for all files.
        """
        all_files = neo4j.list_files(repo_id)
        if not all_files:
            return "No files indexed for this repository."

        if path_filter:
            filtered = [f for f in all_files if path_filter.lower() in f.lower()]
        else:
            filtered = all_files

        if not filtered:
            return f"No files matching '{path_filter}' found."

        result = f"Indexed files ({len(filtered)} of {len(all_files)} total):\n"
        for f in filtered[:50]:
            result += f"- {f}\n"
        if len(filtered) > 50:
            result += f"\n... and {len(filtered) - 50} more files."
        return result

    return [
        search_codebase,
        find_symbol_usages,
        get_call_chain,
        expand_graph_neighborhood,
        read_file,
        get_definition,
        get_callers,
        get_file_dependencies,
        list_files,
    ]

