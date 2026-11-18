"""Read upstream's `atualizacoes` entries into article-level amendments: which norm changed which Dispositivo of
this norm, how (nova redação, inclusão, revogação) and from when. Deterministic: regex + rules, no guessing.

An entry lives in the amended norm's frontmatter and names the amending norm first:

    Resolução BCB nº 589/2026 - Alteração, a partir de 1º/1/2027 - Nova redação: art. 88, inciso III, alíneas "b",
    "c", "d" e "e". Inclusão: arts. 90-A e 90-B.
    CIRCULAR BCB 1932/91 DOU 11/04/1991 PAG 6717 - ALTERACAO: ART/7 PARAG/1 ITEM/IV (REGULAMENTO).

Rules, learned from the corpus (18,860 entries; see docs/decisions/0002):

- The amending norm is read with upstream's own rules (`citacoes.autor_da_atualizacao`), so it is the norm of
  upstream's norm-level edge. Entries upstream reads as notes ("OBS: …") are notes here too.
- "Revogação total" (and the other whole-norm events upstream recognizes) concern the whole norm: no Dispositivo.
- The rest is a sequence of clauses, each opened by an action word: nova redação / alteração (-> `nova_redacao`),
  inclusão / acréscimo (-> `inclusao`), revogação (-> `revogacao`). Other actions (prorrogação, citação,
  renumeração, retificação…) name no change of wording: they are kept as an event of the whole norm.
- A clause's targets are articles (`art. 88`, `arts. 2º a 12, 14 e 47 a 51`, `arts. 60-A a 60-I`, `ART/7`), annexes
  (`Anexos I e III`, `Regulamento anexo`, `ANEXO/XV`) and, with no article in the group, top-level items
  (`item I`, `itens II a IV`, `ITEM/IV`). Anything finer (§, inciso, alínea, caput) is kept as `detalhe` text on
  the article: Dispositivos are articles (ADR 0001).
- "Alteração no Anexo I - Nova redação: art. 24" puts the articles that follow into that annex, until another annex
  is named; an annex named with no article after it is itself the target. "ART/7 … (REGULAMENTO)" and "art. 2º do
  Anexo I" put that group's articles into the annex.
- "a partir de <date>" applies to the targets after it; targets before any date have none (in force from the
  amending norm's own date, which `vigencia_em` says).
- A clause that names another norm ("ALTERACAO: ITEM/II DA CIRCULAR BCB 963/85") is about that norm: skipped.
- A clause with an action and something that looks like a target we cannot read is a failure, reported with the
  entry; the readable targets of the same entry are kept (`parcial`). Nothing is dropped silently.

Matching targets to the norm's actual Dispositivos (an `anexo-i` written `Anexo 1`, an article that lives in the only
annex) is `ligar`'s job, since it needs the split of the amended norm.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Literal

from .citacoes import autor_da_atualizacao, citar, plano, sem_datas

VERSAO = 1  # bump when the rules change: the next ingest re-reads every entry

TipoAlteracao = Literal["nova_redacao", "inclusao", "revogacao"]
Resultado = Literal["dispositivos", "parcial", "norma", "nota", "falha", "ausente"]

# same length as the input, so positions map back to the original text
_PLANO = str.maketrans(
    "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇºª°“”‘’–—",
    "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUCoao\"\"''--",
)
_ACAO = re.compile(
    r"""(?P<revogacao>\brevoga(?:cao|coes|dos?|das?|r)?\b|\brevogam\b)
      | (?P<inclusao>\binclu(?:sao|soes|idos?|idas?|i|em|ir)\b|\bacresc(?:imos?|idos?|idas?|enta|entam|entar)\b
          |\binser(?:cao|idos?|idas?|e)\b)
      | (?P<nova_redacao>\bnova\s+redacao\b|\bredacao\s+dada\b|\balterac(?:ao|oes)\b|\balterad[oa]s?\b|\baltera\b
          |\bmodifica(?:cao|dos?|das?)?\b|\bsubstitui(?:cao|dos?|das?)?\b)
      | (?P<outro>\bprorroga(?:cao|dos?|das?)?\b|\bcita(?:cao)?\b|\brevigora(?:cao|dos?|das?)?\b|\bretifica(?:cao)?\b
          |\brenumera(?:cao|dos?|das?)?\b|\bsuspen(?:sao|sos?|sas?|de)\b|\batualiza(?:cao)?\b|\baprova\b
          |\bexclu(?:i|sao)\b|\bconsolida(?:cao)?\b|\btorna\s+sem\s+efeito\b|\bretira\b
          |\bnormas\s+complementares\b)""",
    re.VERBOSE,
)
# what upstream counts as an event of the whole norm (scripts/grafo.py `acoes`)
_NAO_TOTAL = re.compile(r"prorrog|revigor|sem efeito a revog")
_TOTAL = re.compile(
    r"revogac?ao (?:total|tacita)|revoga est[ae]|sem efeito est[ae]|cancelad|cancelamento dest|em desuso"
)

_N = r"\d+(?:o(?![a-z]))?(?:\s*-\s*[a-z]{1,2}(?![a-z]))?"
_SEP = r"\s*(?:,|\be\b|\ba\b|\bate\b)\s*"
_ARTIGOS = re.compile(rf"\b(?:arts?|artigos?)\b\.?\s*(?P<lista>{_N}(?:{_SEP}{_N})*)")
_ARTIGO_L = re.compile(r"\barts?/(?P<lista>\d+(?:-?[a-z])?)")
_R = r"(?:[ivxlc]+|\d+)(?![a-z\d])"
_ITENS = re.compile(rf"\bite(?:m|ns)\b\.?\s*(?P<lista>{_R}(?:{_SEP}{_R})*)")
_ITEM_L = re.compile(r"\bitem/(?P<lista>[ivxlc]+)(?![a-z])")
_A = r"(?:[ivxlc]+|\d+|[a-z])(?![a-z\d])"
_ANEXOS = re.compile(rf"\b(?:regulamentos?\s+)?anexos?\b(?:\s+(?P<lista>{_A}(?:\s*(?:,|\be\b|\ba\b)\s*{_A})*))?")
_ANEXO_L = re.compile(r"\banexo/(?P<lista>[ivxlc]+|\d+)(?![a-z])")
_REGULAMENTO = re.compile(r"\bregulamento\b(?!\s+anexo)")
_POSFIXO = re.compile(r"(?:\bd[oa]s?|\bn[oa]s?|\()\s*$")
_DATA = re.compile(r"a\s+partir\s+de\s+(?:de\s+)?(\d{1,2})o?\s*[/.]\s*(\d{1,2})\s*[/.]\s*(\d{4}|\d{2})\b")
_DATA_EXTENSO = re.compile(r"a\s+partir\s+de\s+(\d{1,2})o?\s+de\s+([a-z]+)\s+de\s+(\d{4})\b")
_MESES = {
    m: i
    for i, m in enumerate(
        [
            "janeiro",
            "fevereiro",
            "marco",
            "abril",
            "maio",
            "junho",
            "julho",
            "agosto",
            "setembro",
            "outubro",
            "novembro",
            "dezembro",
        ],
        1,
    )
}
# a clause with one of these but no target we can read is a failure, not an event of the whole norm
# old entries that point into the BCB's consolidated manuals (CNC 2/13, MNI 13-7-8, TITULO/V): no Dispositivo here
_MANUAL = re.compile(r"\b(?:cnc|mni|mcr|cosif|rmcci|cobam|coban|manual|titulo)\b")
_DATAS = re.compile(r"\d{1,2}o?\s*[/.]\s*\d{1,2}\s*[/.]\s*\d{2,4}")
_PARECE_ALVO = re.compile(r"\bart\b|\barts\b|\bartigos?\b|§|\bincisos?\b|\bparagrafos?\b|\balineas?\b|\bitens?\b|/")


@dataclass(frozen=True)
class Alvo:
    """One Dispositivo an entry changes, as written (resolve it with `ligar`)."""

    chave: str  # "art-88", "anexo-i/art-2", "anexo/art-4" (the only annex), "anexo-ii", "item-iii"
    tipo: TipoAlteracao
    a_partir_de: date | None
    detalhe: str | None = None  # "inciso III, alíneas “b”, “c”", "caput", "§§ 1º e 2º"


@dataclass(frozen=True)
class Leitura:
    """What one `atualizacoes` entry says."""

    texto: str
    de: str | None  # the amending norm (upstream ID)
    resultado: Resultado
    motivo: str | None = None
    alvos: tuple[Alvo, ...] = ()
    ausentes: tuple[str, ...] = field(default=())  # targets not found among the norm's Dispositivos (after `ligar`)
    ausentes_detalhe: tuple[tuple[str, TipoAlteracao, date | None], ...] = field(default=())  # (key, type, date)


def _plano(s: str) -> str:
    return s.translate(_PLANO).lower()


def romano_para_int(r: str) -> int | None:
    valores = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100}
    total, anterior = 0, 0
    for ch in reversed(r.lower()):
        v = valores.get(ch)
        if v is None:
            return None
        total = total - v if v < anterior else total + v
        anterior = max(anterior, v)
    return total or None


def _romano(n: int) -> str:
    out = ""
    for v, s in ((100, "c"), (90, "xc"), (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")):
        while n >= v:
            out, n = out + s, n - v
    return out


def _item(tok: str) -> str | None:
    if tok.isdigit():
        return str(int(tok))
    v = romano_para_int(tok)
    return _romano(v) if v else None


def _numero(tok: str) -> tuple[int, str]:
    m = re.match(r"(\d+)(?:o)?\s*(?:-\s*([a-z]{1,2}))?", tok.strip())
    assert m
    return int(m[1]), (m[2] or "")


def _intervalo(a: tuple[int, str], b: tuple[int, str]) -> list[tuple[int, str]]:
    """'2º a 12' -> 2..12; '60-A a 60-I' -> 60-a..60-i. Nonsense ranges (reversed, huge) are just the two ends."""
    (na, sa), (nb, sb) = a, b
    if na == nb and len(sa) <= 1 and len(sb) == 1 and (sa or "a") <= sb:
        letras = "abcdefghijklmnopqrstuvwxyz"
        ini = letras.index(sa) if sa else -1
        return [(na, "")] * (ini < 0) + [(na, letras[i]) for i in range(max(ini, 0), letras.index(sb) + 1)]
    if na < nb and nb - na <= 400 and not sa and not sb:
        return [(n, "") for n in range(na, nb + 1)]
    return [a, b]


def _lista(lista: str, conv) -> list:
    """Expand 'X, Y e Z a W' with `conv` (token -> value) and ranges."""
    partes = re.split(r"(\s*,\s*|\s+e\s+|\s+a\s+|\s+ate\s+)", lista)
    out: list = []
    pendente_intervalo = False
    for p in partes:
        s = p.strip()
        if s in (",", "e", ""):
            pendente_intervalo = False
            continue
        if s in ("a", "ate"):
            pendente_intervalo = True
            continue
        v = conv(s)
        if v is None:
            continue
        if pendente_intervalo and out:
            ini = out.pop()
            out.extend(_intervalo(ini, v) if isinstance(v, tuple) else _intervalo_int(ini, v))
        else:
            out.append(v)
        pendente_intervalo = False
    return out


def _intervalo_int(a, b) -> list:
    """Ranges of items, written in Roman numerals ("ii" a "iv") or digits ("1" a "7")."""
    if isinstance(a, str) and isinstance(b, str):
        dig = a.isdigit() and b.isdigit()
        va, vb = (int(a), int(b)) if dig else (romano_para_int(a), romano_para_int(b))
        if va and vb and va < vb and vb - va <= 100:
            return [str(v) if dig else _romano(v) for v in range(va, vb + 1)]
    return [a, b]


def _data(m: re.Match[str]) -> date | None:
    try:
        if m.re is _DATA_EXTENSO:
            mes = _MESES.get(m[2])
            return date(int(m[3]), mes, int(m[1])) if mes else None
        ano = m[3] if len(m[3]) == 4 else ("20" if int(m[3]) <= 29 else "19") + m[3]
        return date(int(ano), int(m[2]), int(m[1]))
    except ValueError:
        return None


def _anexos(original: str, n: str, ini: int, fim: int) -> list[tuple[int, int, list[str]]]:
    """Annex mentions in n[ini:fim]: (start, end, numbers as written upper case; [""] for an unnumbered annex)."""
    out = []
    for m in _ANEXOS.finditer(n, ini, fim):
        if m["lista"]:
            # numbers must be written in capitals or digits: "anexo à Resolução" is not "Anexo A"
            nums = [
                original[ini_ : ini_ + len(t)].upper()
                for t, ini_ in _tokens(m["lista"], m.start("lista"))
                if original[ini_ : ini_ + len(t)].isupper() or t.isdigit()
            ]
            if nums:
                out.append((m.start(), m.end(), nums))
                continue
            out.append((m.start(), m.start("lista"), [""]))
        else:
            out.append((m.start(), m.end(), [""]))
    for m in _ANEXO_L.finditer(n, ini, fim):
        out.append((m.start(), m.end(), [m["lista"].upper()]))
    for m in _REGULAMENTO.finditer(n, ini, fim):
        if not any(a <= m.start() < b for a, b, _ in out):
            out.append((m.start(), m.end(), [""]))
    return sorted(out)


def _tokens(lista: str, base: int) -> Iterable[tuple[str, int]]:
    for m in re.finditer(r"[a-z\d]+", lista):
        if m[0] not in ("e", "a") or len(lista.strip()) == 1:
            yield m[0], base + m.start()


def _anexo_chave(num: str) -> str:
    return f"anexo-{num.lower()}" if num else "anexo"


_DATA_NO_DETALHE = re.compile(r"[(,]?\s*(?:produzindo\s+efeitos\s+)?a\s+partir\s+d[eoa]\s+[^);]*\)?", re.I)


def _detalhe(original: str, ini: int, fim: int) -> str | None:
    s = _DATA_NO_DETALHE.sub("", original[ini:fim])  # the date is kept apart
    s = s.strip(" ,.;:-–—")
    s = re.sub(r"^(?:e|do|da|no|na)\s+(?=\S)", "", s).strip(" ,.;:")
    s = re.sub(r"\s+(?:e|do|da|no|na)$", "", s).strip(" ,.;:")
    return s or None


def ler(texto: str, norma_id: str, acervo: str = "bcb") -> Leitura:
    """Read one `atualizacoes` entry of the norm `norma_id`."""
    de = autor_da_atualizacao(texto, acervo)
    if de is None:
        nota = plano(texto).startswith("obs")
        return Leitura(texto, None, "nota" if nota else "falha", "observação" if nota else "norma não identificada")
    if de == norma_id:  # upstream data error: the norm named as its own amender (upstream drops these edges too)
        return Leitura(texto, None, "nota", "a própria norma aparece como autora")
    p = plano(texto)
    if _TOTAL.search(p) and not _NAO_TOTAL.search(p):
        return Leitura(texto, de, "norma", "revogação total")

    n = _plano(texto)
    acoes = list(_ACAO.finditer(n))
    if not acoes:
        return Leitura(texto, de, "falha", "ação não reconhecida")
    datas = sorted([*_DATA.finditer(n), *_DATA_EXTENSO.finditer(n)], key=lambda m: m.start())

    def posfixa(m: re.Match[str]) -> bool:
        """'art. 9º (a partir de 6/2/2009)': the date closes its group and is for the targets before it."""
        antes, depois = n[: m.start()].rstrip(), n[m.end() :].lstrip()
        return (antes.endswith(("(", ",")) or antes[-1:].isalnum()) and (depois[:1] in ("", ")", ".", ";"))

    def data_em(pos: int, fim_grupo: int) -> date | None:
        for m in datas:  # a closing date in the same group
            if pos < m.start() < fim_grupo and posfixa(m):
                return _data(m)
        antes = [m for m in datas if m.start() < pos and not posfixa(m)]
        return _data(antes[-1]) if antes else None

    st = _Estado()
    falhas: list[str] = []
    outras = manual = ementa = False
    no_manual = bool(_MANUAL.search(_DATAS.sub(" ", n)))
    for k, m in enumerate(acoes):
        tipo = m.lastgroup
        fim = acoes[k + 1].start() if k + 1 < len(acoes) else len(n)
        if tipo == "outro":
            continue
        # another norm named in the clause: it is about that norm
        citadas = [c for c, _, _ in citar(sem_datas(plano(texto[m.end() : fim])), acervo) if c not in (de, norma_id)]
        if citadas:
            outras = True
            continue
        corpo = _DATAS.sub(" ", n[m.end() : fim])  # dates are not targets
        sem_artigo = not (_ARTIGOS.search(corpo) or _ARTIGO_L.search(corpo) or _ITENS.search(corpo))
        if _MANUAL.search(corpo) or (no_manual and sem_artigo):
            manual = True  # "ALTERACAO: CNC 2/13", then "INCLUSAO: 2/19" in the same manual
            continue
        if re.match(r"\s*total\b", corpo):
            continue  # "prorroga … a data de revogação total": a whole-norm event
        antes = (len(st.alvos), len(st.anexos))
        _clausula(texto, n, m.end(), fim, tipo, data_em, st)  # type: ignore[arg-type]
        if re.search(r"\bementa\b", corpo):
            ementa = True
        if (len(st.alvos), len(st.anexos)) == antes and _PARECE_ALVO.search(corpo):
            falhas.append(texto[m.start() : fim].strip(" .-"))

    # a heading annex no article went into is itself the target ("Alteração do Regulamento anexo")
    alvos = st.alvos + [Alvo(a.chave, a.tipo, a.quando) for a in st.anexos if not a.usado]
    alvos = _juntar(alvos)
    if alvos:
        if falhas:
            return Leitura(texto, de, "parcial", "trecho ilegível: " + " | ".join(falhas)[:300], tuple(alvos))
        return Leitura(texto, de, "dispositivos", None, tuple(alvos))
    if falhas:
        return Leitura(texto, de, "falha", "dispositivo ilegível: " + " | ".join(falhas)[:300])
    if outras:
        return Leitura(texto, de, "nota", "trata de outra norma")
    if manual:
        return Leitura(texto, de, "norma", "manual consolidado (CNC, MNI, MCR…)")
    if ementa:
        return Leitura(texto, de, "norma", "ementa")
    return Leitura(texto, de, "norma", "sem dispositivo indicado")


@dataclass
class _Anexo:
    chave: str
    tipo: TipoAlteracao
    quando: date | None
    usado: bool = False  # articles went into it: it was a heading, not a target


@dataclass
class _Estado:
    alvos: list[Alvo] = field(default_factory=list)
    anexos: list[_Anexo] = field(default_factory=list)  # heading annexes, in order
    escopo: _Anexo | None = None  # the heading annex the following articles belong to


_CONTINUA = re.compile(rf"\s*(?:e\s+)?(?P<lista>{_N}(?:{_SEP}{_N})*)(?![\d/])")
_CABECALHO = re.compile(r"^[\s,]*(?:[-:]|\barts?\b|\bartigos?\b|\bart/)")


def _clausula(original: str, n: str, ini: int, fim: int, tipo: TipoAlteracao, data_em, st: _Estado) -> None:
    """Targets of one clause n[ini:fim], into `st`."""
    grupos, a = [], ini
    for m in re.finditer(";", n[ini:fim]):
        grupos.append((a, ini + m.start()))
        a = ini + m.end()
    grupos.append((a, fim))

    ultimo: int | None = None  # index in st.alvos of the last single-article target, for "; II, “c”" groups
    continua = False  # the previous group listed articles: "arts. 1º; e 5º, incisos II…" goes on
    for gi, gf in grupos:
        artigos = [(m.start(), m.end(), _lista(m["lista"], _numero)) for m in _ARTIGOS.finditer(n, gi, gf)]
        artigos += [(m.start(), m.end(), [_numero(m["lista"])]) for m in _ARTIGO_L.finditer(n, gi, gf)]
        if not artigos and continua and (m := _CONTINUA.match(n, gi, gf)):
            artigos = [(m.start("lista"), m.end(), _lista(m["lista"], _numero))]
        continua = bool(artigos)
        artigos.sort()
        anexos = _anexos(original, n, gi, gf)
        posfixo: str | None = None
        eventos: list[tuple[int, str, object]] = [(x[0], "art", x) for x in artigos]
        for ai, af, nums in anexos:
            if artigos and ai > artigos[0][0] and (_POSFIXO.search(n[gi:ai]) or n[ai - 1 : ai] == "("):
                posfixo = posfixo or _anexo_chave(nums[0])  # "art. 2º do Anexo I", "ART/7 … (REGULAMENTO)"
                continue
            eventos.append((ai, "anexo", (ai, af, nums)))
        eventos.sort(key=lambda e: e[0])
        for _pos, qual, ev in eventos:
            if qual == "anexo":
                ai, af, nums = ev  # type: ignore[misc]
                if _CABECALHO.match(n[af:fim]):  # "Anexo I - Nova redação", "Regulamento anexo: art. 47"
                    st.escopo = _Anexo(_anexo_chave(nums[-1]), tipo, data_em(ai, gf))
                    st.anexos.append(st.escopo)
                else:  # "Nova redação: Anexos I e III"
                    st.alvos.extend(Alvo(_anexo_chave(x), tipo, data_em(ai, gf)) for x in nums)
                    ultimo = None
                continue
            si, sf, lista = ev  # type: ignore[misc]
            base = posfixo
            if base is None and st.escopo is not None:
                base = st.escopo.chave
                st.escopo.usado = True
            depois = [e[0] for e in eventos if e[0] > si]
            det = _detalhe(original, sf, min(depois + [gf])) if len(lista) == 1 else None
            for num, suf in lista:
                chave = f"art-{num}{'-' + suf if suf else ''}"
                st.alvos.append(Alvo(f"{base}/{chave}" if base else chave, tipo, data_em(si, gf), det))
            ultimo = len(st.alvos) - 1 if len(lista) == 1 else None
        if re.search(r"\bpreambulo\b", n[gi:gf]):
            st.alvos.append(Alvo("preambulo", tipo, data_em(gi, gf)))
        if artigos or anexos:
            continue
        itens = [(m.start(), _lista(m["lista"], _item)) for m in _ITENS.finditer(n, gi, gf)]
        itens += [(m.start(), [_item(m["lista"])]) for m in _ITEM_L.finditer(n, gi, gf)]
        if itens:
            for si, lista in sorted(itens):
                st.alvos.extend(Alvo(f"item-{v}", tipo, data_em(si, gf)) for v in lista if v)
            ultimo = None
            continue
        # no target of its own: finer parts of the previous article ("art. 1º, I, “c”; II, “c”")
        resto = _detalhe(original, gi, gf)
        if ultimo is not None and resto:
            x = st.alvos[ultimo]
            st.alvos[ultimo] = replace(x, detalhe=f"{x.detalhe}; {resto}" if x.detalhe else resto)


def _juntar(alvos: list[Alvo]) -> list[Alvo]:
    """One target per (key, type, date); details joined in order."""
    out: dict[tuple, Alvo] = {}
    for a in alvos:
        k = (a.chave, a.tipo, a.a_partir_de)
        if k in out:
            d = [x for x in (out[k].detalhe, a.detalhe) if x]
            out[k] = replace(out[k], detalhe="; ".join(dict.fromkeys(d)) or None)
        else:
            out[k] = a
    return list(out.values())


def ligar(leitura: Leitura, chaves: set[str]) -> Leitura:
    """Match the targets to the amended norm's Dispositivo keys. Annexes are found by number written either way
    (`Anexo 1` = `anexo-i`), an unnumbered annex or article of "the Regulamento" is the norm's only annex, and an
    article missing from the main body is the one in the norm's only annex that has it. What still doesn't match is
    listed in `ausentes` (the splitter may not have found it, or the text upstream doesn't have it)."""
    if not leitura.alvos:
        return leitura
    anexos = sorted({c.split("/")[0] for c in chaves if c.startswith("anexo")})
    out, ausentes = [], []
    for a in leitura.alvos:
        chave = _resolver(a.chave, chaves, anexos)
        if chave:
            out.append(replace(a, chave=chave))
        else:
            ausentes.append(a)
    out = _juntar(out)
    falta = {
        "ausentes": tuple(a.chave for a in ausentes),
        "ausentes_detalhe": tuple((a.chave, a.tipo, a.a_partir_de) for a in ausentes),
    }
    if not out:
        return replace(leitura, resultado="ausente", alvos=(), **falta)
    resultado: Resultado = "parcial" if ausentes or leitura.resultado == "parcial" else "dispositivos"
    return replace(leitura, resultado=resultado, alvos=tuple(out), **falta)


def _resolver(chave: str, chaves: set[str], anexos: list[str]) -> str | None:
    if chave in chaves:
        return chave
    anexo, _, art = chave.rpartition("/") if "/" in chave else ("", "", chave)
    if chave.startswith("anexo") and "/" not in chave:
        anexo, art = chave, ""
    candidatos_anexo = [anexo] if anexo else [""]
    if anexo:
        num = anexo.removeprefix("anexo").removeprefix("-")
        alt = []
        if num.isdigit():
            alt.append(f"anexo-{_romano(int(num))}")
        elif num and (v := romano_para_int(num)):
            alt.append(f"anexo-{v}")
        if not num and len(anexos) == 1:
            alt.append(anexos[0])
        if num and anexos == ["anexo"]:
            alt.append("anexo")  # "Anexo I" of a norm whose only annex has no number
        candidatos_anexo += alt
    for an in candidatos_anexo:
        k = f"{an}/{art}" if an and art else an or art
        if k in chaves:
            return k
    if not anexo and art:
        com = [a for a in anexos if f"{a}/{art}" in chaves]
        if len(com) == 1:
            return f"{com[0]}/{art}"
    return None
