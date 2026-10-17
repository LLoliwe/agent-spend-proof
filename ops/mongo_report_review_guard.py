"""Review candidate: offline audit-report readiness classification.

No DB/cloud access. Does NOT approve a release. 2 invalid, 3 blocked, 4
independent review required. An exit code of zero is intentionally impossible.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

MAX_REPORT_BYTES = 65536
SEVERITIES = ("critical", "high", "medium", "info")


def _unique_pairs(pairs):
    output = {}
    for key, value in pairs:
        if key in output:
            raise ValueError("duplicate JSON key")
        output[key] = value
    return output


def assess(report):
    if type(report) is not dict or set(report) != {"schema_version", "mode", "findings", "summary"}:
        raise ValueError("invalid report envelope")
    if type(report["schema_version"]) is not int or report["schema_version"] != 1:
        raise ValueError("unsupported schema version")
    if report["mode"] != "offline-read-only":
        raise ValueError("unsupported mode")
    findings, summary = report["findings"], report["summary"]
    if type(findings) is not list or type(summary) is not dict or set(summary) != set(SEVERITIES):
        raise ValueError("invalid report structure")
    counts = {severity: 0 for severity in SEVERITIES}
    codes = []
    for finding in findings:
        if type(finding) is not dict or set(finding) != {"code", "severity", "detail"}:
            raise ValueError("invalid finding")
        code, severity, detail = finding["code"], finding["severity"], finding["detail"]
        if type(code) is not str or not code.isidentifier() or not code.isupper():
            raise ValueError("invalid finding code")
        if type(detail) is not str or len(detail) > 1000:
            raise ValueError("invalid finding detail")
        if severity not in SEVERITIES:
            raise ValueError("invalid severity")
        counts[severity] += 1
        codes.append(code)
    if len(set(codes)) != len(codes):
        raise ValueError("duplicate finding code")
    if any(type(summary[s]) is not int or summary[s] != counts[s] for s in SEVERITIES):
        raise ValueError("inconsistent summary")
    return {"decision": "BLOCKED" if findings else "REVIEW_REQUIRED",
            "exit_code": 3 if findings else 4, "finding_codes": sorted(codes),
            "counts": counts, "independent_review": "REQUIRED"}


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print(json.dumps({"decision": "INVALID_REPORT", "exit_code": 2}))
        return 2
    try:
        path = Path(args[0])
        if path.stat().st_size > MAX_REPORT_BYTES:
            raise ValueError("oversized report")
        report = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))
        outcome = assess(report)
    except (OSError, UnicodeError, ValueError, TypeError, json.JSONDecodeError):
        outcome = {"decision": "INVALID_REPORT", "exit_code": 2}
    print(json.dumps(outcome, sort_keys=True))
    return outcome["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
