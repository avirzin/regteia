"""The only code in Regteia that writes to Neo4j. Batched, idempotent MERGEs; every query is a .cypher file here."""

import logging
from collections.abc import Iterable, Sequence
from functools import cache
from pathlib import Path
from typing import Any

from neo4j import Driver, ManagedTransaction
from regteia_schema import EXTERNAL_PREFIX, FEDERAL_PREFIXES, NaoResolvidoAlvo, prefixo

from ..parse import atualizacoes, citacoes_texto, dispositivos
from ..sources.normas_grafo import Plano

log = logging.getLogger(__name__)
BATCH = 5_000
TEXTO_POR_LOTE = 8_000_000  # characters of Dispositivo text per write transaction
_DIR = Path(__file__).parent


@cache
def cypher(name: str) -> str:
    return (_DIR / f"{name}.cypher").read_text(encoding="utf-8")


class LoadError(RuntimeError):
    pass


def _batches(rows: Sequence[Any], size: int = BATCH) -> Iterable[Sequence[Any]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def _count(tx: ManagedTransaction, query: str, **params: Any) -> int:
    rec = tx.run(query, **params).single()
    return int(rec["n"]) if rec else 0


def _write(driver: Driver, name: str, rows: Sequence[dict] | None = None, **params: Any) -> int:
    """Run a .cypher file, in batches if `rows` is given. Return the summed `n` it reports."""
    query = cypher(name)
    if rows is None:
        return driver.execute_query(query, params, routing_="w").records[0]["n"]
    total = 0
    with driver.session() as s:
        for batch in _batches(rows):
            total += s.execute_write(_count, query, rows=list(batch), **params)
    return total


def _expect(name: str, got: int, want: int) -> None:
    if got != want:
        raise LoadError(f"{name}: expected {want} rows to be written, got {got}")


def ultima(driver: Driver, fonte: str) -> tuple[str | None, tuple[int | None, ...]]:
    """(last loaded SHA, (splitter, atualizacoes parser, citation extractor) versions) for an upstream; Nones if
    never loaded."""
    recs = driver.execute_query(cypher("ingestao_get"), {"fonte": fonte}, routing_="r").records
    if not recs:
        return None, (None, None, None)
    r = recs[0]
    return r["sha"], (r["divisao"], r["atualizacoes"], r["citacoes"])


def versoes() -> tuple[int, ...]:
    """The current (splitter, atualizacoes parser, citation extractor) versions, as `ultima` returns them."""
    return dispositivos.VERSAO, atualizacoes.VERSAO, citacoes_texto.VERSAO


def _entradas(norma: str, leituras: list[atualizacoes.Leitura]) -> tuple[list[dict], list[dict]]:
    """Rows for atualizacoes_create (one per entry) and atualizacoes_alteram (one per matched target)."""
    entradas, alteram = [], []
    for k, x in enumerate(leituras):
        entradas.append(
            {
                "norma": norma,
                "ordem": k,
                "texto": x.texto,
                "de": x.de,
                "resultado": x.resultado,
                "motivo": x.motivo,
                # Neo4j lists can't hold nulls: no date is ""
                "ausentes": list(x.ausentes) or None,
                "ausentes_tipo": [a.tipo for a in x.ausentes_alvos] or None,
                "ausentes_desde": [str(a.a_partir_de or "") for a in x.ausentes_alvos] or None,
                "ausentes_detalhe": [a.detalhe or "" for a in x.ausentes_alvos] or None,
            }
        )
        for a in x.alvos:
            alteram.append(
                {
                    "de": x.de,
                    "acervo": prefixo(x.de) if x.de else None,
                    "dispositivo": f"{norma}#{a.chave}",
                    "tipo": a.tipo,
                    "a_partir_de": a.a_partir_de.isoformat() if a.a_partir_de else None,
                    "detalhe": a.detalhe,
                    "entrada": k,
                }
            )
    return entradas, alteram


def _citacoes(citacoes: dict[str, list[str]]) -> list[dict]:
    """Rows for citacoes_create, one per (Dispositivo, cited norm)."""
    externos = FEDERAL_PREFIXES | {EXTERNAL_PREFIX}
    return [
        {"dispositivo": d, "alvo": a, "ordem": k, "acervo": prefixo(a), "externo": prefixo(a) in externos}
        for d, alvos in citacoes.items()
        for k, a in enumerate(alvos)
    ]


def _dispositivos(driver: Driver, plano: Plano, run: str) -> dict[str, int]:
    """Split every planned norm, write its Dispositivos, then its `atualizacoes` (entries and article-level ALTERA
    edges) and the citations in its text, in transactions bounded by text size. A norm's entries and citations are
    replaced whole each time it is read."""
    stats = {
        "dispositivos": 0,
        "dispositivos_removidos": 0,
        "atualizacoes": 0,
        "alteracoes_dispositivo": 0,
        "citacoes_texto": 0,
    }
    lote: list[dict] = []
    entradas: list[dict] = []
    alteram: list[dict] = []
    citam: list[dict] = []
    tamanho = 0

    def gravar() -> None:
        nonlocal lote, entradas, alteram, citam, tamanho
        if not lote:
            return
        esperado = sum(len(r["itens"]) for r in lote)
        normas = [r["norma"] for r in lote]
        with driver.session() as s:
            n = s.execute_write(_count, cypher("dispositivos_upsert"), rows=lote, run=run)
            _expect("dispositivos_upsert", n, esperado)
            stats["dispositivos"] += n
            stats["dispositivos_removidos"] += s.execute_write(
                _count, cypher("dispositivos_prune"), normas=normas, run=run
            )
            s.execute_write(_count, cypher("atualizacoes_clear"), normas=normas)
            for parte in _batches(entradas):
                n = s.execute_write(_count, cypher("atualizacoes_create"), rows=list(parte), run=run)
                _expect("atualizacoes_create", n, len(parte))
                stats["atualizacoes"] += n
            for parte in _batches(alteram):
                n = s.execute_write(_count, cypher("atualizacoes_alteram"), rows=list(parte))
                _expect("atualizacoes_alteram (a target Dispositivo is missing)", n, len(parte))
                stats["alteracoes_dispositivo"] += n
            s.execute_write(_count, cypher("citacoes_clear"), normas=normas)
            for parte in _batches(citam):
                n = s.execute_write(_count, cypher("citacoes_create"), rows=list(parte))
                _expect("citacoes_create (a citing Dispositivo is missing)", n, len(parte))
                stats["citacoes_texto"] += n
        lote, entradas, alteram, citam, tamanho = [], [], [], [], 0

    for t in plano.textos():
        itens = []
        for x in t.divisao.dispositivos:
            row = x.model_dump(exclude={"norma"})
            row["redacoes_anteriores"] = list(x.redacoes_anteriores) or None
            itens.append(row)
            tamanho += len(x.texto) + sum(map(len, x.redacoes_anteriores))
        lote.append({"norma": t.norma, "divisao": t.divisao.metodo, "itens": itens})
        e, a = _entradas(t.norma, t.atualizacoes)
        entradas += e
        alteram += a
        citam += _citacoes(t.citacoes)
        if tamanho >= TEXTO_POR_LOTE or len(lote) >= 1_000:
            gravar()
    gravar()
    return stats


def aplicar(driver: Driver, plano: Plano, run: str) -> dict[str, int]:
    """Write one upstream's plan. Safe to re-run: a failed run is repaired by the next one."""
    up = plano.upstream
    stats: dict[str, int] = {}

    rows = [n.model_dump() for n in plano.normas]
    stats["normas"] = _write(driver, "normas_upsert", rows)
    _expect("normas_upsert", stats["normas"], len(rows))
    stats |= _dispositivos(driver, plano, run)

    if plano.estados is not None:
        rows = [{"id": e.id, "estado": e.estado.value, "caminho": e.caminho, "por": e.por} for e in plano.estados]
        n = _write(driver, "estados_set", rows)
        _expect("estados_set (norms in estado.jsonl missing from the graph)", n, len(rows))
        stats["normas_removidas"] = _write(driver, "normas_demote", upstream=up, vivos=sorted(plano.ids_vivos))

    if plano.arestas is not None:
        endpoints = {a.de for a in plano.arestas} | {a.para for a in plano.arestas}
        _write(driver, "stubs_merge", [{"id": i, "acervo": prefixo(i)} for i in sorted(endpoints)])
        rows = [
            {"de": a.de, "para": a.para, "relacao": a.relacao.value, "desde": a.desde, "fonte": a.fonte}
            for a in plano.arestas
        ]
        stats["arestas"] = _write(driver, "arestas_merge", rows, upstream=up, run=run)
        _expect("arestas_merge", stats["arestas"], len(rows))
        stats["arestas_removidas"] = _write(driver, "arestas_prune", upstream=up, run=run)

    if plano.externos is not None:
        rows = [{"id": e.id, "acervo": prefixo(e.id), "url": e.url} for e in plano.externos]
        stats["externos"] = _write(driver, "externos_set", rows)

    if plano.nao_resolvidos is not None:
        _write(driver, "nao_resolvidos_clear", upstream=up)
        rows = [
            {"tipo": "alvo" if isinstance(x, NaoResolvidoAlvo) else "padrao", **x.model_dump()}
            for x in plano.nao_resolvidos
        ]
        stats["nao_resolvidos"] = _write(driver, "nao_resolvidos_create", rows, upstream=up)

    stats["citacoes_ligadas"] = _write(driver, "citacoes_pendentes")
    stats["stubs_removidos"] = _write(driver, "stubs_prune")
    return stats


def registrar(driver: Driver, plano: Plano) -> None:
    params = {
        "fonte": plano.upstream,
        "sha": plano.sha,
        "arquivos": plano.arquivos,
        "modo": "full" if plano.full else "incremental",
        "divisao": dispositivos.VERSAO,
        "atualizacoes": atualizacoes.VERSAO,
        "citacoes": citacoes_texto.VERSAO,
    }
    driver.execute_query(cypher("ingestao_set"), params, routing_="w")
