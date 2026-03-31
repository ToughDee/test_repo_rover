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
    import os
    exts = set(EXT_TO_LANG.keys())
    out: list[Path] = []
    
    print(f"DEBUG: Indexer scanning root: {repo_root}")
    # Convert Path to string for os.walk
    root_str = str(repo_root.resolve())
    
    for root, dirs, files in os.walk(root_str):
        # Mutate 'dirs' to skip directories we don't like
        # This prevents os.walk from even entering node_modules, .git, etc.
        skip_dirs = {".work", ".chroma", "node_modules", ".git", ".venv", "dist", "build"}
        dirs[:] = [d for d in dirs if d.lower() not in skip_dirs]
        
        for file in files:
            p = Path(root) / file
            if p.suffix.lower() in exts:
                out.append(p)
                
    print(f"DEBUG: Indexer found {len(out)} files.")
    return out


def index_repo(repo_id: str, repo_root: Path) -> IndexedRepo:
    files: list[IndexedFile] = []

    for fp in iter_code_files(repo_root):
        s, txt, imports = extract_symbols(fp, repo_id=repo_id, repo_root=repo_root)
        rel = str(fp.resolve().relative_to(repo_root.resolve())).replace("\\", "/")
        if s or txt:
            files.append(IndexedFile(rel_path=rel, text=txt, symbols=s, imports=imports))

    return IndexedRepo(repo_id=repo_id, repo_root=repo_root, files=files)

