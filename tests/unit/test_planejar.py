import pytest
from regteia_ingest.config import Upstream
from regteia_ingest.migrate import statements
from regteia_ingest.sources.git import Change
from regteia_ingest.sources.normas_grafo import UpstreamValidationError, is_norm_path, planejar

from tests.conftest import FIXTURES

BCB = Upstream(name="normas-bcb", url="x", ref="main", adapter="normas_grafo", acervo="bcb")


def test_full_plan_from_fixtures():
    p = planejar(FIXTURES / "normas-bcb", BCB, "abc", None)
    assert p.full and len(p.normas) == 14 == len(p.estados)
    assert len(p.arestas) == 52 and len(p.nao_resolvidos) == 2
    n520 = next(n for n in p.normas if n.id == "bcb:resolucao-bcb:520")
    assert n520.estado == "alterada"
    assert n520.fonte_url.startswith("https://www.bcb.gov.br/")
    assert n520.caminho == "resolucoes-bcb/2025/resolucao-bcb-0520.md"
    assert n520.upstream_sha == "abc"


def test_incremental_plan_only_reads_changed_norms():
    changes = [Change("M", "resolucoes-bcb/2025/resolucao-bcb-0520.md"), Change("M", "README.md")]
    p = planejar(FIXTURES / "normas-bcb", BCB, "def", changes)
    assert [n.id for n in p.normas] == ["bcb:resolucao-bcb:520"]
    assert p.arestas is None and p.estados is None  # grafo/ untouched
    p = planejar(FIXTURES / "normas-bcb", BCB, "def", [Change("M", "grafo/arestas.jsonl")])
    assert p.normas == [] and len(p.arestas) == 52


def test_changed_norm_missing_from_estado_fails_loudly():
    with pytest.raises(UpstreamValidationError, match="missing from grafo/estado.jsonl"):
        planejar(FIXTURES / "normas-bcb", BCB, "x", [Change("A", "circulares/2030/circular-9999.md")])


def test_is_norm_path():
    assert is_norm_path("resolucoes-bcb/2025/resolucao-bcb-0520.md")
    for p in ("README.md", "grafo/estado.jsonl", "scripts/x/y.md", "_indice/a/b.md", "a/b.md"):
        assert not is_norm_path(p)


def test_migration_statements():
    text = "// comment; ignored\nCREATE A;\nCREATE B\n  ON X;\n\n"
    assert statements(text) == ["CREATE A", "CREATE B\n  ON X"]
