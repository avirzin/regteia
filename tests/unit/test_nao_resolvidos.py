"""Classifying upstream's unresolved references (real patterns and IDs from normas-bcb nao_resolvidos.jsonl)."""

import pytest
from regteia_query.estatisticas import categoria


@pytest.mark.parametrize(
    "tipo, id_, padrao, esperado",
    [
        ("alvo", "dec:1085-1975", None, "lei_federal"),
        ("alvo", "ext:comunicado-firce:123-1980", None, "outro_orgao"),
        ("alvo", "bcb:circular:284719", None, "acervo"),
        ("padrao", None, "Cita MCR N", "manual"),
        ("padrao", None, "ALTERA CNC N, N", "manual"),
        ("padrao", None, "Altera RMCCI N", "manual"),
        ("padrao", None, "CITA COSIF N", "manual"),
        ("padrao", None, "Constituição Federal/N, ADCT, art. N", "constituicao"),
        ("padrao", None, "Cita CF, art. N, § Nº.", "constituicao"),
        ("padrao", None, "Voto N–BCB.", "voto"),
        ("padrao", None, "DOU      N PAG N", "outro"),
        ("padrao", None, "SUMULA:", "outro"),
        ("padrao", None, "RESOLUÇÃO 5783/6", "outro"),
    ],
)
def test_categoria(tipo, id_, padrao, esperado):
    assert categoria(tipo, id_, padrao) == esperado
