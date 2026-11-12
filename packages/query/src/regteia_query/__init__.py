"""Regteia read logic. mcp, server and the CLI are thin adapters over these functions."""

from .db import Leitor
from .estatisticas import estatisticas
from .grafo import GRUPOS, GrafoExportado, exportar_grafo, versao_dados
from .normas import DispositivoNaoEncontrado, NormaNaoEncontrada, buscar, dispositivo, norma, panorama, resolver
from .relacoes import relacoes

__all__ = [
    "GRUPOS",
    "GrafoExportado",
    "Leitor",
    "exportar_grafo",
    "versao_dados",
    "DispositivoNaoEncontrado",
    "NormaNaoEncontrada",
    "buscar",
    "dispositivo",
    "estatisticas",
    "norma",
    "panorama",
    "relacoes",
    "resolver",
]
