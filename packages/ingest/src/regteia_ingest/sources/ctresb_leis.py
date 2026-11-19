"""Adapter for ctresb/leis: the federal acts that BCB/CVM norms point to, as real nodes with text (ADR 0005).

The repo is huge (~1.49M files: federal, state and municipal acts, other regulators, treaties) and has no graph of
its own. We list its trees (no file content), resolve the federal IDs our graph already references to paths, and
check out only those files. A federal act nothing in the BCB/CVM corpora points to is never loaded.
"""

import logging
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError
from regteia_schema import Estado, LeiFrontmatter, Norma, prefixo

from ..config import Upstream
from ..parse.frontmatter import FrontmatterError, read_frontmatter
from . import git
from .normas_grafo import Plano, UpstreamValidationError, url_arquivo

log = logging.getLogger(__name__)

#: ID prefix -> folder. Folders starting with "_" are the maintainer's work in progress and are never read.
PASTAS = {
    "lei": "federal/leis-ordinarias",
    "lcp": "federal/leis-complementares",
    "ldl": "federal/leis-delegadas",
    "del": "federal/decretos-lei",
    "dec": "federal/decretos",
    "mpv": "federal/medidas-provisorias",
}
# federal/<folder>/<year>/<prefix>-<number>[-<reissue>]-<yyyy>-<mm>-<dd>.md ("mpv-2200-2-2001-08-24.md")
_ARQUIVO = re.compile(
    r"^federal/[^/_][^/]*/\d{4}/(?P<p>[a-z]+)-(?P<n>\d+)(?:-(?P<r>\d+))?-(?P<a>\d{4})-\d{2}-\d{2}\.md$"
)
_ID = re.compile(r"^(?P<p>[a-z]+):(?P<n>\d+)(?:-(?P<r>\d+))?-(?P<a>\d{4})$")
ORGAO = {
    "lei": "Congresso Nacional",
    "lcp": "Congresso Nacional",
    "ldl": "Presidência da República",
    "del": "Presidência da República",
    "dec": "Presidência da República",
    "mpv": "Presidência da República",
}


@dataclass(frozen=True)
class Arquivo:
    caminho: str
    reedicao: bool = False  # an MP cited without its reissue number, resolved to its last reissue


def resolver(ids: set[str], caminhos: list[str]) -> dict[str, Arquivo]:
    """The file of each federal ID, where ctresb/leis has one. "mpv:2158-2001" (no reissue number) is the last
    reissue that year ("mpv-2158-35-2001-08-24.md"): the one that stayed in force under EC 32/2001."""
    exatos: dict[str, str] = {}
    reedicoes: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for c in sorted(caminhos):
        m = _ARQUIVO.match(c)
        if not m or PASTAS.get(m["p"]) != c.rsplit("/", 2)[0]:
            continue
        chave = f"{m['p']}:{m['n']}{'-' + m['r'] if m['r'] else ''}-{m['a']}"
        exatos.setdefault(chave, c)
        if m["p"] == "mpv" and m["r"]:
            reedicoes.setdefault((m["n"], m["a"]), []).append((int(m["r"]), c))
    out = {}
    for i in ids:
        if i in exatos:
            out[i] = Arquivo(exatos[i])
            continue
        m = _ID.match(i)
        if m and m["p"] == "mpv" and not m["r"] and (rs := reedicoes.get((m["n"], m["a"]))):
            out[i] = Arquivo(max(rs)[1], reedicao=True)
    return out


def estado(fm: LeiFrontmatter) -> tuple[Estado, str | None]:
    """In force or not, and why, from what the file says. Conservative: an act is in force only when the source says
    it is not revoked and nothing else says it lost effect; with no information it is `sem_informacao`."""
    situacao = (fm.situacao or "").strip().rstrip(".")
    s = situacao.lower()
    if fm.revogada is True or s.startswith("revogad"):
        return Estado.REVOGADA, situacao or None
    if s.startswith(("reeditada", "convertida")):
        return Estado.REVOGADA, situacao  # a reissued or converted MP lost effect
    if "NotInForce" in (fm.forca_legal_fonte or []):
        return Estado.REVOGADA, "sem vigência segundo os metadados de normas.leg.br"
    if fm.revogada is False:
        return Estado.VIGENTE, situacao or None
    return Estado.SEM_INFORMACAO, None


def _norma(root: Path, up: Upstream, sha: str, id_: str, arquivo: Arquivo) -> Norma:
    fm = LeiFrontmatter.model_validate(read_frontmatter(root / arquivo.caminho))
    est, motivo = estado(fm)
    p = prefixo(id_)
    return Norma(
        id=id_,
        acervo=p,
        orgao=ORGAO[p],
        tipo=fm.tipo,
        numero=fm.numero,
        data=fm.data,
        titulo=fm.titulo,
        ementa=fm.ementa or None,
        estado=est,
        revogada=fm.revogada,
        cancelada=False,
        fonte_url=fm.fonte,
        caminho=arquivo.caminho,
        upstream=up.name,
        upstream_sha=sha,
        url_arquivo=url_arquivo(up.url, sha, arquivo.caminho),
        versao_texto=fm.versao_texto,
        publicacao=None,
        responsavel=None,
        baixado_em=fm.baixado_em,
        arquivo=None,
        ocr=False,
        temas=None,
        urn=fm.urn,
        estado_motivo=motivo,
    )


def planejar(
    root: Path, up: Upstream, sha: str, desejados: set[str], carregadas: dict[str, str], *, full: bool
) -> Plano:
    """Plan the federal acts in `desejados` (IDs the BCB/CVM corpora point to). `carregadas`: the ones already loaded,
    id -> the commit they were read at. A file is read again when the commit changed (the clone is shallow, so there
    is no diff to narrow it down) or on a full load; acts no longer wanted go back to stubs."""
    arquivos = resolver(desejados, git.listar(root, sha, list(PASTAS.values())))
    git.restringir(root, [a.caminho for a in arquivos.values()], sha)
    faltam = len(desejados) - len(arquivos)
    log.info(
        "%s: %d of %d referenced federal acts have a file (%d stay stubs)",
        up.name,
        len(arquivos),
        len(desejados),
        faltam,
    )

    errors: list[str] = []
    normas: list[Norma] = []
    for i, a in sorted(arquivos.items()):
        if not full and carregadas.get(i) == sha:
            continue
        try:
            normas.append(_norma(root, up, sha, i, a))
        except (OSError, FrontmatterError, ValidationError) as e:
            errors.append(f"{a.caminho}: {e}")
    if errors:
        raise UpstreamValidationError(up.name, errors)
    return Plano(
        upstream=up.name,
        sha=sha,
        full=full,
        normas=normas,
        arquivos=len(normas),
        ids_vivos=set(arquivos),
        root=root,
        podar=True,
        cita_cria_stubs=False,
    )
