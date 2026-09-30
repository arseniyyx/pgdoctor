from __future__ import annotations

from collections.abc import Callable

import psycopg

from pgdoctor.model import CheckResult

CheckFunc = Callable[[psycopg.Connection, dict], CheckResult]

_REGISTRY: list[tuple[str, str, CheckFunc]] = []


def check(key: str, name: str):
    def deco(fn: CheckFunc) -> CheckFunc:
        _REGISTRY.append((key, name, fn))
        return fn

    return deco


def all_checks() -> list[tuple[str, str, CheckFunc]]:
    return list(_REGISTRY)
