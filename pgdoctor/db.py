from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row


@contextmanager
def connect(dsn: str):
    conn = psycopg.connect(dsn, row_factory=dict_row, connect_timeout=10)
    try:
        conn.read_only = True
        yield conn
    finally:
        conn.close()


def query(conn: psycopg.Connection, sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(sql, params)
        if cur.description is None:
            return []
        return cur.fetchall()


def extension_installed(conn: psycopg.Connection, name: str) -> bool:
    rows = query(conn, "SELECT 1 FROM pg_extension WHERE extname = %s", (name,))
    return bool(rows)


def scalar(conn: psycopg.Connection, sql: str, params: tuple = ()) -> Any:
    rows = query(conn, sql, params)
    if not rows:
        return None
    return next(iter(rows[0].values()))
