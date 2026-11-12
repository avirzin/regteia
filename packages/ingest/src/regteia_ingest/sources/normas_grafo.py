"""Adapter for BrunooMoniz/normas-bcb and normas-cvm (same layout, same grafo.py).

Reads an upstream checkout and returns a validated `Plano` (what to write). It never touches the database, and it
validates everything before anything is written: one bad record fails the whole run.
"""

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError
from regteia_schema import (
    ArestaRow,
    EstadoRow,
    ExternoRow,
    Frontmatter,
    NaoResolvidoAlvo,
    NaoResolvidoPadrao,
    Norma,
    parse_nao_resolvido,
)

from ..config import Upstream
from ..parse.frontmatter import FrontmatterError, read_frontmatter
from .git import Change

GRAFO = "grafo"


class UpstreamValidationError(RuntimeError):
    """Raised with every problem found, so a format change upstream is reported in one go."""

    def __init__(self, upstream: str, errors: list[str]):
        self.errors = errors
        shown = "\n  ".join(errors[:30])
        more = f"\n  ... and {len(errors) - 30} more" if len(errors) > 30 else ""
        super().__init__(f"{upstream}: {len(errors)} invalid upstream record(s):\n  {shown}{more}")


@dataclass
class Plano:
    """What one run writes for one upstream. `None` means "unchanged, leave as is"."""

    upstream: str
    sha: str
    full: bool
    normas: list[Norma]
    estados: list[EstadoRow] | None = None
    arestas: list[ArestaRow] | None = None
    externos: list[ExternoRow] | None = None
    nao_resolvidos: list[NaoResolvidoAlvo | NaoResolvidoPadrao] | None = None
    arquivos: int = 0  # files changed upstream (all norm files on a full load)
    ids_vivos: set[str] = field(default_factory=set)  # norm ids backed by a file at `sha`


def is_norm_path(path: str) -> bool:
    """Same rule as upstream's ler_acervo: <serie>/<ano>/<arquivo>.md, outside scripts/, grafo/ and dot/underscore."""
    parts = path.split("/")
    return len(parts) == 3 and path.endswith(".md") and path[0] not in "._" and parts[0] not in ("scripts", GRAFO)


def _read_jsonl[T](path: Path, parse: Callable[[dict], T], errors: list[str]) -> list[T]:
    rows: list[T] = []
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(parse(json.loads(line)))
            except (ValueError, ValidationError) as e:
                errors.append(f"{path.parent.name}/{path.name}:{n}: {_short(e)}")
    return rows


def _short(e: Exception) -> str:
    if isinstance(e, ValidationError):
        return "; ".join(f"{'.'.join(map(str, x['loc'])) or '<root>'}: {x['msg']}" for x in e.errors())
    return str(e)


def url_arquivo(url: str, sha: str, caminho: str) -> str | None:
    """Link to the exact file version, e.g. https://github.com/<o>/<r>/blob/<sha>/<caminho>. None for local paths."""
    if not url.startswith(("https://", "http://")):
        return None
    return f"{url.removesuffix('/').removesuffix('.git')}/blob/{sha}/{caminho}"


def _norma(root: Path, up: Upstream, sha: str, row: EstadoRow) -> Norma:
    fm = Frontmatter.model_validate(read_frontmatter(root / row.caminho))
    return Norma(
        id=row.id,
        acervo=up.acervo,
        orgao=fm.orgao,
        tipo=fm.tipo,
        numero=fm.numero,
        data=fm.data,
        titulo=fm.titulo,
        ementa=fm.ementa or None,
        estado=row.estado,
        revogada=fm.revogada,
        cancelada=fm.cancelada,
        fonte_url=fm.fonte,
        caminho=row.caminho,
        upstream=up.name,
        upstream_sha=sha,
        url_arquivo=url_arquivo(up.url, sha, row.caminho),
        versao_texto=fm.versao_texto,
        publicacao=fm.publicacao,
        responsavel=fm.responsavel,
        baixado_em=fm.baixado_em,
        arquivo=fm.arquivo,
        ocr=fm.ocr,
        temas=fm.temas,
    )


def planejar(root: Path, up: Upstream, sha: str, changes: list[Change] | None) -> Plano:
    """Build the plan for `root` checked out at `sha`. `changes=None` means a full load."""
    errors: list[str] = []
    grafo = root / GRAFO

    estados = _read_jsonl(grafo / "estado.jsonl", EstadoRow.model_validate, errors)
    by_path: dict[str, EstadoRow] = {}
    ids: set[str] = set()
    for e in estados:
        if e.id in ids:
            errors.append(f"grafo/estado.jsonl: duplicate id {e.id}")
        if e.caminho in by_path:
            errors.append(f"grafo/estado.jsonl: duplicate path {e.caminho}")
        ids.add(e.id)
        by_path[e.caminho] = e

    full = changes is None
    if full:
        targets = list(estados)
        grafo_changed = True
        arquivos = len(estados)
    else:
        targets = []
        grafo_changed = False
        for c in changes:
            if c.path.startswith(f"{GRAFO}/"):
                grafo_changed = True
            elif is_norm_path(c.path) and c.status != "D":
                row = by_path.get(c.path)
                if row is None:
                    errors.append(f"{c.path}: norm file changed upstream but is missing from grafo/estado.jsonl")
                else:
                    targets.append(row)
        arquivos = len(changes)

    normas: list[Norma] = []
    for row in targets:
        try:
            normas.append(_norma(root, up, sha, row))
        except (OSError, FrontmatterError, ValidationError) as e:
            errors.append(f"{row.caminho}: {_short(e)}")

    plano = Plano(upstream=up.name, sha=sha, full=full, normas=normas, arquivos=arquivos, ids_vivos=ids)
    if grafo_changed:
        plano.estados = estados
        plano.arestas = _read_jsonl(grafo / "arestas.jsonl", ArestaRow.model_validate, errors)
        plano.externos = _read_jsonl(grafo / "externos.jsonl", ExternoRow.model_validate, errors)
        plano.nao_resolvidos = _read_jsonl(grafo / "nao_resolvidos.jsonl", parse_nao_resolvido, errors)

    if errors:
        raise UpstreamValidationError(up.name, errors)
    return plano
