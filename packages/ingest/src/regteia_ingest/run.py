"""One ingest run: for each enabled upstream, sync the clone, plan what changed, validate, write, record the SHA."""

import fcntl
import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from neo4j import Driver

from .config import Settings, Upstream
from .load import writer
from .sources import ctresb_leis, git, normas_grafo

log = logging.getLogger(__name__)

ADAPTERS = {"normas_grafo": normas_grafo.planejar}  # ctresb_leis is planned from the graph: see ingest_leis


class AlreadyRunning(RuntimeError):
    pass


@contextmanager
def lock(upstream_dir: Path) -> Iterator[None]:
    """One ingest at a time per upstream directory (the hourly loop and a manual `full` share the volume)."""
    upstream_dir.mkdir(parents=True, exist_ok=True)
    with (upstream_dir / ".regteia-ingest.lock").open("w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise AlreadyRunning(f"another ingest holds the lock in {upstream_dir}") from None
        yield


def ingest_leis(driver: Driver, settings: Settings, up: Upstream, *, full: bool) -> dict[str, int] | None:
    """ctresb/leis: load the federal acts the BCB/CVM corpora point to. Run after them, since what to load comes from
    the graph; so it is planned even when ctresb/leis didn't move (new BCB norms may cite new laws)."""
    dest = settings.upstream_dir / up.name
    t0 = time.monotonic()
    git.ensure_clone(up, dest)
    new_sha = git.update(dest, up.ref, shallow=up.shallow)
    old_sha, carregadas_v = writer.ultima(driver, up.name)
    full = full or old_sha is None or carregadas_v != writer.versoes()
    carregadas = writer.carregadas(driver, up.name)
    plano = ctresb_leis.planejar(dest, up, new_sha, writer.federais(driver), carregadas, full=full)
    if not full and old_sha == new_sha and not plano.normas and plano.ids_vivos == set(carregadas):
        log.info("%s: up to date at %s", up.name, new_sha[:12])
        return None
    log.info("%s: %s, %d act(s) to read", up.name, "full" if full else "incremental", len(plano.normas))
    stats = writer.aplicar(driver, plano, run=uuid.uuid4().hex)
    writer.registrar(driver, plano)
    log.info("%s: loaded %s at %s in %.1fs", up.name, stats, new_sha[:12], time.monotonic() - t0)
    return stats


def ingest_upstream(driver: Driver, settings: Settings, up: Upstream, *, full: bool) -> dict[str, int] | None:
    if up.adapter == "ctresb_leis":
        return ingest_leis(driver, settings, up, full=full)
    planejar = ADAPTERS.get(up.adapter)
    if planejar is None:
        raise NotImplementedError(f"{up.name}: adapter {up.adapter!r} is not implemented yet")

    dest = settings.upstream_dir / up.name
    t0 = time.monotonic()
    git.ensure_clone(up, dest)
    new_sha = git.update(dest, up.ref, shallow=up.shallow)
    old_sha, carregadas = writer.ultima(driver, up.name)
    atuais = writer.versoes()

    changes = None
    if not full and old_sha is not None and carregadas != atuais:
        log.info(
            "%s: loaded with splitter, atualizacoes parser and citation extractor versions %s, current are %s: "
            "full reload",
            up.name,
            carregadas,
            atuais,
        )
    elif not full and old_sha is not None:
        if old_sha == new_sha:
            log.info("%s: up to date at %s", up.name, new_sha[:12])
            return None
        if git.has_commit(dest, old_sha):
            changes = git.diff(dest, old_sha, new_sha)
        else:
            log.warning("%s: last loaded commit %s is not in history (force push?), full reload", up.name, old_sha)

    mode = "full" if changes is None else f"incremental {old_sha[:12]}..{new_sha[:12]}"
    log.info("%s: %s", up.name, mode)
    plano = planejar(dest, up, new_sha, changes)
    log.info("%s: validated %d norm file(s) in %.1fs", up.name, len(plano.normas), time.monotonic() - t0)

    stats = writer.aplicar(driver, plano, run=uuid.uuid4().hex)
    writer.registrar(driver, plano)
    log.info("%s: loaded %s at %s in %.1fs", up.name, stats, new_sha[:12], time.monotonic() - t0)
    return stats


def ingest(driver: Driver, settings: Settings, upstreams: list[Upstream], *, full: bool) -> bool:
    """Return True if every upstream loaded. One failing upstream does not block the others."""
    ok = True
    with lock(settings.upstream_dir):
        for up in upstreams:
            if not up.enabled:
                log.info("%s: disabled, skipping", up.name)
                continue
            try:
                ingest_upstream(driver, settings, up, full=full)
            except Exception:
                log.exception("%s: ingest failed; last loaded SHA unchanged, will retry next run", up.name)
                ok = False
    return ok
