"""FastAPI app: /api/* over regteia_query, and the built web app at /. Argument parsing and formatting only."""

import os
import threading
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.staticfiles import StaticFiles
from regteia_query import (
    Leitor,
    NormaNaoEncontrada,
    buscar,
    dispositivo,
    estatisticas,
    exportar_grafo,
    norma,
    panorama,
    relacoes,
    versao_dados,
)
from regteia_query.modelos import DispositivoDetalhe, Estatisticas, NormaDetalhe, ResultadoBusca, Subgrafo
from regteia_query.relacoes import PROFUNDIDADE_MAX

from . import arrow

ARROW = "application/vnd.apache.arrow.stream"


class _GrafoCache:
    """Arrow bytes per `comunicados` flag, rebuilt only when the data version changes (i.e. after an ingest)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._por_flag: dict[bool, tuple[str, bytes, bytes]] = {}

    def get(self, db: Leitor, comunicados: bool) -> tuple[str, bytes, bytes]:
        versao = versao_dados(db)
        with self._lock:
            hit = self._por_flag.get(comunicados)
            if hit and hit[0] == versao:
                return hit
            g = exportar_grafo(db, comunicados=comunicados)
            entry = (g.versao, arrow.nos(g), arrow.arestas(g))
            self._por_flag[comunicados] = entry
            return entry


def create_app(leitor: Callable[[], Leitor] = Leitor.do_ambiente, web_dist: Path | None = None) -> FastAPI:
    state: dict[str, Leitor] = {}
    cache = _GrafoCache()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        state["db"] = leitor()
        yield
        state.pop("db").close()

    app = FastAPI(title="Regteia", docs_url="/api/docs", openapi_url="/api/openapi.json", lifespan=lifespan)

    def db() -> Leitor:
        return state["db"]

    def nao_encontrada(e: NormaNaoEncontrada) -> HTTPException:
        return HTTPException(404, {"erro": str(e), "sugestoes": [{"id": i, "titulo": t} for i, t in e.sugestoes]})

    @app.get("/api/saude")
    def saude() -> dict[str, str]:
        return {"status": "ok", "versao": versao_dados(db())}

    @app.get("/api/estatisticas")
    def get_estatisticas() -> Estatisticas:
        return estatisticas(db())

    @app.get("/api/normas/{ref:path}")
    def get_norma(ref: str, limite: Annotated[int, Query(ge=1, le=100)] = 10) -> NormaDetalhe:
        try:
            return norma(db(), ref, limite=limite)
        except NormaNaoEncontrada as e:
            raise nao_encontrada(e) from None

    @app.get("/api/dispositivos/{ref:path}")
    def get_dispositivo(ref: str) -> DispositivoDetalhe:
        """One article, annex or item: `bcb:resolucao-bcb:520#art-88` (`#` as %23) or `Res. BCB 520, art. 88`."""
        try:
            return dispositivo(db(), ref)
        except NormaNaoEncontrada as e:
            raise nao_encontrada(e) from None
        except ValueError as e:
            raise HTTPException(422, {"erro": str(e)}) from None

    @app.get("/api/buscar")
    def get_buscar(
        q: str,
        limite: Annotated[int, Query(ge=1, le=200)] = 20,
        revogadas: bool = True,
        comunicados: bool = False,
    ) -> ResultadoBusca:
        return buscar(db(), q, limite=limite, incluir_revogadas=revogadas, incluir_comunicados=comunicados)

    @app.get("/api/panorama")
    def get_panorama(tema: str, limite: Annotated[int, Query(ge=1, le=200)] = 30) -> ResultadoBusca:
        return panorama(db(), tema, limite=limite)

    @app.get("/api/relacoes")
    def get_relacoes(
        ref: str,
        tipo: Annotated[list[str] | None, Query()] = None,
        direcao: Literal["saida", "entrada", "ambas"] = "saida",
        profundidade: Annotated[int, Query(ge=1, le=PROFUNDIDADE_MAX)] = 1,
        limite: Annotated[int, Query(ge=1, le=2000)] = 200,
        comunicados: bool = False,
    ) -> Subgrafo:
        try:
            return relacoes(
                db(),
                ref,
                tipos=tipo,
                direcao=direcao,
                profundidade=profundidade,
                limite=limite,
                incluir_comunicados=comunicados,
            )
        except NormaNaoEncontrada as e:
            raise nao_encontrada(e) from None
        except ValueError as e:
            raise HTTPException(422, str(e)) from None

    @app.get("/api/grafo.arrow", responses={200: {"content": {ARROW: {}}}})
    def get_grafo(
        request: Request,
        tabela: Literal["nos", "arestas"] = "nos",
        comunicados: bool = False,
    ) -> Response:
        """The whole graph for the overview, as an Arrow IPC stream: `tabela=nos` (default) or `tabela=arestas`.
        Edge `origem`/`destino` are row indices into the node table of the same version (ETag)."""
        versao, nos, arestas = cache.get(db(), comunicados)
        etag = f'"{versao}-{int(comunicados)}-{tabela}"'
        headers = {"ETag": etag, "Cache-Control": "no-cache"}
        if request.headers.get("if-none-match") == etag:
            return Response(status_code=304, headers=headers)
        return Response(nos if tabela == "nos" else arestas, media_type=ARROW, headers=headers)

    dist = web_dist or Path(os.environ.get("REGTEIA_WEB_DIST", "apps/web/dist"))
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="web")
    return app
