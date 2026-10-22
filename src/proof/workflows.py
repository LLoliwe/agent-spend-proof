"""Business-workflow demo wired to the spend ledger. All provider responses are synthetic."""
from __future__ import annotations

import hashlib
from .core import Ledger


def creator_brief(ledger: Ledger, task_id: str, handle: str, idempotency_key: str, outcome: str = "delivered") -> dict:
    """Simulate paying a distinct service for public creator insights.

    This demonstrates why the purchase is necessary for the agent task, but is
    not a real provider call or independently sourced market intelligence.
    """
    request, replay = ledger.add(task_id, "https://data.example.org", "creator-audience-snapshot", 35, "USD", idempotency_key)
    if request["status"] == "rejected":
        return {"mode": "simulation", "paid": False, "status": "rejected", "intent": request, "result": None}
    if replay:
        # A repeated request does not result in another purchase. Its saved
        # state is returned; we never execute it again from this workflow.
        return {"mode": "simulation", "paid": False, "status": "replay_blocked", "intent": request, "result": None}
    done = ledger.simulate(request["id"], outcome)
    if done["status"] != "settled":
        return {"mode": "simulation", "paid": False, "status": done["status"], "intent": done, "result": None}

    # Stable synthetic sample for UI demonstrations. Not inferred from a real
    # account and not represented as actual creator analytics.
    n = int(hashlib.sha256(handle.lower().encode()).hexdigest()[:8], 16)
    samples = [
        {"channel": "Short-form video", "demo_share_pct": 38 + n % 17},
        {"channel": "Static / carousel", "demo_share_pct": 24 + n % 9},
    ]
    samples.append({"channel": "Other", "demo_share_pct": 100 - samples[0]["demo_share_pct"] - samples[1]["demo_share_pct"]})
    recommendation = max(samples, key=lambda s:s["demo_share_pct"])["channel"]
    return {"mode": "simulation", "paid": False, "status": "synthetic_data_delivered", "intent": done,
            "result": {"handle": handle, "data_provenance": "SYNTHETIC DEMO DATA — not a real social media account",
                       "channels": samples,
                       "example_output": f"Using DEMO ONLY data, the most represented format is {recommendation}. This is not an actionable insight for a real business."}}
