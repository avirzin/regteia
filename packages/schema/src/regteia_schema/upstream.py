"""Records as they appear in the upstream normas-bcb / normas-cvm repos.

Upstream publishes no schema, so these models *are* our understanding of it. They forbid unknown fields on purpose:
if upstream adds or renames something, ingest must fail loudly instead of silently dropping data.
"""

from datetime import date
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, field_validator

from .enums import Estado, Relacao
from .ids import validate_id

NormaId = Annotated[str, AfterValidator(validate_id)]

#: Frontmatter fields upstream uses as the origin of an edge (`fonte`), possibly joined with "+".
FONTES_ARESTA = frozenset({"referencias", "atualizacoes", "normas_vinculadas", "numero", "notas", "revogada_por"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Frontmatter(_Strict):
    """The `---` header of one norm file (both corpora)."""

    # always present
    titulo: str
    orgao: str
    tipo: str
    numero: str
    data: date
    revogada: bool
    versao_texto: str
    fonte: str
    baixado_em: date
    # sometimes present
    ementa: str | None = None
    responsavel: str | None = None
    versao_normativo: str | None = None
    publicacao: str | None = None
    atualizacoes: list[str] | None = None
    normas_vinculadas: list[str] | None = None
    referencias: list[str] | None = None
    cancelada: bool = False  # BCB only
    # from PDF
    arquivo: str | None = None
    sha256_arquivo: str | None = None
    ocr: bool = False
    # CVM only
    notas: str | None = None
    revogada_por: str | None = None
    temas: list[str] | None = None


class EstadoRow(_Strict):
    """grafo/estado.jsonl: one line per norm file in the repo. The canonical id -> path map."""

    id: NormaId
    caminho: str
    estado: Estado
    por: list[NormaId]

    @field_validator("caminho")
    @classmethod
    def _caminho(cls, v: str) -> str:
        if not v.endswith(".md") or v.startswith(("/", ".")) or ".." in v.split("/"):
            raise ValueError(f"unexpected norm path: {v!r}")
        return v


class ArestaRow(_Strict):
    """grafo/arestas.jsonl: one norm-to-norm relation."""

    de: NormaId
    para: NormaId
    relacao: Relacao
    desde: date | None
    fonte: str

    @field_validator("fonte")
    @classmethod
    def _fonte(cls, v: str) -> str:
        unknown = set(v.split("+")) - FONTES_ARESTA
        if unknown:
            raise ValueError(f"unknown edge fonte {sorted(unknown)} in {v!r}")
        return v


class ExternoRow(_Strict):
    """grafo/externos.jsonl: a norm referenced here that lives in another repo (or in ctresb/leis)."""

    id: NormaId
    url: str


class NaoResolvidoAlvo(_Strict):
    """grafo/nao_resolvidos.jsonl, shape 1: a reference parsed into an id that matches no known norm."""

    id: NormaId
    arestas: int
    em: NormaId
    campo: str


class NaoResolvidoPadrao(_Strict):
    """grafo/nao_resolvidos.jsonl, shape 2: a reference pattern upstream could not parse at all."""

    padrao: str
    trechos: int
    em: NormaId
    campo: str
    exemplo: str


def parse_nao_resolvido(obj: dict) -> NaoResolvidoAlvo | NaoResolvidoPadrao:
    if "padrao" in obj:
        return NaoResolvidoPadrao.model_validate(obj)
    return NaoResolvidoAlvo.model_validate(obj)
