"""Adversarial Base evidence fixtures. None of these fixtures is live chain usage."""
import base64
import copy
import hashlib
import json

import pytest

from proof import base_evidence as evidence
from proof.base_evidence import EvidenceError, TRANSFER_TOPIC, validate_quote, verify_settlement

ASSET = "0x" + "a" * 40
PAYER = "0x" + "b" * 40
PAYEE = "0x" + "c" * 40
TX = "0x" + "d" * 64
BLOCK = "0x" + "e" * 64
OTHER_HASH = "0x" + "f" * 64
URL = "https://api.example.org/paid-report?region=za"
NETWORK = "eip155:8453"
AMOUNT = 10000


def challenge(network=NETWORK):
    return {
        "x402Version": 2,
        "resource": {"url": URL, "description": "Synthetic test resource", "mimeType": "application/json"},
        "accepts": [{"scheme": "exact", "network": network, "amount": str(AMOUNT),
                     "asset": ASSET, "payTo": PAYEE, "maxTimeoutSeconds": 300,
                     "extra": {"name": "Test token", "version": "2"}}],
    }


def quote(raw=None, network=NETWORK, **changes):
    args = dict(request_url=URL, network=network, expected_asset=ASSET,
                expected_pay_to=PAYEE, max_amount_atomic=AMOUNT,
                request_method="POST", request_body=b'{"task":"synthetic fixture"}')
    args.update(changes)
    return validate_quote(challenge(network) if raw is None else raw, **args)


class FixtureRPC:
    """Independent captured-shape fixture, explicitly not a real RPC provider."""
    def __init__(self, network=NETWORK):
        self.chain_id = hex(evidence.NETWORKS[network]["chain_id"])
        self.receipt = {
            "transactionHash": TX, "status": "0x1", "blockNumber": "0x64",
            "blockHash": BLOCK, "transactionIndex": "0x0",
            "logs": [{
                "removed": False, "logIndex": "0x4", "transactionHash": TX,
                "transactionIndex": "0x0", "blockHash": BLOCK, "blockNumber": "0x64",
                "address": ASSET,
                "topics": [TRANSFER_TOPIC, "0x" + PAYER[2:].rjust(64, "0"),
                           "0x" + PAYEE[2:].rjust(64, "0")],
                "data": "0x" + hex(AMOUNT)[2:].rjust(64, "0"),
            }],
        }
        self.transaction = {"hash": TX, "blockHash": BLOCK, "blockNumber": "0x64",
                            "transactionIndex": "0x0", "chainId": self.chain_id,
                            "input": "0xaabbccdd"}
        self.block = {"number": "0x64", "hash": BLOCK, "transactions": [TX]}
        self.latest = {"number": "0x70", "hash": OTHER_HASH}
        self.finalized = {"number": "0x64", "hash": BLOCK}
        self.calls = []

    def __call__(self, method, params):
        self.calls.append((method, copy.deepcopy(params)))
        if method == "eth_chainId":
            return self.chain_id
        if method == "eth_getTransactionReceipt":
            return copy.deepcopy(self.receipt)
        if method == "eth_getTransactionByHash":
            return copy.deepcopy(self.transaction)
        if method == "eth_getBlockByNumber":
            assert params[1] is False
            return copy.deepcopy({"latest": self.latest, "finalized": self.finalized,
                                  "0x64": self.block}[params[0]])
        raise AssertionError("A write or unexpected RPC method was attempted")


def verify(rpc=None, **changes):
    args = dict(tx_hash=TX, payer=PAYER, rpc=rpc or FixtureRPC())
    args.update(changes)
    return verify_settlement(quote(), **args)


def test_valid_quote_binds_exact_request_and_atomic_offer():
    raw = challenge()
    result = quote(raw)
    raw["accepts"][0]["amount"] = "999"
    assert result["selected_offer"]["amount"] == "10000"
    assert result["amount_atomic"] == AMOUNT
    assert result["request"]["url"] == URL
    assert result["request"]["body_sha256"] == hashlib.sha256(b'{"task":"synthetic fixture"}').hexdigest()
    assert not result["payment_executed"] and not result["spend_authorisation_verified"]
    assert not result["quote_authenticity_verified"]
    assert len(result["fingerprint"]) == 64


def test_base64_quote_and_dictionary_agree():
    header = base64.b64encode(json.dumps(challenge()).encode()).decode()
    assert quote(header) == quote()


def test_fingerprint_changes_when_exact_body_or_request_method_changes():
    original = quote()
    assert quote(request_body=b'{ "task":"synthetic fixture"}')['fingerprint'] != original['fingerprint']
    assert quote(request_method="GET")['fingerprint'] != original['fingerprint']


@pytest.mark.parametrize("field,value", [
    ("network", "eip155:84532"), ("network", "base"), ("scheme", "upto"),
    ("asset", "0x" + "1" * 40), ("asset", "0x" + "0" * 40),
    ("payTo", PAYER), ("payTo", "0x+" + "c" * 39),
    ("amount", AMOUNT), ("amount", True), ("amount", "0"), ("amount", "-1"),
    ("amount", "1e4"), ("amount", "1.0"), ("amount", "010000"),
    ("amount", str(2**256)), ("maxTimeoutSeconds", True),
    ("maxTimeoutSeconds", 0), ("maxTimeoutSeconds", "300"), ("extra", []),
])
def test_rejects_unsafe_or_ambiguous_selected_offer(field, value):
    raw = challenge()
    raw["accepts"][0][field] = value
    with pytest.raises(EvidenceError):
        quote(raw)


@pytest.mark.parametrize("version", [1, "2", 2.0, True, None])
def test_rejects_legacy_or_ambiguous_protocol_version(version):
    raw = challenge()
    raw["x402Version"] = version
    with pytest.raises(EvidenceError, match="V2"):
        quote(raw)


@pytest.mark.parametrize("resource_url", [
    "https://api.example.org/paid-report?region=us", URL + "#receipt",
    "https://user:password@api.example.org/paid-report", "http://api.example.org/paid-report",
    "https://api.example.org:443/paid-report", "https://api.example.org/paid-report\n",
])
def test_rejects_resource_substitution_or_unsafe_url(resource_url):
    raw = challenge()
    raw["resource"]["url"] = resource_url
    with pytest.raises(EvidenceError):
        quote(raw)


def test_rejects_missing_offers_resource_amount_or_operator_limit():
    for key in ("accepts", "resource"):
        raw = challenge()
        del raw[key]
        with pytest.raises(EvidenceError):
            quote(raw)
    raw = challenge()
    del raw["accepts"][0]["amount"]
    with pytest.raises(EvidenceError):
        quote(raw)
    for cap in (True, 0, AMOUNT - 1, float(AMOUNT)):
        with pytest.raises(EvidenceError):
            quote(max_amount_atomic=cap)


def test_selected_offer_is_explicit_and_mainnet_is_not_testnet():
    raw = challenge()
    raw["accepts"].insert(0, challenge("eip155:84532")["accepts"][0])
    with pytest.raises(EvidenceError, match="network"):
        quote(raw)
    assert quote(raw, offer_index=1)["network"] == NETWORK
    with pytest.raises(EvidenceError):
        quote(raw, offer_index=True)
    with pytest.raises(EvidenceError):
        quote(raw, offer_index=2)


def test_header_decoder_rejects_duplicate_keys_nonfinite_and_oversized_input():
    for raw in (b'{"x402Version":2,"x402Version":1}', b'{"price":NaN}', b'[]'):
        with pytest.raises(EvidenceError):
            quote(base64.b64encode(raw).decode())
    for invalid in ("not base64!", "A" * (evidence.MAX_QUOTE_BYTES * 2)):
        with pytest.raises(EvidenceError):
            quote(invalid)


@pytest.mark.parametrize("network", list(evidence.NETWORKS))
def test_matches_complete_exact_transfer_but_preserves_nonclaims(network):
    rpc = FixtureRPC(network)
    result = verify_settlement(quote(network=network), tx_hash=TX, payer=PAYER, rpc=rpc,
                               require_finalized=True)
    assert result["transfer_matched"] is True
    assert result["confirmations"] == 13
    assert result["canonical_block_consistent"] is True
    assert result["finality"]["finalized"] is True
    assert result["testnet"] is (network == "eip155:84532")
    assert result["evidence_origin"] == "caller_supplied_rpc"
    assert result["rpc_url"] is None
    assert result["service_delivery"]["verified"] is False
    assert result["attribution"]["verified"] is False
    assert result["quote_payment_binding"]["verified"] is False
    assert result["payment_executed"] is False
    assert result["grant_eligibility_verified"] is False
    assert result["spend_authorisation_verified"] is False
    assert all(method in ("eth_chainId", "eth_getTransactionReceipt", "eth_getTransactionByHash",
                          "eth_getBlockByNumber") for method, _ in rpc.calls)


def test_confirmations_are_not_finality():
    rpc = FixtureRPC()
    rpc.finalized = {"number": "0x63", "hash": OTHER_HASH}
    result = verify(rpc)
    assert result["confirmations"] == 13 and not result["finality"]["finalized"]
    assert result["status"] == "matched_provisional_transfer"
    with pytest.raises(EvidenceError, match="finalized"):
        verify(rpc, require_finalized=True)


def test_rejects_mutated_quote_even_with_unchanged_transfer():
    bound = quote()
    bound["request"]["body_sha256"] = "a" * 64
    with pytest.raises(EvidenceError, match="fingerprint"):
        verify_settlement(bound, tx_hash=TX, payer=PAYER, rpc=FixtureRPC())


def test_rejects_self_payment_and_bool_confirmation_policies():
    with pytest.raises(EvidenceError, match="Self-payment"):
        verify(payer=PAYEE)
    for changes in ({"min_confirmations": True}, {"min_confirmations": 0},
                    {"require_finalized": "false"}):
        with pytest.raises(EvidenceError):
            verify(**changes)


@pytest.mark.parametrize("value", ["0x1", "0xa4ec", "0x14a34", "8453", "0x02105", None])
def test_rejects_wrong_or_malformed_rpc_chain(value):
    rpc = FixtureRPC()
    rpc.chain_id = value
    with pytest.raises(EvidenceError):
        verify(rpc)


@pytest.mark.parametrize("field,value", [
    ("status", "0x0"), ("status", None), ("transactionHash", OTHER_HASH),
    ("blockHash", OTHER_HASH), ("blockNumber", "0x65"), ("transactionIndex", "0x1"),
])
def test_rejects_reverted_or_inconsistent_receipt(field, value):
    rpc = FixtureRPC()
    rpc.receipt[field] = value
    with pytest.raises(EvidenceError):
        verify(rpc)


@pytest.mark.parametrize("field,value", [
    ("hash", OTHER_HASH), ("blockHash", OTHER_HASH), ("blockNumber", None),
    ("transactionIndex", "0x1"), ("chainId", "0x1"), ("input", "not calldata"),
])
def test_rejects_inconsistent_or_partial_transaction(field, value):
    rpc = FixtureRPC()
    rpc.transaction[field] = value
    with pytest.raises(EvidenceError):
        verify(rpc)


def test_rejects_pending_receipt_and_missing_finality_evidence():
    rpc = FixtureRPC()
    rpc.receipt = None
    with pytest.raises(EvidenceError, match="receipt"):
        verify(rpc)
    rpc = FixtureRPC()
    rpc.finalized = None
    with pytest.raises(EvidenceError, match="finalized"):
        verify(rpc)


@pytest.mark.parametrize("transactions", [[], [OTHER_HASH], [TX, TX], [dict(hash=TX)]])
def test_rejects_missing_or_ambiguous_canonical_membership(transactions):
    rpc = FixtureRPC()
    rpc.block["transactions"] = transactions
    with pytest.raises(EvidenceError):
        verify(rpc)


def test_rejects_invalid_finalized_and_latest_relationships():
    rpc = FixtureRPC()
    rpc.latest["number"] = "0x63"
    with pytest.raises(EvidenceError, match="confirmations"):
        verify(rpc)
    rpc = FixtureRPC()
    rpc.finalized["number"] = "0x71"
    with pytest.raises(EvidenceError, match="ahead"):
        verify(rpc)
    rpc = FixtureRPC()
    rpc.finalized["hash"] = OTHER_HASH
    with pytest.raises(EvidenceError, match="conflicts"):
        verify(rpc)


@pytest.mark.parametrize("field,value", [
    ("removed", True), ("removed", "false"), ("removed", None),
    ("transactionHash", OTHER_HASH), ("blockHash", OTHER_HASH),
    ("blockNumber", "0x65"), ("transactionIndex", "0x1"), ("logIndex", None),
    ("address", "0x" + "1" * 40), ("topics", []), ("data", "0x2710"),
    ("data", "0x" + "0" * 64),
])
def test_rejects_removed_mismatched_or_partial_event(field, value):
    rpc = FixtureRPC()
    rpc.receipt["logs"][0][field] = value
    with pytest.raises(EvidenceError):
        verify(rpc)


def test_rejects_duplicate_event_and_split_payment_instead_of_summing():
    for same_index, split in ((True, False), (False, False), (False, True)):
        rpc = FixtureRPC()
        duplicate = copy.deepcopy(rpc.receipt["logs"][0])
        duplicate["logIndex"] = "0x4" if same_index else "0x5"
        if split:
            rpc.receipt["logs"][0]["data"] = "0x" + hex(AMOUNT // 2)[2:].rjust(64, "0")
            duplicate["data"] = rpc.receipt["logs"][0]["data"]
        rpc.receipt["logs"].append(duplicate)
        with pytest.raises(EvidenceError, match="Duplicate|ambiguous"):
            verify(rpc)


def test_rejects_extra_unapproved_debit_from_payer():
    rpc = FixtureRPC()
    extra = copy.deepcopy(rpc.receipt["logs"][0])
    extra["logIndex"] = "0x5"
    extra["topics"][2] = "0x" + ("1" * 40).rjust(64, "0")
    rpc.receipt["logs"].append(extra)
    with pytest.raises(EvidenceError, match="additional transfer"):
        verify(rpc)


def test_wrong_payer_is_not_accepted_as_a_customer_payment():
    with pytest.raises(EvidenceError, match="unambiguous"):
        verify(payer="0x" + "1" * 40)


def test_reorganisation_during_reads_is_rejected():
    rpc = FixtureRPC()
    count = 0

    def reorganising(method, params):
        nonlocal count
        result = rpc(method, params)
        if method == "eth_getBlockByNumber" and params[0] == "0x64":
            count += 1
            if count == 2:
                result["hash"] = OTHER_HASH
        return result

    with pytest.raises(EvidenceError, match="changed during"):
        verify(reorganising)


def test_chain_switch_during_reads_is_rejected():
    rpc = FixtureRPC()
    count = 0

    def switching(method, params):
        nonlocal count
        if method == "eth_chainId":
            count += 1
            if count == 2:
                return "0x1"
        return rpc(method, params)

    with pytest.raises(EvidenceError, match="chain changed"):
        verify(switching)


def test_rpc_exception_does_not_echo_private_transport_data():
    def failed(_method, _params):
        raise ValueError("transport secret should not appear")

    with pytest.raises(EvidenceError) as failure:
        verify(failed)
    assert "transport secret" not in str(failure.value)


@pytest.mark.parametrize("method,params", [
    ("eth_sendRawTransaction", ["0x1234"]), ("eth_sendTransaction", [{}]),
    ("personal_sign", []), ("eth_getBlockByNumber", ["pending", False]),
    ("eth_getBlockByNumber", ["latest", True]), ("eth_chainId", ["unexpected"]),
])
def test_network_adapter_refuses_writes_and_unsupported_reads_before_io(monkeypatch, method, params):
    monkeypatch.setattr(evidence, "build_opener", lambda *_args: pytest.fail("No I/O expected"))
    with pytest.raises(EvidenceError):
        evidence.read_base_rpc(NETWORK, method, params)


def test_default_adapter_uses_fixed_network_and_validates_rpc_envelope(monkeypatch):
    class Response:
        status = 200
        raw = b'{"jsonrpc":"2.0","id":1,"result":"0x2105"}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def read(self, limit):
            return self.raw[:limit]

    class Opener:
        def open(self, request, timeout):
            assert request.full_url == "https://mainnet.base.org"
            assert json.loads(request.data)["method"] == "eth_chainId"
            assert timeout <= 5
            return Response()

    monkeypatch.setattr(evidence, "build_opener", lambda *_args: Opener())
    assert evidence.read_base_rpc(NETWORK, "eth_chainId", []) == "0x2105"
    for raw in (b'{"jsonrpc":"2.0","id":2,"result":"0x2105"}',
                b'{"jsonrpc":"2.0","id":true,"result":"0x2105"}',
                b'{"jsonrpc":"2.0","id":1,"error":{"message":"private"}}',
                b'{"jsonrpc":"2.0","id":1,"id":2,"result":"0x2105"}',
                b'x' * (evidence.MAX_JSON_BYTES + 1)):
        Response.raw = raw
        with pytest.raises(EvidenceError):
            evidence.read_base_rpc(NETWORK, "eth_chainId", [])


def test_redirects_are_rejected():
    with pytest.raises(EvidenceError, match="redirects"):
        evidence._NoRedirect().redirect_request(None, None, 302, "Found", {}, "http://127.0.0.1/")
