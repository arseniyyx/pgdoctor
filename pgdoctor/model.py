from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Any


class Severity(enum.IntEnum):
    OK = 0
    INFO = 1
    WARNING = 2
    CRITICAL = 3

    @property
    def label(self) -> str:
        return self.name


@dataclass
class Finding:
    severity: Severity
    title: str
    detail: str = ""
    rows: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CheckResult:
    key: str
    name: str
    findings: list[Finding] = field(default_factory=list)
    skipped: str = ""

    @property
    def max_severity(self) -> Severity:
        if not self.findings:
            return Severity.OK
        return max(f.severity for f in self.findings)


@dataclass
class Report:
    dsn_label: str
    database: str
    results: list[CheckResult] = field(default_factory=list)

    @property
    def max_severity(self) -> Severity:
        sevs = [r.max_severity for r in self.results if not r.skipped]
        return max(sevs) if sevs else Severity.OK
