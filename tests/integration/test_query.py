"""query functions over the real fixture excerpts loaded into a real Neo4j."""

from datetime import date
from pathlib import Path

import pytest
from neo4j import READ_ACCESS, GraphDatabase
from neo4j.exceptions import ClientError
from regteia_ingest.config import Settings, Upstream
from regteia_ingest.migrate import migrate
from regteia_ingest.run import ingest
from regteia_query import Leitor, NormaNaoEncontrada, buscar, estatisticas, norma, panorama, relacoes
from regteia_schema.env import AVISO

pytestmark = pytest.mark.integration
MIGRATIONS = Path(__file__).parents[2] / "db" / "migrations"


@pytest.fixture(scope="module")
def db(neo4j_url, tmp_path_factory):
    import shutil
    import subprocess

    from tests.conftest import FIXTURES

    tmp = tmp_path_factory.mktemp("q")
    driver = GraphDatabase.driver(neo4j_url, auth=("neo4j", "test-password"), notifications_min_severity="OFF")
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
    leitor = Leitor(GraphDatabase.driver(neo4j_url, auth=("neo4j", "test-password"), notifications_min_severity="OFF"))
    yield leitor
    leitor.close()


def test_read_sessions_reject_writes(db):
    with db._driver.session(default_access_mode=READ_ACCESS) as s, pytest.raises(ClientError):
        s.execute_read(lambda tx: tx.run("CREATE (:Intruso)").consume())


def test_norma_by_name(db):
    r = norma(db, "Resolução BCB 520", hoje=date(2026, 11, 11))
    assert r.norma.id == "bcb:resolucao-bcb:520"
    assert r.norma.estado == "alterada" and r.norma.situacao == "VIGENTE, ALTERADA"
    assert r.norma.fonte_url.startswith("https://www.bcb.gov.br/")
    assert r.aviso == AVISO
    alterada_por = next(g for g in r.relacoes if (g.direcao, g.tipo) == ("entrada", "ALTERA"))
    assert [v.norma.id for v in alterada_por.itens] == ["bcb:resolucao-bcb:589"]
    assert any("consolidado" in n for n in r.notas)


def test_future_amendment_is_flagged(db):
    # 589 amends 520 from 2026-10-01: future when asked on 2026-09-30, in force after
    antes = norma(db, "bcb:resolucao-bcb:520", hoje=date(2026, 9, 30))
    depois = norma(db, "bcb:resolucao-bcb:520", hoje=date(2026, 10, 2))
    assert any("vigência futura" in n and "01/10/2026" in n for n in antes.notas)
    assert not any("vigência futura" in n for n in depois.notas)


def test_revoked_and_stub_notes(db):
    rev = norma(db, "Circular 1")
    assert rev.norma.estado == "revogada" and rev.norma.situacao == "REVOGADA"
    assert rev.notas[0].startswith("REVOGADA")
    lei = norma(db, "Lei nº 4.595/1964")
    assert lei.norma.externo and lei.norma.situacao == "FORA DO ACERVO"


def test_not_found_gives_suggestions(db):
    with pytest.raises(NormaNaoEncontrada) as e:
        norma(db, "Resolução BCB 99999")
    assert e.value.sugestoes  # title search fallback


def test_buscar_and_panorama(db):
    r = buscar(db, "ativos virtuais")
    assert r.itens[0].norma.id in {"bcb:resolucao-bcb:520", "bcb:resolucao-bcb:589"}
    assert all(i.norma.fonte_url for i in r.itens if not i.norma.externo)
    p = panorama(db, "ativos virtuais")
    assert p.itens and all(i.norma.estado != "revogada" and not i.norma.externo for i in p.itens)
    assert buscar(db, '"(:').itens == []  # query syntax is escaped, not executed


def test_relacoes_multi_hop(db):
    um = relacoes(db, "bcb:resolucao-bcb:589", tipos=["altera"])
    assert [n.norma.id for n in um.nos] == ["bcb:resolucao-bcb:589", "bcb:resolucao-bcb:520"]
    dois = relacoes(db, "bcb:resolucao-bcb:589", profundidade=2)
    assert {n.distancia for n in dois.nos} == {0, 1, 2}
    assert any(a.para == "lei:4595-1964" for a in dois.arestas)
    entrada = relacoes(db, "bcb:resolucao-bcb:520", direcao="entrada", tipos=["altera"])
    assert [a.de for a in entrada.arestas] == ["bcb:resolucao-bcb:589"]
    capped = relacoes(db, "bcb:resolucao-bcb:589", profundidade=2, limite=3)
    assert len(capped.nos) == 3 and capped.truncado
    with pytest.raises(ValueError):
        relacoes(db, "bcb:resolucao-bcb:589", tipos=["substitui"])


def test_estatisticas(db):
    e = estatisticas(db)
    assert e.normas == 20 and e.arestas == 56 and e.nao_resolvidos == 3
    assert sum(e.por_estado.values()) == 20
    assert sum(s.total for s in e.por_serie) == 20
    assert {i.fonte for i in e.ingestoes} == {"normas-bcb", "normas-cvm"}
    assert e.falhas_atualizacoes is None
