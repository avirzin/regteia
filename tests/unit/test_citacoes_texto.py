"""Norms cited in article text, on real upstream text (fixtures and normas-bcb/normas-cvm at the 2026-11-19 load)."""

from regteia_ingest.parse.citacoes_texto import citacoes


def _bcb(texto: str, norma: str = "bcb:resolucao-bcb:589") -> list[str]:
    return citacoes(texto, norma, "bcb")


def _cvm(texto: str, norma: str = "cvm:deliberacao:1") -> list[str]:
    return citacoes(texto, norma, "cvm")


def test_dates_in_words_and_numbers():
    assert _bcb("Circular nº 3.978, de 23 de janeiro de 2020;") == ["bcb:circular:3978"]
    assert _bcb("Lei nº 9.613, de 3 de março de 1998;") == ["lei:9613-1998"]
    assert _bcb("Instrução Normativa BCB nº 739, de 29/5/2026.") == ["bcb:instrucao-normativa-bcb:739"]
    assert _bcb("Resolução BCB nº 520, de 2025;") == ["bcb:resolucao-bcb:520"]
    assert _cvm("Instrução CVM nº 481/09, a serem enviadas") == ["cvm:instrucao:481"]


def test_line_breaks_inside_a_reference():
    assert _bcb("Resolução BCB nº 519, de 10 de\nnovembro de 2025") == ["bcb:resolucao-bcb:519"]


def test_a_norm_does_not_cite_itself():
    assert _bcb("Resolução BCB nº 520, de 2025;", norma="bcb:resolucao-bcb:520") == []
    # the portal's heading names no issuer; read alone it would be Res. CMN 589
    assert _bcb("Resolução Nº 589\n\nRESOLUÇÃO BCB Nº 589, DE 23 DE SETEMBRO DE 2026") == []


def test_year_needed_only_where_the_id_has_one():
    # BCB series IDs have no year; a federal law's has, so a law without its year is not read
    assert _bcb("no art. 2º da Circular nº 3.978") == ["bcb:circular:3978"]
    assert _bcb("nos termos do art. 9º da Lei nº 4.595") == []


def test_issuer_after_the_number():
    assert _cvm(
        "prevista no\nRegulamento Anexo III à Resolução nº 1.289, de 20\nde março de 1987, do Conselho Monetário "
        "Nacional."
    ) == ["bcb:resolucao-cmn:1289"]
    assert _cvm(
        "nos termos da LEI Nº 6.385, de 7 de dezembro\nde 1976, e de seu Regimento Interno, aprovado pela PORTARIA "
        "Nº 327, de 11 de julho de 1977, do\nMinistro de Estado da Fazenda, torna público"
    ) == ["lei:6385-1976", "ext:portaria-mf:327-1977"]
    assert _cvm(
        "Prorroga o prazo de que trata a Decisão-Conjunta 10/2002, do Banco Central do Brasil e da Comissão"
    ) == ["cvm:decisao-conjunta-bcb:10-2002"]
    assert _cvm("O presente Ofício-Circular complementa o Ofício-Circular nº 3/2022-CVM/SRE (Ofício") == [
        "cvm:oficio-circular-sre:3-2022"
    ]


def test_resolution_before_2020_is_the_cmns():
    # upstream reads "Resolução" with no issuer in a CVM text as a Resolução CVM, a series that starts in 2020
    assert _cvm(
        "na forma prevista no Regulamento Anexo IV à RESOLUÇÃO Nº\n1.289/87, instituído pela RESOLUÇÃO Nº 1.832, de "
        "31/05/91 e INSTRUÇÃO CVM Nº 169, de\n02/01/92."
    ) == ["bcb:resolucao-cmn:1289", "bcb:resolucao-cmn:1832", "cvm:instrucao:169"]
    assert _cvm("O Banco Central do Brasil, por meio da Resolução nº 3.786/09, estabeleceu o que\nse segue:") == [
        "bcb:resolucao-cmn:3786"
    ]
    assert _cvm("Resolução CVM nº 44/21.") == ["cvm:resolucao:44"]


def test_lists_only_after_a_plural():
    assert _bcb(
        "relativamente às disposições das Resoluções nºs 3.516 e 3.518 e da Circular nº 3.371, todas de 6 de dezembro "
        "de 2007"
    ) == ["bcb:resolucao-cmn:3516", "bcb:resolucao-cmn:3518", "bcb:circular:3371"]
    assert _bcb("com base no item II da Resolução nº 1.552/88, e no art. 2º da Resolução nº 1.925/92") == [
        "bcb:resolucao-cmn:1552",
        "bcb:resolucao-cmn:1925",
    ]


def test_tables_of_numbers_are_not_norms():
    # circular:3245#art-1: a list of banks, then the norm's own number and the table's line numbers
    assert (
        _bcb("BCO NOSSA CAIXA S.A.\n\nCircular nº 3245, de 07 de julho de 2004\n\n8\n9\n\n10\n11", "bcb:circular:3245")
        == []
    )
    assert _bcb("Comunicado nº 0") == []


def test_the_portals_amendment_notes_are_not_citations():
    # Res. CMN 4.966, art. 17: the notes say who amended the article (atualizacoes has that), not what it cites
    art17 = (
        "Parágrafo único.  [(Revogado, a partir de 1º/10/2023, pela Resolução CMN nº 5.100, de 24/8/2023.)]"
        "(https://www.bcb.gov.br/estabilidadefinanceira/exibenormativo?tipo=Resolu%C3%A7%C3%A3o%20CMN&numero=5100)\n\n"
        "§ 2º  O disposto no **caput**e no § 1º não se aplicam às receitas geradas pela recuperação de ativos "
        "baixados de que trata o art. 49. [(Incluído, a partir de 1º/10/2023, pela Resolução CMN nº 5.100, de "
        "24/8/2023.)](https://www.bcb.gov.br/x)"
    )
    assert _bcb(art17, "bcb:resolucao-cmn:4966") == []
    cabecalho = "CARTA-CIRCULAR Nº 1061\nDocumento normativo revogado pela Resolução 1.301, de 06/04/1987.\nComunicamos"
    assert _bcb(cabecalho, "bcb:carta-circular:1061") == []
    # a real citation next to a note is kept
    assert _bcb("nos termos da Circular nº 3.978, de 2020. (Redação dada pela Resolução BCB nº 589, de 2026.)") == [
        "bcb:circular:3978"
    ]
