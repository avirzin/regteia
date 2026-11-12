"""query functions over the real fixture excerpts loaded into a real Neo4j."""

from datetime import date

import pytest
from neo4j import READ_ACCESS
from neo4j.exceptions import ClientError
from regteia_query import (
    DispositivoNaoEncontrado,
    NormaNaoEncontrada,
    buscar,
    dispositivo,
    estatisticas,
    norma,
    panorama,
    relacoes,
)
from regteia_schema.env import AVISO

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def db(leitor):
    return leitor


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


def test_exportar_grafo(db):
    from regteia_query import GRUPOS, exportar_grafo

    g = exportar_grafo(db)
    n = len(g.ids)
    assert len(g.titulos) == len(g.grupos) == len(g.estados) == len(g.anos) == n
    assert len(g.origens) == len(g.destinos) == len(g.tipos)
    assert all(0 <= i < n for i in g.origens + g.destinos)
    assert "bcb:comunicado:10000" not in g.ids  # comunicados hidden by default
    assert "bcb:comunicado:10000" in exportar_grafo(db, comunicados=True).ids
    i520 = g.ids.index("bcb:resolucao-bcb:520")
    assert GRUPOS[g.grupos[i520]] == "BCB"
    assert GRUPOS[g.grupos[g.ids.index("lei:4595-1964")]] == "Lei federal"
    assert GRUPOS[g.grupos[g.ids.index("bcb:resolucao-cmn:102")]] == "CMN"
    assert GRUPOS[g.grupos[g.ids.index("cvm:resolucao:1")]] == "CVM"
    i589 = g.ids.index("bcb:resolucao-bcb:589")
    assert any(o == i589 and d == i520 for o, d in zip(g.origens, g.destinos, strict=True))


def test_buscar_finds_article_text_with_excerpt(db):
    # "embaralhadores" is only in the body of Res. BCB 520 (art. 90, parágrafo único), not in any title or ementa
    r = buscar(db, "misturadores embaralhadores")
    assert r.itens[0].norma.id == "bcb:resolucao-bcb:520"
    [t, *_] = r.itens[0].trechos
    assert t.dispositivo.id == "bcb:resolucao-bcb:520#art-90" and t.dispositivo.rotulo == "Art. 90"
    assert "embaralhadores" in t.trecho and len(t.trecho) < 340
    assert "dispositivos" in r.notas[0]


def test_norma_lists_its_dispositivos(db):
    r = norma(db, "Resolução BCB 520, art. 88")  # the article part is ignored here
    assert r.norma.id == "bcb:resolucao-bcb:520"
    assert r.divisao == "artigos" and len(r.sumario) == 94
    assert [d.rotulo for d in r.sumario[:3]] == ["Preâmbulo", "Art. 1", "Art. 2"]


def test_dispositivo_latest_wording_earlier_wording_and_future_dates(db):
    r = dispositivo(db, "art. 91 da Resolução BCB 520", hoje=date(2026, 9, 1))
    assert r.dispositivo.id == "bcb:resolucao-bcb:520#art-91" and not r.dispositivo.revogado
    assert "6 de novembro de 2026" in r.texto and "~~" not in r.texto
    assert len(r.redacoes_anteriores) == 1 and "30 de outubro de 2026" in r.redacoes_anteriores[0]
    assert r.anterior.rotulo == "Art. 90" and r.proximo.rotulo == "Art. 92"
    assert r.dispositivo.contexto.startswith("CAPÍTULO XI")
    assert any("redação mais recente" in n for n in r.notas)
    assert any("01/10/2026" in n and "vigência futura" in n for n in r.notas)  # "Redação dada, a partir de 1º/10/2026"
    assert any(n.startswith("Alterada") for n in r.notas)  # the norm-level note comes too
    assert r.aviso == AVISO
    # same article by id, and after the date the future note is gone
    r2 = dispositivo(db, "bcb:resolucao-bcb:520#art-91", hoje=date(2026, 11, 12))
    assert r2.texto == r.texto and not any("vigência futura" in n for n in r2.notas)


def test_dispositivo_not_found_and_missing_reference(db):
    with pytest.raises(DispositivoNaoEncontrado) as e:
        dispositivo(db, "Resolução BCB 520, art. 95")
    assert [i for i, _ in e.value.sugestoes][:2] == ["bcb:resolucao-bcb:520#art-92", "bcb:resolucao-bcb:520#art-91"]
    with pytest.raises(ValueError):
        dispositivo(db, "Resolução BCB 520")
    with pytest.raises(NormaNaoEncontrada):
        dispositivo(db, "Resolução BCB 99999, art. 1")


def test_estatisticas_dispositivos(db):
    e = estatisticas(db)
    assert e.dispositivos == sum(e.dispositivos_por_tipo.values()) > 100
    assert e.normas_por_divisao["vazio"] == 1 and e.normas_por_divisao["artigos"] >= 10
    assert e.dispositivos_com_redacao_anterior >= 1
