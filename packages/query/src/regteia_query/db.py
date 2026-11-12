"""Read-only access to Neo4j. Every query runs in a READ transaction, so the server itself rejects writes.

Neo4j Community has no RBAC: read-only is enforced here, in code. Nothing in this package writes.
"""

from pathlib import Path
from typing import Any

from neo4j import READ_ACCESS, Driver, GraphDatabase, ManagedTransaction
from regteia_schema.env import neo4j_settings

_QUERIES = Path(__file__).parent / "queries"
#: Every .cypher file in queries/, loaded at import time.
CYPHER: dict[str, str] = {p.stem: p.read_text(encoding="utf-8") for p in sorted(_QUERIES.glob("*.cypher"))}


def nativo(value: Any) -> Any:
    """Neo4j temporal values -> Python ones, recursively."""
    if hasattr(value, "to_native"):
        return value.to_native()
    if isinstance(value, dict):
        return {k: nativo(v) for k, v in value.items()}
    if isinstance(value, list):
        return [nativo(v) for v in value]
    return value


def _ler(tx: ManagedTransaction, consultas: list[tuple[str, dict[str, Any]]]) -> list[list[dict[str, Any]]]:
    return [[nativo(r.data()) for r in tx.run(CYPHER[nome], params)] for nome, params in consultas]


class Leitor:
    """The only way `query` talks to the database."""

    def __init__(self, driver: Driver):
        self._driver = driver

    @classmethod
    def do_ambiente(cls) -> "Leitor":
        uri, user, password = neo4j_settings()
        return cls(GraphDatabase.driver(uri, auth=(user, password), notifications_min_severity="OFF"))

    def ler(self, nome: str, **params: Any) -> list[dict[str, Any]]:
        return self.ler_varios([(nome, params)])[0]

    def ler_varios(self, consultas: list[tuple[str, dict[str, Any]]]) -> list[list[dict[str, Any]]]:
        """Several named queries in one read transaction (one consistent snapshot)."""
        with self._driver.session(default_access_mode=READ_ACCESS) as s:
            return s.execute_read(_ler, consultas)

    def close(self) -> None:
        self._driver.close()

    def __enter__(self) -> "Leitor":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
