"""Norms cited in the text of a Dispositivo -> upstream IDs, for `(:Dispositivo)-[:CITA {fonte: "texto"}]->(:Norma)`.

Built on upstream's reference rules (`citacoes.citar`), so a cited norm gets the ID upstream's own edges would give
it. The text of an article differs from the frontmatter fields those rules were written for, and these rules are
added here (ADR 0004):

- Dates in words: "Lei nº 4.595, de 31 de dezembro de 1964" and "Resolução CMN nº 4.966, de 2021" carry the year
  the way "4.595/1964" does.
- The year may be missing, as in "art. 2º da Circular nº 3.978": fine for the BCB and CVM series, whose IDs have no
  year; a reference that needs one (a federal law, `ext:`) and has none is not read.
- The issuer after the number, which upstream doesn't read: "Decisão Conjunta nº 10/2002, do Banco Central do Brasil e
  da Comissão de Valores Mobiliários", "Portaria nº 327/1977, do Ministério da Fazenda", "Ofício Circular nº
  3/2022-CVM/SRE". A "Resolução" dated before 2020 is the CMN's, even in a CVM text or "do Banco Central": the
  Resolução BCB and Resolução CVM series start in 2020.
- Lists of numbers only after a plural ("Resoluções nºs 4.966 e 4.975"): in "Circular nº 3.978/2020, 5 dias" the 5 is
  not a norm. Not a norm either: numbers after a norm apart only by spaces (a table: "Circular nº 3245, de 07 de
  julho de 2004 8 9 10"), "nº 0", and numbers longer than six digits (CNPJs).
- The portal's notes on the consolidated text ("(Redação dada pela Resolução CMN nº 5.100…)", "Documento normativo
  revogado pela…"): they say who amended the norm, which `atualizacoes` and upstream's edges already record, in the
  other direction. Read as citations, every amended article would "cite" its amender.
- The norm itself: "Resolução Nº 589", the portal's heading of Res. BCB 589, is not Res. CMN 589.
"""

import re

from .citacoes import REF_TITULO, TIPOS, _citacao, ano4, ident, plano, sem_datas

VERSAO = 1

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
         "novembro", "dezembro"]  # fmt: skip
_NUM = r"(?<![\d/.])(\d[\d.]*(?:-\d+)?)"
_DATA_EXTENSO = re.compile(_NUM + r",? de (?:\d{1,2}o?|primeiro) de (?:" + "|".join(MESES) + r") de (\d{4})\b")
_DE_ANO = re.compile(_NUM + r",? de (\d{4})\b")
_ORGAOS = [
    (r"conselho monetario nacional|cmn", "cmn"),
    (r"banco central(?: do brasil)?|bacen|bcb", "bcb"),
    (r"comissao de valores mobiliarios|cvm", "cvm"),
    (r"ministerio da fazenda|ministro(?: de estado)? da fazenda|mf", "mf"),
]  # fmt: skip
_ORGAO = "|".join(f"(?:{p})" for p, _ in _ORGAOS)
# ", do Banco Central do Brasil e da Comissão de Valores Mobiliários" right after the number(s)
_ORGAOS_DEPOIS = re.compile(rf" ?,? d[aeo] ((?:{_ORGAO})(?: e d[aeo] (?:{_ORGAO}))*)\b")
_SUPERINTENDENCIA = re.compile(r" ?[-/] ?cvm[ /-](s[a-z]{2})\b")  # "Ofício Circular nº 3/2022-CVM/SRE"
# in running text a list of numbers is "Resoluções nºs 1.234, 1.235 e 1.236"; numbers apart only by spaces are a table
CITA = _citacao(REF_TITULO, sep=r"(?:[,;] ?| e |, e )")


# the portal's notes on the consolidated text: who amended or revoked a passage, already read from `atualizacoes`
# and upstream's edges. "[(Incluído, a partir de 1º/10/2023, pela Resolução CMN nº 5.100, de 24/8/2023.)](https://…)"
_NOTA = re.compile(
    r"\[?\((?:com )?(?:redacao dad[ao]|incluid[ao]s?|acrescid[ao]s?|acrescentad[ao]s?|revogad[ao]s?|renumerad[ao]s?|"
    r"alterad[ao]s?|suprimid[ao]s?|vide)\b[^)]*\)(?:\]\([^)\s]*\))?"
)
_CABECALHO = re.compile(r"^documento normativo [^\n]*$", re.M)  # "Documento normativo revogado pela Circular 164…"


def preparar(texto: str) -> str:
    """Plain text (see `citacoes.plano`) on one line, without the portal's amendment notes, with every date reduced
    to the year after a norm number."""
    t = _CABECALHO.sub(" ", _NOTA.sub(" ", plano(texto)))
    t = re.sub(r"\s+", " ", t)
    t = _DATA_EXTENSO.sub(lambda m: f"{m[1]}/{m[2]}", t)
    t = _DE_ANO.sub(lambda m: f"{m[1]}/{m[2]}", t)
    return sem_datas(t)


def _orgao_depois(tipo: str, depois: str, ano: str, acervo: str) -> str:
    """The issuer(s) named right after the number(s), as `ident` reads issuers ("cmn", "bcb cvm"); "" if none.
    Only used when no issuer comes before the number."""
    if tipo == "oficio-circular" and (m := _SUPERINTENDENCIA.match(depois)):
        return f"cvm {m[1]}"
    nomes = []
    if m := _ORGAOS_DEPOIS.match(depois):
        for nome in re.split(r" e d[aeo] ", m[1]):
            nomes.append(next(sigla for p, sigla in _ORGAOS if re.fullmatch(p, nome)))
    if tipo == "resolucao":
        # the Resolução BCB and Resolução CVM series start in 2020: an earlier "Resolução" is the CMN's (at the BCB
        # the CMN's resolutions were published by the BCB: "Resolução nº 1.289, do Banco Central")
        if nomes == ["bcb"] and not (ano and int(ano) >= 2020):
            return "cmn" if ano else ""  # with no year, upstream's default (the CMN's at the BCB)
        if not nomes and acervo == "cvm" and ano and int(ano) < 2020:
            return "cmn"
    return " ".join(nomes)


def _plural(m: re.Match[str]) -> bool:
    marca = m.string[m.end("orgao") : m.start("refs")]
    return (m["tipo"].endswith("s") and m["tipo"] != "res") or bool(re.search(r"\bn(?:os|s)\b", marca))


def _propria(norma: str, tipo: str, num: str) -> bool:
    """A mention with no issuer of the citing norm's own type and number: the heading "Resolução Nº 589" of Res.
    BCB 589 names itself, not Res. CMN 589."""
    _, serie, numero = norma.split(":", 2)
    n = "-".join(str(int(p)) for p in num.replace(".", "").split("-"))
    return serie.startswith(tipo) and numero.split("-")[0] == n.split("-")[0]


def citacoes(texto: str, norma: str, acervo: str) -> list[str]:
    """Distinct norms cited in `texto`, in order of first mention, without `norma` itself."""
    t = preparar(texto)
    out: dict[str, None] = {}
    for m in CITA.finditer(t):
        tipo = next(nome for p, nome in TIPOS if re.fullmatch(p, m["tipo"]))
        refs = re.findall(REF_TITULO, m["refs"])
        if not _plural(m):
            refs = refs[:1]  # "Circular nº 3.978/2020, 5 dias": a list needs "Circulares" or "nºs"
        orgao = m["orgao"]
        if not orgao.strip():
            ultimo_ano = ano4(refs[-1][1]) if refs and refs[-1][1] else ""
            orgao = " " + _orgao_depois(tipo, t[m.end() :], ultimo_ano, acervo)
        for num, ano in refs:
            if not num.strip("0.-") or len(num.replace(".", "").split("-")[0]) > 6:
                continue  # "nº 0" or "33.700.394": a table of numbers or a CNPJ, not a norm
            i = ident(tipo, orgao, num, ano or "0000", acervo)
            if i.endswith("-0000"):
                continue  # this kind of ID (a federal law, `ext:`) needs the year, and the text doesn't give it
            if i == norma or (not orgao.strip() and _propria(norma, tipo, num)):
                continue
            out.setdefault(i)
    return list(out)
