from __future__ import annotations

import psycopg

from pgdoctor.checks.base import check
from pgdoctor.db import query
from pgdoctor.model import CheckResult, Finding, Severity


@check("unused_indexes", "Unused indexes")
def unused_indexes(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("unused_indexes", "Unused indexes")
    min_size_mb = opts.get("unused_index_min_mb", 1)
    rows = query(
        conn,
        """
        SELECT s.schemaname AS schema,
               s.relname AS table,
               s.indexrelname AS index,
               pg_size_pretty(pg_relation_size(s.indexrelid)) AS size,
               s.idx_scan AS scans
        FROM pg_stat_user_indexes s
        JOIN pg_index i ON i.indexrelid = s.indexrelid
        WHERE s.idx_scan = 0
          AND NOT i.indisunique
          AND NOT i.indisprimary
          AND pg_relation_size(s.indexrelid) > %s * 1024 * 1024
        ORDER BY pg_relation_size(s.indexrelid) DESC
        """,
        (min_size_mb,),
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.WARNING,
                f"{len(rows)} index(es) never used since stats reset",
                "Unused indexes cost write performance and disk. Confirm before dropping.",
                rows,
            )
        )
    return res


@check("missing_indexes", "Possible missing indexes")
def missing_indexes(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("missing_indexes", "Possible missing indexes")
    rows = query(
        conn,
        """
        SELECT schemaname AS schema,
               relname AS table,
               seq_scan,
               idx_scan,
               pg_size_pretty(pg_relation_size(relid)) AS size
        FROM pg_stat_user_tables
        WHERE seq_scan > 0
          AND seq_scan > coalesce(idx_scan, 0) * 5
          AND pg_relation_size(relid) > 50 * 1024 * 1024
        ORDER BY seq_scan DESC
        LIMIT 20
        """,
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.INFO,
                f"{len(rows)} large table(s) scanned sequentially far more than by index",
                "These may benefit from an index. Check the queries hitting them.",
                rows,
            )
        )
    return res


@check("invalid_indexes", "Invalid indexes")
def invalid_indexes(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("invalid_indexes", "Invalid indexes")
    rows = query(
        conn,
        """
        SELECT n.nspname AS schema, c.relname AS index
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE NOT i.indisvalid
        ORDER BY 1, 2
        """,
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.WARNING,
                f"{len(rows)} invalid index(es)",
                "Usually a failed CREATE INDEX CONCURRENTLY. Drop and rebuild.",
                rows,
            )
        )
    return res


@check("duplicate_indexes", "Duplicate indexes")
def duplicate_indexes(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("duplicate_indexes", "Duplicate indexes")
    rows = query(
        conn,
        """
        SELECT indrelid::regclass::text AS table,
               array_agg(indexrelid::regclass::text ORDER BY indexrelid) AS indexes,
               count(*) AS n
        FROM pg_index
        GROUP BY indrelid, indkey, indclass, indoption, indcollation,
                 coalesce(pg_get_expr(indexprs, indrelid), ''),
                 coalesce(pg_get_expr(indpred, indrelid), '')
        HAVING count(*) > 1
        ORDER BY 1
        """,
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.WARNING,
                f"{len(rows)} set(s) of duplicate indexes",
                "Identical indexes waste space and slow writes.",
                rows,
            )
        )
    return res
