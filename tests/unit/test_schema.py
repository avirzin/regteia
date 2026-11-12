import pytest
from pydantic import ValidationError
from regteia_schema import (
    ArestaRow,
    EstadoRow,
    NaoResolvidoAlvo,
    NaoResolvidoPadrao,
    Relacao,
    parse_nao_resolvido,
    prefixo,
)


def test_ids():
    assert prefixo("bcb:resolucao-bcb:520") == "bcb"
    assert prefixo("lei:4595-1964") == "lei"
    assert prefixo("ext:resolucao-cfc:607-1985") == "ext"
    for bad in ("resolucao-bcb-520", "xyz:1", "bcb:a b"):
        with pytest.raises(ValueError):
            prefixo(bad)


def test_real_edge():
    a = ArestaRow.model_validate(
        {"de": "bcb:resolucao-bcb:589", "para": "bcb:resolucao-bcb:520", "relacao": "altera",
         "desde": "2026-10-01", "fonte": "atualizacoes+referencias"}
    )  # fmt: skip
    assert a.relacao is Relacao.ALTERA and a.relacao.tipo_neo4j == "ALTERA"
    assert str(a.desde) == "2026-10-01"


def test_unknown_relation_or_fonte_fails():
    base = {"de": "bcb:circular:1", "para": "bcb:circular:2", "relacao": "cita", "desde": None, "fonte": "referencias"}
    with pytest.raises(ValidationError):
        ArestaRow.model_validate(base | {"relacao": "substitui"})
    with pytest.raises(ValidationError, match="unknown edge fonte"):
        ArestaRow.model_validate(base | {"fonte": "referencias+outra"})


def test_estado_path_must_be_relative_markdown():
    ok = {"id": "bcb:circular:1", "caminho": "circulares/1965/circular-0001.md", "estado": "revogada", "por": []}
    EstadoRow.model_validate(ok)
    for bad in ("/etc/passwd.md", "circulares/../x.md", "circulares/1965/circular-0001.txt"):
        with pytest.raises(ValidationError):
            EstadoRow.model_validate(ok | {"caminho": bad})


def test_nao_resolvido_shapes():
    alvo = parse_nao_resolvido(
        {"id": "bcb:carta-circular:11283", "arestas": 1, "em": "bcb:circular:925", "campo": "normas_vinculadas"}
    )
    padrao = parse_nao_resolvido(
        {"campo": "referencias", "padrao": "Cita MCR N", "trechos": 144, "em": "bcb:carta-circular:1001",
         "exemplo": "Cita MCR 2-2-20."}
    )  # fmt: skip
    assert isinstance(alvo, NaoResolvidoAlvo)
    assert isinstance(padrao, NaoResolvidoPadrao)
