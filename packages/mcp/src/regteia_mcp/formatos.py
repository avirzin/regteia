"""Markdown for the AI client: what each tool returns. Formatting only; every fact comes from regteia_query.

Every answer leads with the norm's status (with who revoked or amended it) and the official source, and ends with
the disclaimer. Texts are capped so one call never floods the client's context.
"""

from regteia_query.modelos import (
    DispositivoDetalhe,
    NormaDetalhe,
    NormaResumo,
    ResultadoBusca,
    Subgrafo,
)
from regteia_schema.env import AVISO

TEXTO_MAX = 20_000  # characters of one Dispositivo in `dispositivo`
ANTERIOR_MAX = 3_000  # characters of each superseded wording
RESPOSTA_MAX = 40_000  # characters of a whole `buscar` answer

RELACAO = {
    ("saida", "REVOGA"): "Revoga",
    ("saida", "REVOGA_PARCIAL"): "Revoga em parte",
    ("saida", "ALTERA"): "Altera",
    ("saida", "CITA"): "Cita",
    ("saida", "REGULAMENTA"): "Fundamenta-se em / regulamenta",
    ("saida", "CONJUNTA"): "Norma conjunta com",
    ("entrada", "REVOGA"): "Revogada por",
    ("entrada", "REVOGA_PARCIAL"): "Revogada em parte por",
    ("entrada", "ALTERA"): "Alterada por",
    ("entrada", "CITA"): "Citada por",
    ("entrada", "REGULAMENTA"): "Base legal de / regulamentada por",
    ("entrada", "CONJUNTA"): "Norma conjunta com",
}


def _data(n: NormaResumo) -> str:
    return f"{n.data:%d/%m/%Y}" if n.data else "sem data"


def ficha(n: NormaResumo) -> str:
    linhas = [f"Situação: {n.situacao_detalhada}", f"Data: {_data(n)} | id: `{n.id}`"]
    if n.fonte_url:
        linhas.append(f"Fonte oficial: {n.fonte_url}")
    if n.url_arquivo:
        linhas.append(f"Texto convertido (versão exata): {n.url_arquivo}")
    if n.url_externa:
        linhas.append(f"Onde está: {n.url_externa}")
    if n.versao_texto and "original" in n.versao_texto.lower():
        linhas.append(f"Versão do texto: {n.versao_texto} (pode não refletir alterações posteriores)")
    if n.ocr:
        linhas.append("Texto obtido por OCR: pode conter erros de reconhecimento.")
    return "\n".join(linhas)


def _nome(n: NormaResumo) -> str:
    return n.titulo or n.id


def _cortar(texto: str, limite: int) -> str:
    if len(texto) <= limite:
        return texto
    return texto[:limite].rstrip() + "\n[… cortado]"


def _fim(partes: list[str], notas: list[str]) -> str:
    if notas:
        partes.append("\n".join(f"> {n}" for n in notas))
    partes.append(AVISO)
    return "\n\n".join(p for p in partes if p)


def busca(r: ResultadoBusca) -> str:
    if not r.itens:
        return _fim([f"Nada encontrado para “{r.consulta}”. Tente os termos da regulação ou outras palavras."], r.notas)
    partes: list[str] = []
    usado = 0
    for i in r.itens:
        bloco = [f"## {_nome(i.norma)}", ficha(i.norma)]
        if i.norma.ementa:
            bloco.append(f"Ementa: {i.norma.ementa}")
        for t in i.trechos:
            d = t.dispositivo
            cab = f"### {d.rotulo}" + (" — DISPOSITIVO REVOGADO" if d.revogado else "")
            ctx = f"_{d.contexto}_" if d.contexto else ""
            corpo = t.texto if t.texto is not None else t.trecho
            bloco.append("\n".join(x for x in (cab, ctx, corpo) if x) + f"\n(id: `{d.id}`)")
        texto = "\n\n".join(bloco)
        if partes and usado + len(texto) > RESPOSTA_MAX:
            partes.append(f"[… mais {len(r.itens) - len(partes)} norma(s) omitidas por tamanho: refine a busca]")
            break
        partes.append(texto)
        usado += len(texto)
    return _fim(partes, r.notas)


def norma(r: NormaDetalhe) -> str:
    n = r.norma
    partes = [f"# {_nome(n)}", ficha(n)]
    if n.ementa:
        partes.append(f"Ementa: {n.ementa}")
    for g in r.relacoes:
        linhas = [f"**{RELACAO.get((g.direcao, g.tipo), g.tipo)} ({g.total})**"]
        for v in g.itens:
            desde = f", a partir de {v.desde:%d/%m/%Y}" if v.desde else ""
            linhas.append(f"- {_nome(v.norma)} ({v.norma.situacao}{desde}) `{v.norma.id}`")
        if g.total > len(g.itens):
            linhas.append(f"- … e mais {g.total - len(g.itens)} (use `relacoes`)")
        partes.append("\n".join(linhas))
    if r.sumario:
        exemplo = r.sumario[min(1, len(r.sumario) - 1)]
        rotulos = [d.rotulo + (" [revogado]" if d.revogado else "") for d in r.sumario]
        mais = f" … e mais {len(rotulos) - 150}" if len(rotulos) > 150 else ""
        partes.append(
            f"**Dispositivos ({len(r.sumario)}; divisão: {r.divisao})**: "
            + "; ".join(rotulos[:150])
            + mais
            + f"\nPara ler um, chame `dispositivo` com, por exemplo, “{_nome(n)}, {exemplo.rotulo}”."
        )
    elif r.divisao == "vazio":
        partes.append("O portal não traz o texto desta norma; só os metadados.")
    return _fim(partes, r.notas)


def dispositivo(r: DispositivoDetalhe) -> str:
    d = r.dispositivo
    cab = f"# {_nome(r.norma)}, {d.rotulo}" + (" — DISPOSITIVO REVOGADO" if d.revogado else "")
    partes = [cab, ficha(r.norma) + f"\nDispositivo: `{d.id}`"]
    if d.contexto:
        partes.append(f"_{d.contexto}_")
    partes.append(_cortar(r.texto, TEXTO_MAX) if r.texto else "(sem texto: o dispositivo foi revogado)")
    for k, ant in enumerate(r.redacoes_anteriores, 1):
        partes.append(f"**Redação anterior {k}** (riscada no portal; não vale mais):\n{_cortar(ant, ANTERIOR_MAX)}")
    nav = [f"anterior: {r.anterior.rotulo} (`{r.anterior.id}`)" if r.anterior else ""]
    nav.append(f"próximo: {r.proximo.rotulo} (`{r.proximo.id}`)" if r.proximo else "")
    if any(nav):
        partes.append(" | ".join(x for x in nav if x))
    return _fim(partes, r.notas)


def subgrafo(r: Subgrafo) -> str:
    origem = r.nos[0].norma
    tipos = ", ".join(r.tipos)
    partes = [
        f"# Relações de {_nome(origem)}",
        ficha(origem),
        f"{len(r.nos) - 1} norma(s) a até {r.profundidade} salto(s), direção {r.direcao}, tipos {tipos}.",
    ]
    tipos_de: dict[str, set[str]] = {}
    for a in r.arestas:
        for ponta in (a.de, a.para):
            tipos_de.setdefault(ponta, set()).add(a.tipo)
    linhas = []
    for no in r.nos[1:]:
        t = ", ".join(sorted(tipos_de.get(no.norma.id, set()))) or "-"
        linhas.append(
            f"- [{no.distancia}] {_nome(no.norma)} — {no.norma.situacao} ({_data(no.norma)}; {t}) `{no.norma.id}`"
        )
    partes.append("\n".join(linhas))
    notas = (
        ["Resultado truncado pelo limite: há mais normas (aumente o limite ou filtre os tipos)."] if r.truncado else []
    )
    return _fim(partes, notas)


def erro(msg: str, sugestoes: list[tuple[str, str]] | None = None) -> str:
    partes = [msg]
    if sugestoes:
        partes.append("Talvez:\n" + "\n".join(f"- {t} (`{i}`)" for i, t in sugestoes))
    return "\n\n".join(partes)
