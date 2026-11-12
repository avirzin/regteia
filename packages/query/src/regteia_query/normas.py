"""norma, dispositivo, buscar, panorama."""

import re
from datetime import date

from .db import Leitor
from .modelos import (
    DispositivoDetalhe,
    DispositivoResumo,
    GrupoRelacoes,
    ItemBusca,
    NormaDetalhe,
    NormaResumo,
    ResultadoBusca,
    Trecho,
)
from .resolver import candidatos, escapar_lucene, separar_dispositivo
from .trechos import trecho

PESO_COMUNICADO = 0.2  # comunicados are mostly auction notices: down-ranked, never deleted
TRECHOS_POR_NORMA = 3
TEXTO_MAX = 60_000  # characters of a matched Dispositivo read back to cut its excerpt
NOTA_BUSCA = (
    "A busca cobre títulos, ementas e o texto dos dispositivos na redação mais recente publicada "
    "(sem as redações anteriores riscadas no portal)."
)
_A_PARTIR_DE = re.compile(r"a partir de (\d{1,2})[º°o]?/(\d{1,2})/(\d{4})")


class NormaNaoEncontrada(LookupError):
    def __init__(self, ref: str, sugestoes: list[tuple[str, str]], oque: str = "norma não encontrada"):
        self.ref = ref
        self.sugestoes = sugestoes  # (id, titulo)
        msg = f"{oque}: {ref!r}"
        if sugestoes:
            msg += ". Talvez: " + "; ".join(f"{t} ({i})" for i, t in sugestoes)
        super().__init__(msg)


class DispositivoNaoEncontrado(NormaNaoEncontrada):
    """The norm exists but not this Dispositivo. `sugestoes` lists the norm's Dispositivos nearest to it."""

    def __init__(self, ref: str, sugestoes: list[tuple[str, str]]):
        super().__init__(ref, sugestoes, oque="dispositivo não encontrado")


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
    """One norm: status, official source, direct relations (both directions) grouped by type, and its Dispositivos
    (table of contents)."""
    ref_norma, chave = separar_dispositivo(ref)
    resumo = resolver(db, ref_norma if chave else ref)
    rows, sumario = db.ler_varios(
        [("norma_vizinhos", {"id": resumo.id, "limite": limite}), ("norma_sumario", {"id": resumo.id})]
    )
    grupos = [GrupoRelacoes.model_validate(r) for r in rows]
    s = sumario[0] if sumario else {"divisao": None, "sumario": []}
    return NormaDetalhe(
        norma=resumo,
        relacoes=grupos,
        notas=_notas(resumo, grupos, hoje or date.today()),
        divisao=s["divisao"],
        sumario=[DispositivoResumo.model_validate(d) for d in s["sumario"]],
    )


def _datas_futuras(texto: str, hoje: date) -> list[date]:
    out = set()
    for d, m, a in _A_PARTIR_DE.findall(texto):
        try:
            quando = date(int(a), int(m), int(d))
        except ValueError:
            continue
        if quando > hoje:
            out.add(quando)
    return sorted(out)


def dispositivo(db: Leitor, ref: str, *, hoje: date | None = None) -> DispositivoDetalhe:
    """One Dispositivo: "Resolução BCB 520, art. 88", "art. 88 da Resolução BCB 520", "bcb:resolucao-bcb:520#art-88".

    Its text is the latest wording the portal publishes (consolidated, struck-through wording removed). Notes say
    when the norm or the Dispositivo is revoked and when part of the text only applies from a future date."""
    hoje = hoje or date.today()
    ref_norma, chave = separar_dispositivo(ref)
    if chave is None:
        raise ValueError(
            f"indique o dispositivo em {ref!r}: por exemplo 'Resolução BCB 520, art. 88' ou "
            "'bcb:resolucao-bcb:520#art-88'"
        )
    n = resolver(db, ref_norma)
    rows = db.ler("dispositivo", norma=n.id, id=f"{n.id}#{chave}")
    if not rows:
        sumario = db.ler("norma_sumario", id=n.id)
        itens = sumario[0]["sumario"] if sumario else []
        raise DispositivoNaoEncontrado(f"{n.id}#{chave}", _proximos(chave, itens))
    r = rows[0]
    d = r["d"]
    grupos = [GrupoRelacoes.model_validate(x) for x in db.ler("norma_vizinhos", id=n.id, limite=50)]
    notas = _notas(n, grupos, hoje)
    if d["revogado"]:
        notas.insert(0, "DISPOSITIVO REVOGADO: não está em vigor.")
    if d["tipo"] == "texto":
        notas.append("Norma sem artigos reconhecíveis: este é o texto integral.")
    anteriores = d.get("redacoes_anteriores") or []
    if anteriores:
        notas.append(
            f"O texto é a redação mais recente publicada no portal; {len(anteriores)} trecho(s) com redação anterior "
            "(riscados no portal) estão em redacoes_anteriores."
        )
    for quando in _datas_futuras(d["texto"], hoje):
        notas.append(f"Parte deste texto só vale a partir de {quando:%d/%m/%Y} (vigência futura: ainda não se aplica).")
    return DispositivoDetalhe(
        norma=n,
        dispositivo=DispositivoResumo.model_validate(d),
        texto=d["texto"],
        redacoes_anteriores=anteriores,
        anterior=DispositivoResumo.model_validate(r["anterior"]) if r["anterior"] else None,
        proximo=DispositivoResumo.model_validate(r["proximo"]) if r["proximo"] else None,
        notas=notas,
    )


def _proximos(chave: str, itens: list[dict], n: int = 5) -> list[tuple[str, str]]:
    """Dispositivos of the norm nearest to the requested key (same annex, nearest number), for suggestions."""
    alvo = re.search(r"(\d+)", chave.rsplit("/", 1)[-1])
    prefixo = chave.rsplit("/", 1)[0] + "/" if "/" in chave else ""

    def distancia(item: dict) -> tuple[int, int]:
        k = item["id"].split("#", 1)[1]
        mesmo = (k.rsplit("/", 1)[0] + "/" if "/" in k else "") == prefixo
        num = re.search(r"(\d+)", k.rsplit("/", 1)[-1])
        dn = abs(int(num[1]) - int(alvo[1])) if num and alvo else 10_000
        return (0 if mesmo else 1, dn)

    return [(i["id"], i["rotulo"]) for i in sorted(itens, key=distancia)[:n]]


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
        return ResultadoBusca(consulta=texto, itens=[], notas=[NOTA_BUSCA])
    rows = _buscar(db, q, limite, incluir_revogadas, 1.0 if incluir_comunicados else PESO_COMUNICADO)
    return ResultadoBusca(consulta=texto, itens=[_item(r, texto) for r in rows], notas=[NOTA_BUSCA])


def _buscar(db: Leitor, q: str, limite: int, incluir_revogadas: bool, peso_comunicado: float) -> list[dict]:
    return db.ler(
        "buscar",
        q=q,
        candidatos=max(limite * 25, 500),
        limite=limite,
        incluir_revogadas=incluir_revogadas,
        peso_comunicado=peso_comunicado,
        por_norma=TRECHOS_POR_NORMA,
        texto_max=TEXTO_MAX,
    )


def _item(r: dict, consulta: str) -> ItemBusca:
    trechos = [
        Trecho(dispositivo=DispositivoResumo.model_validate(t), trecho=trecho(t["texto"], consulta), score=t["score"])
        for t in r["trechos"]
    ]
    return ItemBusca(norma=NormaResumo.model_validate(r["n"]), score=r["score"], trechos=trechos)


def panorama(db: Leitor, tema: str, *, limite: int = 30) -> ResultadoBusca:
    """Norms not revoked on a topic, comunicados and out-of-corpus norms excluded."""
    q = escapar_lucene(tema)
    if not q:
        return ResultadoBusca(consulta=tema, itens=[], notas=[NOTA_BUSCA])
    rows = _buscar(db, q, limite, False, 0.0)
    itens = [_item(r, tema) for r in rows if r["score"] > 0 and not r["n"]["externo"]]
    notas = [
        NOTA_BUSCA,
        "Inclui normas vigentes e alteradas (estado atual). Revogadas e comunicados ficam de fora.",
    ]
    return ResultadoBusca(consulta=tema, itens=itens, notas=notas)
