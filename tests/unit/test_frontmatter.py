from datetime import date

import pytest
from pydantic import ValidationError
from regteia_ingest.parse.frontmatter import FrontmatterError, parse_frontmatter, read_frontmatter
from regteia_schema import Frontmatter

from tests.conftest import FIXTURES

RES_520 = FIXTURES / "normas-bcb/resolucoes-bcb/2025/resolucao-bcb-0520.md"


def test_real_header_res_bcb_520():
    fm = read_frontmatter(RES_520)
    assert fm["titulo"] == "Resolução BCB N° 520"
    assert fm["data"] == "2025-11-10"  # raw value, not JSON
    assert fm["revogada"] == "false"
    assert fm["atualizacoes"][1].startswith("Resolução BCB nº 589/2026 - Alteração, a partir de 1º/1/2027")

    model = Frontmatter.model_validate(fm)
    assert model.data == date(2025, 11, 10)
    assert model.revogada is False
    assert model.ocr is False


@pytest.mark.parametrize("path", sorted(FIXTURES.glob("normas-*/*/*/*.md")), ids=lambda p: p.name)
def test_every_fixture_validates(path):
    Frontmatter.model_validate(read_frontmatter(path))


@pytest.mark.parametrize(
    "text, msg",
    [
        ("titulo: x\n", "does not start"),
        ("---\ntitulo x\n---\n", "expected 'key: value'"),
        ('---\ntitulo: "x\n---\n', "invalid JSON"),
        ("---\na: 1\na: 2\n---\n", "duplicate key"),
        ("---\na: 1\n", "not closed"),
    ],
)
def test_parser_is_strict(text, msg):
    with pytest.raises(FrontmatterError, match=msg):
        parse_frontmatter(text.splitlines(keepends=True))


def test_unknown_frontmatter_key_fails_loudly():
    fm = read_frontmatter(RES_520) | {"campo_novo": "x"}
    with pytest.raises(ValidationError, match="campo_novo"):
        Frontmatter.model_validate(fm)
