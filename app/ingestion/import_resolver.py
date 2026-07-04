from __future__ import annotations
from pathlib import Path
from tree_sitter import Node

def _get_text(src: bytes, node: Node) -> str:
    if node is None:
        return ""
    return src[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")

def _resolve_python_module_path(repo_root: Path, current_file_rel: Path, module_name: str, level: int = 0) -> Path | None:
    """
    Resolves a python module name (e.g. 'app.core.settings') to a relative file path.
    Handles relative imports (level > 0).
    """
    parts = module_name.split('.') if module_name else []
    
    # Handle relative imports (from . import X)
    if level > 0:
        base_dir = repo_root / current_file_rel.parent
        # Go up directories for each extra dot
        for _ in range(level - 1):
            base_dir = base_dir.parent
        search_path = base_dir.joinpath(*parts)
    else:
        search_path = repo_root.joinpath(*parts)

    # 1. Check if it's a direct file (e.g., app/core/settings.py)
    file_target = search_path.with_suffix('.py')
    if file_target.is_file():
        return file_target.relative_to(repo_root)

    # 2. Check if it's a package (e.g., app/core/ -> app/core/__init__.py)
    pkg_target = search_path / "__init__.py"
    if pkg_target.is_file():
        return pkg_target.relative_to(repo_root)
        
    return None

def resolve_python_import(repo_root: Path, current_file_rel: str, import_node: Node, src: bytes) -> list[str]:
    """
    Returns a list of FQNs that this import resolves to.
    e.g. ['app/core/settings.py::settings']
    """
    resolved_fqns = []
    curr_path = Path(current_file_rel)

    if import_node.type == "import_from_statement":
        # Extract module name
        module_node = None
        for child in import_node.named_children:
            if child.type == "dotted_name":
                module_node = child
                break
            
        module_name = _get_text(src, module_node) if module_node else ""
        
        # Count relative dots (tree-sitter python handles dots as anonymous nodes in import_from_statement)
        # However, a simpler way is checking the text if it starts with dots
        raw_text = _get_text(src, import_node)
        level = 0
        if raw_text.startswith("from"):
            after_from = raw_text[4:].lstrip()
            while after_from.startswith("."):
                level += 1
                after_from = after_from[1:]
        
        rel_target = _resolve_python_module_path(repo_root, curr_path, module_name, level)
        if not rel_target:
            return [] # External import or not found
            
        # Get imported names
        for child in import_node.named_children:
            if child.type == "dotted_name" and child != module_node:
                # Aliased imports (from X import Y as Z) are usually wrapped in aliased_import
                name = _get_text(src, child)
                resolved_fqns.append(f"{rel_target.as_posix()}::{name}")
            elif child.type == "aliased_import":
                orig_name = child.named_children[0]
                name = _get_text(src, orig_name)
                resolved_fqns.append(f"{rel_target.as_posix()}::{name}")
                
    elif import_node.type == "import_statement":
        # import x, y.z
        for child in import_node.named_children:
            if child.type == "dotted_name":
                module_name = _get_text(src, child)
                rel_target = _resolve_python_module_path(repo_root, curr_path, module_name, 0)
                if rel_target:
                    # In standard imports, the FQN is just the file itself since it imports the module
                    resolved_fqns.append(f"{rel_target.as_posix()}::")
            elif child.type == "aliased_import":
                orig_name = child.named_children[0]
                module_name = _get_text(src, orig_name)
                rel_target = _resolve_python_module_path(repo_root, curr_path, module_name, 0)
                if rel_target:
                    resolved_fqns.append(f"{rel_target.as_posix()}::")

    return resolved_fqns

def resolve_import(lang: str, repo_root: Path, current_file_rel: str, import_node: Node, src: bytes) -> list[str]:
    if lang == "python":
        return resolve_python_import(repo_root, current_file_rel, import_node, src)
    # TODO: Add JS/TS support
    return []
