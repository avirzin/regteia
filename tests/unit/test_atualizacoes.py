"""The atualizacoes parser, on real upstream entries (normas-bcb 39a59edc)."""

from datetime import date

from regteia_ingest.parse.atualizacoes import Alvo, ler, ligar
from regteia_ingest.parse.citacoes import autor_da_atualizacao


def _alvos(texto: str, norma: str = "bcb:resolucao-bcb:520") -> list[tuple]:
    return [(a.chave, a.tipo, a.a_partir_de, a.detalhe) for a in ler(texto, norma).alvos]


def test_author_is_read_as_upstream_does():
    assert autor_da_atualizacao("Resolução BCB nº 589/2026 - Alteração") == "bcb:resolucao-bcb:589"
    assert (
        autor_da_atualizacao("CIRCULAR BCB 1932/91 DOU 11/04/1991 PAG 6717 - ALTERACAO: ART/7") == "bcb:circular:1932"
    )
    assert autor_da_atualizacao("Resolução Conjunta BCB/CMN nº 14/2025 - Revogação") == "bcb:resolucao-conjunta:14"
    assert autor_da_atualizacao("Instrução Normativa BCB nº 653/2025 - X") == "bcb:instrucao-normativa-bcb:653"
    assert autor_da_atualizacao("OBS: A RESOLUÇÃO CMN 575/1979 ENCONTRA-SE REVOGADA.") is None


def test_res_bcb_520_future_amendment():
    t = (
        "Resolução BCB nº 589/2026 - Alteração, a partir de 1º/1/2027 - Nova redação: art. 88, inciso III, "
        'alíneas "b", "c", "d" e "e". Inclusão: arts. 90-A e 90-B.'
    )
    lido = ler(t, "bcb:resolucao-bcb:520")
    assert lido.de == "bcb:resolucao-bcb:589" and lido.resultado == "dispositivos"
    jan = date(2027, 1, 1)
    assert _alvos(t) == [
        ("art-88", "nova_redacao", jan, 'inciso III, alíneas "b", "c", "d" e "e"'),
        ("art-90-a", "inclusao", jan, None),
        ("art-90-b", "inclusao", jan, None),
    ]
    # the portal's consolidated text doesn't have arts. 90-A and 90-B yet: matched to nothing, kept as absent
    ligado = ligar(lido, {"art-88", "art-90", "art-91"})
    assert ligado.resultado == "parcial"
    assert [a.chave for a in ligado.alvos] == ["art-88"]
    assert ligado.ausentes_alvos == (Alvo("art-90-a", "inclusao", jan), Alvo("art-90-b", "inclusao", jan))


def test_whole_norm_events():
    for t in (
        "Resolução CMN nº 4.991/2022 - Revogação total, a partir de 2/5/2022.",
        "RESOLUÇÃO CMN 1764/90 DOU 01/11/1990 PAG 20875 - REVOGACAO TOTAL.",
    ):
        lido = ler(t, "bcb:resolucao-cmn:1")
        assert (lido.resultado, lido.motivo, lido.alvos) == ("norma", "revogação total", ())
    assert ler("CARTA CIRCULAR BCB 1565/87 DOU 19/02/1987 PAG 2492 - ATUALIZACAO DO MNI.", "x:y").resultado == "norma"
    assert ler("Circular BCB nº 2.664/1996 DOU 16/02/1996 PAG 2701 - Alteração: CNC 2/13.", "x:y").motivo.startswith(
        "manual"
    )


def test_ranges_lettered_articles_and_details():
    t = "Resolução CMN nº 4.970/2021 - Alteração, a partir de 1º/9/2022 - Revogação: arts. 2º a 4º, 14, 47 a 49 e 65."
    assert [a[0] for a in _alvos(t)] == ["art-2", "art-3", "art-4", "art-14", "art-47", "art-48", "art-49", "art-65"]
    t = "Resolução BCB nº 581/2026 - Alteração do anexo - Inclusão: Capítulo VII-A, Seções I e II, arts. 60-A a 60-C"
    assert [a[0] for a in _alvos(t)] == ["anexo/art-60-a", "anexo/art-60-b", "anexo/art-60-c"]
    t = "Resolução CMN nº 4.440/2015 – Alteração: art. 1º, I, “c”; II, “c”; III, “c”."
    assert _alvos(t) == [("art-1", "nova_redacao", None, "I, “c”; II, “c”; III, “c”")]
    t = "Resolução BCB nº 399/2024 - Nova redação: ementa; e arts. 1º; e 5º, incisos II e III. Inclusão: art. 5º, IV."
    assert [(a[0], a[1]) for a in _alvos(t)] == [
        ("art-1", "nova_redacao"),
        ("art-5", "nova_redacao"),
        ("art-5", "inclusao"),
    ]


def test_annex_scopes():
    t = (
        "Resolução CMN nº 5.184/2024 - Nova redação: art. 2º. Alteração Anexo I - Nova redação: art. 10, inciso I; "
        "art. 15, incisos IV e V."
    )
    assert [a[0] for a in _alvos(t)] == ["art-2", "anexo-i/art-10", "anexo-i/art-15"]
    t = "Instrução Normativa BCB nº 538/2024 - Alteração - Nova redação: Anexos I e III. Inclusão: Anexo IV."
    assert [(a[0], a[1]) for a in _alvos(t)] == [
        ("anexo-i", "nova_redacao"),
        ("anexo-iii", "nova_redacao"),
        ("anexo-iv", "inclusao"),
    ]
    t = "Resolução CMN nº 2.480/1998 - Alteração do Regulamento anexo - Revogação arts. 49 e 50."
    assert [(a[0], a[1]) for a in _alvos(t)] == [("anexo/art-49", "revogacao"), ("anexo/art-50", "revogacao")]
    t = "CIRCULAR BCB 1932/91 DOU 11/04/1991 - CITACAO: ART/3 - ALTERACAO: ART/7 PARAG/1 ITEM/IV (REGULAMENTO)."
    assert [(a[0], a[1]) for a in _alvos(t)] == [("anexo/art-7", "nova_redacao")]  # the citation is not a change


def test_legacy_items_and_dates_after_the_target():
    assert [a[0] for a in _alvos("RESOLUÇÃO CMN 1280/87 DOU 23/03/1987 PAG 4090- ALTERACAO: ITEM/I.")] == ["item-i"]
    assert [a[0] for a in _alvos('Resolução CMN nº 1.366/1987 - Alteração: item I, "c"; item X.')] == [
        "item-i",
        "item-x",
    ]
    assert _alvos("Circular BCB nº 3.432/2009 DOU 4/2/2009 p. 33 - Revogação: art. 9º (a partir de 6/2/2009).") == [
        ("art-9", "revogacao", date(2009, 2, 6), None)
    ]
    # a date followed by a new clause is for what comes after it
    t = (
        "Instrução Normativa BCB nº 754/2026 - Inclusão: Capítulo II, Seção XI, e art. 10-F. Produzindo efeitos a "
        "partir de 1º/10/2026 - Inclusão: Capítulo II, Seção XII, e art. 10-G."
    )
    assert [(a[0], a[2]) for a in _alvos(t)] == [("art-10-f", None), ("art-10-g", date(2026, 10, 1))]


def test_other_norms_notes_and_failures_are_reported():
    t = "CIRCULAR BCB 1010/86 DOU 21/03/1986 PAG 4212 - RET: 26/03/1986 - ALTERACAO: ITEM/II DA CIRCULAR BCB 963/85."
    lido = ler(t, "bcb:circular:900")
    assert (lido.resultado, lido.motivo) == ("nota", "trata de outra norma")
    assert ler("OBS: A RESOLUÇÃO CMN 602/1980 ENCONTRA-SE REVOGADA.", "x:y").resultado == "nota"
    assert (
        ler("Instrução Normativa BCB nº 371/2025 - Revogação total.", "bcb:instrucao-normativa-bcb:371").resultado
        == "nota"
    )
    falha = ler("Carta Circular BCB nº 3.412/2009 - Alteração: § 1º. Revogação: § 6º.", "bcb:carta-circular:1")
    assert falha.resultado == "falha" and falha.motivo.startswith("dispositivo ilegível")
    assert ler("RESOLUÇÃO CMN 1267/1987.", "x:y").resultado == "falha"


def test_ligar_finds_annexes_and_articles_written_another_way():
    lido = ler("Resolução CMN nº 1.867/91 - Alteração: Regulamento Anexo IV, art. 27; Anexo 2.", "x:y")
    ligado = ligar(lido, {"anexo-4/art-27", "anexo-ii"})
    assert [a.chave for a in ligado.alvos] == ["anexo-4/art-27", "anexo-ii"] and ligado.resultado == "dispositivos"
    # an article missing from the main body is the one in the norm's only annex
    lido = ler("CIRCULAR BCB 1736/90 DOU 25/05/1990 PAG 10006 - ALTERACAO: ART/3.", "x:y")
    assert [a.chave for a in ligar(lido, {"art-1", "anexo/art-3"}).alvos] == ["anexo/art-3"]
    assert ligar(lido, {"art-1"}).resultado == "ausente"


def test_alvo_is_hashable_and_frozen():
    assert hash(Alvo("art-1", "inclusao", None))
