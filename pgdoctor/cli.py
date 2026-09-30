from __future__ import annotations

import argparse
import os
import sys

from pgdoctor import engine, render
from pgdoctor.db import connect
from pgdoctor.model import Severity

_SEV_NAMES = {s.label.lower(): s for s in Severity}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pgdoctor",
        description="Health inspector for PostgreSQL.",
    )
    p.add_argument(
        "--dsn",
        default=os.environ.get("PGDOCTOR_DSN") or os.environ.get("DATABASE_URL"),
        help="connection string (or PGDOCTOR_DSN / DATABASE_URL env var)",
    )
    p.add_argument("--format", choices=["console", "json", "html"], default="console")
    p.add_argument("--output", help="write the report to this file instead of stdout")
    p.add_argument("--only", help="comma-separated check keys to run")
    p.add_argument(
        "--fail-on",
        choices=list(_SEV_NAMES),
        default="critical",
        help="exit non-zero when the worst finding is at this level or above",
    )
    p.add_argument("--no-color", action="store_true")
    p.add_argument("--list-checks", action="store_true", help="list checks and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_checks:
        engine._load_checks()
        from pgdoctor.checks.base import all_checks

        for key, name, _ in sorted(all_checks()):
            print(f"{key:24} {name}")
        return 0

    if not args.dsn:
        print("pgdoctor: no DSN given (use --dsn or PGDOCTOR_DSN)", file=sys.stderr)
        return 2

    only = {k.strip() for k in args.only.split(",")} if args.only else None
    opts = {"dsn_label": _safe_label(args.dsn)}

    try:
        with connect(args.dsn) as conn:
            report = engine.run(conn, opts, only=only)
    except Exception as exc:  # noqa: BLE001
        print(f"pgdoctor: could not connect: {exc}", file=sys.stderr)
        return 2

    if args.format == "json":
        text = render.as_json(report)
    elif args.format == "html":
        text = render.html_report(report)
    else:
        text = render.console(report, color=not args.no_color and args.output is None)

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(text)
        print(f"wrote {args.format} report to {args.output}", file=sys.stderr)
    else:
        print(text)

    return engine.exit_code(report, _SEV_NAMES[args.fail_on])


def _safe_label(dsn: str) -> str:
    try:
        from urllib.parse import urlparse

        u = urlparse(dsn)
        if u.hostname:
            host = u.hostname
            port = f":{u.port}" if u.port else ""
            db = u.path.lstrip("/")
            return f"{host}{port}/{db}"
    except Exception:  # noqa: BLE001
        pass
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
