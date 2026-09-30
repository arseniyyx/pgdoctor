from __future__ import annotations

import psycopg

from pgdoctor.checks.base import check
from pgdoctor.db import extension_installed, query
from pgdoctor.model import CheckResult, Finding, Severity


@check("slow_queries", "Slowest queries")
def slow_queries(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("slow_queries", "Slowest queries")
    if not extension_installed(conn, "pg_stat_statements"):
        res.skipped = "pg_stat_statements not installed"
        return res
    limit = opts.get("slow_query_limit", 10)
    rows = query(
        conn,
        """
        SELECT round(mean_exec_time::numeric, 2) AS mean_ms,
               calls,
               round(total_exec_time::numeric, 2) AS total_ms,
               left(regexp_replace(query, '\\s+', ' ', 'g'), 120) AS query
        FROM pg_stat_statements
        ORDER BY mean_exec_time DESC
        LIMIT %s
        """,
        (limit,),
    )
    if rows:
        sev = Severity.WARNING if rows[0]["mean_ms"] and rows[0]["mean_ms"] > 100 else Severity.INFO
        res.findings.append(
            Finding(sev, f"Top {len(rows)} queries by mean execution time", "", rows)
        )
    return res
