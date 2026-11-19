"""Full + incremental ingest of the real fixture excerpts into a real Neo4j (testcontainers)."""

import json
from datetime import date
from pathlib import Path

import pytest
from neo4j import GraphDatabase
from regteia_ingest.config import Settings, Upstream
from regteia_ingest.migrate import migrate
from regteia_ingest.parse import atualizacoes, dispositivos
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
        "dispositivos": q(driver, "MATCH (:Norma)-[:TEM_DISPOSITIVO]->(d:Dispositivo) RETURN count(d) AS c")[0]["c"],
        "soltos": q(driver, "MATCH (d:Dispositivo) WHERE NOT ()-[:TEM_DISPOSITIVO]->(d) RETURN count(d) AS c")[0]["c"],
        "atualizacoes": q(driver, "MATCH (:Norma)-[:TEM_ATUALIZACAO]->(a) RETURN count(a) AS c")[0]["c"],
        "alteram": q(driver, "MATCH (:Norma)-[r:ALTERA]->(:Dispositivo) RETURN count(r) AS c")[0]["c"],
    }


def test_full_load_and_idempotency(env):
    driver, settings, ups, _ = env
    assert ingest(driver, settings, ups, full=True)
    first = snapshot(driver)
    assert first["normas"] == 20
    assert first["arestas"] == 57 + 4
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

    # Dispositivos: every file-backed norm with text is split; Res. BCB 520 into preamble, 92 articles and annex
    assert first["soltos"] == 0
    assert q(driver, "MATCH (n:Norma {id: 'bcb:resolucao-bcb:520'}) RETURN n.divisao AS d") == [{"d": "artigos"}]
    [a91] = q(
        driver,
        "MATCH (:Norma {id: 'bcb:resolucao-bcb:520'})-[:TEM_DISPOSITIVO]->(d {id: 'bcb:resolucao-bcb:520#art-91'}) "
        "RETURN d.rotulo AS rotulo, d.ordem AS ordem, d.revogado AS revogado, size(d.redacoes_anteriores) AS ant",
    )
    assert a91 == {"rotulo": "Art. 91", "ordem": 91, "revogado": False, "ant": 1}
    n520 = q(driver, "MATCH (:Norma {id: 'bcb:resolucao-bcb:520'})-[:TEM_DISPOSITIVO]->(d) RETURN count(d) AS c")
    assert n520 == [{"c": 94}]
    sem = q(driver, "MATCH (n:Norma {externo: false}) WHERE NOT (n)-[:TEM_DISPOSITIVO]->() RETURN n.divisao AS d")
    assert sem == [{"d": "vazio"}]  # Carta Circular 3365: the portal has no text
    [ing] = q(driver, "MATCH (i:Ingestao {fonte: 'normas-bcb'}) RETURN i.divisao AS v")
    assert ing["v"] == dispositivos.VERSAO

    # atualizacoes: Res. BCB 589 amends arts. 91 (from 1/10/2026) and 88 (from 1/1/2027) of Res. BCB 520, and includes
    # arts. 90-A and 90-B from 1/1/2027, which the portal's consolidated text doesn't have yet
    alteram = q(
        driver,
        "MATCH (:Norma {id: 'bcb:resolucao-bcb:589'})-[r:ALTERA]->(d:Dispositivo) "
        "RETURN d.id AS d, r.tipo AS tipo, r.a_partir_de AS desde, r.detalhe AS detalhe, r.entrada AS entrada "
        "ORDER BY d",
    )
    assert [{**a, "desde": a["desde"].to_native()} for a in alteram] == [
        {"d": "bcb:resolucao-bcb:520#art-88", "tipo": "nova_redacao", "desde": date(2027, 1, 1),
         "detalhe": 'inciso III, alíneas "b", "c", "d" e "e"', "entrada": 1},
        {"d": "bcb:resolucao-bcb:520#art-91", "tipo": "nova_redacao", "desde": date(2026, 10, 1), "detalhe": "caput",
         "entrada": 0},
    ]  # fmt: skip
    entradas = q(
        driver,
        "MATCH (:Norma {id: 'bcb:resolucao-bcb:520'})-[:TEM_ATUALIZACAO]->(a) "
        "RETURN a.ordem AS k, a.de AS de, a.resultado AS r, a.ausentes AS aus, a.ausentes_tipo AS t, "
        "a.ausentes_desde AS ad, a.ausentes_detalhe AS dt ORDER BY k",
    )
    assert entradas == [
        {"k": 0, "de": "bcb:resolucao-bcb:589", "r": "dispositivos", "aus": None, "t": None, "ad": None,
         "dt": None},
        {"k": 1, "de": "bcb:resolucao-bcb:589", "r": "parcial", "aus": ["art-90-a", "art-90-b"],
         "t": ["inclusao", "inclusao"], "ad": ["2027-01-01", "2027-01-01"], "dt": ["", ""]},
    ]  # fmt: skip
    [rev] = q(
        driver, "MATCH (:Norma {id: 'bcb:circular:1'})-[:TEM_ATUALIZACAO]->(a) RETURN a.resultado AS r, a.motivo AS m"
    )
    assert rev == {"r": "norma", "m": "revogação total"}
    [ing] = q(driver, "MATCH (i:Ingestao {fonte: 'normas-bcb'}) RETURN i.atualizacoes AS v")
    assert ing["v"] == atualizacoes.VERSAO

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

    # upstream commit: Res. BCB 520 gets revoked, one of its edges disappears, Carta Circular 3365 and IN BCB 712
    # are deleted, and the text of Res. BCB 520 changes: art. 1 is reworded and art. 92 loses its heading
    estado = [json.loads(line) for line in (bcb / "grafo/estado.jsonl").read_text().splitlines()]
    for e in estado:
        if e["id"] == "bcb:resolucao-bcb:520":
            e["estado"], e["por"] = "revogada", ["bcb:resolucao-bcb:589"]
    for gone in ("bcb:carta-circular:3365", "bcb:instrucao-normativa-bcb:712"):
        removed = next(e for e in estado if e["id"] == gone)
        estado.remove(removed)
        (bcb / removed["caminho"]).unlink()
    f520 = bcb / "resolucoes-bcb/2025/resolucao-bcb-0520.md"
    texto = f520.read_text(encoding="utf-8")
    texto = texto.replace("Art. 1º  Esta Resolução disciplina", "Art. 1º  Esta Resolução (REDAÇÃO NOVA) disciplina")
    texto = texto.replace("Art. 92.  Esta Resolução entra em vigor", "Esta Resolução entra em vigor")
    f520.write_text(texto, encoding="utf-8")
    (bcb / "grafo/estado.jsonl").write_text("".join(json.dumps(e, ensure_ascii=False) + "\n" for e in estado))
    arestas = (bcb / "grafo/arestas.jsonl").read_text().splitlines(keepends=True)
    dropped = json.loads(arestas.pop(0))
    (bcb / "grafo/arestas.jsonl").write_text("".join(arestas))
    new_sha = commit_all(bcb, "upstream change")

    assert ingest(driver, settings, ups, full=False)
    after = snapshot(driver)
    assert after["normas"] == before["normas"] - 2
    assert after["arestas"] == before["arestas"] - 1
    # IN 712's 4 Dispositivos go with its file, and Res. BCB 520 loses art. 92; nothing is left dangling
    assert after["dispositivos"] == before["dispositivos"] - 4 - 1
    assert after["soltos"] == 0
    assert not q(driver, "MATCH (d:Dispositivo) WHERE d.id STARTS WITH 'bcb:instrucao-normativa-bcb:712#' RETURN d")
    assert not q(driver, "MATCH (d:Dispositivo {id: 'bcb:resolucao-bcb:520#art-92'}) RETURN d")
    [a1] = q(driver, "MATCH (d:Dispositivo {id: 'bcb:resolucao-bcb:520#art-1'}) RETURN d.texto AS t")
    assert "(REDAÇÃO NOVA)" in a1["t"]
    [a91] = q(driver, "MATCH (d:Dispositivo {id: 'bcb:resolucao-bcb:520#art-91'}) RETURN d.texto AS t")
    assert "Esta Resolução entra em vigor" in a91["t"]
    assert q(driver, "MATCH (n:Norma {id: 'bcb:resolucao-bcb:520'}) RETURN n.estado AS e") == [{"e": "revogada"}]
    # Res. BCB 520 was re-read: its entries and article-level edges are replaced, not duplicated (the deleted
    # Carta Circular 3365 and IN 712 have no atualizacoes)
    assert (after["atualizacoes"], after["alteram"]) == (before["atualizacoes"], before["alteram"])
    assert not q(
        driver,
        "MATCH (:Norma {id: $de})-[r]->(:Norma {id: $para}) WHERE type(r) = toUpper($rel) RETURN r.fonte",
        de=dropped["de"], para=dropped["para"], rel=dropped["relacao"],
    )  # fmt: skip
    [ing] = q(driver, "MATCH (i:Ingestao {fonte: 'normas-bcb'}) RETURN i.sha AS sha, i.modo AS modo")
    assert ing == {"sha": new_sha, "modo": "incremental"}


@pytest.mark.parametrize("campo, versao", [("divisao", dispositivos.VERSAO), ("atualizacoes", atualizacoes.VERSAO)])
def test_new_parser_version_forces_full_reload(env, campo, versao):
    driver, settings, ups, _ = env
    assert ingest(driver, settings, ups, full=True)
    before = snapshot(driver)
    driver.execute_query(f"MATCH (i:Ingestao) SET i.{campo} = $v, i.modo = 'x'", v=versao - 1)
    # as if the old version had built none
    driver.execute_query("MATCH (d:Dispositivo) DETACH DELETE d")
    driver.execute_query("MATCH (a:Atualizacao) DETACH DELETE a")

    assert ingest(driver, settings, ups, full=False)  # same upstream SHA: would be a no-op without the version check
    assert snapshot(driver) == before
    modos = q(driver, f"MATCH (i:Ingestao) RETURN i.modo AS m, i.{campo} AS v")
    assert modos == [{"m": "full", "v": versao}] * 2
