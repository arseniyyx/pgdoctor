from __future__ import annotations

import psycopg

from pgdoctor.checks.base import check
from pgdoctor.db import query
from pgdoctor.model import CheckResult, Finding, Severity


@check("dead_tuples", "Table bloat (dead tuples)")
def dead_tuples(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("dead_tuples", "Table bloat (dead tuples)")
    warn_pct = opts.get("dead_tuple_warn_pct", 20)
    rows = query(
        conn,
        """
        SELECT schemaname AS schema,
               relname AS table,
               n_live_tup AS live,
               n_dead_tup AS dead,
               CASE WHEN n_live_tup + n_dead_tup > 0
                    THEN round(100.0 * n_dead_tup / (n_live_tup + n_dead_tup), 1)
                    ELSE 0 END AS dead_pct,
               to_char(last_autovacuum, 'YYYY-MM-DD HH24:MI') AS last_autovacuum
        FROM pg_stat_user_tables
        WHERE n_dead_tup > 1000
          AND n_live_tup + n_dead_tup > 0
          AND 100.0 * n_dead_tup / (n_live_tup + n_dead_tup) >= %s
        ORDER BY n_dead_tup DESC
        LIMIT 20
        """,
        (warn_pct,),
    )
    if rows:
        worst = rows[0]["dead_pct"]
        sev = Severity.CRITICAL if worst >= 40 else Severity.WARNING
        res.findings.append(
            Finding(
                sev,
                f"{len(rows)} table(s) with high dead-tuple ratio (worst {worst}%)",
                "Dead tuples bloat tables and indexes. Check autovacuum settings.",
                rows,
            )
        )
    return res


@check("table_bloat", "Estimated table bloat")
def table_bloat(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("table_bloat", "Estimated table bloat")
    rows = query(
        conn,
        """
        SELECT current_database() AS db,
               schemaname AS schema,
               tablename AS table,
               pg_size_pretty(pg_total_relation_size(
                   quote_ident(schemaname) || '.' || quote_ident(tablename))) AS total_size
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY pg_total_relation_size(
            quote_ident(schemaname) || '.' || quote_ident(tablename)) DESC
        LIMIT 10
        """,
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.INFO,
                "Largest tables by total size",
                "Total size includes indexes and TOAST.",
                rows,
            )
        )
    return res
