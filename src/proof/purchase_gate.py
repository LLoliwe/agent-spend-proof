"""Fail-closed buy purchase gate. No wallet, signer, or payment calls live here.

The gate captures one exact unpaid x402 quote and a local approval packet.
It does *not* approve payments automatically, verify provider legitimacy, or
infer that a payment/identity/real user exists. Must be used only from a trusted
operator computer with the official buy CLI after separate verification.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit
import json
import re

CELO_NETWORKS = {"celo", "eip155:42220", "42220"}
GATEWAY = "gateway.usebuy.ai"
HEX_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")


class GateError(ValueError):
    """Purchase proposal is not safe enough to present for approval."""


def _json_bytes(payload: dict) -> bytes:
    if not isinstance(payload, dict) or not payload:
        raise GateError("Nonempty JSON object required")
    try:
        data = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (TypeError, ValueError) as exc:
        raise GateError("Request body must be JSON serialisable") from exc
    if len(data) > 32768:
        raise GateError("Request body exceeds 32KiB safe preflight ceiling")
    return data


def _address(value: str, label: str) -> str:
    if not isinstance(value, str) or not HEX_ADDRESS.fullmatch(value):
        raise GateError(f"{label} must be a 20-byte EVM address")
    if int(value, 16) == 0:
        raise GateError(f"{label} must not be zero address")
    return value.lower()


def _gateway_url(value: str) -> str:
    if not isinstance(value, str) or len(value) > 2048:
        raise GateError("Invalid request URL")
    parts = urlsplit(value)
    if (parts.scheme != "https" or parts.hostname != GATEWAY or parts.username
            or parts.password or parts.port or parts.fragment or parts.query
            or not parts.path.startswith("/") or parts.path.startswith("//")
            or "\\" in value):
        raise GateError("Only exact HTTPS gateway path, no query/credentials/redirects")
    return value


def _atomic(raw: Any) -> int:
    if not isinstance(raw, str) or not re.fullmatch(r"[1-9][0-9]*", raw):
        raise GateError("Exact positive decimal-string atomic amount required")
    amount = int(raw)
    if amount > 10**30:
        raise GateError("Atomic amount is out of bounds")
    return amount


def _max_units(value: str) -> Decimal:
    if not isinstance(value, str):
        raise GateError("Operator maximum must be a decimal string")
    try:
        d = Decimal(value)
    except InvalidOperation as exc:
        raise GateError("Invalid maximum amount") from exc
    if not d.is_finite() or d <= 0 or d > 100:
        raise GateError("Maximum must be finite, positive, and <= 100 token units")
    return d


@dataclass(frozen=True)
class PurchasePreflight:
    url: str
    body: dict
    body_sha256: str
    token: str
    token_decimals: int
    pay_to: str
    max_amount_atomic: int
    wallet: str
    chain_id: int
    approval_fingerprint: str
    max_token_units: str
    purchase_enabled: bool = False

    def report(self) -> dict:
        # No body that might include user or private data appears in the report.
        return {
            "status": "PREPARED_NOT_APPROVED",
            "purchase_enabled": False,
            "no_payment_made": True,
            "network": "celo-mainnet",
            "chain_id": self.chain_id,
            "gateway": self.url,
            "body_sha256": self.body_sha256,
            "token": self.token,
            "token_decimals": self.token_decimals,
            "max_amount_atomic": str(self.max_amount_atomic),
            "human_max_token_units": self.max_token_units,
            "pay_to": self.pay_to,
            "wallet": self.wallet,
            "approval_fingerprint": self.approval_fingerprint,
            "unproven": ["wallet ownership", "quote freshness", "provider legitimacy",
                         "identity registration", "payment", "service delivery", "independent users"],
        }


def prepare_purchase(*, quote: dict, body: dict, wallet: str, token_decimals: int,
                     human_max_units: str, offered_index: int = 0) -> PurchasePreflight:
    """Prepare from *unpaid* inspect_quote output, without enabling spend.

    No automatic offer selection: caller supplies the index after inspecting the
    real 402 challenge. The exact offer, wallet and body form a fingerprint.
    A CLI preflight is *not* a payment-authorisation mechanism.
    """
    if not isinstance(quote, dict) or quote.get("status") != "quote_only" or quote.get("no_payment_made") is not True:
        raise GateError("Unpaid quote inspector evidence required")
    url = _gateway_url(quote.get("url"))
    if quote.get("method") != "POST":
        raise GateError("Only POST is supported")
    raw = _json_bytes(body)
    digest = sha256(raw).hexdigest()
    if quote.get("exact_body_sha256") != digest:
        raise GateError("Quote request body changed: obtain a fresh quote")
    challenge = quote.get("challenge")
    if not isinstance(challenge, dict):
        raise GateError("Malformed x402 challenge")
    offers = challenge.get("accepts")
    if not isinstance(offers, list) or not offers:
        raise GateError("Quote has no x402 payment requirements")
    if isinstance(offered_index, bool) or not isinstance(offered_index, int) or not 0 <= offered_index < len(offers):
        raise GateError("Explicit offer index required")
    offer = offers[offered_index]
    if not isinstance(offer, dict):
        raise GateError("Invalid offer")
    network = str(offer.get("network", "")).lower()
    if network not in CELO_NETWORKS:
        raise GateError("Quote is not Celo mainnet")
    token = _address(offer.get("asset"), "Quoted token")
    recipient = _address(offer.get("payTo"), "Quoted payTo")
    wallet_address = _address(wallet, "Operator wallet")
    if recipient == wallet_address:
        raise GateError("Self payment is not evidence of an independent merchant")
    amount = _atomic(offer.get("maxAmountRequired"))
    if isinstance(token_decimals, bool) or not isinstance(token_decimals, int) or not 0 <= token_decimals <= 24:
        raise GateError("Token decimals must be externally verified")
    max_units = _max_units(human_max_units)
    if Decimal(amount) / (Decimal(10) ** token_decimals) > max_units:
        raise GateError("Live quote exceeds explicit operator-approved token ceiling")
    if offer.get("scheme") not in ("exact", None):
        raise GateError("Unsupported x402 settlement scheme")
    fingerprint_input = {"url": url, "request_sha256": digest,
                         "offer": {"asset": token, "payTo": recipient,
                                   "atomic": str(amount), "network": network},
                         "wallet": wallet_address, "decimals": token_decimals,
                         "maximum": str(max_units)}
    fingerprint = sha256(json.dumps(fingerprint_input, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PurchasePreflight(url=url, body=body, body_sha256=digest,
                             token=token, token_decimals=token_decimals,
                             pay_to=recipient, max_amount_atomic=amount,
                             wallet=wallet_address, chain_id=42220,
                             approval_fingerprint=fingerprint,
                             max_token_units=str(max_units))
