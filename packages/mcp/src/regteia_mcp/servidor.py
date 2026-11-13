"""regteia-mcp: the local graph for AI clients on this machine, over stdio only (no network listener).

Read-only by construction: every tool calls a fixed function of regteia_query, which only opens read sessions
(Neo4j Community has no RBAC, so this is enforced in code). There is no tool that runs arbitrary Cypher or writes.
The AI client launches this process; it connects to Neo4j lazily, so the server starts even if Neo4j is down and
each tool then says how to bring it up.
"""

import logging
import sys
import threading
from collections.abc import Callable
from typing import Annotated, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations
from pydantic import Field
from regteia_query import BancoIndisponivel, Leitor, NormaNaoEncontrada
from regteia_query import buscar as q_buscar
from regteia_query import dispositivo as q_dispositivo
from regteia_query import norma as q_norma
from regteia_query import panorama as q_panorama
from regteia_query import relacoes as q_relacoes
from regteia_query.relacoes import PROFUNDIDADE_MAX, TODOS

from . import formatos

INSTRUCOES = """\
Grafo local da regulação financeira brasileira: todas as normas do BCB, do CMN e da CVM (cerca de 63 mil), divididas
em artigos, com a situação de vigência e as relações entre elas (revoga, altera, cita, regulamenta).

Como usar:
- `buscar` acha os artigos pelo assunto (busca por palavras em português); `panorama` lista as normas em vigor de um
  tema; `norma` mostra uma norma, quem a alterou ou revogou e seus artigos; `dispositivo` devolve o texto de um
  artigo; `relacoes` percorre as relações a mais de um salto.
- Para citar um artigo, leia-o com `dispositivo` e cite a norma, o artigo e a fonte oficial.

Regras (não negociáveis):
- Nunca apresente como vigente uma norma ou um dispositivo marcado como REVOGADO/REVOGADA.
- “Alterada” significa que o texto é o consolidado atual do portal. Partes com “a partir de <data futura>” ainda não
  valem: diga isso.
- Redações anteriores (riscadas no portal) não valem mais; use-as só para explicar o que mudou.
- Não invente redação histórica: o grafo tem o texto atual e as redações riscadas, não o texto em cada data.
- Leis federais aparecem só como referência, sem texto.
- Sempre indique a fonte oficial e lembre que o texto é uma conversão automatizada e informativa, que não substitui
  o Diário Oficial nem os portais do BCB e da CVM.
"""

LEITURA = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
SEM_NEO4J = (
    "O Neo4j local não está respondendo. Suba a pilha com `docker compose up -d` na pasta do Regteia e tente de novo."
)


def create_server(abrir: Callable[[], Leitor] = Leitor.do_ambiente) -> MCPServer:
    """The MCP server over the Leitor that `abrir` returns (opened on first use, then reused)."""
    estado: dict[str, Leitor] = {}
    trava = threading.Lock()

    def db() -> Leitor:
        with trava:
            if "db" not in estado:
                estado["db"] = abrir()
            return estado["db"]

    def executar(chamada: Callable[[Leitor], str]) -> str:
        try:
            return chamada(db())
        except NormaNaoEncontrada as e:
            return formatos.erro(str(e).split(". Talvez:")[0] + ".", e.sugestoes)
        except ValueError as e:
            return formatos.erro(str(e))
        except BancoIndisponivel:
            return formatos.erro(SEM_NEO4J)

    mcp = MCPServer("regteia", instructions=INSTRUCOES)

    @mcp.tool(annotations=LEITURA)
    def buscar(
        consulta: Annotated[str, Field(description="Assunto em português, com os termos da regulação se possível")],
        limite: Annotated[int, Field(ge=1, le=20, description="Quantas normas")] = 8,
        incluir_revogadas: Annotated[bool, Field(description="Incluir normas revogadas")] = True,
        incluir_comunicados: Annotated[bool, Field(description="Não rebaixar comunicados (avisos de leilão)")] = False,
    ) -> str:
        """Busca no texto dos artigos, títulos e ementas de todas as normas do BCB, do CMN e da CVM.

        Devolve, por norma, a situação de vigência (e quem revogou ou alterou), a fonte oficial e os artigos que
        mais batem, com o texto. Termos comuns como "exchange", "cripto", "PLD", "open finance" são traduzidos
        para a linguagem das normas. Refaça com outras palavras se o resultado não servir.
        """
        return executar(
            lambda d: formatos.busca(
                q_buscar(
                    d,
                    consulta,
                    limite=limite,
                    incluir_revogadas=incluir_revogadas,
                    incluir_comunicados=incluir_comunicados,
                    com_texto=True,
                )
            )
        )

    @mcp.tool(annotations=LEITURA)
    def norma(
        ref: Annotated[str, Field(description='Nome ou id: "Resolução BCB 520", "ICVM 400", "bcb:resolucao-cmn:4966"')],
        limite: Annotated[int, Field(ge=1, le=50, description="Itens por tipo de relação")] = 10,
    ) -> str:
        """Uma norma: situação de vigência, fonte oficial, ementa, quem a revogou ou alterou, o que ela revoga, altera,
        cita e regulamenta, e a lista dos seus dispositivos (artigos, anexos)."""
        return executar(lambda d: formatos.norma(q_norma(d, ref, limite=limite)))

    @mcp.tool(annotations=LEITURA)
    def dispositivo(
        ref: Annotated[
            str,
            Field(
                description='Artigo de uma norma: "Resolução BCB 520, art. 88", "art. 3º da Resolução CMN 4.966", '
                '"Resolução CMN 4.966, anexo I, art. 2", "Resolução 1, item II" ou o id "bcb:resolucao-bcb:520#art-88"'
            ),
        ],
    ) -> str:
        """O texto de um artigo (ou anexo, item, preâmbulo): redação mais recente publicada, capítulo e seção, se está
        revogado, redações anteriores riscadas no portal e avisos de vigência futura."""
        return executar(lambda d: formatos.dispositivo(q_dispositivo(d, ref)))

    @mcp.tool(annotations=LEITURA)
    def relacoes(
        ref: Annotated[str, Field(description="Nome ou id da norma de partida")],
        direcao: Annotated[
            Literal["saida", "entrada", "ambas"],
            Field(description="saida: o que ela revoga/altera/cita; entrada: o que aponta para ela"),
        ] = "saida",
        tipos: Annotated[
            list[Literal["REVOGA", "REVOGA_PARCIAL", "ALTERA", "CITA", "REGULAMENTA", "CONJUNTA"]] | None,
            Field(description="Tipos de relação; vazio = todos"),
        ] = None,
        profundidade: Annotated[int, Field(ge=1, le=PROFUNDIDADE_MAX, description="Saltos")] = 1,
        limite: Annotated[int, Field(ge=1, le=500, description="Máximo de normas")] = 100,
    ) -> str:
        """Normas ligadas a uma norma, a um ou mais saltos: por exemplo, o que altera as normas que alteram esta."""
        return executar(
            lambda d: formatos.subgrafo(
                q_relacoes(d, ref, tipos=tipos or TODOS, direcao=direcao, profundidade=profundidade, limite=limite)
            )
        )

    @mcp.tool(annotations=LEITURA)
    def panorama(
        tema: Annotated[str, Field(description="Tema em português")],
        limite: Annotated[int, Field(ge=1, le=60, description="Quantas normas")] = 20,
    ) -> str:
        """Normas em vigor (vigentes ou alteradas) sobre um tema, sem revogadas e sem comunicados: bom ponto de
        partida para "quais normas regem…"."""
        return executar(lambda d: formatos.busca(q_panorama(d, tema, limite=limite)))

    return mcp


def main() -> None:
    # stdout is the protocol channel: logs go to stderr only
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    create_server().run("stdio")


if __name__ == "__main__":
    main()
