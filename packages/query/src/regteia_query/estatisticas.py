"""estatisticas: corpus coverage and health, computed live from the graph in one read transaction."""

import re
from collections import Counter, defaultdict

from regteia_schema import FEDERAL_PREFIXES

from .db import Leitor
from .modelos import (
    ArestaContagem,
    CategoriaNaoResolvido,
    CitacaoPendente,
    DecadaContagem,
    DispositivoContagem,
    Estatisticas,
    FalhaAtualizacao,
    Ingestao,
    NaoResolvidoAcervo,
    NaoResolvidoCategoria,
    NaoResolvidoContagem,
    SerieContagem,
)

PENDENTES_MAX = 50
EXEMPLOS = 5

# upstream's unresolved patterns that aren't norm references (ADR 0004)
_MANUAL = re.compile(r"\b(MCR|MNI|CNC|RMCCI|MCA|COSIF|SFH|MSI)\b", re.I)  # sections of the BCB's manuals
_CONSTITUICAO = re.compile(r"constitui|\bCF\b|\bADCT\b|emenda constitucional", re.I)
_VOTO = re.compile(r"^\s*voto\b", re.I)


def categoria(tipo: str, id_: str | None, padrao: str | None) -> CategoriaNaoResolvido:
    """What kind of thing one of upstream's unresolved references is. `alvo`: an ID upstream parsed that no norm has;
    `padrao`: text upstream couldn't parse."""
    if tipo == "alvo" and id_:
        prefixo = id_.split(":", 1)[0]
        if prefixo in FEDERAL_PREFIXES:
            return "lei_federal"
        return "outro_orgao" if prefixo == "ext" else "acervo"
    p = padrao or ""
    if _MANUAL.search(p):
        return "manual"
    if _CONSTITUICAO.search(p):
        return "constituicao"
    if _VOTO.search(p):
        return "voto"
    return "outro"


def _classificar(rows: list[dict]) -> tuple[list[NaoResolvidoCategoria], list[NaoResolvidoAcervo]]:
    grupos: dict[CategoriaNaoResolvido, list[dict]] = defaultdict(list)
    for r in rows:
        grupos[categoria(r["tipo"], r["id"], r["padrao"])].append(r)
    categorias = []
    for cat, itens in grupos.items():
        itens.sort(key=lambda r: (-r["ocorrencias"], r["id"] or r["padrao"] or ""))
        categorias.append(
            NaoResolvidoCategoria(
                categoria=cat,
                n=len(itens),
                ocorrencias=sum(r["ocorrencias"] for r in itens),
                exemplos=[r["id"] or r["exemplo"] or r["padrao"] for r in itens[:EXEMPLOS]],
            )
        )
    categorias.sort(key=lambda c: -c.n)
    acervo = sorted(
        (NaoResolvidoAcervo.model_validate(r) for r in grupos.get("acervo", [])), key=lambda x: (x.id, x.em)
    )
    return categorias, acervo


_CONSULTAS = [
    "est_totais",
    "est_por_serie",
    "est_por_decada",
    "est_arestas",
    "est_stubs",
    "est_nao_resolvidos",
    "est_ingestoes",
    "est_dispositivos",
    "est_dispositivos_tipo",
    "est_atualizacoes",
    "est_alteracoes",
    "est_atualizacoes_falhas",
    "est_nao_resolvidos_lista",
    "est_citacoes_texto",
    "est_citacoes_pendentes",
]


def estatisticas(db: Leitor) -> Estatisticas:
    (
        totais, series, decadas, arestas, stubs, nao_res, ingestoes, disp, disp_tipo, atu, alt, falhas,
        nao_res_lista, citacoes, pendentes,
    ) = db.ler_varios([(c, {"limite": PENDENTES_MAX}) for c in _CONSULTAS])  # fmt: skip
    t = totais[0]
    c = citacoes[0]
    categorias, nao_res_acervo = _classificar(nao_res_lista)

    por_estado: Counter[str] = Counter()
    por_orgao: dict[str, Counter[str]] = defaultdict(Counter)
    por_serie: dict[tuple[str, str, str], SerieContagem] = {}
    for r in series:
        por_estado[r["estado"]] += r["n"]
        por_orgao[r["orgao"]][r["estado"]] += r["n"]
        key = (r["acervo"], r["serie"], r["orgao"])
        s = por_serie.setdefault(key, SerieContagem(acervo=r["acervo"], serie=r["serie"], orgao=r["orgao"], total=0))
        s.total += r["n"]
        setattr(s, r["estado"], getattr(s, r["estado"]) + r["n"])

    por_relacao: Counter[str] = Counter()
    por_fonte: Counter[str] = Counter()
    for r in arestas:
        por_relacao[r["relacao"]] += r["n"]
        por_fonte[r["fonte"] or "?"] += r["n"]

    detalhe = [DispositivoContagem.model_validate(r) for r in disp]
    por_divisao: Counter[str] = Counter()
    for d in detalhe:
        por_divisao[d.divisao] += d.normas

    return Estatisticas(
        normas=t["normas"],
        stubs=t["stubs"],
        arestas=t["arestas"],
        nao_resolvidos=t["nao_resolvidos"],
        ocr=t["ocr"],
        por_estado=dict(por_estado),
        por_orgao={k: dict(v) for k, v in sorted(por_orgao.items())},
        por_serie=sorted(por_serie.values(), key=lambda s: (-s.total, s.serie)),
        por_decada=[DecadaContagem.model_validate(r) for r in decadas],
        arestas_por_relacao=dict(por_relacao.most_common()),
        arestas_por_fonte=dict(por_fonte.most_common()),
        arestas_com_desde=sum(r["com_desde"] for r in arestas),
        arestas_detalhe=[ArestaContagem.model_validate(r) for r in arestas],
        stubs_por_prefixo={r["acervo"]: r["n"] for r in stubs},
        nao_resolvidos_detalhe=[NaoResolvidoContagem.model_validate(r) for r in nao_res],
        dispositivos=sum(r["n"] for r in disp_tipo),
        dispositivos_por_tipo={r["tipo"]: r["n"] for r in disp_tipo},
        normas_por_divisao=dict(por_divisao.most_common()),
        dispositivos_revogados=sum(d.revogados for d in detalhe),
        dispositivos_com_redacao_anterior=sum(d.com_redacao_anterior for d in detalhe),
        dispositivos_detalhe=detalhe,
        atualizacoes=sum(r["n"] for r in atu),
        atualizacoes_por_resultado={r["resultado"]: r["n"] for r in atu},
        falhas_atualizacoes=sum(r["n"] for r in atu if r["resultado"] == "falha"),
        alteracoes_dispositivo=sum(r["n"] for r in alt),
        alteracoes_por_tipo={r["tipo"]: r["n"] for r in alt},
        alteracoes_com_data=sum(r["com_data"] for r in alt),
        alteracoes_futuras=sum(r["futuras"] for r in alt),
        atualizacoes_falhas=[FalhaAtualizacao.model_validate(r) for r in falhas],
        nao_resolvidos_por_categoria=categorias,
        nao_resolvidos_acervo=nao_res_acervo,
        citacoes_texto=sum(x["n"] for x in c["por_alvo"]),
        citacoes_texto_por_alvo={x["alvo"]: x["n"] for x in sorted(c["por_alvo"], key=lambda x: -x["n"])},
        citacoes_texto_dispositivos=c["dispositivos"],
        citacoes_texto_pares=c["pares"],
        citacoes_texto_pares_novos=c["pares_novos"],
        citacoes_pendentes=c["pendentes"],
        citacoes_pendentes_lista=[CitacaoPendente.model_validate(r) for r in pendentes],
        ingestoes=[Ingestao.model_validate(r) for r in ingestoes],
    )
