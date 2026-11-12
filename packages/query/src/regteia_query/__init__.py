"""Regteia read logic. mcp, server and the CLI are thin adapters over these functions."""

from .db import Leitor
from .estatisticas import estatisticas
from .normas import NormaNaoEncontrada, buscar, norma, panorama, resolver
from .relacoes import relacoes

__all__ = ["Leitor", "NormaNaoEncontrada", "buscar", "estatisticas", "norma", "panorama", "relacoes", "resolver"]
