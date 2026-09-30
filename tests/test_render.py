from pgdoctor.model import CheckResult, Finding, Report, Severity
from pgdoctor.render import as_json, console, html_report


def _sample() -> Report:
    r = Report(dsn_label="host/db", database="db")
    c = CheckResult("x", "Example")
    c.findings.append(Finding(Severity.CRITICAL, "bad thing", "explanation", [{"a": 1}]))
    r.results.append(c)
    skipped = CheckResult("y", "Skipped one")
    skipped.skipped = "not installed"
    r.results.append(skipped)
    return r


def test_console_has_verdict():
    out = console(_sample(), color=False)
    assert "CRITICAL" in out
    assert "bad thing" in out
    assert "SKIP" in out


def test_json_valid():
    import json

    d = json.loads(as_json(_sample()))
    assert d["overall"] == "CRITICAL"
    assert d["checks"][0]["findings"][0]["title"] == "bad thing"


def test_html_escapes():
    r = _sample()
    r.results[0].findings[0].title = "<script>alert(1)</script>"
    out = html_report(r)
    assert "<script>alert(1)</script>" not in out
    assert "&lt;script&gt;" in out
