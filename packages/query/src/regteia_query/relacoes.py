"""relacoes: multi-hop traversal from a norm, one breadth-first hop per query (bounded, no path explosion)."""

from typing import Literal

from regteia_schema import Relacao

from .db import Leitor
from .modelos import Aresta, NormaResumo, NoSubgrafo, Subgrafo
from .normas import resolver

TODOS = [r.tipo_neo4j for r in Relacao]
PROFUNDIDADE_MAX = 4
LIMITE_MAX = 2_000


def relacoes(
    db: Leitor,
    ref: str,
    *,
    tipos: list[str] | None = None,
    direcao: Literal["saida", "entrada", "ambas"] = "saida",
    profundidade: int = 1,
    limite: int = 200,
    incluir_comunicados: bool = False,
) -> Subgrafo:
    """Norms reachable from `ref` within `profundidade` hops over `tipos` (default: all), up to `limite` norms.

    saida: what `ref` revokes/amends/cites/... (and what those do, for depth > 1). entrada: what points at `ref`.
    """
    tipos = [t.upper() for t in (tipos or TODOS)]
    invalidos = sorted(set(tipos) - set(TODOS))
    if invalidos:
        raise ValueError(f"tipos de relação desconhecidos: {invalidos}. Válidos: {TODOS}")
    if not 1 <= profundidade <= PROFUNDIDADE_MAX:
        raise ValueError(f"profundidade deve estar entre 1 e {PROFUNDIDADE_MAX}")
    if direcao not in ("saida", "entrada", "ambas"):
        raise ValueError("direcao deve ser saida, entrada ou ambas")
    limite = max(1, min(limite, LIMITE_MAX))

    origem = resolver(db, ref)
    distancia = {origem.id: 0}
    arestas: dict[tuple[str, str, str], Aresta] = {}
    consultas = ["relacoes_saida", "relacoes_entrada"] if direcao == "ambas" else [f"relacoes_{direcao}"]
    fronteira = [origem.id]
    truncado = False

    for d in range(1, profundidade + 1):
        params = {"ids": fronteira, "tipos": tipos, "comunicados": incluir_comunicados, "limite": limite * 5}
        resultados = db.ler_varios([(c, params) for c in consultas])
        proxima: list[str] = []
        for rows in resultados:
            if len(rows) == params["limite"]:
                truncado = True
            for r in rows:
                v = r["vizinho"]
                if v not in distancia:
                    if len(distancia) >= limite:
                        truncado = True
                        continue
                    distancia[v] = d
                    proxima.append(v)
                arestas.setdefault((r["de"], r["para"], r["tipo"]), Aresta.model_validate(r))
        fronteira = proxima
        if not fronteira:
            break

    normas = {r["n"]["id"]: NormaResumo.model_validate(r["n"]) for r in db.ler("normas_por_id", ids=list(distancia))}
    nos = sorted(
        (NoSubgrafo(norma=normas[i], distancia=dist) for i, dist in distancia.items()),
        key=lambda n: (n.distancia, -(n.norma.data.toordinal() if n.norma.data else 0), n.norma.id),
    )
    return Subgrafo(
        origem=origem.id,
        direcao=direcao,
        tipos=tipos,
        profundidade=profundidade,
        nos=nos,
        arestas=sorted(arestas.values(), key=lambda a: (a.de, a.para, a.tipo)),
        truncado=truncado,
    )
