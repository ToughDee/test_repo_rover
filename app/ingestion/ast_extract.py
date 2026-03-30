from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from tree_sitter import Node
from tree_sitter_languages import get_parser


@dataclass(frozen=True)
class Symbol:
    kind: str  # "function" | "class"
    name: str
    qualified_name: str
    file_path: str
    start_byte: int
    end_byte: int
    calls: list[str]
    # NOTE: file-level imports are extracted separately and should not be copied onto every symbol.
    imports: list[str]


EXT_TO_LANG: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
}


def _text(src: bytes, node: Node) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _first_named_child(node: Node, t: str) -> Node | None:
    for c in node.named_children:
        if c.type == t:
            return c
    return None


def _collect(node: Node, types: set[str]) -> list[Node]:
    out: list[Node] = []
    stack = [node]
    while stack:
        cur = stack.pop()
        if cur.type in types:
            out.append(cur)
        stack.extend(reversed(cur.named_children))
    return out


def _collect_calls_within(src: bytes, scope: Node) -> list[str]:
    # Calls (best-effort): capture callee expression text, but only within the provided scope node.
    call_nodes = _collect(scope, {"call", "call_expression"})
    calls: list[str] = []
    for cn in call_nodes:
        callee = cn.named_children[0] if cn.named_children else None
        if callee is None:
            continue
        callee_txt = _text(src, callee).strip()
        if callee_txt:
            calls.append(callee_txt[:200])
    return calls


def extract_symbols(file_path: Path, repo_id: str, repo_root: Path) -> tuple[list[Symbol], str, list[str]]:
    ext = file_path.suffix.lower()
    lang = EXT_TO_LANG.get(ext)
    if not lang:
        return ([], "", [])

    src = file_path.read_bytes()
    parser = get_parser(lang)
    tree = parser.parse(src)
    root = tree.root_node

    rel_path = str(file_path.resolve().relative_to(repo_root.resolve())).replace("\\", "/")

    symbols: list[Symbol] = []

    # Language-agnostic-ish node types (approximate across supported grammars)
    func_nodes = _collect(
        root,
        {
            "function_definition",  # python
            "function_declaration",  # js/ts
            "method_definition",  # js/ts class method
        },
    )
    # JS/TS: capture "const foo = async (...) => ..." style definitions
    var_decl_nodes = _collect(root, {"variable_declarator"})
    class_nodes = _collect(root, {"class_definition", "class_declaration"})

    # Imports
    import_nodes = _collect(
        root,
        {
            "import_statement",  # python/js/ts
            "import_from_statement",  # python
            "import_declaration",  # js/ts
            "require_call",  # some js grammars
        },
    )
    imports: list[str] = []
    for n in import_nodes:
        snippet = _text(src, n).strip()
        if snippet:
            imports.append(snippet[:300])

    # Create symbols with per-symbol calls/imports for now (simple MVP)
    def add_symbol(kind: str, node: Node, name_guess: str) -> None:
        # Include a stable span component to avoid collisions (e.g. many anonymous functions)
        qn = f"{rel_path}::{name_guess}::{node.start_byte}"
        per_symbol_calls = _collect_calls_within(src, node) if kind == "function" else []
        symbols.append(
            Symbol(
                kind=kind,
                name=name_guess,
                qualified_name=qn,
                file_path=rel_path,
                start_byte=node.start_byte,
                end_byte=node.end_byte,
                calls=per_symbol_calls,
                imports=[],
            )
        )

    for fn in func_nodes:
        name_node = _first_named_child(fn, "identifier") or _first_named_child(fn, "name")
        name_guess = _text(src, name_node).strip() if name_node else "anonymous"
        add_symbol("function", fn, name_guess)

    # JS/TS: variable declarators whose value is a function/arrow function
    for vd in var_decl_nodes:
        ident = _first_named_child(vd, "identifier")
        if ident is None:
            continue
        name_guess = _text(src, ident).strip()
        # Look for an initializer node that is a function
        init = None
        for c in vd.named_children:
            if c is ident:
                continue
            if c.type in {"arrow_function", "function", "function_expression"}:
                init = c
                break
        if init is None:
            continue
        add_symbol("function", init, name_guess or "anonymous")

    for cn in class_nodes:
        name_node = _first_named_child(cn, "identifier") or _first_named_child(cn, "name")
        name_guess = _text(src, name_node).strip() if name_node else "AnonymousClass"
        add_symbol("class", cn, name_guess)

    file_text = src.decode("utf-8", errors="ignore")
    return (symbols, file_text, imports)
