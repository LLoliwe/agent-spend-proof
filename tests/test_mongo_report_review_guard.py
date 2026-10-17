"""Synthetic-only tests for review-required report gate."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "guard_under_review", Path(__file__).resolve().parents[1] / "ops" / "mongo_report_review_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def report():
    return {"schema_version": 1, "mode": "offline-read-only", "findings": [],
            "summary": {"critical": 0, "high": 0, "medium": 0, "info": 0}}


def test_empty_report_requires_independent_review():
    result = guard.assess(report())
    assert result["decision"] == "REVIEW_REQUIRED"
    assert result["exit_code"] == 4
    assert result["independent_review"] == "REQUIRED"


@pytest.mark.parametrize("severity", ["critical", "high", "medium", "info"])
def test_any_finding_blocks_release(severity):
    case = report()
    case["findings"] = [{"code": "PROOF_MISSING", "severity": severity, "detail": "synthetic"}]
    case["summary"][severity] = 1
    result = guard.assess(case)
    assert result["decision"] == "BLOCKED"
    assert result["exit_code"] == 3
    assert result["finding_codes"] == ["PROOF_MISSING"]


@pytest.mark.parametrize("mutation", [
    lambda r: r.update({"mode": "production-ready"}),
    lambda r: r.update({"unexpected": True}),
    lambda r: r["summary"].update({"info": 1}),
    lambda r: r["summary"].update({"critical": True}),
    lambda r: r.update({"schema_version": True}),
    lambda r: r.update({"findings": {}}),
])
def test_invalid_envelope_rejected(mutation):
    case = report()
    mutation(case)
    with pytest.raises(ValueError):
        guard.assess(case)


def test_duplicate_findings_rejected():
    case = report()
    case["findings"] = [{"code": "DUPLICATE", "severity": "info", "detail": "s"}] * 2
    case["summary"]["info"] = 2
    with pytest.raises(ValueError):
        guard.assess(case)


def test_cli_invalid_duplicate_keys_exit_two(tmp_path, capsys):
    p = tmp_path / "invalid.json"
    p.write_text('{"schema_version":1,"schema_version":1}')
    assert guard.main([str(p)]) == 2
    assert "INVALID_REPORT" in capsys.readouterr().out


def test_cli_review_never_success(tmp_path, capsys):
    p = tmp_path / "clean.json"
    p.write_text(json.dumps(report()))
    assert guard.main([str(p)]) == 4
    assert "REVIEW_REQUIRED" in capsys.readouterr().out


def test_cli_missing_path_exit_two(capsys):
    assert guard.main(["/missing/pryntor-nonexistent-report.json"]) == 2
    assert "INVALID_REPORT" in capsys.readouterr().out
