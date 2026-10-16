"""Submission evidence gate. Missing evidence fails closed; never self-certifies truth."""
from __future__ import annotations

from urllib.parse import urlsplit
import re

EVIDENCE_FIELDS = {
    "enrollment_email": "Organizer enrollment confirmation retained",
    "project_url": "Enrolled project URL / track recorded",
    "identity_explorer": "ERC-8004 agent identity verified on Celo",
    "wallet_address": "Operator wallet tied to entry",
    "third_party_provider": "Independent provider and purchased service named",
    "celo_payment_tx": "Celo mainnet payment transaction verified",
    "delivery_evidence": "Purchased service result and receipt linked",
    "independent_user_evidence": "Genuine unrelated user activity and consent evidenced",
    "demo_url": "Working demo externally accessible or reproducible",
    "reviewer_signoff": "Independent eligibility / claim audit signed off",
    "accepted_submission_receipt": "Loops House accepted submission receipt retained",
}


def audit_evidence(evidence: dict, *, verify_receipt=None) -> dict:
    """Check evidence packet structure. No claim of external checks without callback.

    Real-world verification requires inspecting the identity registry, actual x402
    settlement, provider delivery, project page and participant history separately.
    """
    if not isinstance(evidence, dict):
        raise ValueError("evidence must be an object")
    passed, blocked = [], []
    for field, desc in EVIDENCE_FIELDS.items():
        raw = evidence.get(field)
        valid = isinstance(raw, str) and len(raw.strip()) >= 8 and not re.search(
            r"(placeholder|example\.com|synthetic|^SIM-|not.submitted|not.verified)", raw, re.I)
        if field.endswith("_url") or field in {"identity_explorer", "delivery_evidence", "demo_url", "project_url", "accepted_submission_receipt"}:
            valid = bool(valid and urlsplit(raw).scheme == "https" and urlsplit(raw).netloc)
        if field == "wallet_address":
            valid = bool(isinstance(raw, str) and re.fullmatch(r"0x[0-9a-fA-F]{40}", raw))
        if field == "celo_payment_tx":
            valid = bool(isinstance(raw, str) and re.fullmatch(r"0x[0-9a-fA-F]{64}", raw))
        (passed if valid else blocked).append({"field": field, "description": desc})
    if verify_receipt is not None and not callable(verify_receipt):
        raise ValueError("verify_receipt callback must be callable")
    # A verifier callback must return a real verified=True; its presence alone is insufficient.
    chain_verified = False
    if "celo_payment_tx" in evidence and verify_receipt is not None:
        try:
            chain_verified = verify_receipt(evidence) is True
        except Exception:
            chain_verified = False
    # Even a good receipts result alone can never prove delivery or independent user.
    return {
        "ready_to_submit": False,
        "packet_fields_present": len(blocked) == 0,
        "chain_transfer_verified": chain_verified,
        "present_fields": passed,
        "missing_or_invalid_fields": blocked,
        "review_required": ["verify ERC-8004 registry ownership on Celo mainnet",
                            "verify live quote + token Transfer + settlement attribution",
                            "verify provider is independent and delivered results",
                            "verify independence and prior activity of qualified users",
                            "verify submitted project and Loops receipt"],
        "message": "Documentary completeness is not proof of eligibility; manual independent review required.",
    }
