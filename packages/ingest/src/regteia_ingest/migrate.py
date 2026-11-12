"""Apply db/migrations/NNN_description.cypher in order. Each file runs once; applied ones are recorded as
(:Migracao {nome}). Statements are separated by a `;` at the end of a line."""

import logging
import re
from pathlib import Path

from neo4j import Driver

log = logging.getLogger(__name__)
_NAME = re.compile(r"^\d{3}_[a-z0-9_]+\.cypher$")


def statements(text: str) -> list[str]:
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("//")]
    parts = re.split(r";\s*$", "\n".join(lines), flags=re.MULTILINE)
    return [p.strip() for p in parts if p.strip()]


def migrations(directory: Path) -> list[Path]:
    files = sorted(directory.glob("*.cypher"))
    bad = [f.name for f in files if not _NAME.match(f.name)]
    if bad:
        raise ValueError(f"migration files must be named NNN_description.cypher: {bad}")
    return files


def migrate(driver: Driver, directory: Path) -> list[str]:
    applied = {
        r["nome"] for r in driver.execute_query("MATCH (m:Migracao) RETURN m.nome AS nome", routing_="r").records
    }
    done = []
    for f in migrations(directory):
        if f.name in applied:
            continue
        for stmt in statements(f.read_text(encoding="utf-8")):
            # schema statements must run in their own auto-commit transaction
            with driver.session() as s:
                s.run(stmt).consume()
        driver.execute_query("MERGE (m:Migracao {nome: $nome}) SET m.em = datetime()", {"nome": f.name})
        log.info("applied migration %s", f.name)
        done.append(f.name)
    return done
