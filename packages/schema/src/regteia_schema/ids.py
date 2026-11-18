"""Norm IDs. We reuse upstream IDs as primary keys and never rewrite them."""

import re

#: Prefixes upstream uses for federal acts (they will become real nodes from ctresb/leis).
FEDERAL_PREFIXES = frozenset({"lei", "lcp", "ldl", "del", "dec", "mpv"})
#: Corpora we ingest as full nodes.
CORPUS_PREFIXES = frozenset({"bcb", "cvm"})
#: Other external references (other regulators, accounting bodies...).
EXTERNAL_PREFIX = "ext"

KNOWN_PREFIXES = FEDERAL_PREFIXES | CORPUS_PREFIXES | {EXTERNAL_PREFIX}

# "<prefix>:<rest>" with no whitespace. Upstream IDs are lower case ASCII, but we only enforce the shape.
_ID = re.compile(r"^(?P<prefix>[a-z]+):\S+$")


def prefixo(norma_id: str) -> str:
    """Return the prefix of a norm ID ("bcb", "lei", ...). Raise ValueError on malformed or unknown prefixes."""
    m = _ID.match(norma_id)
    if not m:
        raise ValueError(f"malformed norm id: {norma_id!r}")
    p = m["prefix"]
    if p not in KNOWN_PREFIXES:
        raise ValueError(f"unknown id prefix {p!r} in {norma_id!r}")
    return p


def validate_id(norma_id: str) -> str:
    prefixo(norma_id)
    return norma_id


_TIPO_FEDERAL = {
    "lei": "Lei",
    "lcp": "Lei Complementar",
    "ldl": "Lei Delegada",
    "del": "Decreto-Lei",
    "dec": "Decreto",
    "mpv": "Medida Provisória",
}
# "lei:14478-2022"; medidas provisórias may carry the reissue number: "mpv:1470-14-1996"
_FEDERAL = re.compile(r"^(?P<p>[a-z]+):(?P<n>\d+)(?:-(?P<r>\d+))?-(?P<a>\d{4})$")


def nome_federal(norma_id: str) -> str | None:
    """Readable name of a federal act from its ID ("lei:14478-2022" -> "Lei nº 14.478/2022"), None otherwise.

    Federal acts are stubs (no title) until ctresb/leis is ingested; this only reformats the ID, it adds nothing.
    """
    m = _FEDERAL.match(norma_id)
    if not m or m["p"] not in _TIPO_FEDERAL:
        return None
    numero = f"{int(m['n']):,}".replace(",", ".")
    reedicao = f"-{m['r']}" if m["r"] else ""
    return f"{_TIPO_FEDERAL[m['p']]} nº {numero}{reedicao}/{m['a']}"
