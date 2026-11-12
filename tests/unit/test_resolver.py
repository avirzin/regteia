import pytest
from regteia_query.resolver import candidatos, escapar_lucene, normalizar


@pytest.mark.parametrize(
    "ref, primeiro",
    [
        # real titles and references as they appear upstream
        ("Resolução BCB N° 520", "bcb:resolucao-bcb:520"),
        ("Resolução BCB nº 589/2026", "bcb:resolucao-bcb:589"),
        ("Res. BCB 520", "bcb:resolucao-bcb:520"),
        ("Resolução CMN N° 4.839", "bcb:resolucao-cmn:4839"),
        ("Resolução Nº 1", "bcb:resolucao-cmn:1"),
        ("Carta Circular Nº 1", "bcb:carta-circular:1"),
        ("Carta-Circular nº 3.365", "bcb:carta-circular:3365"),
        ("Instrução Normativa BCB N° 701", "bcb:instrucao-normativa-bcb:701"),
        ("COMUNICADO N. 010000", "bcb:comunicado:10000"),
        ("ATO-PRESI N. 000001", "bcb:ato-do-presidente:1"),
        ("ATO-DE-DIRETOR N. 000653", "bcb:ato-de-diretor:653"),
        ("Instrução CVM 116 (Revogada)", "cvm:instrucao:116"),
        ("ICVM 400", "cvm:instrucao:400"),
        ("Resolução CVM 175", "cvm:resolucao:175"),
        ("Ofício-Circular CVM/SIN 01/02", "cvm:oficio-circular-sin:1-2002"),
        ("Decisão Conjunta BACEN/CVM 10/02", "cvm:decisao-conjunta-bcb:10-2002"),
        ("Lei nº 4.595/1964", "lei:4595-1964"),
        ("Decreto nº 11.563/2023", "dec:11563-2023"),
        ("Decreto-Lei 2.848/1940", "del:2848-1940"),
        ("Lei Complementar 105/2001", "lcp:105-2001"),
        ("bcb:resolucao-bcb:520", "bcb:resolucao-bcb:520"),
    ],
)
def test_candidatos(ref, primeiro):
    assert candidatos(ref)[0] == primeiro


def test_ambiguous_and_fallback_candidates():
    assert candidatos("Resolução 4.839") == ["bcb:resolucao-cmn:4839", "bcb:resolucao-bcb:4839"]
    assert "cvm:portaria:10-2021" in candidatos("Portaria CVM/PTE Nº 10/2021")


def test_not_a_reference():
    assert candidatos("ativos virtuais") == []
    assert candidatos("Lei 4.595") == []  # federal IDs need the year


def test_normalizar_and_escape():
    assert normalizar("Ofício-Circular  CVM/SIN Nº 01/02") == "oficio circular cvm/sin 01/02"
    assert escapar_lucene('ativos "virtuais" (cripto):') == 'ativos \\"virtuais\\" \\(cripto\\)\\:'
