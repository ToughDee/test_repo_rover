from __future__ import annotations

import json
from pathlib import Path

from app.core.settings import settings


def _registry_path() -> Path:
    work = Path(settings.work_dir)
    work.mkdir(parents=True, exist_ok=True)
    return work / "repos.json"


def set_repo_root(repo_id: str, root_dir: Path) -> None:
    p = _registry_path()
    data: dict[str, str] = {}
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    data[repo_id] = str(root_dir.resolve())
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_repo_root(repo_id: str) -> Path | None:
    p = _registry_path()
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
    val = data.get(repo_id)
    if not val:
        return None
    rp = Path(val)
    return rp if rp.exists() else None
