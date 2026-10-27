"""Local, read-only Base evidence checks. No wallet, signer or payment routes."""
from __future__ import annotations

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from .base_evidence import EvidenceError, validate_quote, verify_settlement

router = APIRouter(prefix="/api/base", tags=["Base evidence"])


class EvidenceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_required: dict | str
    request_url: str = Field(min_length=9, max_length=2048)
    network: Literal["eip155:8453", "eip155:84532"]
    expected_asset: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    expected_pay_to: str = Field(pattern=r"^0x[0-9a-fA-F]{40}$")
    max_amount_atomic: StrictInt = Field(ge=1, le=10**30)
    request_method: Literal["GET", "POST"] = "GET"
    request_body: str = Field(default="", max_length=32768)
    offer_index: StrictInt = Field(default=0, ge=0, le=31)
    tx_hash: str | None = Field(default=None, pattern=r"^0x[0-9a-fA-F]{64}$")
    payer: str | None = Field(default=None, pattern=r"^0x[0-9a-fA-F]{40}$")
    min_confirmations: StrictInt = Field(default=12, ge=1, le=10000)
    require_finalized: bool = True


@router.get("/status")
def status():
    return {
        "mode": "read_only",
        "networks": ["eip155:8453", "eip155:84532"],
        "payment_executed": False,
        "builder_code_attribution": "not_verified",
        "usage_metrics": "Not collected; verification requests are not paying users or transaction volume.",
    }


@router.post("/check")
def check(body: EvidenceRequest):
    # No caller-controlled RPC or remote merchant fetch is accepted.
    if len(json.dumps(body.payment_required).encode("utf-8")) > 65536:
        raise HTTPException(422, "Payment requirement exceeds the 64 KiB limit")
    if bool(body.tx_hash) != bool(body.payer):
        raise HTTPException(422, "Supply both transaction hash and payer, or neither")
    try:
        quote = validate_quote(
            body.payment_required,
            request_url=body.request_url,
            network=body.network,
            expected_asset=body.expected_asset,
            expected_pay_to=body.expected_pay_to,
            max_amount_atomic=body.max_amount_atomic,
            request_method=body.request_method,
            request_body=body.request_body.encode("utf-8"),
            offer_index=body.offer_index,
        )
        settlement = None
        if body.tx_hash:
            settlement = verify_settlement(
                quote,
                tx_hash=body.tx_hash,
                payer=body.payer,
                min_confirmations=body.min_confirmations,
                require_finalized=body.require_finalized,
            )
        return {
            "mode": "read_only",
            "payment_executed": False,
            "quote": quote,
            "settlement": settlement,
            "scope": "An observed token transfer alone does not establish quote correlation, service delivery or customer use.",
        }
    except EvidenceError as exc:
        raise HTTPException(422, str(exc)) from exc

