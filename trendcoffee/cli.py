"""One command for setup, HTTP, MCP and repeatable local benchmarks."""

import argparse
import json
import os
from pathlib import Path

from .merchant import from_environment
from .service import Service


def bundle_path():
    project = Path(__file__).resolve().parent.parent / "data/trendcoffee-public.json"
    return project if project.exists() else Path(__file__).parent / "data/trendcoffee-public.json"


def main(argv=None):
    parser = argparse.ArgumentParser(prog="trendcoffee")
    parser.add_argument(
        "command", choices=["init", "serve", "mcp", "import", "sync-public", "benchmark"]
    )
    parser.add_argument("--db", default=os.environ.get("TREND_DB", ".runtime/trendcoffee.db"))
    parser.add_argument("--bundle", default=str(bundle_path()))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--requests", type=int, default=300)
    args = parser.parse_args(argv)
    service = Service(args.db, merchant=from_environment())
    if args.command in ["init", "import"]:
        service.ingest(json.loads(Path(args.bundle).read_text()))
        print(json.dumps({"imported": True, "menu_items": len(service.menu()), "db": args.db}))
    elif args.command == "sync-public":
        from .ingest import sync_public

        bundle = sync_public()
        service.ingest(bundle)
        print(
            json.dumps(
                {
                    "refreshed": True,
                    "menu_items": len(service.menu()),
                    "source": bundle["source_url"],
                }
            )
        )
    elif args.command == "serve":
        import uvicorn

        from .api import create_app
        from .semantic import from_environment as semantic_from_environment

        if not service.menu():
            service.ingest(json.loads(Path(args.bundle).read_text()))
        uvicorn.run(
            create_app(service=service, semantic=semantic_from_environment()),
            host=args.host,
            port=args.port,
            ws_max_size=300000,
        )
    elif args.command == "mcp":
        from .mcp_server import create_server

        # All diagnostics go to stderr; stdout belongs exclusively to MCP JSON-RPC.
        if not service.menu() and Path(args.bundle).exists():
            service.ingest(json.loads(Path(args.bundle).read_text()))
        create_server(service).run(transport="stdio")
    elif args.command == "benchmark":
        from .benchmark import run

        print(json.dumps(run(requests=args.requests), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
