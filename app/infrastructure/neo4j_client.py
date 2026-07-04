from __future__ import annotations

from dataclasses import dataclass

from neo4j import Driver, GraphDatabase

from app.core.settings import settings


@dataclass(frozen=True)
class Neo4jClient:
    driver: Driver

    @classmethod
    def from_settings(cls) -> "Neo4jClient":
        driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        return cls(driver=driver)

    def close(self) -> None:
        self.driver.close()

    def init_schema(self) -> None:
        queries = [
            "CREATE CONSTRAINT repo_key IF NOT EXISTS FOR (r:Repository) REQUIRE r.repo_id IS UNIQUE",
            "CREATE CONSTRAINT dir_key IF NOT EXISTS FOR (d:Directory) REQUIRE (d.repo_id, d.path) IS UNIQUE",
            "CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE (f.repo_id, f.path) IS UNIQUE",
            "CREATE CONSTRAINT func_key IF NOT EXISTS FOR (fn:Function) REQUIRE (fn.repo_id, fn.qualified_name) IS UNIQUE",
            "CREATE CONSTRAINT class_key IF NOT EXISTS FOR (c:Class) REQUIRE (c.repo_id, c.qualified_name) IS UNIQUE",
            "CREATE CONSTRAINT var_key IF NOT EXISTS FOR (v:Variable) REQUIRE (v.repo_id, v.qualified_name) IS UNIQUE",
            "CREATE CONSTRAINT import_key IF NOT EXISTS FOR (i:Import) REQUIRE (i.repo_id, i.value) IS UNIQUE",
        ]
        with self.driver.session() as s:
            for q in queries:
                s.run(q)

    def upsert_file(self, repo_id: str, path: str) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (f:File {repo_id: $repo_id, path: $path})
                """,
                repo_id=repo_id,
                path=path,
            )

    def delete_files(self, repo_id: str, file_paths: list[str]) -> None:
        if not file_paths:
            return
        with self.driver.session() as s:
            s.run(
                """
                MATCH (f:File {repo_id: $repo_id})
                WHERE f.path IN $file_paths
                OPTIONAL MATCH (f)-[:DEFINES]->(sym)
                DETACH DELETE f, sym
                """,
                repo_id=repo_id,
                file_paths=file_paths,
            )

    def upsert_symbol(
        self,
        repo_id: str,
        kind: str,
        qualified_name: str,
        name: str,
        file_path: str,
    ) -> None:
        label = "Function" if kind == "function" else "Class"
        with self.driver.session() as s:
            s.run(
                f"""
                MERGE (s:{label} {{repo_id: $repo_id, qualified_name: $qualified_name}})
                SET s.name = $name
                WITH s
                MATCH (f:File {{path: $file_path}})
                MERGE (f)-[:DEFINES]->(s)
                """,
                repo_id=repo_id,
                qualified_name=qualified_name,
                name=name,
                file_path=file_path,
            )

    def add_calls(self, repo_id: str, caller_qn: str, callees: list[str]) -> None:
        if not callees:
            return
        with self.driver.session() as s:
            s.run(
                """
                MATCH (caller:Function {repo_id: $repo_id, qualified_name: $caller_qn})
                UNWIND $callees AS callee_name
                MERGE (callee:Function {repo_id: $repo_id, qualified_name: $repo_id + '::external::' + callee_name})
                SET callee.name = callee_name
                MERGE (caller)-[:CALLS]->(callee)
                """,
                repo_id=repo_id,
                caller_qn=caller_qn,
                callees=callees[:200],
            )

    def add_mentions(self, repo_id: str, file_path: str, symbol_qns: list[str]) -> None:
        if not symbol_qns:
            return
        with self.driver.session() as s:
            s.run(
                """
                MATCH (f:File {path: $file_path})
                UNWIND $qns AS qn
                MATCH (sym {repo_id: $repo_id, qualified_name: qn})
                MERGE (f)-[:MENTIONS]->(sym)
                """,
                repo_id=repo_id,
                file_path=file_path,
                qns=symbol_qns[:500],
            )

    def add_resolved_imports(self, repo_id: str, file_path: str, target_fqns: list[str]) -> None:
        if not target_fqns:
            return
        with self.driver.session() as s:
            s.run(
                """
                MATCH (f:File {repo_id: $repo_id, path: $file_path})
                UNWIND $target_fqns AS target_fqn
                MATCH (target {repo_id: $repo_id}) 
                WHERE target.qualified_name = target_fqn OR target.path = target_fqn
                MERGE (f)-[:RESOLVES_TO]->(target)
                """,
                repo_id=repo_id,
                file_path=file_path,
                target_fqns=target_fqns[:500],
            )

    def add_imports(self, repo_id: str, file_path: str, imports: list[str]) -> None:
        if not imports:
            return
        with self.driver.session() as s:
            s.run(
                """
                MATCH (f:File {path: $file_path})
                WITH f
                UNWIND $imports AS imp
                MERGE (i:Import {repo_id: $repo_id, value: imp})
                MERGE (f)-[:IMPORTS]->(i)
                """,
                repo_id=repo_id,
                file_path=file_path,
                imports=imports[:300],
            )

    # ------ Query methods for agent tools ------

    def find_symbol(self, repo_id: str, symbol_name: str) -> list[dict]:
        """Find symbols by name. Returns list of {qualified_name, kind, file_path}."""
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH (sym {repo_id: $repo_id, name: $name})
                OPTIONAL MATCH (f:File)-[:DEFINES]->(sym)
                RETURN sym.qualified_name AS qualified_name,
                       labels(sym)[0] AS kind,
                       f.path AS file_path
                LIMIT 10
                """,
                repo_id=repo_id,
                name=symbol_name,
            )
            return [dict(r) for r in res]

    def get_callers(self, repo_id: str, qualified_name: str) -> list[dict]:
        """Find all functions that CALL this function (reverse traversal)."""
        with self.driver.session() as s:
            res = s.run(
                """
                MATCH (caller:Function {repo_id: $repo_id})-[:CALLS]->(target {repo_id: $repo_id})
                WHERE target.qualified_name = $qn OR target.name = $name
                OPTIONAL MATCH (f:File)-[:DEFINES]->(caller)
                RETURN caller.qualified_name AS caller_qn,
                       caller.name AS caller_name,
                       f.path AS file_path
                LIMIT 30
                """,
                repo_id=repo_id,
                qn=qualified_name,
                name=qualified_name.split("::")[-1] if "::" in qualified_name else qualified_name,
            )
            return [dict(r) for r in res]

    def get_file_dependencies(self, repo_id: str, file_path: str) -> dict:
        """Get what a file imports (outgoing) and what imports it (incoming)."""
        with self.driver.session() as s:
            # Outgoing: what does this file depend on?
            out_res = s.run(
                """
                MATCH (f:File {repo_id: $repo_id, path: $path})-[:RESOLVES_TO]->(target)
                RETURN target.path AS target_path, target.qualified_name AS target_qn,
                       labels(target)[0] AS target_kind
                LIMIT 50
                """,
                repo_id=repo_id,
                path=file_path,
            )
            outgoing = [dict(r) for r in out_res]

            # Incoming: what files depend on this file?
            in_res = s.run(
                """
                MATCH (source:File {repo_id: $repo_id})-[:RESOLVES_TO]->(f:File {repo_id: $repo_id, path: $path})
                RETURN source.path AS source_path
                LIMIT 50
                """,
                repo_id=repo_id,
                path=file_path,
            )
            incoming = [dict(r) for r in in_res]

        return {"imports": outgoing, "imported_by": incoming}

    def list_files(self, repo_id: str) -> list[str]:
        """List all indexed file paths for a repo."""
        with self.driver.session() as s:
            res = s.run(
                "MATCH (f:File {repo_id: $repo_id}) RETURN f.path AS path ORDER BY path",
                repo_id=repo_id,
            )
            return [r["path"] for r in res if r.get("path")]

