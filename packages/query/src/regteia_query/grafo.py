"""exportar_grafo: the whole graph, columnar, for the overview visualization."""

import hashlib
from dataclasses import dataclass

from regteia_schema import FEDERAL_PREFIXES, Estado, Relacao

from .db import Leitor

#: Issuing bodies the overview colors by, in legend order.
GRUPOS = ["CMN", "BCB", "CVM", "Lei federal", "Outros"]
ESTADOS = [e.value for e in Estado] + ["externa"]
RELACOES = [r.tipo_neo4j for r in Relacao]


def grupo(acervo: str | None, orgao: str | None) -> str:
    if orgao == "Conselho Monetário Nacional":
        return "CMN"
    if orgao and orgao.startswith("Banco Central do Brasil"):
        return "BCB"
    if orgao == "Comissão de Valores Mobiliários":
        return "CVM"
    if acervo in FEDERAL_PREFIXES:
        return "Lei federal"
    return {"bcb": "BCB", "cvm": "CVM"}.get(acervo or "", "Outros")


@dataclass(frozen=True)
class GrafoExportado:
    """Columnar: node i is ids[i]; edges point at node indices. Small enough to ship whole to the browser."""

    versao: str  # changes whenever the underlying data does
    comunicados: bool
    ids: list[str]
    titulos: list[str | None]
    grupos: list[int]  # index into GRUPOS
    estados: list[int]  # index into ESTADOS
    anos: list[int | None]
    origens: list[int]
    destinos: list[int]
    tipos: list[int]  # index into RELACOES


def _chave(rows: list[dict]) -> str:
    return hashlib.sha256(repr([(r["fonte"], r["sha"], r["em"]) for r in rows]).encode()).hexdigest()[:16]


def versao_dados(db: Leitor) -> str:
    """A short key that changes whenever any ingest records a new load. Cheap: use it to invalidate caches."""
    return _chave(db.ler("versao_dados"))


def exportar_grafo(db: Leitor, *, comunicados: bool = False) -> GrafoExportado:
    versao, nos, arestas = db.ler_varios(
        [
            ("versao_dados", {}),
            ("grafo_nos", {"comunicados": comunicados}),
            ("grafo_arestas", {"comunicados": comunicados}),
        ]
    )

    ligados = {a["de"] for a in arestas} | {a["para"] for a in arestas}
    nos = [n for n in nos if not n["externo"] or n["id"] in ligados]  # stubs only reachable from hidden norms
    indice = {n["id"]: i for i, n in enumerate(nos)}
    arestas = [a for a in arestas if a["de"] in indice and a["para"] in indice]
    rel = {r: i for i, r in enumerate(RELACOES)}
    est = {e: i for i, e in enumerate(ESTADOS)}
    grp = {g: i for i, g in enumerate(GRUPOS)}

    return GrafoExportado(
        versao=_chave(versao),
        comunicados=comunicados,
        ids=[n["id"] for n in nos],
        titulos=[n["titulo"] for n in nos],
        grupos=[grp[grupo(n["acervo"], n["orgao"])] for n in nos],
        estados=[est["externa" if n["externo"] else n["estado"]] for n in nos],
        anos=[n["ano"] for n in nos],
        origens=[indice[a["de"]] for a in arestas],
        destinos=[indice[a["para"]] for a in arestas],
        tipos=[rel[a["tipo"]] for a in arestas],
    )
