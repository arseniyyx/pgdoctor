from __future__ import annotations

import importlib
import pkgutil

import psycopg

import pgdoctor.checks as checks_pkg
from pgdoctor.checks.base import all_checks
from pgdoctor.db import query
from pgdoctor.model import CheckResult, Report, Severity


def _load_checks() -> None:
    for mod in pkgutil.iter_modules(checks_pkg.__path__):
        if mod.name != "base":
            importlib.import_module(f"pgdoctor.checks.{mod.name}")


def run(conn: psycopg.Connection, opts: dict, only: set[str] | None = None) -> Report:
    _load_checks()
    dbname = query(conn, "SELECT current_database() AS d")[0]["d"]
    report = Report(dsn_label=opts.get("dsn_label", ""), database=dbname)
    for key, name, fn in all_checks():
        if only and key not in only:
            continue
        try:
            report.results.append(fn(conn, opts))
        except psycopg.Error as exc:
            r = CheckResult(key, name)
            r.skipped = f"error: {str(exc).strip()}"
            report.results.append(r)
    report.results.sort(key=lambda r: (-r.max_severity, r.key))
    return report


def exit_code(report: Report, fail_on: Severity) -> int:
    return 1 if report.max_severity >= fail_on else 0
