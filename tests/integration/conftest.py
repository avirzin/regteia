import shutil
import subprocess
from pathlib import Path

import pytest
from neo4j import GraphDatabase
from regteia_ingest.config import Settings, Upstream
from regteia_ingest.migrate import migrate
from regteia_ingest.run import ingest
from regteia_query import Leitor

from tests.conftest import FIXTURES

MIGRATIONS = Path(__file__).parents[2] / "db" / "migrations"
AUTH = ("neo4j", "test-password")


@pytest.fixture(scope="session")
def neo4j_url():
    from testcontainers.neo4j import Neo4jContainer

    with Neo4jContainer("neo4j:5.26-community", password=AUTH[1]) as c:
        yield c.get_connection_url()


@pytest.fixture(scope="module")
def leitor(neo4j_url, tmp_path_factory):
    """A fresh graph loaded from the real fixture excerpts, and a read-only Leitor over it."""
    tmp = tmp_path_factory.mktemp("upstreams")
    driver = GraphDatabase.driver(neo4j_url, auth=AUTH, notifications_min_severity="OFF")
    driver.execute_query("MATCH (n) DETACH DELETE n")
    migrate(driver, MIGRATIONS)
    ups = []
    for name in ("normas-bcb", "normas-cvm"):
        repo = tmp / name
        shutil.copytree(FIXTURES / name, repo)
        for cmd in (["init", "-q", "-b", "main"], ["add", "-A"], ["commit", "-q", "-m", "f"]):
            subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *cmd], cwd=repo, check=True)
        ups.append(Upstream(name=name, url=str(repo), ref="main", adapter="normas_grafo", acervo=name[7:]))
    assert ingest(driver, Settings("", "", "", tmp / "clones", Path("x"), MIGRATIONS), ups, full=True)
    driver.execute_query("CALL db.awaitIndexes(60)")
    driver.close()
    db = Leitor(GraphDatabase.driver(neo4j_url, auth=AUTH, notifications_min_severity="OFF"))
    yield db
    db.close()
