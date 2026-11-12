"""norma, buscar, panorama."""

from datetime import date

from .db import Leitor
from .modelos import GrupoRelacoes, ItemBusca, NormaDetalhe, NormaResumo, ResultadoBusca
from .resolver import candidatos, escapar_lucene

PESO_COMUNICADO = 0.2  # comunicados are mostly auction notices: down-ranked, never deleted
NOTA_BUSCA_NIVEL_NORMA = (
    "A busca cobre por enquanto títulos e ementas; a busca no texto dos artigos chega com a divisão em dispositivos."
)


class NormaNaoEncontrada(LookupError):
    def __init__(self, ref: str, sugestoes: list[tuple[str, str]]):
        self.ref = ref
        self.sugestoes = sugestoes  # (id, titulo)
        msg = f"norma não encontrada: {ref!r}"
        if sugestoes:
            msg += ". Talvez: " + "; ".join(f"{t} ({i})" for i, t in sugestoes)
        super().__init__(msg)


def resolver(db: Leitor, ref: str) -> NormaResumo:
    """The norm `ref` names (an ID or a name like "Resolução BCB 520"). Raise NormaNaoEncontrada with suggestions."""
    ids = candidatos(ref)
    if ids:
        achadas = {r["n"]["id"]: r["n"] for r in db.ler("normas_por_id", ids=ids)}
        for i in ids:
            if i in achadas:
                return NormaResumo.model_validate(achadas[i])
    q = escapar_lucene(ref)
    sugestoes = [(r["id"], r["titulo"]) for r in db.ler("busca_titulo", q=q, limite=5)] if q else []
    raise NormaNaoEncontrada(ref, sugestoes)


def _notas(n: NormaResumo, grupos: list[GrupoRelacoes], hoje: date) -> list[str]:
    notas = []
    if n.externo:
        notas.append(
            "Norma fora dos acervos carregados: aparece apenas porque outras normas se referem a ela; sem texto."
        )
    elif n.estado == "revogada":
        notas.append("REVOGADA: esta norma não está em vigor.")
    elif n.estado == "alterada":
        notas.append(
            "Alterada: o texto armazenado é o texto consolidado atual do portal, já com as alterações incorporadas."
        )
    if n.cancelada:
        notas.append("Marcada como cancelada no portal do BCB.")
    if n.ocr:
        notas.append("Texto obtido por OCR de um PDF digitalizado: pode conter erros de reconhecimento.")
    if n.versao_texto and "original" in n.versao_texto.lower():
        notas.append(f"Texto em '{n.versao_texto}': pode não refletir alterações posteriores.")
    for g in grupos:
        if g.direcao != "entrada" or g.tipo not in ("ALTERA", "REVOGA", "REVOGA_PARCIAL"):
            continue
        for v in g.itens:
            if v.desde and v.desde > hoje:
                acao = {"ALTERA": "altera", "REVOGA": "revoga", "REVOGA_PARCIAL": "revoga parcialmente"}[g.tipo]
                notas.append(
                    f"{v.norma.rotulo} {acao} esta norma a partir de {v.desde:%d/%m/%Y} (vigência futura: "
                    "ainda não se aplica)."
                )
    return notas


def norma(db: Leitor, ref: str, *, limite: int = 10, hoje: date | None = None) -> NormaDetalhe:
    """One norm: status, official source, and its direct relations (both directions) grouped by type."""
    resumo = resolver(db, ref)
    rows = db.ler("norma_vizinhos", id=resumo.id, limite=limite)
    grupos = [GrupoRelacoes.model_validate(r) for r in rows]
    return NormaDetalhe(norma=resumo, relacoes=grupos, notas=_notas(resumo, grupos, hoje or date.today()))


def buscar(
    db: Leitor,
    texto: str,
    *,
    limite: int = 20,
    incluir_revogadas: bool = True,
    incluir_comunicados: bool = False,
) -> ResultadoBusca:
    """Full-text search (Portuguese analyzer). Comunicados are down-ranked unless `incluir_comunicados`."""
    q = escapar_lucene(texto)
    if not q:
        return ResultadoBusca(consulta=texto, itens=[], notas=[NOTA_BUSCA_NIVEL_NORMA])
    rows = db.ler(
        "buscar",
        q=q,
        candidatos=max(limite * 5, 100),
        limite=limite,
        incluir_revogadas=incluir_revogadas,
        peso_comunicado=1.0 if incluir_comunicados else PESO_COMUNICADO,
    )
    itens = [ItemBusca(norma=NormaResumo.model_validate(r["n"]), score=r["score"]) for r in rows]
    return ResultadoBusca(consulta=texto, itens=itens, notas=[NOTA_BUSCA_NIVEL_NORMA])


def panorama(db: Leitor, tema: str, *, limite: int = 30) -> ResultadoBusca:
    """Norms not revoked on a topic, comunicados and out-of-corpus norms excluded."""
    q = escapar_lucene(tema)
    if not q:
        return ResultadoBusca(consulta=tema, itens=[], notas=[NOTA_BUSCA_NIVEL_NORMA])
    rows = db.ler(
        "buscar", q=q, candidatos=max(limite * 5, 200), limite=limite, incluir_revogadas=False, peso_comunicado=0.0
    )
    itens = [
        ItemBusca(norma=NormaResumo.model_validate(r["n"]), score=r["score"])
        for r in rows
        if r["score"] > 0 and not r["n"]["externo"]
    ]
    notas = [
        NOTA_BUSCA_NIVEL_NORMA,
        "Inclui normas vigentes e alteradas (estado atual). Revogadas e comunicados ficam de fora.",
    ]
    return ResultadoBusca(consulta=tema, itens=itens, notas=notas)
