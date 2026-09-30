# pgdoctor

A health inspector for PostgreSQL. Point it at a database and it runs a set of checks a DBA
runs by hand — bloat, unused and duplicate indexes, slow queries, wraparound risk, cache
hit ratio — and prints a report. It exits non-zero when something crosses a threshold, so it
also works as a scheduled check or a CI gate.

It connects read-only and runs only `SELECT`s against the system catalogs and statistics
views. It changes nothing in your database.

## What it checks

| check | severity | what it looks at |
|---|---|---|
| dead_tuples | up to critical | tables with a high dead-tuple ratio (bloat, autovacuum falling behind) |
| table_bloat | info | largest tables by total size |
| unused_indexes | warning | indexes never scanned since stats reset |
| duplicate_indexes | warning | identical indexes on the same columns |
| invalid_indexes | warning | indexes left invalid by a failed CREATE INDEX CONCURRENTLY |
| missing_indexes | info | large tables scanned sequentially far more than by index |
| slow_queries | up to warning | slowest statements from pg_stat_statements |
| wraparound | up to critical | relations approaching transaction-ID wraparound |
| cache_hit | up to critical | share of table reads served from shared buffers |
| connections | up to critical | connections in use vs max_connections |
| idle_in_transaction | warning | sessions idle in a transaction (they hold locks) |
| long_running | warning | queries running longer than a threshold |
| tables_without_pk | info | tables without a primary key |

`slow_queries` is skipped (not failed) if `pg_stat_statements` isn't installed.

## Install and run

```bash
uv sync
uv run pgdoctor --dsn postgresql://user:pass@host:5432/dbname
```

Or with the connection string in the environment:

```bash
export PGDOCTOR_DSN=postgresql://user:pass@host:5432/dbname
uv run pgdoctor
```

## Example

```
pgdoctor — shop @ db.internal:5432/shop
=======================================
  [CRITICAL] Table bloat (dead tuples)
      - 1 table(s) with high dead-tuple ratio (worst 50.0%)
        schema=public  table=orders  live=66668  dead=66666  dead_pct=50.0
  [WARNING] Unused indexes
      - 3 index(es) never used since stats reset
        schema=public  table=orders  index=idx_orders_amount_unused  size=2872 kB  scans=0
  ...
Overall: CRITICAL
```

## Output formats

```bash
uv run pgdoctor --format console          # default, colored
uv run pgdoctor --format html --output report.html
uv run pgdoctor --format json --output report.json
```

The HTML report is a self-contained page you can open in a browser or email. The JSON output
is for dashboards and further processing.

## Use it as a gate or a scheduled check

`--fail-on` sets the exit code. Combined with cron or CI it turns pgdoctor into an alarm:

```bash
# exit 1 if anything is WARNING or worse
uv run pgdoctor --fail-on warning || echo "database needs attention"
```

```
0  worst finding below the threshold
1  worst finding at or above --fail-on
2  could not connect or bad arguments
```

Run a subset of checks with `--only`:

```bash
uv run pgdoctor --only unused_indexes,dead_tuples,wraparound
uv run pgdoctor --list-checks
```

## Docker

```bash
docker build -t pgdoctor .
docker run --rm -e PGDOCTOR_DSN=postgresql://user:pass@host:5432/db pgdoctor
```

## Development

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/), and a PostgreSQL to test against.

```bash
uv sync
createdb pgdoctor_test
PGDOCTOR_TEST_DSN=postgresql://postgres:postgres@localhost:5432/pgdoctor_test uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Tests run each check against a real PostgreSQL with seeded problems (bloat, duplicate and
unused indexes, a table without a primary key) and assert the findings.

## Adding a check

Each check is a function that takes a connection and returns a `CheckResult`. Drop a new one
in `pgdoctor/checks/`, decorate it, and it's picked up automatically:

```python
@check("long_idle_replicas", "Lagging replicas")
def long_idle_replicas(conn, opts):
    res = CheckResult("long_idle_replicas", "Lagging replicas")
    rows = query(conn, "SELECT ...")
    if rows:
        res.findings.append(Finding(Severity.WARNING, "replicas lagging", "", rows))
    return res
```

## Layout

```
pgdoctor/
  cli.py          argument parsing, output, exit code
  engine.py       discovers and runs checks
  db.py           read-only connection, query helpers
  model.py        Severity, Finding, CheckResult, Report
  render.py       console, HTML and JSON renderers
  checks/         one module per group of checks
tests/            pytest against a real PostgreSQL
```

## What I'd add next

- A `--compare` mode that diffs against a previous JSON run to show what got worse
- Bloat estimation with pgstattuple when the extension is available
- Replication lag and checkpoint-frequency checks
- A Prometheus text-format output
