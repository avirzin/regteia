"""Minimal git plumbing for upstream clones: blobless clone, fetch, detached checkout, diff."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..config import Upstream


class GitError(RuntimeError):
    pass


def _git(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc


def ensure_clone(up: Upstream, dest: Path) -> None:
    if (dest / ".git").exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    args = ["clone", "--quiet", "--filter=blob:none", "--no-checkout"]
    if up.sparse:
        args.append("--sparse")
    _git(*args, up.url, str(dest))
    if up.sparse:
        _git("sparse-checkout", "set", "--no-cone", *up.sparse, cwd=dest)


def update(dest: Path, ref: str) -> str:
    """Fetch and check out `ref` detached. Return the resolved commit SHA."""
    _git("fetch", "--quiet", "--prune", "--tags", "origin", cwd=dest)
    for candidate in (f"origin/{ref}", ref):
        proc = _git("rev-parse", "--verify", "--quiet", f"{candidate}^{{commit}}", cwd=dest, check=False)
        if proc.returncode == 0:
            sha = proc.stdout.strip()
            break
    else:
        raise GitError(f"ref {ref!r} not found in {dest}")
    _git("checkout", "--quiet", "--force", "--detach", sha, cwd=dest)
    return sha


def has_commit(dest: Path, sha: str) -> bool:
    return _git("cat-file", "-e", f"{sha}^{{commit}}", cwd=dest, check=False).returncode == 0


@dataclass(frozen=True)
class Change:
    status: str  # A, M, D, T (renames are disabled, so they show up as D + A)
    path: str


def diff(dest: Path, old: str, new: str) -> list[Change]:
    out = _git("diff", "--name-status", "--no-renames", "-z", old, new, cwd=dest).stdout
    parts = out.split("\0")
    changes = []
    for i in range(0, len(parts) - 1, 2):
        changes.append(Change(status=parts[i][0], path=parts[i + 1]))
    return changes
