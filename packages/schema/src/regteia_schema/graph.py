"""Graph nodes as Regteia stores them. See docs/graph-model.md."""

from datetime import date

from pydantic import BaseModel, ConfigDict

from .enums import Estado
from .upstream import NormaId


class Norma(BaseModel):
    """A norm backed by an upstream file. Stub nodes (edge targets without a file) are not built from this model."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: NormaId
    acervo: str  # "bcb" | "cvm": which corpus the file came from
    orgao: str
    tipo: str
    numero: str
    data: date
    titulo: str
    ementa: str | None
    estado: Estado
    revogada: bool  # frontmatter flag; `estado` (from grafo/estado.jsonl) is authoritative
    cancelada: bool
    fonte_url: str  # official source; always shown first
    caminho: str
    upstream: str  # upstream name in upstreams.toml
    upstream_sha: str  # commit the file was read at
    url_arquivo: str | None  # <upstream url>/blob/<upstream_sha>/<caminho>, for http(s) upstreams
    versao_texto: str
    publicacao: str | None
    responsavel: str | None
    baixado_em: date
    arquivo: str | None
    ocr: bool
    temas: list[str] | None
