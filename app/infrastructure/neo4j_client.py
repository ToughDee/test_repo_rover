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
            "CREATE CONSTRAINT file_path IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT func_key IF NOT EXISTS FOR (fn:Function) REQUIRE (fn.repo_id, fn.qualified_name) IS UNIQUE",
            "CREATE CONSTRAINT class_key IF NOT EXISTS FOR (c:Class) REQUIRE (c.repo_id, c.qualified_name) IS UNIQUE",
            "CREATE CONSTRAINT import_key IF NOT EXISTS FOR (i:Import) REQUIRE (i.repo_id, i.value) IS UNIQUE",
        ]
        with self.driver.session() as s:
            for q in queries:
                s.run(q)

    def upsert_file(self, repo_id: str, path: str) -> None:
        with self.driver.session() as s:
            s.run(
                """
                MERGE (f:File {path: $path})
                SET f.repo_id = $repo_id
                """,
                repo_id=repo_id,
                path=path,
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
