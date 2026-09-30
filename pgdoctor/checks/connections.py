from __future__ import annotations

import psycopg

from pgdoctor.checks.base import check
from pgdoctor.db import query, scalar
from pgdoctor.model import CheckResult, Finding, Severity


@check("connections", "Connection usage")
def connections(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("connections", "Connection usage")
    used = scalar(conn, "SELECT count(*) FROM pg_stat_activity")
    limit = int(scalar(conn, "SHOW max_connections"))
    ratio = used / limit if limit else 0
    detail = f"{used} of {limit} connections in use ({ratio:.0%})"
    if ratio >= 0.9:
        sev = Severity.CRITICAL
    elif ratio >= 0.75:
        sev = Severity.WARNING
    else:
        sev = Severity.INFO
    res.findings.append(Finding(sev, "Connection usage", detail))
    return res


@check("idle_in_transaction", "Idle-in-transaction sessions")
def idle_in_transaction(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("idle_in_transaction", "Idle-in-transaction sessions")
    threshold = opts.get("idle_txn_seconds", 60)
    rows = query(
        conn,
        """
        SELECT pid, usename, state,
               EXTRACT(EPOCH FROM (now() - state_change))::int AS idle_seconds,
               left(coalesce(query, ''), 100) AS query
        FROM pg_stat_activity
        WHERE state = 'idle in transaction'
          AND now() - state_change > make_interval(secs => %s)
        ORDER BY idle_seconds DESC
        """,
        (threshold,),
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.WARNING,
                f"{len(rows)} session(s) idle in transaction over {threshold}s",
                "Long idle transactions hold locks and block autovacuum.",
                rows,
            )
        )
    return res


@check("long_running", "Long-running queries")
def long_running(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("long_running", "Long-running queries")
    threshold = opts.get("long_query_seconds", 300)
    rows = query(
        conn,
        """
        SELECT pid, usename,
               EXTRACT(EPOCH FROM (now() - query_start))::int AS running_seconds,
               left(query, 120) AS query
        FROM pg_stat_activity
        WHERE state = 'active'
          AND query_start IS NOT NULL
          AND now() - query_start > make_interval(secs => %s)
          AND query NOT ILIKE '%%pg_stat_activity%%'
        ORDER BY running_seconds DESC
        """,
        (threshold,),
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.WARNING,
                f"{len(rows)} query(ies) running longer than {threshold}s",
                "",
                rows,
            )
        )
    return res
