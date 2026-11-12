"""Regteia read logic. mcp, server and the CLI are thin adapters over these functions."""

from .db import Leitor
from .estatisticas import estatisticas
from .grafo import GRUPOS, GrafoExportado, exportar_grafo, versao_dados
from .normas import NormaNaoEncontrada, buscar, norma, panorama, resolver
from .relacoes import relacoes

__all__ = [
    "GRUPOS",
    "GrafoExportado",
    "Leitor",
    "exportar_grafo",
    "versao_dados",
    "NormaNaoEncontrada",
    "buscar",
    "estatisticas",
    "norma",
    "panorama",
    "relacoes",
    "resolver",
]
