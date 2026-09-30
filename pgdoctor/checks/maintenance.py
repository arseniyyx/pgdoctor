from __future__ import annotations

import psycopg

from pgdoctor.checks.base import check
from pgdoctor.db import query, scalar
from pgdoctor.model import CheckResult, Finding, Severity


@check("wraparound", "Transaction ID wraparound")
def wraparound(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("wraparound", "Transaction ID wraparound")
    max_age = int(scalar(conn, "SHOW autovacuum_freeze_max_age"))
    rows = query(
        conn,
        """
        SELECT relname AS table,
               age(relfrozenxid) AS xid_age,
               round(100.0 * age(relfrozenxid) / %s, 1) AS pct_to_wraparound
        FROM pg_class
        WHERE relkind IN ('r', 'm', 't')
        ORDER BY age(relfrozenxid) DESC
        LIMIT 10
        """,
        (max_age,),
    )
    rows = [r for r in rows if r["pct_to_wraparound"] and r["pct_to_wraparound"] >= 50]
    if rows:
        worst = rows[0]["pct_to_wraparound"]
        sev = Severity.CRITICAL if worst >= 90 else Severity.WARNING
        res.findings.append(
            Finding(
                sev,
                f"{len(rows)} relation(s) approaching wraparound (worst {worst}%)",
                "At 100% Postgres forces an aggressive vacuum. Vacuum these tables now.",
                rows,
            )
        )
    return res


@check("cache_hit", "Cache hit ratio")
def cache_hit(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("cache_hit", "Cache hit ratio")
    row = query(
        conn,
        """
        SELECT sum(heap_blks_hit) AS hit, sum(heap_blks_read) AS read
        FROM pg_statio_user_tables
        """,
    )[0]
    hit = row["hit"] or 0
    read = row["read"] or 0
    total = hit + read
    if total == 0:
        res.skipped = "no I/O statistics yet"
        return res
    ratio = hit / total
    detail = f"{ratio:.2%} of table reads served from cache"
    sev = Severity.OK if ratio >= 0.99 else Severity.WARNING if ratio >= 0.90 else Severity.CRITICAL
    res.findings.append(Finding(sev, "Cache hit ratio", detail))
    return res


@check("tables_without_pk", "Tables without a primary key")
def tables_without_pk(conn: psycopg.Connection, opts: dict) -> CheckResult:
    res = CheckResult("tables_without_pk", "Tables without a primary key")
    rows = query(
        conn,
        """
        SELECT n.nspname AS schema, c.relname AS table
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind = 'r'
          AND n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND NOT EXISTS (
              SELECT 1 FROM pg_constraint con
              WHERE con.conrelid = c.oid AND con.contype = 'p'
          )
        ORDER BY 1, 2
        """,
    )
    if rows:
        res.findings.append(
            Finding(
                Severity.INFO,
                f"{len(rows)} table(s) without a primary key",
                "Tables without a PK complicate replication and dedup.",
                rows,
            )
        )
    return res
