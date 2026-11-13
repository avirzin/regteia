"""The MCP server through the real protocol: in-process client, then the `regteia-mcp` command over stdio."""

import asyncio
import os
import shutil
import sys
from pathlib import Path

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters
from regteia_mcp.servidor import create_server
from regteia_schema.env import AVISO

from .conftest import AUTH

pytestmark = pytest.mark.integration


def _texto(resultado) -> str:
    assert not resultado.is_error, resultado
    return "\n".join(c.text for c in resultado.content)


def _chamar(server, *chamadas):
    async def rodar():
        async with Client(server) as c:
            ferramentas = await c.list_tools()
            saidas = [_texto(await c.call_tool(nome, args)) for nome, args in chamadas]
            return ferramentas, saidas

    return asyncio.run(rodar())


@pytest.fixture(scope="module")
def server(leitor):
    return create_server(lambda: leitor)


def test_tools_are_fixed_and_read_only(server):
    ferramentas, _ = _chamar(server)
    nomes = sorted(t.name for t in ferramentas.tools)
    assert nomes == ["buscar", "dispositivo", "norma", "panorama", "relacoes"]
    for t in ferramentas.tools:
        assert t.annotations.read_only_hint is True and t.annotations.destructive_hint is False, t.name
        assert "cypher" not in (t.description or "").lower()
        assert "cypher" not in str(t.input_schema).lower()


def test_buscar_returns_articles_with_status_source_and_synonyms(server):
    _, [saida, sinonimo] = _chamar(
        server,
        ("buscar", {"consulta": "misturadores embaralhadores", "limite": 3}),
        ("buscar", {"consulta": "exchange", "limite": 5}),
    )
    assert "## Resolução BCB N° 520" in saida
    assert "Situação: VIGENTE, ALTERADA por Resolução BCB N° 589" in saida
    assert "Fonte oficial: https://www.bcb.gov.br/" in saida
    assert "### Art. 90" in saida and "embaralhadores" in saida  # the article text itself
    assert saida.rstrip().endswith(AVISO)
    # "exchange" is not in any norm: the synonym table maps it to the regulation's wording
    assert "Resolução BCB N° 520" in sinonimo and "prestadora de serviços de ativos virtuais" in sinonimo


def test_norma_dispositivo_relacoes_panorama(server):
    _, [n, d, r, p] = _chamar(
        server,
        ("norma", {"ref": "Resolução BCB 520"}),
        ("dispositivo", {"ref": "Resolução BCB 520, art. 91"}),
        ("relacoes", {"ref": "Resolução BCB 589", "direcao": "saida", "tipos": ["ALTERA"]}),
        ("panorama", {"tema": "ativos virtuais", "limite": 5}),
    )
    assert "Alterada por (1)" in n and "Dispositivos (94; divisão: artigos)" in n
    assert "Art. 91" in d and "Redação anterior 1" in d and "não vale mais" in d
    assert "6 de novembro de 2026" in d and d.rstrip().endswith(AVISO)
    assert "Resolução BCB N° 520" in r and "ALTERA" in r
    situacoes = [x.split("\n")[0] for x in p.split("Situação: ")[1:]]
    assert situacoes and all(s.startswith("VIGENTE") for s in situacoes)  # panorama: never a revoked norm


def test_errors_come_back_as_text_with_suggestions(server):
    _, [a, b, c] = _chamar(
        server,
        ("norma", {"ref": "Resolução BCB 99999"}),
        ("dispositivo", {"ref": "Resolução BCB 520, art. 95"}),
        ("dispositivo", {"ref": "Resolução BCB 520"}),
    )
    assert a.startswith("norma não encontrada")
    assert b.startswith("dispositivo não encontrado") and "bcb:resolucao-bcb:520#art-92" in b
    assert "indique o dispositivo" in c


def test_stdio_command(neo4j_url):
    """`regteia-mcp` as an AI client launches it: a subprocess speaking MCP on stdin/stdout (logs never on stdout)."""
    comando = shutil.which("regteia-mcp") or str(Path(sys.executable).with_name("regteia-mcp"))
    assert Path(comando).exists(), "regteia-mcp is not installed in this environment"
    env = {**os.environ, "NEO4J_URI": neo4j_url, "NEO4J_USER": AUTH[0], "NEO4J_PASSWORD": AUTH[1]}
    params = StdioServerParameters(command=comando, args=[], env=env)
    _, [saida] = _chamar(params, ("norma", {"ref": "ICVM 1"}))
    assert "Instrução CVM" in saida and saida.rstrip().endswith(AVISO)
