"""What `query` returns. Every top-level result carries the disclaimer (`aviso`), and every norm its `estado` and
official source (`fonte_url`)."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from regteia_schema import Estado, nome_federal
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
    estado_por: list[str] = Field(default_factory=list)  # titles of the norms upstream says revoked/amended this one

    @model_validator(mode="after")
    def _nome_dos_stubs(self) -> "NormaResumo":
        # federal acts have no title until ctresb/leis is ingested: name them from the ID ("Lei nº 14.478/2022")
        if self.titulo is None:
            self.titulo = nome_federal(self.id)
        return self

    @property
    def situacao(self) -> str:
        if self.externo:
            return "FORA DO ACERVO"
        return {"vigente": "VIGENTE", "alterada": "VIGENTE, ALTERADA", "revogada": "REVOGADA"}[self.estado]

    @property
    def situacao_detalhada(self) -> str:
        """'REVOGADA por Resolução BCB N° 603', 'VIGENTE, ALTERADA por …', 'VIGENTE'."""
        s = self.situacao
        if self.estado == "revogada" and not self.estado_por:
            return f"{s} (o portal não informa por qual norma)"
        if self.estado in ("revogada", "alterada") and self.estado_por:
            nomes = self.estado_por[:8]
            mais = f" e mais {len(self.estado_por) - 8}" if len(self.estado_por) > 8 else ""
            return f"{s} por {', '.join(nomes)}{mais}"
        return s

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


SituacaoVigencia = Literal["vigente", "revogada", "nao_vigente", "indeterminada"]


class NormaCitada(BaseModel):
    """A norm named in an event: enough to cite it."""

    id: str
    titulo: str | None = None
    data: date | None = None

    @model_validator(mode="after")
    def _nome_dos_stubs(self) -> "NormaCitada":
        if self.titulo is None:
            self.titulo = nome_federal(self.id)
        return self

    @property
    def rotulo(self) -> str:
        return self.titulo or self.id


class EventoVigencia(BaseModel):
    """One event in a norm's or Dispositivo's history, as the graph records it."""

    tipo: Literal["revogacao", "nova_redacao", "inclusao"]
    alcance: Literal["norma", "dispositivo", "parte"]  # parte: only part of the Dispositivo (`detalhe`)
    por: NormaCitada | None = None
    data: date | None = None  # when it takes effect; None: the graph doesn't know
    origem_data: Literal["a_partir_de", "data_da_norma", "desconhecida"]  # a_partir_de: stated in the entry/edge
    aplicado: bool | None = None  # in effect on the date asked (None: date unknown)
    dispositivo: str | None = None  # id
    rotulo: str | None = None
    detalhe: str | None = None  # what inside the Dispositivo: "inciso III", "caput"
    no_texto: bool = True  # False: the Dispositivo is not in the portal's text (e.g. included from a future date)
    entrada: str | None = None  # the upstream `atualizacoes` entry, as written
    fonte: str | None = None  # "atualizacoes", or the REVOGA edge's upstream field(s)


class Vigencia(BaseModel):
    """Whether a norm, or one of its Dispositivos, applied on a date. Status over time, not text over time: `texto`
    is set only when the stored (latest published) wording is the one that applied on that date."""

    ref: str
    data: date
    norma: NormaResumo
    dispositivo: DispositivoResumo | None = None  # None for a norm, or for a Dispositivo missing from the text
    chave: str | None = None  # the Dispositivo asked for ("art-90-a"), even when it is missing from the text
    rotulo: str | None = None  # its label ("Art. 90-A")
    situacao: SituacaoVigencia
    motivo: str  # one sentence: why
    # for a Dispositivo: armazenado (the stored text applied on `data`), desconhecido (changed after `data`: the
    # graph doesn't have the wording of that date), sem_texto (not in force, or not in the portal's text)
    texto_na_data: Literal["armazenado", "desconhecido", "sem_texto"] | None = None
    texto: str | None = None
    eventos: list[EventoVigencia]  # by date; undated last
    notas: list[str]
    aviso: str = AVISO


class Trecho(BaseModel):
    """A Dispositivo that matched a search, with a short excerpt around the match."""

    dispositivo: DispositivoResumo
    trecho: str
    score: float
    texto: str | None = None  # the whole Dispositivo (capped), only when asked for (buscar com_texto)


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


class FalhaAtualizacao(BaseModel):
    """One `atualizacoes` entry the parser could not read (or read only in part): the stats page's report."""

    norma: str
    titulo: str | None = None
    texto: str
    resultado: str  # falha | parcial | ausente
    motivo: str | None = None


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
    atualizacoes: int  # upstream `atualizacoes` entries
    # dispositivos | parcial | ausente (targets not in our split) | norma (whole norm, no detail) | nota | falha
    atualizacoes_por_resultado: dict[str, int]
    falhas_atualizacoes: int
    alteracoes_dispositivo: int  # article-level ALTERA edges
    alteracoes_por_tipo: dict[str, int]  # nova_redacao | inclusao | revogacao
    alteracoes_com_data: int  # with an explicit "a partir de"
    alteracoes_futuras: int  # starting after today
    atualizacoes_falhas: list[FalhaAtualizacao]  # the report (capped)
    ingestoes: list[Ingestao]
    aviso: str = AVISO
