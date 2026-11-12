"""estatisticas: corpus coverage and health, computed live from the graph in one read transaction."""

from collections import Counter, defaultdict

from .db import Leitor
from .modelos import (
    ArestaContagem,
    DecadaContagem,
    Estatisticas,
    Ingestao,
    NaoResolvidoContagem,
    SerieContagem,
)

_CONSULTAS = [
    "est_totais",
    "est_por_serie",
    "est_por_decada",
    "est_arestas",
    "est_stubs",
    "est_nao_resolvidos",
    "est_ingestoes",
]


def estatisticas(db: Leitor) -> Estatisticas:
    totais, series, decadas, arestas, stubs, nao_res, ingestoes = db.ler_varios([(c, {}) for c in _CONSULTAS])
    t = totais[0]

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
        falhas_atualizacoes=None,
        ingestoes=[Ingestao.model_validate(r) for r in ingestoes],
    )
