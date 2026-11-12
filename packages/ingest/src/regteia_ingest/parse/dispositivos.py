"""Split a norm's body into Dispositivos: preamble, articles, annexes (with their own articles), or the top-level
Roman-numeral items of older norms. Deterministic: regex + sequence rules, no guessing.

Granularity is the article (ADR 0001): paragraphs, incisos and alíneas stay inside their article's text.

Rules, all learned from the corpus (see the ADR for the numbers):

- An article heading is a line starting with `Art. N` (`Art. 1º`, `Art. 10.`, `Art. 90-A`, `**Art. 2º**`) followed by a
  capital letter, an opening quote/bracket or a markdown mark. A line starting with a lowercase `art.` is a wrapped
  citation, never a heading.
- Article numbers must start at 1 and increase (`90`, `90-A`, `90-B`, `91`; a suffix only after its own number). Of
  all candidate headings, the best valid sequence wins: one point per article, minus 0.1 per skipped number. The
  rest is text: that is how an article of another norm quoted in an amendment (`Art. 37-A`, `Art. 17`) stays in the
  amending article.
- Inside a curly-quoted block (`“` opened, `”` not yet closed) nothing is a heading. If a body's curly quotes don't
  balance, quote tracking is dropped for that body and the sequence rule alone decides.
- Annex headings (`ANEXO I`, `Anexo II à Instrução Normativa…`, `REGULAMENTO ANEXO…`) start a paragraph and open a
  new scope whose articles restart at 1. Mid-paragraph lines (`Anexo 3 à Instrução CVM nº 480/09, devem ser…`, a
  wrapped citation) and repeated annex ids are text.
- A main body with no articles but at least two top-level Roman items in exact sequence (`I -`, `II -`, …) is split by
  item, as old CMN resolutions are. A restart (`I -` again) means nested lists: the body is kept whole instead.
- Whatever has no recognizable structure is kept whole (`#texto`), so full-text search still covers it.
- Hard-wrapped texts sometimes break the heading itself (`Art.` / `91.  É vedado`): the two lines are joined.
- Consolidated texts keep superseded wording struck through (`~~…~~`) next to the new wording. `texto` is the latest
  published wording, without the struck parts; the struck parts go to `redacoes_anteriores`. A struck article
  heading goes to the next article if that has its number; if its number fits between the current and the next
  article, it is a revoked article (`revogado`, empty `texto`); otherwise (a quoted article of another norm) it
  stays where it is. An article
  whose text is just "(Revogado…)" is revoked too. The latest wording can carry a future effective date: that is
  for `vigencia_em` (roadmap step 7) to decide, not this module.

IDs: `<norma>#preambulo`, `#art-88`, `#art-90-a`, `#item-iii`, `#anexo-i`, `#anexo-i/art-2`, `#anexo` (unnumbered),
`#texto`.
"""

import re
from dataclasses import dataclass, field

from regteia_schema import Dispositivo
from regteia_schema import Divisao as Metodo

# Bump when the splitting rules change: the next ingest notices and reloads everything (run.py).
VERSAO = 1

FENCE = re.compile(r"^\s*```")
TITULO_MD = re.compile(r"^#\s")
ART_PARTIDO = re.compile(r"^\s*(?:\*\*)?(?:Art|ART)\.?(?:\*\*)?\s*$")
RISCADO = re.compile(r"~~(.+?)~~", re.S)
REVOGADO = re.compile(r"^[\s*\[(]*revogad[oa]", re.I)

ART = re.compile(
    r"""^[ \t]*(?:\*\*)?[ \t]*(?:Art|ART)(?:igo|IGO)?\.?[ \t]*
    (?P<n>\d{1,4})[ \t]*(?:~~[º°o]~~|[º°o])?
    (?:[-–](?P<suf>[A-Z]{1,2})(?![A-Za-zÀ-ÿ]))?
    [ \t]*(?:\*\*)?[ \t]*[.\-–—:]?[ \t]*(?:\*\*)?
    (?:[ \t]*(?=[A-ZÀ-ÖØ-Þ“"'(\[*_])|[ \t]*$)""",
    re.X,
)
ANEXO = re.compile(
    r"""^[ \t]*(?:\*\*|\#{1,6}[ \t]*)?[ \t]*(?:(?:REGULAMENTO|Regulamento)[ \t]+)?(?:ANEXO|Anexo)
    (?:[ \t]+(?:N[º°o.]+[ \t]*)?(?P<n>[IVXLC]{1,6}|\d{1,3})(?![\w]))?
    (?P<resto>.*)$""",
    re.X,
)
ANEXO_RESTO_OK = re.compile(r'^(?:\s*$|\s*[-–—:.]\s*(?:$|[A-ZÀ-ÖØ-Þ“"*(])|\s*\*\*|\s+[A-ZÀ-ÖØ-Þ])')
ANEXO_DE = re.compile(r"^\s+(?:à|ao|a|às|aos|À|AO|A)\s")  # "Anexo I à Instrução Normativa…"
SEM_TEXTO = re.compile(r"^>\s*O portal d[oa] (?:BCB|CVM) não traz o texto desta norma")
ITEM = re.compile(r"^[ \t]*(?:\*\*)?[ \t]*(?P<r>[IVXLC]{1,7})[ \t]*(?:\*\*)?[ \t]*[-–—][ \t]+(?=\S)")
SECAO = re.compile(
    r"""^[ \t]*(?:\*\*)?[ \t]*
    (?P<nivel>LIVRO|Livro|T[ÍI]TULO|Título|CAP[ÍI]TULO|Capítulo|SE[ÇC][ÃA]O|Seção|SUBSE[ÇC][ÃA]O|Subseção)
    [ \t]+(?P<n>[IVXLC]{1,7}|\d{1,3}|[ÚU]NIC[OA]|Únic[oa])\b(?P<resto>.*)$""",
    re.X,
)
NIVEIS = {"LIVRO": 0, "TITULO": 1, "CAPITULO": 2, "SECAO": 3, "SUBSECAO": 4}
_SEM_ACENTO = str.maketrans("ÍÇÃ", "ICA")

_ROMANOS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL")]
_ROMANOS += [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def romano(n: int) -> str:
    out = []
    for v, s in _ROMANOS:
        while n >= v:
            out.append(s)
            n -= v
    return "".join(out)


@dataclass
class Divisao:
    metodo: Metodo
    dispositivos: list[Dispositivo] = field(default_factory=list)


@dataclass
class _Bloco:
    chave: str
    tipo: str
    rotulo: str
    numero: str | None
    anexo: str | None
    contexto: str | None
    linhas: list[str] = field(default_factory=list)
    revogado: bool = False
    anteriores: list[str] = field(default_factory=list)
    texto: str = ""


def _limpar(linhas: list[str]) -> list[str]:
    out: list[str] = []
    for i, linha in enumerate(linhas):
        if FENCE.match(linha):
            continue
        if i == 0 and TITULO_MD.match(linha):
            continue
        linha = linha.rstrip()
        if out and ART_PARTIDO.match(out[-1]) and re.match(r"\s*\d", linha):
            out[-1] = f"{out[-1].rstrip()} {linha.lstrip()}"
            continue
        out.append(linha)
    return out


def _texto(linhas: list[str]) -> str:
    return re.sub(r"\n{3,}", "\n\n", "\n".join(linhas)).strip()


def _aspas(linha: str) -> int:
    return linha.count("“") - linha.count("”")


def _equilibradas(linhas: list[str]) -> bool:
    saldo = 0
    for linha in linhas:
        saldo += _aspas(linha)
        if saldo < 0:
            return False
    return saldo == 0


def _anexo_id(m: re.Match[str]) -> str | None:
    """Annex number from a heading match ("I", "2", "" for unnumbered), or None if the line is not a heading."""
    resto = m["resto"]
    if len(m[0]) > 250 or "”" in resto or "(NR)" in resto:
        return None
    if not (ANEXO_RESTO_OK.match(resto) or ANEXO_DE.match(resto)):
        return None
    return (m["n"] or "").upper()


def _escopos(linhas: list[str], aspas: bool) -> list[tuple[str | None, int, int]]:
    """Split into the main body (None) and annexes: (annex number or None, start, end)."""
    marcos: list[tuple[str, int]] = []
    vistos: set[str] = set()
    saldo = 0
    for i, linha in enumerate(linhas):
        inicio_paragrafo = i == 0 or not linhas[i - 1].strip()
        if inicio_paragrafo and not (aspas and saldo > 0) and (m := ANEXO.match(linha)):
            n = _anexo_id(m)
            if n is not None and n not in vistos:
                vistos.add(n)
                marcos.append((n, i))
        if aspas:
            saldo = max(0, saldo + _aspas(linha))
    out: list[tuple[str | None, int, int]] = []
    inicio = 0
    atual: str | None = None
    for n, i in marcos:
        out.append((atual, inicio, i))
        atual, inicio = n, i
    out.append((atual, inicio, len(linhas)))
    return out


def _proximo_ok(ultimo: tuple[int, str] | None, n: int, suf: str) -> bool:
    if ultimo is None:
        return n == 1 and suf == ""
    un, us = ultimo
    if n == un:
        return suf > us  # 90 -> 90-A -> 90-B
    return n > un and suf == ""


SALTO = 0.1  # cost of each skipped article number


def _sequencia(cands: list[tuple[int, int, str]]) -> list[tuple[int, int, str]]:
    """Best chain of candidates (in text order) forming a valid article sequence from 1 (see SALTO)."""
    melhor: list[tuple[float, int]] = []  # per candidate: (score, predecessor index); score 0 = unreachable
    for k, (_, n, suf) in enumerate(cands):
        best = (1.0, -1) if _proximo_ok(None, n, suf) else (0.0, -1)
        for j in range(k):
            sj = melhor[j][0]
            if sj and _proximo_ok((cands[j][1], cands[j][2]), n, suf):
                cand = (sj + 1 - SALTO * max(0, n - cands[j][1] - 1), j)
                if cand[0] > best[0]:
                    best = cand
        melhor.append(best)
    if not melhor or max(m[0] for m in melhor) <= 0:
        return []
    k = max(range(len(melhor)), key=lambda x: melhor[x][0])
    out = []
    while k >= 0:
        out.append(cands[k])
        k = melhor[k][1]
    return out[::-1]


def _secao(linhas: list[str], i: int) -> tuple[int, str, int] | None:
    """A chapter/section heading at line i: (level, label, lines consumed)."""
    m = SECAO.match(linhas[i])
    if not m:
        return None
    nivel = NIVEIS[m["nivel"].upper().translate(_SEM_ACENTO)]
    cabeca = f"{m['nivel']} {m['n']}"
    resto = m["resto"].replace("*", " ").strip(" -–—:.")
    if resto and (resto[0].islower() or resto[0] in ",;"):
        return None  # "Capítulo II desta Resolução": a reference, not a heading
    if resto:
        return nivel, f"{cabeca} · {resto}", 1
    j = i + 1
    while j < len(linhas) and not linhas[j].strip():
        j += 1
    k = j
    while k < len(linhas) and k - j < 3 and linhas[k].strip():
        if ART.match(linhas[k]) or SECAO.match(linhas[k]) or ANEXO.match(linhas[k]):
            break
        k += 1
    titulo = " ".join(linhas[x].replace("*", " ").strip() for x in range(j, k))
    if titulo and len(titulo) <= 150 and titulo[-1] not in ".;:," and (k == len(linhas) or not linhas[k].strip()):
        return nivel, f"{cabeca} · {titulo}", k - i
    return nivel, cabeca, 1


def _artigos(
    linhas: list[str], ini: int, fim: int, aspas: bool, anexo: str | None, cabeca: _Bloco
) -> list[_Bloco] | None:
    """Article split of one scope, or None if it has no articles. `cabeca` collects text before the first article."""
    candidatos: list[tuple[int, int, str]] = []
    saldo = 0
    for i in range(ini, fim):
        if not (aspas and saldo > 0) and (m := ART.match(linhas[i])):
            candidatos.append((i, int(m["n"]), m["suf"] or ""))
        if aspas:
            saldo = max(0, saldo + _aspas(linhas[i]))
    heads = _sequencia(candidatos)
    if not heads:
        return None

    pref = "" if anexo is None else f"anexo-{anexo.lower()}/" if anexo else "anexo/"
    rot_anexo = "" if anexo is None else (f"Anexo {anexo}, " if anexo else "Anexo, ")
    blocos = [cabeca]
    atual = cabeca
    pilha: dict[int, str] = {}
    inicio = {i: (n, suf) for i, n, suf in heads}
    i = ini
    saldo = 0
    while i < fim:
        if i in inicio:
            n, suf = inicio[i]
            numero = f"{n}-{suf}" if suf else str(n)
            ctx = " › ".join(pilha[k] for k in sorted(pilha)) or None
            atual = _Bloco(
                chave=f"{pref}art-{numero.lower()}",
                tipo="artigo",
                rotulo=f"{rot_anexo}{'art.' if anexo is not None else 'Art.'} {numero}",
                numero=numero,
                anexo=anexo,
                contexto=ctx,
            )
            blocos.append(atual)
        elif not (aspas and saldo > 0) and (s := _secao(linhas, i)):
            nivel, rotulo, usadas = s
            for k in [k for k in pilha if k >= nivel]:
                del pilha[k]
            pilha[nivel] = rotulo
            for k in range(i, min(i + usadas, fim)):
                if aspas:
                    saldo = max(0, saldo + _aspas(linhas[k]))
            i += usadas
            continue
        atual.linhas.append(linhas[i])
        if aspas:
            saldo = max(0, saldo + _aspas(linhas[i]))
        i += 1
    return blocos


def _itens(linhas: list[str], ini: int, fim: int, aspas: bool) -> list[_Bloco] | None:
    """Top-level Roman items of an old norm, or None (fewer than two, or a restart that signals nested lists)."""
    heads: list[tuple[int, str]] = []
    esperado = 1
    saldo = 0
    for i in range(ini, fim):
        if not (aspas and saldo > 0) and (m := ITEM.match(linhas[i])):
            r = m["r"]
            if r == romano(esperado):
                heads.append((i, r))
                esperado += 1
            elif r == "I" and heads:
                return None
        if aspas:
            saldo = max(0, saldo + _aspas(linhas[i]))
    if len(heads) < 2:
        return None
    blocos = [_Bloco("preambulo", "preambulo", "Preâmbulo", None, None, None, linhas[ini : heads[0][0]])]
    for k, (i, r) in enumerate(heads):
        j = heads[k + 1][0] if k + 1 < len(heads) else fim
        blocos.append(_Bloco(f"item-{r.lower()}", "item", f"Item {r}", r, None, None, linhas[i:j]))
    return blocos


def dividir(norma_id: str, corpo: str) -> Divisao:
    """Split `corpo` (the Markdown after the frontmatter) into Dispositivos of `norma_id`."""
    linhas = _limpar(corpo.splitlines())
    texto = _texto(linhas)
    if not texto or (SEM_TEXTO.match(texto) and "\n" not in texto):
        return Divisao("vazio")
    aspas = _equilibradas(linhas)
    blocos: list[_Bloco] = []
    metodo: Metodo = "texto"
    for anexo, ini, fim in _escopos(linhas, aspas):
        if anexo is None:
            cabeca = _Bloco("preambulo", "preambulo", "Preâmbulo", None, None, None)
            arts = _artigos(linhas, ini, fim, aspas, None, cabeca)
            if arts:
                blocos += arts
                metodo = "artigos"
            elif itens := _itens(linhas, ini, fim, aspas):
                blocos += itens
                metodo = "itens"
            else:
                blocos.append(_Bloco("texto", "texto", "Texto", None, None, None, linhas[ini:fim]))
        else:
            chave = f"anexo-{anexo.lower()}" if anexo else "anexo"
            rotulo = f"Anexo {anexo}" if anexo else "Anexo"
            cabeca = _Bloco(chave, "anexo", rotulo, anexo or None, anexo, None)
            arts = _artigos(linhas, ini, fim, aspas, anexo, cabeca)
            if arts:
                blocos += arts
                if metodo == "texto":
                    metodo = "artigos"
            else:
                cabeca.linhas = linhas[ini:fim]
                blocos.append(cabeca)

    blocos = _riscados(blocos)
    out: list[Dispositivo] = []
    for b in blocos:
        if not b.texto and not b.anteriores and b.tipo in ("preambulo", "texto"):
            continue
        out.append(
            Dispositivo(
                id=f"{norma_id}#{b.chave}",
                norma=norma_id,
                tipo=b.tipo,
                rotulo=b.rotulo,
                ordem=len(out),
                texto=b.texto,
                numero=b.numero,
                anexo=b.anexo,
                contexto=b.contexto,
                revogado=b.revogado,
                redacoes_anteriores=tuple(b.anteriores),
            )
        )
    return Divisao(metodo, out)


def _riscados(blocos: list[_Bloco]) -> list[_Bloco]:
    """Move struck-through wording out of `texto`, to the article it belongs to (see the module docstring)."""
    por_chave = {b.chave: b for b in blocos}
    seguinte: dict[str, _Bloco | None] = {}  # next article in the same scope
    for k, b in enumerate(blocos):
        seguinte[b.chave] = (
            next((x for x in blocos[k + 1 :] if x.tipo == "artigo" and x.anexo == b.anexo), None)
            if b.tipo in ("artigo", "preambulo", "anexo")
            else None
        )
    out: list[_Bloco] = []
    for b in blocos:
        bruto = _texto(b.linhas)
        out.append(b)
        if bruto.count("~~") % 2:  # unbalanced marks: keep the text as published
            b.texto = bruto
            continue
        b.texto = _texto(RISCADO.sub("", bruto).splitlines())
        for seg in (x.strip() for x in RISCADO.findall(bruto)):
            if not seg:
                continue
            m = ART.match(seg.splitlines()[0])
            alvo = b
            if m and b.tipo in ("artigo", "preambulo", "anexo"):
                n = f"{m['n']}-{m['suf']}" if m["suf"] else m["n"]
                pref = "" if b.anexo is None else f"anexo-{b.anexo.lower()}/" if b.anexo else "anexo/"
                chave = f"{pref}art-{n.lower()}"
                prox = seguinte.get(b.chave)
                if prox is not None and chave == prox.chave:
                    alvo = prox
                elif chave not in por_chave and _entre(b, (int(m["n"]), m["suf"] or ""), prox):
                    alvo = _revogado(b, chave, n, out, por_chave)
            alvo.anteriores.append(seg)
    for b in out:
        if b.tipo == "artigo" and not b.revogado:
            m = ART.match(b.texto.splitlines()[0]) if b.texto else None
            resto = b.texto[m.end() :] if m else b.texto
            b.revogado = not b.texto or bool(REVOGADO.match(resto) and len(resto) < 400)
    return out


def _ordem(b: _Bloco) -> tuple[int, str]:
    if b.tipo != "artigo" or not b.numero:
        return (0, "")
    n, _, suf = b.numero.partition("-")
    return (int(n), suf)


def _entre(b: _Bloco, numero: tuple[int, str], prox: _Bloco | None) -> bool:
    return _ordem(b) < numero and (prox is None or numero < _ordem(prox))


def _revogado(perto: _Bloco, chave: str, numero: str, out: list[_Bloco], por_chave: dict[str, _Bloco]) -> _Bloco:
    """An article that only exists struck through: revoked, placed where it appears in the text."""
    rot_anexo = "" if perto.anexo is None else (f"Anexo {perto.anexo}, " if perto.anexo else "Anexo, ")
    b = _Bloco(
        chave=chave,
        tipo="artigo",
        rotulo=f"{rot_anexo}{'art.' if perto.anexo is not None else 'Art.'} {numero}",
        numero=numero,
        anexo=perto.anexo,
        contexto=perto.contexto,
        revogado=True,
    )
    out.append(b)
    por_chave[chave] = b
    return b
