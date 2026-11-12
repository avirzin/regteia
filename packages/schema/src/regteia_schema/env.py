"""Configuration comes only from environment variables. For local dev, a `.env` in the working directory is read
first; it never overrides variables that are already set."""

import os
from pathlib import Path

#: Repeated in every user-facing output.
AVISO = (
    "Conversão automatizada, apenas informativa. Não substitui o Diário Oficial da União nem os portais oficiais "
    "do BCB e da CVM; confira sempre a fonte oficial indicada."
)


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def neo4j_settings() -> tuple[str, str, str]:
    """(uri, user, password) from the environment."""
    load_dotenv()
    password = os.environ.get("NEO4J_PASSWORD")
    if not password:
        raise SystemExit("NEO4J_PASSWORD is not set (copy .env.example to .env)")
    return os.environ.get("NEO4J_URI", "bolt://localhost:7687"), os.environ.get("NEO4J_USER", "neo4j"), password
