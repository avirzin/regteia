"""What `query` returns. Every top-level result carries the disclaimer (`aviso`), and every norm its `estado` and
official source (`fonte_url`)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field
from regteia_schema import Estado
from regteia_schema.env import AVISO

Direcao = Literal["saida", "entrada"]


class NormaResumo(BaseModel):
    id: str
    externo: bool
    acervo: str | None = None
    titulo: str | None = None
    tipo: str | None = None
    orgao: str | None = None
    data: date | None = None
    estado: Estado | None = None  # None only for stubs (norms outside our corpora)
    ementa: str | None = None
    fonte_url: str | None = None  # official source: always shown first
    url_arquivo: str | None = None  # exact upstream file version
    url_externa: str | None = None  # where upstream says a stub lives
    versao_texto: str | None = None
    ocr: bool | None = None
    cancelada: bool | None = None

    @property
    def situacao(self) -> str:
        if self.externo:
            return "FORA DO ACERVO"
        return {"vigente": "VIGENTE", "alterada": "VIGENTE, ALTERADA", "revogada": "REVOGADA"}[self.estado]

    @property
    def rotulo(self) -> str:
        return self.titulo or self.id


class Vizinho(BaseModel):
    norma: NormaResumo
    desde: date | None = None
    fonte: str | None = None


class GrupoRelacoes(BaseModel):
    direcao: Direcao  # saida: this norm -> other; entrada: other -> this norm
    tipo: str  # REVOGA, ALTERA, ...
    total: int
    itens: list[Vizinho]  # most recent first, capped


class DispositivoResumo(BaseModel):
    id: str
    tipo: str  # preambulo | artigo | item | anexo | texto
    rotulo: str
    revogado: bool = False
    contexto: str | None = None


class NormaDetalhe(BaseModel):
    norma: NormaResumo
    relacoes: list[GrupoRelacoes]
    notas: list[str]  # caveats the reader must see (revoked, consolidated text, OCR, future amendments...)
    divisao: str | None = None  # artigos | itens | texto | vazio; None for norms outside the corpus
    sumario: list[DispositivoResumo] = Field(default_factory=list)  # the norm's Dispositivos, in order
    aviso: str = AVISO


class DispositivoDetalhe(BaseModel):
    norma: NormaResumo
    dispositivo: DispositivoResumo
    texto: str  # latest published wording (struck-through parts removed)
    redacoes_anteriores: list[str] = Field(default_factory=list)  # superseded wording, struck through upstream
    anterior: DispositivoResumo | None = None
    proximo: DispositivoResumo | None = None
    notas: list[str]
    aviso: str = AVISO


class Trecho(BaseModel):
    """A Dispositivo that matched a search, with a short excerpt around the match."""

    dispositivo: DispositivoResumo
    trecho: str
    score: float


class ItemBusca(BaseModel):
    norma: NormaResumo
    score: float
    trechos: list[Trecho] = Field(default_factory=list)  # best-matching Dispositivos; empty for title/ementa hits


class ResultadoBusca(BaseModel):
    consulta: str
    itens: list[ItemBusca]
    notas: list[str] = Field(default_factory=list)
    aviso: str = AVISO


class Aresta(BaseModel):
    de: str
    para: str
    tipo: str
    desde: date | None = None
    fonte: str | None = None


class NoSubgrafo(BaseModel):
    norma: NormaResumo
    distancia: int


class Subgrafo(BaseModel):
    origem: str
    direcao: Literal["saida", "entrada", "ambas"]
    tipos: list[str]
    profundidade: int
    nos: list[NoSubgrafo]
    arestas: list[Aresta]
    truncado: bool  # hit `limite`: there is more
    aviso: str = AVISO


class Ingestao(BaseModel):
    fonte: str
    sha: str | None = None
    em: datetime | None = None
    arquivos: int | None = None
    modo: str | None = None


class SerieContagem(BaseModel):
    acervo: str
    serie: str
    orgao: str
    total: int
    vigente: int = 0
    alterada: int = 0
    revogada: int = 0


class DecadaContagem(BaseModel):
    decada: int
    orgao: str
    n: int


class ArestaContagem(BaseModel):
    relacao: str
    fonte: str | None
    upstream: str | None
    n: int
    com_desde: int


class NaoResolvidoContagem(BaseModel):
    upstream: str
    tipo: str  # alvo | padrao
    campo: str
    n: int
    ocorrencias: int


class DispositivoContagem(BaseModel):
    acervo: str
    serie: str
    divisao: str  # artigos | itens | texto | vazio (or "?" before the first split)
    normas: int
    dispositivos: int
    artigos: int
    revogados: int
    com_redacao_anterior: int


class Estatisticas(BaseModel):
    normas: int  # file-backed
    stubs: int  # edge endpoints outside our corpora
    arestas: int
    nao_resolvidos: int
    ocr: int
    por_estado: dict[str, int]
    por_orgao: dict[str, dict[str, int]]  # orgao -> estado -> n
    por_serie: list[SerieContagem]
    por_decada: list[DecadaContagem]
    arestas_por_relacao: dict[str, int]
    arestas_por_fonte: dict[str, int]
    arestas_com_desde: int
    arestas_detalhe: list[ArestaContagem]
    stubs_por_prefixo: dict[str, int]
    nao_resolvidos_detalhe: list[NaoResolvidoContagem]
    dispositivos: int
    dispositivos_por_tipo: dict[str, int]
    normas_por_divisao: dict[str, int]  # how many norms were split by articles, items, kept whole, or had no text
    dispositivos_revogados: int
    dispositivos_com_redacao_anterior: int
    dispositivos_detalhe: list[DispositivoContagem]
    falhas_atualizacoes: int | None  # None until the `atualizacoes` parser exists (roadmap step 7)
    ingestoes: list[Ingestao]
    aviso: str = AVISO
