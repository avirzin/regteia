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
    texto_norma,
    vigencia_dispositivos,
    vigencia_em,
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
    # a federal act ctresb/leis has no file for stays a stub
    lei = norma(db, "lei:13810-2019")
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
    assert e.normas == 20 + 5 and e.arestas == 61 and e.nao_resolvidos == 3  # 5 federal acts from ctresb/leis
    assert sum(e.por_estado.values()) == 25 and e.por_estado["sem_informacao"] == 1  # Decreto 4.334/2002
    assert sum(s.total for s in e.por_serie) == 25
    assert {s.serie for s in e.por_serie if s.acervo in ("lei", "dec", "mpv")} == {"lei", "dec", "mpv"}
    assert {i.fonte for i in e.ingestoes} == {"normas-bcb", "normas-cvm", "leis"}
    # atualizacoes: every fixture entry is stored and accounted for; Res. BCB 589 -> arts. 88 (2027) and 91 of 520
    assert e.atualizacoes == sum(e.atualizacoes_por_resultado.values()) == 8
    assert e.falhas_atualizacoes == e.atualizacoes_por_resultado.get("falha", 0)
    assert e.alteracoes_dispositivo == sum(e.alteracoes_por_tipo.values()) >= 2
    assert e.alteracoes_futuras >= 1  # art. 88 of Res. BCB 520, from 1/1/2027
    assert e.atualizacoes_por_resultado["norma"] >= 2  # the two total revocations


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


HOJE = date(2026, 11, 18)


def test_vigencia_em_article_whose_stored_text_is_later_wording(db):
    # Res. BCB 589 gives art. 88 new wording from 2027-01-01: before that the stored text is not that date's
    antes = vigencia_em(db, "bcb:resolucao-bcb:520#art-88", date(2026, 12, 31), hoje=HOJE)
    assert (antes.situacao, antes.texto_na_data, antes.texto) == ("vigente", "desconhecido", None)
    assert [(e.tipo, e.alcance, e.data, e.origem_data, e.aplicado) for e in antes.eventos] == [
        ("nova_redacao", "parte", date(2027, 1, 1), "a_partir_de", False)
    ]
    assert antes.eventos[0].por.id == "bcb:resolucao-bcb:589" and antes.eventos[0].entrada.startswith("Resolução BCB")
    assert "não guarda a redação" in antes.notas[0]
    depois = vigencia_em(db, "Resolução BCB 520, art. 88", date(2027, 1, 2), hoje=HOJE)
    assert (depois.situacao, depois.texto_na_data) == ("vigente", "armazenado")
    assert depois.texto.startswith("Art. 88") and depois.eventos[0].aplicado
    assert depois.aviso == AVISO and depois.norma.fonte_url.startswith("https://www.bcb.gov.br/")


def test_vigencia_em_article_missing_from_the_portal_text(db):
    # arts. 90-A and 90-B are included from 2027-01-01, and the portal's text doesn't have them yet
    antes = vigencia_em(db, "bcb:resolucao-bcb:520#art-90-a", date(2026, 12, 31), hoje=HOJE)
    assert (antes.situacao, antes.dispositivo, antes.chave) == ("nao_vigente", None, "art-90-a")
    assert "01/01/2027" in antes.motivo and "Resolução BCB" in antes.motivo
    depois = vigencia_em(db, "Resolução BCB 520, art. 90-A", date(2027, 1, 2), hoje=HOJE)
    assert (depois.situacao, depois.texto_na_data, depois.texto) == ("vigente", "sem_texto", None)
    [e] = depois.eventos
    assert (e.tipo, e.rotulo, e.no_texto, e.aplicado) == ("inclusao", "Art. 90-A", False, True)
    assert any("ainda não o traz" in n for n in depois.notas)
    with pytest.raises(DispositivoNaoEncontrado):
        vigencia_em(db, "Resolução BCB 520, art. 95", date(2027, 1, 2), hoje=HOJE)


def test_vigencia_em_whole_norm(db):
    r = vigencia_em(db, "Resolução BCB 520", date(2027, 1, 2), hoje=HOJE)
    assert r.situacao == "vigente" and r.texto_na_data is None
    assert [e.rotulo for e in r.eventos] == ["Art. 91", "Art. 88", "Art. 90-A", "Art. 90-B"]
    assert vigencia_em(db, "Resolução BCB 589", date(2026, 1, 1), hoje=HOJE).situacao == "nao_vigente"


def test_vigencia_em_revoked_norm(db):
    # Circular 1 (1965) revoked by Circular 58 from 1967-01-01, and again by Res. CMN 469 in 1978
    assert vigencia_em(db, "Circular 1", date(1966, 6, 1), hoje=HOJE).situacao == "vigente"
    r = vigencia_em(db, "Circular 1", date(1967, 1, 2), hoje=HOJE)
    assert r.situacao == "revogada" and "01/01/1967" in r.motivo
    assert [e.data for e in r.eventos] == [date(1967, 1, 1), date(1978, 6, 1)]
    assert vigencia_em(db, "Circular 1", HOJE, hoje=HOJE).situacao == "revogada"
    # Carta Circular 1: one of its revocations (Circular 3081, outside the fixtures) has no date
    duvida = vigencia_em(db, "bcb:carta-circular:1", date(1970, 1, 1), hoje=HOJE)
    assert duvida.situacao == "indeterminada" and "pode ser anterior" in duvida.motivo
    assert vigencia_em(db, "bcb:carta-circular:1", date(1980, 1, 1), hoje=HOJE).situacao == "revogada"
    # a federal act stub: no history, never a guess
    assert vigencia_em(db, "lei:13810-2019", HOJE, hoje=HOJE).situacao == "indeterminada"


def test_vigencia_dispositivos_whole_norm_on_a_date(db):
    r = vigencia_dispositivos(db, "Resolução BCB 520", date(2026, 12, 31), hoje=HOJE)
    assert r.situacao == "vigente" and r.aviso == AVISO
    chaves = [d.chave for d in r.dispositivos]
    # the articles the portal doesn't publish yet sit right after art. 90, in reading order
    assert chaves[chaves.index("art-90") : chaves.index("art-90") + 4] == ["art-90", "art-90-a", "art-90-b", "art-91"]
    por = {d.chave: d for d in r.dispositivos}
    assert (por["art-90-a"].situacao, por["art-90-a"].no_texto, por["art-90-a"].rotulo) == (
        "nao_vigente",
        False,
        "Art. 90-A",
    )
    assert (por["art-88"].texto_na_data, por["art-88"].posteriores) == ("desconhecido", 1)
    assert (por["art-91"].texto_na_data, por["art-1"].texto_na_data) == ("armazenado", "armazenado")
    # each one agrees with vigencia_em
    for k in ("art-88", "art-90-a", "art-91"):
        um = vigencia_em(db, f"bcb:resolucao-bcb:520#{k}", date(2026, 12, 31), hoje=HOJE)
        assert (um.situacao, um.texto_na_data) == (por[k].situacao, por[k].texto_na_data)
    rev = vigencia_dispositivos(db, "Circular 1", date(1967, 1, 2), hoje=HOJE)
    assert rev.situacao == "revogada" and all(d.situacao == "revogada" for d in rev.dispositivos)


def test_texto_norma(db):
    r = texto_norma(db, "Resolução BCB 520")
    assert r.divisao == "artigos" and len(r.dispositivos) == 94
    art91 = next(d for d in r.dispositivos if d.id.endswith("#art-91"))
    assert art91.texto.startswith("Art. 91") and art91.redacoes_anteriores
    assert relacoes(db, "bcb:resolucao-bcb:589").nos[0].grupo == "BCB"


def test_citacoes_no_texto(db):
    n = norma(db, "Resolução BCB 520")
    grupos = {g.direcao: g for g in n.citacoes_texto}
    # IN BCB 701 cites Res. BCB 520 in its preamble and arts. 1, 2, 3, 4 and 6: six articles, the first five listed
    in701 = next(c for c in grupos["entrada"].itens if c.norma.id == "bcb:instrucao-normativa-bcb:701")
    assert in701.total == 6 and len(in701.dispositivos) == 5
    assert [d.id.split("#")[1] for d in in701.dispositivos] == ["preambulo", "art-1", "art-2", "art-3", "art-4"]
    # Res. BCB 520 cites Lei 14.478/2022 in its preamble and arts. 3 and 88; federal laws are stubs named from the ID
    lei = next(c for c in grupos["saida"].itens if c.norma.id == "lei:14478-2022")
    assert lei.total == 3 and not lei.norma.externo and lei.norma.titulo == "Lei nº 14.478 de 21/12/2022"

    d = dispositivo(db, "bcb:instrucao-normativa-bcb:712#art-1")
    assert {c.id for c in d.cita} == {
        "bcb:instrucao-normativa-bcb:330",
        "bcb:instrucao-normativa-bcb:701",
        "bcb:resolucao-bcb:520",
    }
    assert next(c for c in d.cita if c.id == "bcb:resolucao-bcb:520").estado == "alterada"  # status travels along
    t = texto_norma(db, "IN BCB 712")
    assert {c.id for c in next(x for x in t.dispositivos if x.id.endswith("#art-1")).cita} == {c.id for c in d.cita}


def test_estatisticas_citacoes_e_nao_resolvidos(db):
    e = estatisticas(db)
    assert e.citacoes_texto == sum(e.citacoes_texto_por_alvo.values()) > 100
    assert e.citacoes_texto_por_alvo["acervo"] > 0 and e.citacoes_texto_por_alvo["lei_federal"] > 0
    assert 0 < e.citacoes_texto_pares_novos <= e.citacoes_texto_pares
    assert e.citacoes_pendentes > 0
    assert any(p.id == "bcb:resolucao-cmn:454" for p in e.citacoes_pendentes_lista)
    # the fixtures' three: a section of the rural credit manual and two IDs no norm has
    cats = {c.categoria: c for c in e.nao_resolvidos_por_categoria}
    assert set(cats) == {"manual", "acervo"}
    assert (cats["manual"].n, cats["manual"].ocorrencias, cats["manual"].exemplos) == (1, 144, ["Cita MCR 2-2-20."])
    assert [(x.id, x.em) for x in e.nao_resolvidos_acervo] == [
        ("bcb:carta-circular:11283", "bcb:circular:925"),
        ("cvm:comunicado-conjunto-bcb:17-1987", "cvm:instrucao:68"),
    ]


def test_federal_acts_from_ctresb_leis(db):
    # compiled text, not revoked: in force; the text version is always said
    lei = norma(db, "Lei 4.595/1964")
    assert not lei.norma.externo and lei.norma.estado == "vigente" and lei.norma.situacao == "VIGENTE"
    assert lei.norma.versao_texto == "compilada (texto vigente)" and lei.norma.fonte_url.startswith(
        "https://normas.leg.br"
    )
    assert lei.norma.urn == "urn:lex:br:federal:lei:1964-12-31;4595" and lei.divisao == "artigos"
    # original text: flagged as possibly outdated
    original = norma(db, "lei:14478-2022")
    assert any("pode não refletir alterações posteriores" in n for n in original.notas)
    # revogada: null in the source: never shown as in force
    dec = norma(db, "dec:4334-2002")
    assert dec.norma.estado == "sem_informacao" and dec.norma.situacao == "SITUAÇÃO NÃO INFORMADA"
    assert dec.notas[0].startswith("SITUAÇÃO NÃO INFORMADA")
    assert vigencia_em(db, "dec:4334-2002", HOJE, hoje=HOJE).situacao == "indeterminada"


def test_federal_act_text_on_a_date(db):
    # Lei 4.595, compiled text downloaded on 2026-10-13: that day's wording from then to today, unknown before
    agora = vigencia_em(db, "Lei 4.595/1964, art. 1", HOJE, hoje=HOJE)
    assert agora.situacao == "vigente" and agora.texto_na_data == "armazenado" and agora.texto
    antes = vigencia_em(db, "Lei 4.595/1964, art. 1", date(2000, 1, 1), hoje=HOJE)
    assert antes.situacao == "vigente" and antes.texto_na_data == "desconhecido" and antes.texto is None
    assert "histórico de alterações" in antes.notas[0]
    # Lei 14.478, original text: never that date's wording, even today
    r = vigencia_em(db, "lei:14478-2022#art-1", HOJE, hoje=HOJE)
    assert r.texto_na_data == "desconhecido" and r.texto is None and "como publicado" in r.notas[0]
    todos = vigencia_dispositivos(db, "lei:14478-2022", HOJE, hoje=HOJE)
    assert todos.dispositivos and all(
        d.texto_na_data == "desconhecido" for d in todos.dispositivos if d.situacao == "vigente"
    )
