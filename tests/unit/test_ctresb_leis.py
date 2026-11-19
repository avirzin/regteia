"""ctresb/leis: resolving our federal IDs to files, and reading status.

Real paths and frontmatter values from ctresb/leis@c9f21b4a."""

import pytest
from regteia_ingest.sources.ctresb_leis import estado, resolver
from regteia_schema import LeiFrontmatter

CAMINHOS = [
    "federal/leis-ordinarias/1964/lei-4595-1964-12-31.md",
    "federal/medidas-provisorias/2001/mpv-2200-2-2001-08-24.md",
    "federal/medidas-provisorias/2001/mpv-2158-33-2001-06-28.md",
    "federal/medidas-provisorias/2001/mpv-2158-34-2001-07-27.md",
    "federal/medidas-provisorias/2001/mpv-2158-35-2001-08-24.md",
    "federal/decretos-lei/1986/del-2291-1986-11-21.md",
    "federal/leis-ordinarias/1822/lei-sn-1822-10-14-s2.md",
    "federal/_auditoria/1964/lei-4728-1965-07-14.md",  # work in progress: never read
    "federal/decretos/1965/lei-4728-1965-07-14.md",  # wrong folder for the prefix
]


def test_resolver():
    r = resolver({"lei:4595-1964", "mpv:2200-2-2001", "mpv:2158-2001", "lei:2291-1986", "lei:4728-1965"}, CAMINHOS)
    assert r["lei:4595-1964"].caminho == "federal/leis-ordinarias/1964/lei-4595-1964-12-31.md"
    assert r["mpv:2200-2-2001"].caminho.endswith("mpv-2200-2-2001-08-24.md") and not r["mpv:2200-2-2001"].reedicao
    # an MP cited without its reissue number: the last reissue that year
    assert r["mpv:2158-2001"].caminho.endswith("mpv-2158-35-2001-08-24.md") and r["mpv:2158-2001"].reedicao
    # upstream's "lei:2291-1986" is Decreto-Lei 2.291: not guessed; nor are files outside the prefix's folder
    assert "lei:2291-1986" not in r and "lei:4728-1965" not in r


def _fm(**campos):
    base = {
        "titulo": "Medida Provisória nº 2.196-1 de 28/06/2001",
        "tipo": "Medida Provisória",
        "numero": "2196-1",
        "data": "2001-06-28",
        "versao_texto": "original",
        "urn": "urn:lex:br:federal:medida.provisoria:2001-06-28;2196-1",
        "fonte": "https://normas.leg.br/?urn=urn:lex:br:federal:medida.provisoria:2001-06-28;2196-1",
        "baixado_em": "2026-10-13",
    }
    return LeiFrontmatter.model_validate(base | campos)


@pytest.mark.parametrize(
    "campos, esperado",
    [
        ({"revogada": "false"}, ("vigente", None)),
        ({"revogada": "true"}, ("revogada", None)),
        ({"revogada": "null"}, ("sem_informacao", None)),
        ({"revogada": "false", "situacao": "Reeditada"}, ("revogada", "Reeditada")),
        ({"revogada": "false", "situacao": "Reeditada com alteração"}, ("revogada", "Reeditada com alteração")),
        ({"revogada": "false", "situacao": "Convertida em Lei"}, ("revogada", "Convertida em Lei")),
        ({"revogada": "true", "situacao": "Revogada"}, ("revogada", "Revogada")),
        (
            {"revogada": "false", "situacao": "Em vigor por força do art. 2º da Emenda Constitucional nº 32, de 2001."},
            ("vigente", "Em vigor por força do art. 2º da Emenda Constitucional nº 32, de 2001"),
        ),
        (
            {"revogada": "null", "forca_legal_fonte": '["NotInForce"]'},
            ("revogada", "sem vigência segundo os metadados de normas.leg.br"),
        ),
        ({"revogada": "null", "forca_legal_fonte": "[]"}, ("sem_informacao", None)),
    ],
)
def test_estado(campos, esperado):
    assert estado(_fm(**campos)) == esperado
