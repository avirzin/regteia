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
from .parse import dispositivos
from .sources import git, normas_grafo

log = logging.getLogger(__name__)

ADAPTERS = {"normas_grafo": normas_grafo.planejar}


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


def ingest_upstream(driver: Driver, settings: Settings, up: Upstream, *, full: bool) -> dict[str, int] | None:
    planejar = ADAPTERS.get(up.adapter)
    if planejar is None:
        raise NotImplementedError(f"{up.name}: adapter {up.adapter!r} is not implemented yet")

    dest = settings.upstream_dir / up.name
    t0 = time.monotonic()
    git.ensure_clone(up, dest)
    new_sha = git.update(dest, up.ref)
    old_sha, divisao = writer.ultima(driver, up.name)

    changes = None
    if not full and old_sha is not None and divisao != dispositivos.VERSAO:
        log.info(
            "%s: splitter v%s built the loaded Dispositivos, current is v%s: full reload",
            up.name,
            divisao,
            dispositivos.VERSAO,
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
