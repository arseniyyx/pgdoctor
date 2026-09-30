import psycopg
from psycopg.rows import dict_row

from pgdoctor import engine
from pgdoctor.checks.indexes import duplicate_indexes, unused_indexes
from pgdoctor.checks.maintenance import cache_hit, tables_without_pk, wraparound
from pgdoctor.model import Severity


def _dictconn(conn):
    return psycopg.connect(conn.info.dsn, row_factory=dict_row, autocommit=True)


def test_unused_and_duplicate_indexes(clean_schema, dsn):
    with clean_schema.cursor() as cur:
        cur.execute("SET search_path TO pgdoctor_t")
        cur.execute("CREATE TABLE t (id serial primary key, name text)")
        cur.execute("INSERT INTO t (name) SELECT 'n'||i FROM generate_series(1, 30000) i")
        cur.execute("CREATE INDEX ix_name ON t(name)")
        cur.execute("CREATE INDEX ix_name_dup ON t(name)")

    c = _dictconn(clean_schema)
    try:
        with c.cursor() as cur:
            cur.execute("SET search_path TO pgdoctor_t, public")
        res = unused_indexes(c, {"unused_index_min_mb": 0})
        names = {row["index"] for f in res.findings for row in f.rows}
        assert {"ix_name", "ix_name_dup"} <= names

        dup = duplicate_indexes(c, {})
        assert dup.max_severity == Severity.WARNING
    finally:
        c.close()


def test_tables_without_pk(clean_schema):
    with clean_schema.cursor() as cur:
        cur.execute("SET search_path TO pgdoctor_t")
        cur.execute("CREATE TABLE haspk (id int primary key)")
        cur.execute("CREATE TABLE nopk (a int)")

    c = _dictconn(clean_schema)
    try:
        res = tables_without_pk(c, {})
        tables = {row["table"] for f in res.findings for row in f.rows}
        assert "nopk" in tables
        assert "haspk" not in tables
    finally:
        c.close()


def test_wraparound_and_cache_hit_run(conn):
    c = _dictconn(conn)
    try:
        w = wraparound(c, {})
        assert w.key == "wraparound"
        ch = cache_hit(c, {})
        assert ch.key == "cache_hit"
    finally:
        c.close()


def test_engine_runs_all(dsn):
    from pgdoctor.db import connect

    with connect(dsn) as c:
        report = engine.run(c, {})
    keys = {r.key for r in report.results}
    assert "dead_tuples" in keys
    assert "unused_indexes" in keys
    assert len(report.results) >= 10
