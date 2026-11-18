"""Norm references in free text -> upstream IDs ("Resolução BCB nº 589/2026" -> "bcb:resolucao-bcb:589").

Ported from upstream's scripts/grafo.py (normas-bcb 39dfccf0, MIT, Bruno Moniz) so that the norm we name for an
`atualizacoes` entry is exactly the one upstream's own edges name: same normalization, same type table, same ID
rules. Keep it in step with upstream when its rules change; tests/unit/test_citacoes.py pins real cases.
Step 8 (body-text citations) reuses `citar`.
"""

import re
import unicodedata

LEIS = frozenset({"lei", "lcp", "ldl", "del", "dec", "mpv"})

# pattern in plain text -> type; most specific first
TIPOS = [
    (r"leis? complementar(?:es)?", "lcp"), (r"leis? delegadas?", "ldl"), (r"decretos? leis?|dl", "del"),
    (r"medidas? provisorias?|mpv?", "mpv"), (r"decretos?|dec", "dec"), (r"leis?", "lei"),
    (r"res[ou]luc(?:ao|oes) conjuntas?", "resolucao-conjunta"), (r"res[ou]luc(?:ao|oes)|res", "resolucao"),
    (r"instruc(?:ao|oes) normativas? conjuntas?", "instrucao-normativa-conjunta"),
    (r"instruc(?:ao|oes) normativas?", "instrucao-normativa"),
    (r"notas? explicativas? a resolucao", "nota-explicativa-resolucao"),
    (r"notas? explicativas?(?: a instrucao)?", "nota-explicativa"), (r"instruc(?:ao|oes)", "instrucao"),
    (r"oficios? circular(?:es)?", "oficio-circular"),
    (r"cartas? circ(?:ular(?:es)?)?", "carta-circular"), (r"circ(?:ular(?:es)?)?", "circular"),
    (r"comunicados? conjuntos?", "comunicado-conjunto"), (r"comunicados?", "comunicado"),
    (r"deliberac(?:ao|oes)", "deliberacao"), (r"parecer(?:es)? de orientacao", "parecer-de-orientacao"),
    (r"portarias? conjuntas?", "portaria-conjunta"), (r"port(?:arias?)?", "portaria"),
    (r"decis(?:ao|oes) conjuntas?", "decisao-conjunta"), (r"atos? normativos? conjuntos?", "ato-normativo-conjunto"),
    (r"atos? do presidente", "ato-do-presidente"), (r"atos? de diretor", "ato-de-diretor"),
]  # fmt: skip
NUM = r"(\d[\d.]*(?:-\d+)?)"
REF = NUM + r" ?/+ ?(\d{4}|\d{2})(?![\d/])"  # 4.903/2021, 555/14, 1790//98, 2050-11/2000
REF_TITULO = NUM + r"(?: ?/+ ?(\d{4}|\d{2}))?(?![\d/])"  # the year may be missing
DATA = re.compile(r"\b(\d{1,2})o?[/.](\d{1,2})[/.](\d{4}|\d{2})\b")


def _citacao(ref: str) -> re.Pattern[str]:
    """type + optional issuer ('BCB', 'BACEN/CVM') + optional 'nº'/'ns.' + a list of numbers."""
    ref = re.sub(r"\((?!\?)", "(?:", ref)
    return re.compile(
        r"\b(?P<tipo>" + "|".join(p for p, _ in TIPOS) + r")\b(?P<orgao>(?: (?:d[aeo] )?[a-z]{2,8}){0,4}?)"
        r" ?(?:n(?:os?|s)?\b\.? ?)?(?P<refs>" + ref + r"(?:(?:[ ,;]| e )+" + ref + r")*)"
    )


CITA, CITA_TITULO = _citacao(REF), _citacao(REF_TITULO)


def plano(s: str) -> str:
    """Lower case without accents; 'Carta-Circular', 'BCB/CVM' and 'LEI/COMPLEMENTAR' become separate words."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"(?<=[a-z])[-/]+(?=[a-z])", " ", s)


def ano4(a: str) -> str:
    # two digits up to 29 are 20xx (the series here start after 1930); upstream says to revisit in 2030
    return a if len(a) == 4 else ("20" if int(a) <= 29 else "19") + a


def sem_datas(t: str) -> str:
    """Drop dates so they don't read as norm numbers; first 'Carta Circular 53 de 6/12/1971' becomes '53/1971'."""
    t = re.sub(r"(?<![\d/.])(\d[\d.]*),? de " + DATA.pattern, lambda m: f"{m[1]}/{m[4]}", t)
    return DATA.sub(" ", t)


_SERIES_BCB = ("circular", "carta-circular", "comunicado", "instrucao-normativa", "ato-do-presidente", "ato-de-diretor")
_SERIES_CVM = ("instrucao", "deliberacao", "parecer-de-orientacao", "nota-explicativa", "nota-explicativa-resolucao")


def ident(tipo: str, orgao: str, num: str, ano: str, acervo: str) -> str:
    """Upstream ID: 'bcb:resolucao-cmn:4903', 'cvm:instrucao:555', 'lei:4595-1964'."""
    o = [
        ("bcb" if p in ("bacen", "bc") else p)
        for p in orgao.replace("banco central do brasil", "bcb").split()
        if p not in ("da", "de", "do")
    ]
    n = "-".join(str(int(p)) for p in num.replace(".", "").split("-"))
    na = f"{n}-{ano4(ano)}"
    cvm = acervo == "cvm"
    if tipo in LEIS:
        return f"{tipo}:{na}"
    if tipo.endswith(("conjunta", "conjunto")):
        if cvm:
            return f"cvm:{'-'.join([tipo] + [p for p in o if p != 'cvm'])}:{na}"
        if not o or {"bcb", "cmn"} & set(o):
            return f"bcb:{tipo}:{n}"
    elif tipo == "resolucao":
        for sigla, serie in (
            ("cvm", "cvm:resolucao"),
            ("cmn", "bcb:resolucao-cmn"),
            ("bcb", "bcb:resolucao-bcb"),
            ("coseg", "bcb:resolucao-coseg"),
            ("coremec", "bcb:resolucao-coremec"),
        ):
            if sigla in o:
                return f"{serie}:{n}"
        if not o:  # no issuer: at the BCB it is the CMN series; at the CVM, Resolução CVM
            return f"cvm:resolucao:{n}" if cvm else f"bcb:resolucao-cmn:{n}"
    elif tipo in (
        "circular",
        "carta-circular",
        "comunicado",
        "instrucao-normativa",
        "ato-do-presidente",
        "ato-de-diretor",
    ):
        if set(o) <= {"bcb"}:
            return f"bcb:{tipo}{'-bcb' if tipo == 'instrucao-normativa' else ''}:{n}"
    elif tipo in (
        "instrucao",
        "deliberacao",
        "parecer-de-orientacao",
        "nota-explicativa",
        "nota-explicativa-resolucao",
    ):
        if "cvm" in o or (cvm and not o):
            return f"cvm:{tipo}:{n}"
    elif cvm and tipo == "portaria" and set(o) <= {"cvm", "pte"}:
        return f"cvm:portaria:{na}"
    elif cvm and tipo == "oficio-circular":
        return f"cvm:{'-'.join([tipo] + [p for p in o if p != 'cvm'])}:{na}"
    return f"ext:{'-'.join([tipo] + o)}:{na}"  # another body's norm: no corpus to look it up in


def citar(t: str, acervo: str, ano_padrao: str | None = None) -> list[tuple[str, int, int]]:
    """Norms cited in a plain text (see `plano`): [(id, start, end)]. With `ano_padrao` the year is optional."""
    out = []
    for m in (CITA_TITULO if ano_padrao else CITA).finditer(t):
        tipo = next(nome for p, nome in TIPOS if re.fullmatch(p, m["tipo"]))
        for num, ano in re.findall(REF_TITULO if ano_padrao else REF, m["refs"]):
            out.append((ident(tipo, m["orgao"], num, ano or ano_padrao or "0000", acervo), m.start(), m.end()))
    return out


def autor_da_atualizacao(item: str, acervo: str = "bcb") -> str | None:
    """The norm that made an `atualizacoes` entry (it comes first), as upstream reads it; None for notes ('OBS: …')
    and entries without a recognizable norm."""
    t = plano(item)
    t2 = sem_datas(t)
    # the year may be missing at the start ('Resolução BCB nº 33 - Revogação total')
    cs = citar(t2, acervo) or [c for c in citar(t2, acervo, "0000")[:1] if c[1] == 0 and c[0].startswith("bcb:")]
    if not cs or t.startswith("obs"):
        return None
    return cs[0][0]
