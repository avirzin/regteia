"""Graph nodes as Regteia stores them. See docs/graph-model.md."""

from datetime import date
from typing import Literal

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


TipoDispositivo = Literal["preambulo", "artigo", "item", "anexo", "texto"]
Divisao = Literal["artigos", "itens", "texto", "vazio"]  # how a norm's body was split


class Dispositivo(BaseModel):
    """A unit of a norm's text: an article (paragraphs, incisos and alíneas stay inside it), an annex, a top-level
    item of an older norm, the preamble, or the whole text of a norm with no recognizable structure. ADR 0001."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str  # "<norma>#art-88", "#art-90-a", "#anexo-i/art-2", "#item-iii", "#preambulo", "#anexo", "#texto"
    norma: NormaId
    tipo: TipoDispositivo
    rotulo: str  # "Art. 88", "Anexo I, art. 2", "Item III", "Preâmbulo"
    ordem: int  # position in the norm, from 0
    texto: str  # latest published wording, without struck-through parts; may carry future-dated changes
    numero: str | None = None  # "88", "90-A", "III"
    anexo: str | None = None  # annex number for annexes and their articles ("I"; "" if unnumbered)
    contexto: str | None = None  # enclosing headings: "CAPÍTULO II · DAS DEFINIÇÕES › Seção I · …"
    revogado: bool = False
    redacoes_anteriores: tuple[str, ...] = ()  # struck-through (superseded) wording, in document order
