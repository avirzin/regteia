"""Turn what a person types ("Resolução BCB 520", "ICVM 400", "Lei 4.595/1964") into candidate norm IDs.

Pure, deterministic string rules: no database access here. The caller looks the candidates up in order and falls
back to a title search (returning suggestions, never a guess) when none exists.
"""

import re
import unicodedata

_ID = re.compile(r"^[a-z]+:\S+$")
# "<serie words> [nº] <number>[/<year>] [anything else]"
_REF = re.compile(r"^(?P<serie>[a-z][a-z\s/-]*?)[\s.]*(?P<num>\d[\d.]*)(?:\s*/\s*(?P<ano>\d{2,4}))?(?:\b|$)")
_NUMERO = re.compile(r"\b(?:n|no|nr|num|numero)\b\.?")
_LUCENE_SPECIAL = re.compile(r'([+\-&|!(){}\[\]^"~*?:\\/])')

#: Federal acts: words -> id prefix. Federal IDs are "<prefix>:<number>-<year>".
FEDERAIS = {
    "lei complementar": "lcp",
    "lei delegada": "ldl",
    "decreto lei": "del",
    "medida provisoria": "mpv",
    "mp": "mpv",
    "lei": "lei",
    "decreto": "dec",
}

#: BCB series aliases (slug of the typed words -> upstream series). Unlisted slugs are tried as typed.
BCB_ALIASES = {
    "resolucao": ["resolucao-cmn", "resolucao-bcb"],  # old CMN resolutions are titled just "Resolução"
    "res": ["resolucao-cmn", "resolucao-bcb"],
    "res-bcb": ["resolucao-bcb"],
    "res-cmn": ["resolucao-cmn"],
    "resolucao-bacen": ["resolucao-bcb"],
    "in-bcb": ["instrucao-normativa-bcb"],
    "instrucao-normativa": ["instrucao-normativa-bcb"],
    "ato-presidente": ["ato-do-presidente"],
    "ato-presi": ["ato-do-presidente"],
    "circular-bcb": ["circular"],
    "carta-circular-bcb": ["carta-circular"],
}

#: CVM series aliases (slug without "cvm").
CVM_ALIASES = {
    "icvm": ["instrucao"],
    "in": ["instrucao"],
    "res": ["resolucao"],
    "rcvm": ["resolucao"],
    "parecer": ["parecer-de-orientacao"],
    "po": ["parecer-de-orientacao"],
}


def normalizar(texto: str) -> str:
    """Lower case, no accents, "nº"/"n°" removed, punctuation collapsed. Keeps digits, '.', '/' and '-'."""
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    t = _NUMERO.sub(" ", t)
    t = re.sub(r"[^a-z0-9./\-\s]", " ", t)
    t = re.sub(r"(?<=[a-z])\.", " ", t)  # "res. bcb" -> "res bcb"
    t = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", t)  # "ofício-circular" -> "oficio circular"
    return re.sub(r"\s+", " ", t).strip()


def _ano4(ano: str | None) -> str | None:
    if ano is None:
        return None
    if len(ano) == 4:
        return ano
    if len(ano) == 2:
        return ("19" if int(ano) >= 50 else "20") + ano
    return None


def candidatos(ref: str) -> list[str]:
    """Candidate IDs for `ref`, most likely first. Empty when nothing looks like '<series> <number>'."""
    ref = ref.strip()
    if _ID.match(ref):
        return [ref]
    texto = normalizar(ref)
    m = _REF.match(texto)
    if not m:
        return []
    palavras = [p for p in re.split(r"[\s/-]+", m["serie"]) if p]
    num = str(int(m["num"].replace(".", "")))
    ano = _ano4(m["ano"])
    frase = " ".join(palavras)
    out: list[str] = []

    if frase in FEDERAIS:
        if ano:
            out.append(f"{FEDERAIS[frase]}:{num}-{ano}")
        return out

    if "cvm" in palavras or palavras[0] == "icvm":
        joint = {"bcb", "bacen"} & set(palavras)
        resto = [p for p in palavras if p not in ("cvm", "bacen", "bcb")]
        slug = "-".join(resto)
        if joint:
            slug = f"{slug}-bcb"
        series = list(CVM_ALIASES.get(slug, [slug]))
        if "cvm" in palavras and not joint:
            # "Portaria CVM/PTE 10/2021" is cvm:portaria:10-2021: some series drop the issuing unit after "CVM"
            base = "-".join(palavras[: palavras.index("cvm")])
            if base and base not in series:
                series.append(base)
        for s in series:
            if ano:
                out.append(f"cvm:{s}:{num}-{ano}")
            out.append(f"cvm:{s}:{num}")
        return out

    slug = "-".join(palavras)
    if "cmn" in palavras and slug not in BCB_ALIASES:
        slug = "-".join(p for p in palavras if p != "cmn")
        series = ["resolucao-cmn"] if slug == "resolucao" else [f"{slug}-cmn"]
    else:
        series = BCB_ALIASES.get(slug, [slug])
    return [f"bcb:{s}:{num}" for s in series]


def escapar_lucene(texto: str) -> str:
    """Make free text safe for the full-text index (no query syntax)."""
    return _LUCENE_SPECIAL.sub(r"\\\1", texto).strip()


# "art. 88", "artigo 90-A", "item III", "anexo I", "anexo I, art. 2", "preâmbulo"
_DISP = (
    r"(?:anexo(?:\s+(?P<anx>[ivxlc]+|\d+|unico))?(?:\s*,?\s*(?=art))?)?"
    r"(?:art(?:igo)?s?\s*\.?\s*(?P<art>\d+)\s*(?:o\b)?(?:\s*-\s*(?P<suf>[a-z]{1,2})\b)?"
    r"|item\s+(?P<item>[ivxlc]+)|(?P<pre>preambulo))?"
)
_DISP_FIM = re.compile(rf"^(?P<norma>.+?)\s*,?\s+(?P<d>{_DISP})\s*$")
_DISP_INICIO = re.compile(rf"^(?P<d>{_DISP})\s*,?\s+(?:d[oa]s?|,)\s+(?P<norma>.+)$")


def _chave(m: re.Match[str]) -> str | None:
    if not m["d"].strip():
        return None
    if m["pre"]:
        return "preambulo"
    anexo = None
    if "anexo" in m["d"]:
        anexo = "anexo" if not m["anx"] or m["anx"] == "unico" else f"anexo-{m['anx']}"
    if m["art"]:
        art = f"art-{int(m['art'])}" + (f"-{m['suf']}" if m["suf"] else "")
        return f"{anexo}/{art}" if anexo else art
    if m["item"]:
        return f"item-{m['item']}"
    return anexo


def separar_dispositivo(ref: str) -> tuple[str, str | None]:
    """Split a typed reference into (norm reference, Dispositivo key or None).

    "bcb:resolucao-bcb:520#art-88" -> ("bcb:resolucao-bcb:520", "art-88")
    "Resolução BCB 520, art. 88" -> ("resolucao bcb 520", "art-88")
    "art. 2º do Anexo I da Resolução CMN 4.966" is not supported; "Resolução CMN 4.966, anexo I, art. 2" is.
    """
    ref = ref.strip()
    if "#" in ref:
        norma, _, chave = ref.partition("#")
        return norma.strip(), chave.strip().lower() or None
    t = normalizar(ref).rstrip(" .;").replace(",", " , ")
    t = re.sub(r"\s+", " ", t)
    for padrao in (_DISP_INICIO, _DISP_FIM):
        m = padrao.match(t)
        if m and (chave := _chave(m)):
            return m["norma"].strip(" ,"), chave
    return ref, None
