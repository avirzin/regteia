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
