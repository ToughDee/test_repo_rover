from __future__ import annotations

import re

IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


def extract_identifiers(text: str) -> set[str]:
    return set(IDENT_RE.findall(text))

