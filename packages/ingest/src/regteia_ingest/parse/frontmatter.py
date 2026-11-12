"""Upstream's frontmatter format: a `---` block of `key: value` lines, where the value is JSON when it starts with
`"` or `[` and raw text otherwise. It is not YAML; parse it line by line like upstream's grafo.py does, but strictly:
anything unexpected raises instead of falling back."""

import json
from collections.abc import Iterable
from pathlib import Path


class FrontmatterError(ValueError):
    pass


def parse_frontmatter(lines: Iterable[str]) -> dict[str, object]:
    it = iter(lines)
    first = next(it, None)
    if first is None or first.rstrip("\r\n") != "---":
        raise FrontmatterError("file does not start with a '---' frontmatter block")
    out: dict[str, object] = {}
    for n, raw in enumerate(it, start=2):
        line = raw.rstrip("\r\n")
        if line == "---":
            return out
        key, sep, value = line.partition(": ")
        if not sep or not key:
            raise FrontmatterError(f"line {n}: expected 'key: value', got {line[:80]!r}")
        if key in out:
            raise FrontmatterError(f"line {n}: duplicate key {key!r}")
        if value[:1] in ('"', "["):
            try:
                out[key] = json.loads(value)
            except json.JSONDecodeError as e:
                raise FrontmatterError(f"line {n}: invalid JSON for {key!r}: {e}") from None
        else:
            out[key] = value
    raise FrontmatterError("frontmatter block is not closed with '---'")


def read_frontmatter(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8") as f:
        return parse_frontmatter(f)


def read_norma(path: Path) -> tuple[dict[str, object], str]:
    """Frontmatter and body (the Markdown after the closing `---`) of a norm file."""
    with path.open(encoding="utf-8") as f:
        fm = parse_frontmatter(f)
        return fm, f.read()
