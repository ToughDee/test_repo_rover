from __future__ import annotations

import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from git import Repo

from app.core.settings import settings
from app.repos.registry import set_repo_root


def _safe_repo_folder(repo_id: str) -> str:
    h = hashlib.sha256(repo_id.encode("utf-8")).hexdigest()[:16]
    return f"repo_{h}"


def _rmtree_force(path: Path) -> None:
    def _onerror(func, p, exc_info):
        try:
            Path(p).chmod(0o777)
        except Exception:
            pass
        try:
            func(p)
        except Exception:
            pass

    shutil.rmtree(path, onerror=_onerror)


@dataclass(frozen=True)
class ResolvedRepo:
    repo_id: str
    root_dir: Path
    is_temp: bool = False


def resolve_repo_source(repo_id: str, source: str, branch: str | None) -> ResolvedRepo:
    """
    - If `source` is an existing local folder, we index it in-place (no copy).
    - If `source` looks like a remote git URL, we clone it into WORK_DIR.
    """
    src = source.strip()
    p = Path(src)
    if p.exists() and p.is_dir():
        set_repo_root(repo_id, p)
        return ResolvedRepo(repo_id=repo_id, root_dir=p, is_temp=False)

    work = Path(settings.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    target = (work / _safe_repo_folder(repo_id)).resolve()

    if target.exists():
        try:
            _rmtree_force(target)
        except Exception:
            target = (work / f"{_safe_repo_folder(repo_id)}_fresh").resolve()
            if target.exists():
                _rmtree_force(target)

    clone_kwargs = {}
    if branch:
        clone_kwargs["branch"] = branch

    Repo.clone_from(src, str(target), **clone_kwargs)
    set_repo_root(repo_id, target)
    return ResolvedRepo(repo_id=repo_id, root_dir=target, is_temp=True)
