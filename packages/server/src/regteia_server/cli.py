"""regteia-server: the local API + web app on http://127.0.0.1:8080."""

import argparse
import os

import uvicorn


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="regteia-server", description=__doc__)
    p.add_argument("--port", type=int, default=int(os.environ.get("REGTEIA_SERVER_PORT", "8080")))
    p.add_argument("--reload", action="store_true", help="restart on code changes (development)")
    args = p.parse_args(argv)
    # Always 127.0.0.1 on the host. Inside the compose container REGTEIA_SERVER_HOST=0.0.0.0 is needed for Docker's
    # port publishing; docker-compose.yml publishes that port on 127.0.0.1 only.
    host = os.environ.get("REGTEIA_SERVER_HOST", "127.0.0.1")
    uvicorn.run("regteia_server.app:create_app", factory=True, host=host, port=args.port, reload=args.reload)
