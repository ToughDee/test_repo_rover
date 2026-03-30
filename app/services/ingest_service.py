

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from app.infrastructure.neo4j_client import Neo4jClient
from app.infrastructure.vector_store import VectorStore
from app.ingestion.indexer import index_repo
from app.ingestion.text_scan import extract_identifiers
from app.repos.sources import resolve_repo_source


def _doc_id(repo_id: str, qualified_name: str) -> str:
    h = hashlib.sha256(f"{repo_id}|{qualified_name}".encode("utf-8")).hexdigest()[:24]
    return f"sym_{h}"


@dataclass(frozen=True)
class IngestResult:
    repo_id: str
    files_indexed: int
    symbols_indexed: int


def ingest_repo(neo4j: Neo4jClient, repo_id: str, source: str, branch: str | None) -> IngestResult:
    resolved = resolve_repo_source(repo_id=repo_id, source=source, branch=branch)
    indexed = index_repo(repo_id=repo_id, repo_root=resolved.root_dir)

    vs = VectorStore.from_settings(repo_id=repo_id)
    ids: list[str] = []
    docs: list[str] = []
    metas: list[dict] = []
    seen_ids: set[str] = set()

    # Build a name->qualified_name lookup for later "mentions" edges
    name_to_qn: dict[str, str] = {}
    all_symbols: list[tuple[str, str, str, str, list[str]]] = []

    for f in indexed.files:
        neo4j.upsert_file(repo_id=repo_id, path=f.rel_path)
        neo4j.add_imports(repo_id=repo_id, file_path=f.rel_path, imports=f.imports)
        for sym in f.symbols:
            all_symbols.append((sym.kind, sym.qualified_name, sym.name, sym.file_path, sym.calls))
            # Best-effort: if multiple symbols share the same name, keep the first.
            name_to_qn.setdefault(sym.name, sym.qualified_name)

    for kind, qualified_name, name, file_path, _calls in all_symbols:
        neo4j.upsert_symbol(
            repo_id=repo_id,
            kind=kind,
            qualified_name=qualified_name,
            name=name,
            file_path=file_path,
        )

    # CALLS edges: only from the function that actually contains the call sites.
    for kind, qualified_name, _name, _file_path, calls in all_symbols:
        if kind == "function" and calls:
            neo4j.add_calls(repo_id=repo_id, caller_qn=qualified_name, callees=calls)

    # Calls edges + embeddings per symbol (use file text already extracted)
    file_text_by_path = {f.rel_path: f.text for f in indexed.files}
    symbols_by_file: dict[str, list[tuple[str, str, str]]] = {}
    for kind, qualified_name, name, file_path, _calls in all_symbols:
        symbols_by_file.setdefault(file_path, []).append((kind, qualified_name, name))

    for file_path, syms in symbols_by_file.items():
        text = file_text_by_path.get(file_path, "")
        chunk = text[:6000]
        for kind, qualified_name, name in syms:
            doc_id = _doc_id(repo_id, qualified_name)
            if doc_id in seen_ids:
                continue
            seen_ids.add(doc_id)
            ids.append(doc_id)
            docs.append(f"{qualified_name}\n\n{chunk}")
            metas.append(
                {
                    "repo_id": repo_id,
                    "qualified_name": qualified_name,
                    "kind": kind,
                    "file_path": file_path,
                    "name": name,
                }
            )

    # Mentions edges (file -> symbol) so "where is X used?" works in MVP.
    # Simple: tokenize identifiers in each file and link any symbol names found.
    for f in indexed.files:
        idents = extract_identifiers(f.text or "")
        mentioned_qns = [qn for name, qn in name_to_qn.items() if name in idents]
        # Avoid self-only noise: if a file only "mentions" the symbols it defines, still keep it
        # (imports often appear at top; usage is in same file for utils).
        neo4j.add_mentions(repo_id=repo_id, file_path=f.rel_path, symbol_qns=mentioned_qns)

    vs.upsert_documents(ids=ids, docs=docs, metadatas=metas)
    return IngestResult(
        repo_id=repo_id,
        files_indexed=len(indexed.files),
        symbols_indexed=len(all_symbols),
    )
