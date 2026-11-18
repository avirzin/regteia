"""Undo the hard line wrapping that PDF and fixed-width conversions leave inside paragraphs, for display.

Paragraphs are separated by blank lines; a single line break inside one is almost always the source's line width,
not structure. We join those lines, but keep the break whenever the next line starts something of its own (§,
inciso, alínea, item, heading, list, table row) or the previous line closes one (`:` or `;`), so a list typed
without blank lines stays a list. Tables and code blocks are left untouched. The stored text is never changed:
this only shapes what the reader sees, so a rule change needs no reload.
"""

import re

_PARAGRAFOS = re.compile(r"\n[ \t]*\n")
_INICIO = re.compile(
    r"""^\s*(?:
        §                                          # parágrafo
      | art(?:igo)?s?\b\.?                         # Art. 3º, Artigo, Arts.
      | par[áa]grafo\s+[úu]nico
      | [IVXLCDM]+\s*[-–—.)]\s                     # inciso: I -, IV.
      | [a-z]\)\s                                  # alínea: a)
      | \d+(?:\.\d+)*[.)\-–]\s                     # item: 1. 2) 1.1.
      | (?:cap[íi]tulo|se[çc][ãa]o|subse[çc][ãa]o|t[íi]tulo|livro|anexo)\b
      | [-*•>|#]                                   # Markdown list, quote, table, heading
    )""",
    re.IGNORECASE | re.VERBOSE,
)
# roman numerals and section words above are matched case-insensitively; incisos must stay upper case
_INCISO_MINUSCULO = re.compile(r"^\s*[ivxlcdm]+\s*[-–—.)]\s")
_FECHA = (":", ";")
_ALINEA = re.compile(r"^\s*[a-z]\)\s")
# a hyphen at the end of a line is either a word split by the line width ("encami-/nhadas") or a real one: keep it
# before a pronoun ("considerando-/se") or after a prefix ("pré-/pagamento"), drop it otherwise
# only prefixes that always take a hyphen; "pro", "pró", "ex", "sub", "sem"… are also plain syllables ("pro-posta",
# "pró-prio")
_PREFIXOS = frozenset({"pré", "pós", "vice", "recém", "além", "aquém", "grã", "grão", "não"})
_PALAVRA_FINAL = re.compile(r"([^\W\d_]+)-$")
_ESPACOS = re.compile(r"(?<=\S) {2,}")


def _pronome(antes: str, depois: str) -> bool:
    """Whether "antes-/depois" is a verb with a pronoun ("acatando-se", "aplica-se", "fazê-lo"), not a syllable
    split ("ba-se", "pe-los", "exclusivamen-te")."""
    antes, depois = antes.lower(), depois.lower()
    if depois in ("lhe", "lhes"):
        return True
    if depois == "se":
        return len(antes) >= 4 and antes[-1] in "aeoãõm"
    return depois in ("lo", "la", "los", "las") and antes[-1] in "áéêíóô"


def _maiusculas(linha: str) -> bool:
    """A heading line in capitals ("DAS DISPOSIÇÕES GERAIS")."""
    letras = [c for c in linha if c.isalpha()]
    return len(letras) >= 3 and sum(c.isupper() for c in letras) / len(letras) >= 0.8


def _recuo(linha: str) -> int:
    return len(linha) - len(linha.lstrip(" "))


def _quebra(anterior: str, linha: str) -> bool:
    """Whether the break between `anterior` and `linha` is structure (keep it) rather than wrapping."""
    if not anterior.strip() or not linha.strip():
        return True
    minuscula = linha.lstrip()[:1].islower()
    if minuscula and _PALAVRA_FINAL.search(anterior.rstrip()):
        return False  # a word split across lines
    if anterior.rstrip().endswith(_FECHA) or _ALINEA.match(linha):
        return True
    if minuscula:
        return False  # the sentence goes on (also under hanging indents and after lines in capitals)
    if _INICIO.match(linha) and not _INCISO_MINUSCULO.match(linha):
        return True
    if _maiusculas(anterior) or _maiusculas(linha):
        return True
    return _recuo(linha) >= _recuo(anterior) + 2  # fixed-width texts indent a new paragraph


def _paragrafo(p: str) -> str:
    linhas = p.split("\n")
    if any(x.lstrip().startswith(("|", "```")) for x in linhas):
        return p
    out = linhas[0].rstrip()
    for anterior, linha in zip(linhas, linhas[1:], strict=False):
        if _quebra(anterior, linha):
            out += "\n" + linha.rstrip()
        elif (m := _PALAVRA_FINAL.search(out)) and linha.lstrip()[:1].islower():
            seguinte = re.match(r"[^\W\d_]+", linha.lstrip())
            real = m[1].lower() in _PREFIXOS or bool(seguinte and _pronome(m[1], seguinte[0]))
            out = (out if real else out[:-1]) + linha.strip()
        else:
            out += " " + linha.strip()
    # justified fixed-width text pads words with spaces; indentation at the start of a line stays
    return "\n".join(_ESPACOS.sub(" ", x) for x in out.split("\n"))


def desquebrar(texto: str) -> str:
    """`texto` with the wrapping line breaks inside each paragraph joined; blank lines and structure kept."""
    if not texto or "\n" not in texto:
        return texto
    return "\n\n".join(_paragrafo(p) for p in _PARAGRAFOS.split(texto))
