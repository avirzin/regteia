"""Ingest settings, from environment variables only (see regteia_schema.env)."""

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from regteia_schema.env import neo4j_settings


@dataclass(frozen=True)
class Settings:
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    upstream_dir: Path
    upstreams_file: Path
    migrations_dir: Path

    @classmethod
    def from_env(cls) -> "Settings":
        uri, user, password = neo4j_settings()
        return cls(
            neo4j_uri=uri,
            neo4j_user=user,
            neo4j_password=password,
            upstream_dir=Path(os.environ.get("REGTEIA_UPSTREAM_DIR", "_upstream")).resolve(),
            upstreams_file=Path(os.environ.get("REGTEIA_UPSTREAMS", "upstreams.toml")).resolve(),
            migrations_dir=Path(os.environ.get("REGTEIA_MIGRATIONS_DIR", "db/migrations")).resolve(),
        )


class Upstream(BaseModel):
    """One `[[upstream]]` entry in upstreams.toml."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    url: str  # git URL or local path
    ref: str  # branch, tag or commit SHA
    adapter: str
    acervo: str
    sparse: list[str] | None = None
    enabled: bool = True


def load_upstreams(path: Path) -> list[Upstream]:
    with path.open("rb") as f:
        data = tomllib.load(f)
    ups = [Upstream.model_validate(u) for u in data.get("upstream", [])]
    names = [u.name for u in ups]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate upstream names in {path}")
    return ups
