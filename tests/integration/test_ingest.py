"""Full + incremental ingest of the real fixture excerpts into a real Neo4j (testcontainers)."""

import json
from datetime import date
from pathlib import Path

import pytest
from neo4j import GraphDatabase
from regteia_ingest.config import Settings, Upstream
from regteia_ingest.migrate import migrate
from regteia_ingest.run import ingest

from tests.conftest import commit_all

pytestmark = pytest.mark.integration
MIGRATIONS = Path(__file__).parents[2] / "db" / "migrations"


@pytest.fixture
def env(neo4j_url, tmp_path, make_upstream):
    driver = GraphDatabase.driver(neo4j_url, auth=("neo4j", "test-password"), notifications_min_severity="OFF")
    driver.execute_query("MATCH (n) DETACH DELETE n")
    migrate(driver, MIGRATIONS)
    remotes = {name: make_upstream(name) for name in ("normas-bcb", "normas-cvm")}
    ups = [
        Upstream(name=n, url=str(r), ref="main", adapter="normas_grafo", acervo=n.removeprefix("normas-"))
        for n, r in remotes.items()
    ]
    settings = Settings("", "", "", tmp_path / "clones", Path("unused"), MIGRATIONS)
    yield driver, settings, ups, remotes
    driver.close()


def q(driver, cypher, **params):
    return [r.data() for r in driver.execute_query(cypher, params).records]


def snapshot(driver):
    return {
        "normas": q(driver, "MATCH (n:Norma {externo: false}) RETURN count(n) AS c")[0]["c"],
        "stubs": q(driver, "MATCH (n:Norma {externo: true}) RETURN count(n) AS c")[0]["c"],
        "arestas": q(driver, "MATCH (:Norma)-[r]->(:Norma) RETURN count(r) AS c")[0]["c"],
        "nao_resolvidos": q(driver, "MATCH (x:NaoResolvido) RETURN count(x) AS c")[0]["c"],
    }


def test_full_load_and_idempotency(env):
    driver, settings, ups, _ = env
    assert ingest(driver, settings, ups, full=True)
    first = snapshot(driver)
    assert first["normas"] == 20
    assert first["arestas"] == 52 + 4
    assert first["nao_resolvidos"] == 3

    [n520] = q(driver, "MATCH (n:Norma {id: 'bcb:resolucao-bcb:520'}) RETURN n")
    n = n520["n"]
    assert n["estado"] == "alterada" and n["acervo"] == "bcb" and n["externo"] is False
    assert n["fonte_url"].startswith("https://www.bcb.gov.br/")
    assert len(n["upstream_sha"]) == 40

    [alt] = q(
        driver,
        "MATCH (:Norma {id: 'bcb:resolucao-bcb:589'})-[r:ALTERA]->(:Norma {id: 'bcb:resolucao-bcb:520'}) "
        "RETURN r.desde AS desde, r.fonte AS fonte",
    )
    assert alt["desde"].to_native() == date(2026, 10, 1)
    assert alt["fonte"] == "atualizacoes+referencias"

    [lei] = q(driver, "MATCH (n:Norma {id: 'lei:4595-1964'}) RETURN n.externo AS e, n.acervo AS a")
    assert lei == {"e": True, "a": "lei"}

    # the same data again: nothing duplicated, and incremental at the same SHA is a no-op
    assert ingest(driver, settings, ups, full=True)
    assert snapshot(driver) == first
    assert ingest(driver, settings, ups, full=False)
    assert snapshot(driver) == first


def test_incremental_applies_upstream_changes(env):
    driver, settings, ups, remotes = env
    assert ingest(driver, settings, ups, full=True)
    before = snapshot(driver)
    bcb = remotes["normas-bcb"]

    # upstream commit: Res. BCB 520 gets revoked, one of its edges disappears, and Carta Circular 3365 is deleted
    estado = [json.loads(line) for line in (bcb / "grafo/estado.jsonl").read_text().splitlines()]
    for e in estado:
        if e["id"] == "bcb:resolucao-bcb:520":
            e["estado"], e["por"] = "revogada", ["bcb:resolucao-bcb:589"]
    removed = next(e for e in estado if e["id"] == "bcb:carta-circular:3365")
    estado.remove(removed)
    (bcb / removed["caminho"]).unlink()
    (bcb / "grafo/estado.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in estado))
    arestas = (bcb / "grafo/arestas.jsonl").read_text().splitlines(keepends=True)
    dropped = json.loads(arestas.pop(0))
    (bcb / "grafo/arestas.jsonl").write_text("".join(arestas))
    new_sha = commit_all(bcb, "upstream change")

    assert ingest(driver, settings, ups, full=False)
    after = snapshot(driver)
    assert after["normas"] == before["normas"] - 1
    assert after["arestas"] == before["arestas"] - 1
    assert q(driver, "MATCH (n:Norma {id: 'bcb:resolucao-bcb:520'}) RETURN n.estado AS e") == [{"e": "revogada"}]
    assert not q(
        driver,
        "MATCH (:Norma {id: $de})-[r]->(:Norma {id: $para}) WHERE type(r) = toUpper($rel) RETURN r.fonte",
        de=dropped["de"], para=dropped["para"], rel=dropped["relacao"],
    )  # fmt: skip
    [ing] = q(driver, "MATCH (i:Ingestao {fonte: 'normas-bcb'}) RETURN i.sha AS sha, i.modo AS modo")
    assert ing == {"sha": new_sha, "modo": "incremental"}
