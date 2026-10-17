#!/usr/bin/env python3
"""Offline Pryntor GPU decision guard. Never provisions resources or reports savings."""
import argparse
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sys

REQUIRED = ("frozen_model_and_graph","gpu_necessity_demonstrated",
            "rights_and_data_clear","no_cost_entitlement_authenticated",
            "vendor_inventory_authenticated","output_qa_confirmed",
            "successful_job_receipt")
ISSUES = {"PRY-182","PRY-191","PRY-170"}

def evaluate(record):
    if record.get("historical_paid_gpu") is not False:
        raise ValueError("Founder-confirmed paid historical baseline must be false")
    jobs = record.get("workloads", [])
    ids = [j.get("issue") for j in jobs]
    if len(ids) != 3 or set(ids) != ISSUES:
        raise ValueError("Expected exactly three distinct real Pryntor workloads")
    decisions = []
    for job in jobs:
        id_ = job["issue"]
        gates = job.get("gates")
        if not isinstance(gates, dict) or any(type(gates.get(k)) is not bool for k in REQUIRED):
            raise ValueError(f"{id_}: mandatory evidence booleans missing")
        need = job.get("gpu_required", "missing")
        if id_ in ("PRY-182","PRY-191"):
            if need is not False:
                raise ValueError(f"{id_}: no evidenced GPU requirement")
            decision = "CPU_FIRST_NO_GPU_PURCHASE"
        else:
            if need is not None:
                raise ValueError("PRY-170 model-specific GPU need remains unverified")
            decision = "GPU_CANDIDATE_HOLD"
        decisions.append({
            "issue": id_, "decision": decision, "buy_authorized": False,
            "missing_gates": [k for k in REQUIRED if not gates[k]],
            "historical_realized_savings_usd": None
        })
    return {"purchases_initiated": 0, "savings_claim": "NONE",
            "historical_gpu_invoice": "NOT_APPLICABLE", "workloads": decisions}

def illustrative_rates(quotes, minutes):
    try:
        duration = Decimal(str(minutes))
    except InvalidOperation as e:
        raise ValueError("Invalid scenario duration") from e
    if not duration.is_finite() or not 0 < duration <= 1440:
        raise ValueError("Scenario duration must be between 0 and 1440 minutes")
    result = []
    for q in quotes:
        if any(not q.get(x) for x in ("source_url","observed_date","provider","gpu")):
            raise ValueError("Unattributed public rate")
        if not q["source_url"].startswith("https://") or q.get("rate_class") != "PUBLIC_ADVERTISED_NOT_CHECKOUT":
            raise ValueError("Not a public source-linked, unverified listing")
        try:
            hourly = Decimal(str(q["gpu_only_usd_per_hour"]))
        except (InvalidOperation, KeyError) as e:
            raise ValueError("Bad rate") from e
        if not hourly.is_finite() or hourly <= 0:
            raise ValueError("Bad rate")
        result.append({
            "provider": q["provider"], "gpu": q["gpu"], "source": q["source_url"],
            "scenario_minutes": str(duration),
            "hypothetical_gpu_only_usd": str((hourly * duration / 60).quantize(Decimal("0.000001"))),
            "equivalent_successful_job_verified": False, "all_in_cost_usd": None,
            "realized_savings_usd": None
        })
    return result

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workloads", required=True, type=Path)
    parser.add_argument("--quotes", required=True, type=Path)
    parser.add_argument("--minutes", default="15")
    args = parser.parse_args()
    try:
        jobs = json.loads(args.workloads.read_text(encoding="utf8"))
        quotes = json.loads(args.quotes.read_text(encoding="utf8"))
        result = evaluate(jobs)
        result["illustrative_only"] = illustrative_rates(quotes, args.minutes)
    except (ValueError, OSError) as e:
        print("DENY:", e, file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
