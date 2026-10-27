"""Read-only Base x402 evidence checks. Never creates wallets, signs or pays.

Protocol references checked 2026-10-27:
https://docs.x402.org/core-concepts/http-402
https://docs.x402.org/schemes/exact
https://docs.base.org/get-started/connect-to-base

A matched ERC-20 transfer is narrower evidence than a fulfilled x402 purchase.
The quote fingerprint is a consistency check, not an authenticated approval.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

NETWORKS = {
    "eip155:8453": {"chain_id": 8453, "name": "base-mainnet", "testnet": False,
                    "rpc_url": "https://mainnet.base.org", "explorer": "https://basescan.org"},
    "eip155:84532": {"chain_id": 84532, "name": "base-sepolia", "testnet": True,
                     "rpc_url": "https://sepolia.base.org", "explorer": "https://sepolia.basescan.org"},
}
TRANSFER_TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
MAX_JSON_BYTES = 262144
MAX_QUOTE_BYTES = 65536
MAX_UINT256 = 2**256 - 1
RPC = Callable[[str, list], Any]


class EvidenceError(ValueError):
    """Evidence is incomplete, inconsistent or outside the supported scope."""


def _integer(value: Any, name: str, minimum: int = 1, maximum: int = MAX_UINT256) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise EvidenceError(f"{name} must be an integer between {minimum} and {maximum}")
    return value


def _hex(value: Any, size: int, name: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"0x[0-9a-fA-F]{%d}" % (size * 2), value):
        raise EvidenceError(f"Invalid {name}")
    return value.lower()


def _address(value: Any, name: str) -> str:
    result = _hex(value, 20, name)
    if result == "0x" + "0" * 40:
        raise EvidenceError(f"Zero {name} is not supported")
    return result


def _quantity(value: Any, name: str) -> int:
    if not isinstance(value, str) or not re.fullmatch(r"0x(?:0|[1-9a-fA-F][0-9a-fA-F]{0,63})", value):
        raise EvidenceError(f"Invalid RPC {name}")
    return int(value, 16)


def _data(value: Any, name: str) -> str:
    if (not isinstance(value, str) or len(value) > MAX_JSON_BYTES
            or not re.fullmatch(r"0x(?:[0-9a-fA-F]{2})*", value)):
        raise EvidenceError(f"Invalid {name}")
    return value.lower()


def _object(value: Any, name: str) -> dict:
    if not isinstance(value, dict):
        raise EvidenceError(f"Missing or malformed {name}")
    return value


def _json_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    except (ValueError, TypeError, RecursionError, UnicodeError) as exc:
        raise EvidenceError("Unsupported JSON value") from exc


def _load_json(raw: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise EvidenceError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise EvidenceError("Non-finite JSON number")

    try:
        result = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("Malformed JSON evidence") from exc
    return _object(result, "JSON object")


def _network(network: Any) -> dict:
    if not isinstance(network, str) or network not in NETWORKS:
        raise EvidenceError("Select Base mainnet eip155:8453 or Base Sepolia eip155:84532 explicitly")
    return NETWORKS[network]


def _url(value: Any) -> str:
    if (not isinstance(value, str) or not value or len(value) > 4096
            or not value.isascii() or any(ord(c) <= 32 for c in value)):
        raise EvidenceError("Invalid resource URL")
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.port is not None or parsed.fragment
                or "\\" in value):
            raise EvidenceError("Resource must be an exact HTTPS URL without credentials, port or fragment")
    except ValueError as exc:
        raise EvidenceError("Invalid resource URL") from exc
    return value


def validate_quote(
    payment_required: dict | str, *, request_url: str, network: str,
    expected_asset: str, expected_pay_to: str, max_amount_atomic: int,
    request_method: str = "GET", request_body: bytes = b"", offer_index: int = 0,
) -> dict:
    """Check an x402 V2 quote against caller-supplied expectations without I/O.

    ``payment_required`` is the decoded object or a PAYMENT-REQUIRED base64
    header. Only exact ERC-20 offers are supported. The resource URL must match
    byte-for-byte; the body fingerprint records local input, not a server proof.
    """
    profile = _network(network)
    request_url = _url(request_url)
    asset = _address(expected_asset, "expected asset")
    pay_to = _address(expected_pay_to, "expected payee")
    _integer(max_amount_atomic, "maximum atomic amount")
    _integer(offer_index, "offer index", minimum=0, maximum=127)
    if request_method not in ("GET", "POST"):
        raise EvidenceError("Only exact GET or POST requests are supported")
    if type(request_body) is not bytes or len(request_body) > MAX_QUOTE_BYTES:
        raise EvidenceError("Request body must be bounded exact bytes")
    if isinstance(payment_required, str):
        if len(payment_required) > 4 * ((MAX_QUOTE_BYTES + 2) // 3):
            raise EvidenceError("Payment header is too large")
        try:
            raw = base64.b64decode(payment_required, validate=True)
        except (ValueError, UnicodeError) as exc:
            raise EvidenceError("Invalid PAYMENT-REQUIRED base64") from exc
        if len(raw) > MAX_QUOTE_BYTES:
            raise EvidenceError("Quote is too large")
        challenge = _load_json(raw)
    elif isinstance(payment_required, dict):
        raw = _json_bytes(payment_required)
        if len(raw) > MAX_QUOTE_BYTES:
            raise EvidenceError("Quote is too large")
        challenge = _load_json(raw)  # detached copy; reject non-JSON values
    else:
        raise EvidenceError("Expected a quote object or PAYMENT-REQUIRED header")
    if type(challenge.get("x402Version")) is not int or challenge["x402Version"] != 2:
        raise EvidenceError("Only x402 V2 is supported")
    resource = _object(challenge.get("resource"), "quote resource")
    if _url(resource.get("url")) != request_url:
        raise EvidenceError("Quoted resource does not match the exact request URL")
    offers = challenge.get("accepts")
    if not isinstance(offers, list) or not 1 <= len(offers) <= 128 or offer_index >= len(offers):
        raise EvidenceError("Missing offers or invalid selected offer")
    offer = _object(offers[offer_index], "selected offer")
    if offer.get("scheme") != "exact":
        raise EvidenceError("Only the exact payment scheme is supported")
    if offer.get("network") != network:
        raise EvidenceError("Quote network does not match the explicitly selected Base network")
    if _address(offer.get("asset"), "quote asset") != asset:
        raise EvidenceError("Quote asset does not match the expected token")
    if _address(offer.get("payTo"), "quote payee") != pay_to:
        raise EvidenceError("Quote payee does not match the expected recipient")
    amount = offer.get("amount")
    if not isinstance(amount, str) or not re.fullmatch(r"[1-9][0-9]{0,77}", amount):
        raise EvidenceError("Quote amount must be a positive decimal atomic-unit string")
    amount_atomic = _integer(int(amount), "quote atomic amount")
    if amount_atomic > max_amount_atomic:
        raise EvidenceError("Quote exceeds the caller's maximum atomic amount")
    _integer(offer.get("maxTimeoutSeconds"), "quote maximum timeout", maximum=2**31 - 1)
    extra = offer.get("extra", {})
    _object(extra, "offer extra fields")
    selected = {**offer, "asset": asset, "payTo": pay_to}
    evidence = {
        "schema": "proof.base.quote.v1", "network": network, "chain_id": profile["chain_id"],
        "testnet": profile["testnet"],
        "request": {"url": request_url, "method": request_method,
                    "body_sha256": hashlib.sha256(request_body).hexdigest()},
        "selected_offer": selected, "offer_index": offer_index,
        "payment_required_sha256": hashlib.sha256(_json_bytes(challenge)).hexdigest(),
        "max_amount_atomic": max_amount_atomic,
        "amount_atomic": amount_atomic,
        "policy_check": "matched_caller_supplied_expectations",
        "payment_executed": False, "spend_authorisation_verified": False,
        "quote_authenticity_verified": False,
    }
    evidence["fingerprint"] = hashlib.sha256(_json_bytes(evidence)).hexdigest()
    return evidence


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise EvidenceError("RPC redirects are not permitted")


def read_base_rpc(network: str, method: str, params: list) -> Any:
    """Read a fixed official Base RPC endpoint; signing and arbitrary URLs are absent."""
    profile = _network(network)
    valid = False
    if method == "eth_chainId":
        valid = params == []
    elif method in ("eth_getTransactionReceipt", "eth_getTransactionByHash"):
        valid = isinstance(params, list) and len(params) == 1
        if valid:
            _hex(params[0], 32, "transaction hash")
    elif method == "eth_getBlockByNumber":
        valid = isinstance(params, list) and len(params) == 2 and params[1] is False
        if valid and params[0] not in ("latest", "finalized"):
            _quantity(params[0], "block number")
    if not valid:
        raise EvidenceError("RPC method or parameters are not permitted")
    request = Request(profile["rpc_url"], data=_json_bytes(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with build_opener(_NoRedirect).open(request, timeout=5) as response:
            if response.status != 200:
                raise EvidenceError("RPC returned a non-success status")
            raw = response.read(MAX_JSON_BYTES + 1)
        if len(raw) > MAX_JSON_BYTES:
            raise EvidenceError("RPC response exceeds the evidence size limit")
        envelope = _load_json(raw)
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise EvidenceError("Base RPC evidence is unavailable") from exc
    if (envelope.get("jsonrpc") != "2.0" or type(envelope.get("id")) is not int
            or envelope["id"] != 1 or "error" in envelope or "result" not in envelope):
        raise EvidenceError("Invalid RPC response envelope")
    return envelope["result"]


def _checked_quote(quote: Any) -> dict:
    quote = _object(quote, "validated quote")
    data = {key: value for key, value in quote.items() if key != "fingerprint"}
    if (quote.get("schema") != "proof.base.quote.v1"
            or quote.get("fingerprint") != hashlib.sha256(_json_bytes(data)).hexdigest()):
        raise EvidenceError("Quote fingerprint mismatch; revalidate the original quote")
    profile = _network(quote.get("network"))
    if quote.get("chain_id") != profile["chain_id"] or quote.get("testnet") is not profile["testnet"]:
        raise EvidenceError("Quote network metadata mismatch")
    offer = _object(quote.get("selected_offer"), "selected offer")
    request = _object(quote.get("request"), "request binding")
    _url(request.get("url"))
    if request.get("method") not in ("GET", "POST") or not re.fullmatch(
            r"[0-9a-f]{64}", str(request.get("body_sha256", ""))):
        raise EvidenceError("Invalid request binding")
    _integer(quote.get("amount_atomic"), "atomic amount")
    _integer(quote.get("max_amount_atomic"), "maximum atomic amount")
    if (offer.get("network") != quote["network"] or offer.get("scheme") != "exact"
            or offer.get("amount") != str(quote["amount_atomic"])
            or quote["amount_atomic"] > quote["max_amount_atomic"]
            or quote.get("payment_executed") is not False):
        raise EvidenceError("Invalid selected quote binding")
    _address(offer.get("asset"), "asset")
    _address(offer.get("payTo"), "payee")
    return quote


def _block(value: Any, name: str) -> tuple[dict, int, str]:
    block = _object(value, name)
    return block, _quantity(block.get("number"), name + " number"), _hex(block.get("hash"), 32, name + " hash")


def verify_settlement(
    quote: dict, *, tx_hash: str, payer: str, rpc: RPC | None = None,
    min_confirmations: int = 1, require_finalized: bool = False,
) -> dict:
    """Match an exact ERC-20 transfer to a quote's expected fields, without paying.

    Rejects inconsistent chain/receipt/transaction/block/log snapshots. A supplied
    RPC callable is explicitly labelled untrusted caller-supplied evidence. One
    provider's canonical/finalized view is not independent consensus proof.
    """
    quote = _checked_quote(quote)
    network = quote["network"]
    profile = _network(network)
    tx_hash = _hex(tx_hash, 32, "transaction hash")
    payer = _address(payer, "payer")
    pay_to = _address(quote["selected_offer"]["payTo"], "payee")
    asset = _address(quote["selected_offer"]["asset"], "asset")
    if payer == pay_to:
        raise EvidenceError("Self-payment cannot establish the requested service purchase")
    _integer(min_confirmations, "minimum confirmations", maximum=2**31 - 1)
    if type(require_finalized) is not bool:
        raise EvidenceError("require_finalized must be a boolean")
    supplied = rpc is not None
    if rpc is not None and not callable(rpc):
        raise EvidenceError("RPC must be a read-only callable")
    call = rpc if supplied else lambda method, params: read_base_rpc(network, method, params)
    try:
        return _verify_snapshot(quote, tx_hash, payer, asset, pay_to, profile, call,
                                supplied, min_confirmations, require_finalized)
    except EvidenceError:
        raise
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError) as exc:
        raise EvidenceError("Incomplete or malformed RPC evidence") from exc


def _verify_snapshot(quote, tx_hash, payer, asset, pay_to, profile, call, supplied,
                     min_confirmations, require_finalized):
    chain_id = _quantity(call("eth_chainId", []), "chain ID")
    if chain_id != profile["chain_id"]:
        raise EvidenceError("RPC chain does not match the quote's Base network")
    receipt = _object(call("eth_getTransactionReceipt", [tx_hash]), "mined receipt")
    if _hex(receipt.get("transactionHash"), 32, "receipt transaction hash") != tx_hash:
        raise EvidenceError("Receipt transaction hash mismatch")
    if _quantity(receipt.get("status"), "execution status") != 1:
        raise EvidenceError("Transaction execution reverted or failed")
    height = _quantity(receipt.get("blockNumber"), "receipt block number")
    block_hash = _hex(receipt.get("blockHash"), 32, "receipt block hash")
    tx_index = _quantity(receipt.get("transactionIndex"), "transaction index")
    transaction = _object(call("eth_getTransactionByHash", [tx_hash]), "mined transaction")
    if (_hex(transaction.get("hash"), 32, "transaction hash") != tx_hash
            or _hex(transaction.get("blockHash"), 32, "transaction block hash") != block_hash
            or _quantity(transaction.get("blockNumber"), "transaction block number") != height
            or _quantity(transaction.get("transactionIndex"), "transaction index") != tx_index
            or _quantity(transaction.get("chainId"), "transaction chain ID") != chain_id):
        raise EvidenceError("Transaction and receipt are inconsistent")
    calldata = _data(transaction.get("input"), "transaction calldata")
    canonical, canonical_height, canonical_hash = _block(
        call("eth_getBlockByNumber", [hex(height), False]), "canonical receipt block")
    hashes = canonical.get("transactions")
    if (canonical_height != height or canonical_hash != block_hash
            or not isinstance(hashes, list) or tx_index >= len(hashes)):
        raise EvidenceError("Receipt is not in the supplied canonical block")
    normalised_hashes = [_hex(item, 32, "canonical transaction hash") for item in hashes]
    if normalised_hashes[tx_index] != tx_hash or normalised_hashes.count(tx_hash) != 1:
        raise EvidenceError("Transaction membership in the canonical block is ambiguous")
    _, latest_height, _ = _block(call("eth_getBlockByNumber", ["latest", False]), "latest block")
    confirmations = latest_height - height + 1
    if confirmations < min_confirmations:
        raise EvidenceError("Insufficient confirmations or inconsistent latest height")
    finalized_raw = call("eth_getBlockByNumber", ["finalized", False])
    _, finalized_height, finalized_hash = _block(finalized_raw, "finalized block")
    if finalized_height > latest_height:
        raise EvidenceError("Finalized block is ahead of the latest block")
    finalized = finalized_height >= height
    if finalized_height == height and finalized_hash != block_hash:
        raise EvidenceError("Finalized block conflicts with the receipt block")
    if require_finalized and not finalized:
        raise EvidenceError("Receipt has not reached the RPC's finalized block")
    logs = receipt.get("logs")
    if not isinstance(logs, list) or not logs:
        raise EvidenceError("Missing complete receipt logs")
    expected_sender = "0x" + payer[2:].rjust(64, "0")
    expected_receiver = "0x" + pay_to[2:].rjust(64, "0")
    seen_indices, matching = set(), []
    for log in logs:
        log = _object(log, "receipt log")
        if log.get("removed") is not False:
            raise EvidenceError("Removed or incomplete receipt log")
        index = _quantity(log.get("logIndex"), "log index")
        if index in seen_indices:
            raise EvidenceError("Duplicate receipt log index")
        seen_indices.add(index)
        if (_hex(log.get("transactionHash"), 32, "log transaction hash") != tx_hash
                or _hex(log.get("blockHash"), 32, "log block hash") != block_hash
                or _quantity(log.get("blockNumber"), "log block number") != height
                or _quantity(log.get("transactionIndex"), "log transaction index") != tx_index):
            raise EvidenceError("Log is not bound to the receipt transaction and block")
        log_asset = _address(log.get("address"), "log contract address")
        topics = log.get("topics")
        if not isinstance(topics, list) or len(topics) > 4:
            raise EvidenceError("Malformed log topics")
        topics = [_hex(topic, 32, "event topic") for topic in topics]
        data = _data(log.get("data"), "event data")
        if log_asset == asset and topics and topics[0] == TRANSFER_TOPIC:
            if len(topics) != 3 or len(data) != 66:
                raise EvidenceError("Malformed ERC-20 transfer event")
            if topics[1] == expected_sender:
                if topics[2] != expected_receiver:
                    raise EvidenceError("Unexpected additional transfer from the payer")
                matching.append((index, int(data, 16)))
    if len(matching) != 1:
        raise EvidenceError("Expected one unambiguous transfer; missing, duplicate or split payment")
    log_index, amount = matching[0]
    if amount != quote["amount_atomic"]:
        raise EvidenceError("Transfer amount does not match the exact quoted amount")
    # A reorganisation during the reads must not produce a successful result.
    _, repeated_height, repeated_hash = _block(
        call("eth_getBlockByNumber", [hex(height), False]), "rechecked canonical block")
    if repeated_height != height or repeated_hash != block_hash:
        raise EvidenceError("Canonical block changed during verification")
    if _quantity(call("eth_chainId", []), "rechecked chain ID") != chain_id:
        raise EvidenceError("RPC chain changed during verification")
    return {
        "schema": "proof.base.settlement.v1", "network": quote["network"],
        "chain_id": chain_id, "network_name": profile["name"], "testnet": profile["testnet"],
        "evidence_origin": "caller_supplied_rpc" if supplied else "live_base_rpc",
        "rpc_url": None if supplied else profile["rpc_url"],
        "status": "matched_finalized_transfer" if finalized else "matched_provisional_transfer",
        "transfer_matched": True, "tx_hash": tx_hash,
        "explorer_url": profile["explorer"] + "/tx/" + tx_hash,
        "asset": asset, "payer": payer, "pay_to": pay_to, "amount_atomic": amount,
        "block_number": height, "block_hash": block_hash, "log_index": log_index,
        "canonical_block_consistent": True, "confirmations": confirmations,
        "finality": {"finalized": finalized, "finalized_block_number": finalized_height,
                     "basis": "RPC finalized tag; confirmation count alone is not finality"},
        "quote_fingerprint": quote["fingerprint"],
        "calldata_sha256": hashlib.sha256(bytes.fromhex(calldata[2:])).hexdigest(),
        "quote_payment_binding": {"verified": False,
            "reason": "Matching transfer fields do not cryptographically bind this request to an x402 payment."},
        "attribution": {"verified": False,
            "reason": "ERC-8021 attribution and registered Builder Code ownership are not verified by this R0 check."},
        "service_delivery": {"verified": False,
            "reason": "A token transfer does not prove service delivery, usefulness or customer adoption."},
        "payment_executed": False, "spend_authorisation_verified": False,
        "grant_eligibility_verified": False,
        "trust_model": "Single RPC view; caller-supplied fixtures are not independently verified chain activity.",
    }
