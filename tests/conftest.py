import os

import psycopg
import pytest

DSN = os.environ.get("PGDOCTOR_TEST_DSN", "postgresql://postgres@localhost:5432/pgdoctor_test")


@pytest.fixture(scope="session")
def dsn() -> str:
    return DSN


@pytest.fixture
def conn(dsn):
    c = psycopg.connect(dsn, autocommit=True)
    yield c
    c.close()


@pytest.fixture
def clean_schema(conn):
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pgdoctor_t CASCADE")
        cur.execute("CREATE SCHEMA pgdoctor_t")
        cur.execute("SET search_path TO pgdoctor_t")
    yield conn
    with conn.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS pgdoctor_t CASCADE")
