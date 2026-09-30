from __future__ import annotations

import dataclasses
import html
import json

from pgdoctor.model import Report, Severity

_COLOR = {
    Severity.OK: "\033[32m",
    Severity.INFO: "\033[36m",
    Severity.WARNING: "\033[33m",
    Severity.CRITICAL: "\033[31m",
}
_RESET = "\033[0m"


def console(report: Report, color: bool = True) -> str:
    out: list[str] = []
    head = f"pgdoctor — {report.database}"
    if report.dsn_label:
        head += f" @ {report.dsn_label}"
    out.append(head)
    out.append("=" * len(head))
    for r in report.results:
        if r.skipped:
            out.append(f"  [SKIP] {r.name}: {r.skipped}")
            continue
        sev = r.max_severity
        tag = f"[{sev.label}]"
        if color:
            tag = f"{_COLOR[sev]}{tag}{_RESET}"
        out.append(f"  {tag} {r.name}")
        for f in r.findings:
            out.append(f"      - {f.title}")
            if f.detail:
                out.append(f"        {f.detail}")
            for row in f.rows[:5]:
                out.append("        " + _fmt_row(row))
            if len(f.rows) > 5:
                out.append(f"        ... and {len(f.rows) - 5} more")
    out.append("")
    verdict = report.max_severity.label
    out.append(f"Overall: {verdict}")
    return "\n".join(out)


def _fmt_row(row: dict) -> str:
    return "  ".join(f"{k}={v}" for k, v in row.items())


def as_json(report: Report) -> str:
    def enc(o):
        if isinstance(o, Severity):
            return o.label
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return str(o)

    payload = {
        "database": report.database,
        "dsn_label": report.dsn_label,
        "overall": report.max_severity.label,
        "checks": [
            {
                "key": r.key,
                "name": r.name,
                "severity": r.max_severity.label,
                "skipped": r.skipped,
                "findings": [dataclasses.asdict(f) for f in r.findings],
            }
            for r in report.results
        ],
    }
    return json.dumps(payload, default=enc, indent=2)


_CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,sans-serif;margin:2rem auto;max-width:960px;
color:#0f172a;background:#fff}
h1{font-size:1.4rem}
.sev{display:inline-block;padding:.1rem .5rem;border-radius:.3rem;font-size:.8rem;color:#fff}
.OK{background:#059669}.INFO{background:#0891b2}.WARNING{background:#d97706}.CRITICAL{background:#dc2626}
.check{border:1px solid #e2e8f0;border-radius:.5rem;padding:1rem;margin:.75rem 0}
.detail{color:#475569;font-size:.9rem}
table{border-collapse:collapse;margin:.5rem 0;font-size:.85rem;width:100%}
td,th{border:1px solid #e2e8f0;padding:.3rem .5rem;text-align:left}
.skip{color:#94a3b8}
"""


def html_report(report: Report) -> str:
    parts = [
        "<!doctype html><html><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        f"<title>pgdoctor — {html.escape(report.database)}</title>",
        f"<style>{_CSS}</style></head><body>",
        f"<h1>pgdoctor — {html.escape(report.database)}</h1>",
        f"<p>Overall: <span class='sev {report.max_severity.label}'>"
        f"{report.max_severity.label}</span></p>",
    ]
    for r in report.results:
        parts.append("<div class='check'>")
        if r.skipped:
            parts.append(
                f"<strong>{html.escape(r.name)}</strong> "
                f"<span class='skip'>skipped: {html.escape(r.skipped)}</span>"
            )
            parts.append("</div>")
            continue
        parts.append(
            f"<strong>{html.escape(r.name)}</strong> "
            f"<span class='sev {r.max_severity.label}'>{r.max_severity.label}</span>"
        )
        for f in r.findings:
            parts.append(f"<p>{html.escape(f.title)}</p>")
            if f.detail:
                parts.append(f"<p class='detail'>{html.escape(f.detail)}</p>")
            if f.rows:
                parts.append(_html_table(f.rows))
        parts.append("</div>")
    parts.append("</body></html>")
    return "".join(parts)


def _html_table(rows: list[dict]) -> str:
    cols = list(rows[0].keys())
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in cols)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(f"<td>{html.escape(str(row[c]))}</td>" for c in cols) + "</tr>"
    return f"<table><tr>{head}</tr>{body}</table>"
