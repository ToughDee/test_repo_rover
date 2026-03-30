from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.ingestion.ast_extract import EXT_TO_LANG, Symbol, extract_symbols


@dataclass(frozen=True)
class IndexedFile:
    rel_path: str
    text: str
    symbols: list[Symbol]
    imports: list[str]


@dataclass(frozen=True)
class IndexedRepo:
    repo_id: str
    repo_root: Path
    files: list[IndexedFile]


def iter_code_files(repo_root: Path) -> list[Path]:
    exts = set(EXT_TO_LANG.keys())
    out: list[Path] = []
    for p in repo_root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        # Skip common heavy folders
        parts = {x.lower() for x in p.parts}
        if {"node_modules", ".git", ".venv", "dist", "build"} & parts:
            continue
        out.append(p)
    return out


def index_repo(repo_id: str, repo_root: Path) -> IndexedRepo:
    files: list[IndexedFile] = []

    for fp in iter_code_files(repo_root):
        s, txt, imports = extract_symbols(fp, repo_id=repo_id, repo_root=repo_root)
        rel = str(fp.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
        if s or txt:
            files.append(IndexedFile(rel_path=rel, text=txt, symbols=s, imports=imports))

    return IndexedRepo(repo_id=repo_id, repo_root=repo_root, files=files)

