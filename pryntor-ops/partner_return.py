#!/usr/bin/env python3
"""Offline evidence gate for Pryntor reciprocal partner evaluations.

A result is not a partnership, entitlement, verified integration, or commercial claim.
This deliberately cannot contact APIs, pay providers, post reports or approve release.
"""
import argparse
import json
import math
import statistics
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

MODES = {"documentation_only", "local_simulation", "authorized_live"}
OUTCOMES = {"success", "failure", "abstain", "not_tested"}
TOP_KEYS = {"schema_version", "niche", "environment", "records", "independent_reviewed"}
ROW_KEYS = {"provider", "task_id", "trial", "mode", "outcome", "latency_ms", "cost_usd", "evidence_ref"}


class InvalidEvidence(ValueError):
    """Invalid or misleading partner benchmark data."""


def _token(value, field):
    if not isinstance(value, str) or not value or len(value) > 120:
        raise InvalidEvidence(f"{field} must be nonempty text <=120 chars")
    if any(ord(char) < 32 for char in value):
        raise InvalidEvidence(f"{field} contains control characters")
    return value


def _strict_keys(obj, allowed, context):
    if not isinstance(obj, dict):
        raise InvalidEvidence(f"{context} must be an object")
    unexpected = set(obj) - allowed
    if unexpected:
        raise InvalidEvidence(f"{context} contains disallowed fields: {sorted(unexpected)}")


def _cost(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 40:
        raise InvalidEvidence("cost_usd must be decimal text or null")
    try:
        cost = Decimal(value)
    except InvalidOperation as exc:
        raise InvalidEvidence("cost_usd is not a decimal") from exc
    if not cost.is_finite() or cost < 0:
        raise InvalidEvidence("cost_usd must be finite and nonnegative")
    return cost


def _p95(values):
    values = sorted(values)
    return values[math.ceil(len(values) * .95) - 1]


def analyse(payload):
    _strict_keys(payload, TOP_KEYS, "report")
    if payload.get("schema_version") != 1:
        raise InvalidEvidence("unsupported schema_version")
    niche = _token(payload.get("niche"), "niche")
    environment = _token(payload.get("environment"), "environment")
    if type(payload.get("independent_reviewed")) is not bool:
        raise InvalidEvidence("independent_reviewed must be a boolean attestation")
    records = payload.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= 2000:
        raise InvalidEvidence("records must contain 1..2000 entries")
    groups = defaultdict(list)
    seen = set()
    for idx, row in enumerate(records):
        _strict_keys(row, ROW_KEYS, f"records[{idx}]")
        provider = _token(row.get("provider"), "provider")
        task_id = _token(row.get("task_id"), "task_id")
        trial = row.get("trial")
        if type(trial) is not int or not 1 <= trial <= 10000:
            raise InvalidEvidence("trial must be an integer 1..10000")
        mode = row.get("mode")
        outcome = row.get("outcome")
        if mode not in MODES or outcome not in OUTCOMES:
            raise InvalidEvidence("unknown mode or outcome")
        if (mode == "documentation_only") != (outcome == "not_tested"):
            raise InvalidEvidence("documentation_only must be not_tested, and other modes must be measured")
        latency = row.get("latency_ms")
        if latency is not None and (type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0):
            raise InvalidEvidence("latency_ms must be nonnegative finite number or null")
        cost = _cost(row.get("cost_usd"))
        if mode == "documentation_only" and (latency is not None or cost is not None):
            raise InvalidEvidence("documentation-only records cannot contain measured latency or cost")
        ref = _token(row.get("evidence_ref"), "evidence_ref")
        # Public fixtures may use fixture: references; actual runs require a non-placeholder locator.
        if mode == "authorized_live" and (ref.startswith("fixture:") or ref.startswith("example:")):
            raise InvalidEvidence("live evidence must not point at a fixture")
        key = (provider, task_id, trial)
        if key in seen:
            raise InvalidEvidence("duplicate provider/task/trial, which would double-count results")
        seen.add(key)
        groups[provider].append((row, cost))

    modes = {r[0]["mode"] for group in groups.values() for r in group}
    counts = [Counter((row["task_id"], row["trial"]) for row, _ in g) for g in groups.values()]
    equal_tasks = all(counter == counts[0] for counter in counts[1:])
    if modes == {"documentation_only"}:
        state = "DOCUMENTATION_ONLY_NOT_TESTED"
    elif modes == {"local_simulation"}:
        state = "SIMULATED_NOT_VENDOR_PERFORMANCE" if equal_tasks else "NOT_COMPARABLE_TASK_MISMATCH"
    elif modes == {"authorized_live"} and len(groups) >= 2 and equal_tasks:
        state = "REVIEWED_LIVE_ATTESTATION_ONLY" if payload["independent_reviewed"] else "MEASURED_AWAITING_INDEPENDENT_REVIEW"
    else:
        state = "NOT_COMPARABLE"
    summary = []
    for provider, group in sorted(groups.items()):
        measured = [(r, c) for r, c in group if r["mode"] != "documentation_only"]
        passed = sum(r["outcome"] == "success" for r, _ in measured)
        latencies = [r["latency_ms"] for r, _ in measured if r["latency_ms"] is not None]
        known_costs = [c for _, c in measured if c is not None]
        full_cost = bool(measured) and len(known_costs) == len(measured)
        summary.append({
            "provider": provider,
            "observations": len(group),
            "measured_attempts": len(measured),
            "successful_attempts": passed,
            "success_rate": round(passed / len(measured), 6) if measured else None,
            "median_latency_ms": round(statistics.median(latencies), 3) if latencies else None,
            "p95_latency_ms": _p95(latencies) if latencies else None,
            "cost_per_success_usd": str(sum(known_costs, Decimal(0)) / passed) if full_cost and passed else None,
            "missing_latency_count": len(measured) - len(latencies),
            "missing_cost_count": len(measured) - len(known_costs),
        })
    return {
        "schema_version": 1,
        "niche": niche,
        "environment": environment,
        "comparability": state,
        "comparability_contract": "same tasks and trial IDs, same execution mode and environment; no statistical significance inferred",
        "source_verification": "REFERENCES_NOT_INDEPENDENTLY_AUTHENTICATED",
        "public_claim_allowed": False,
        "independent_review_attested": payload["independent_reviewed"],
        "provider_summaries": summary,
        "caveats": [
            "Input data is operator-supplied and reference URLs are not verified by this offline tool.",
            "Documentation-only and local simulation are not evidence of live provider performance.",
            "Provider account permissions, billing, source licences, statistical validity and public disclosures need separate review.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="sanitized benchmark JSON file")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args(argv)
    try:
        report = analyse(json.loads(args.input.read_text(encoding="utf-8")))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.exit(2, f"Invalid evidence: {exc}\n")
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")


if __name__ == "__main__":
    main()
