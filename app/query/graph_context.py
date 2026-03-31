from __future__ import annotations

from app.infrastructure.neo4j_client import Neo4jClient


def graph_expand_neighbors(
    neo4j: Neo4jClient,
    repo_id: str,
    qualified_names: list[str],
    depth: int = 1,
) -> list[str]:
    if not qualified_names:
        return []
    d = max(1, min(int(depth), 3))
    q = f"""
    MATCH (s {{repo_id: $repo_id}})
    WHERE s.qualified_name IN $qns
    CALL (s) {{
      MATCH (s)-[:CALLS|DEFINES*1..{d}]-(n)
      RETURN DISTINCT n.qualified_name AS qn
    }}
    RETURN DISTINCT qn
    """
    with neo4j.driver.session() as sess:
        res = sess.run(q, repo_id=repo_id, qns=qualified_names)
        out: list[str] = []
        for r in res:
            qn = r.get("qn")
            if qn:
                out.append(qn)
        return out[:50]


def files_mentioning_symbol(neo4j: Neo4jClient, repo_id: str, symbol_name: str) -> list[str]:
    q = """
    MATCH (sym {repo_id: $repo_id})
    WHERE sym.name = $name
    MATCH (f:File)-[:MENTIONS]->(sym)
    RETURN DISTINCT f.path AS path
    LIMIT 30
    """
    with neo4j.driver.session() as sess:
        res = sess.run(q, repo_id=repo_id, name=symbol_name)
        return [r["path"] for r in res if r.get("path")]


def snip_around_text(text: str, needle: str, max_len: int = 900) -> str:
    idx = text.lower().find(needle.lower())
    if idx < 0:
        return text[:max_len]
    start = max(0, idx - 200)
    end = min(len(text), idx + 600)
    return text[start:end]

def graph_get_call_flows(
    neo4j: Neo4jClient,
    repo_id: str,
    qualified_names: list[str],
    max_depth: int = 4,
) -> list[str]:
    if not qualified_names:
        return []
    
    q = f"""
    MATCH path = (s:Function {{repo_id: $repo_id}})-[:CALLS*1..{max_depth}]->(n:Function)
    WHERE s.qualified_name IN $qns
    RETURN [node in nodes(path) | node.name] AS call_chain
    """
    with neo4j.driver.session() as sess:
        res = sess.run(q, repo_id=repo_id, qns=qualified_names)
        out: list[str] = []
        for r in res:
            chain = r.get("call_chain")
            if chain:
                out.append(" -> ".join(chain))
        return out[:50]
