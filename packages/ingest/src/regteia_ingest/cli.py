"""regteia-ingest: migrate | full | incremental | status."""

import argparse
import logging
import sys
import time

from neo4j import Driver, GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from .config import Settings, load_upstreams
from .load import writer
from .migrate import migrate
from .run import AlreadyRunning, ingest


def _driver(settings: Settings, wait: float = 60) -> Driver:
    driver = GraphDatabase.driver(
        settings.neo4j_uri,
        auth=(settings.neo4j_user, settings.neo4j_password),
        notifications_min_severity="OFF",
    )
    deadline = time.monotonic() + wait
    while True:
        try:
            driver.verify_connectivity()
            return driver
        except ServiceUnavailable:
            if time.monotonic() > deadline:
                raise
            time.sleep(2)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="regteia-ingest", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("migrate", help="apply db/migrations")
    for name, help_ in (
        ("full", "reload every upstream from scratch (idempotent)"),
        ("incremental", "load only what changed since the last loaded upstream SHA"),
    ):
        sp = sub.add_parser(name, help=help_)
        sp.add_argument("--only", action="append", metavar="NAME", help="limit to these upstreams")
    sub.add_parser("status", help="show the last loaded SHA per upstream")
    args = p.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("neo4j").setLevel(logging.WARNING)
    settings = Settings.from_env()
    upstreams = load_upstreams(settings.upstreams_file)

    with _driver(settings) as driver:
        if args.cmd == "status":
            for up in upstreams:
                print(f"{up.name:12} {'enabled ' if up.enabled else 'disabled'} {writer.last_sha(driver, up.name)}")
            return 0
        migrate(driver, settings.migrations_dir)
        if args.cmd == "migrate":
            return 0
        if args.only:
            unknown = set(args.only) - {u.name for u in upstreams}
            if unknown:
                p.error(f"unknown upstream(s): {sorted(unknown)}")
            upstreams = [u for u in upstreams if u.name in args.only]
        try:
            ok = ingest(driver, settings, upstreams, full=args.cmd == "full")
        except AlreadyRunning as e:
            logging.error("%s", e)
            return 75  # EX_TEMPFAIL
        return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
