"""Boundary tests: quote-only requests must not make network calls or mutate the ledger."""
import copy

import httpx
import pytest

from proof import base_api
from proof.app import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


def packet():
    token = "0x" + "a" * 40
    payee = "0x" + "c" * 40
    return {
        "payment_required": {
            "x402Version": 2,
            "resource": {"url": "https://example.org/report"},
            "accepts": [{"scheme": "exact", "network": "eip155:84532",
                         "asset": token, "amount": "10000", "payTo": payee,
                         "maxTimeoutSeconds": 60}],
        },
        "request_url": "https://example.org/report", "network": "eip155:84532",
        "expected_asset": token, "expected_pay_to": payee, "max_amount_atomic": 10000,
    }


@pytest.mark.anyio
async def test_quote_only_is_read_only(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Quote validation must not query a chain")
    monkeypatch.setattr(base_api, "verify_settlement", forbidden)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        before = (await client.get("/api/stats")).json()
        result = await client.post("/api/base/check", json=packet())
        after = (await client.get("/api/stats")).json()
    assert result.status_code == 200, result.text
    assert result.json()["payment_executed"] is False
    assert result.json()["settlement"] is None
    assert before == after


@pytest.mark.anyio
@pytest.mark.parametrize("change", [
    {"rpc_url": "http://127.0.0.1/private"},
    {"network": "eip155:42220"},
    {"max_amount_atomic": True},
    {"max_amount_atomic": 1.2},
    {"tx_hash": "0x" + "d" * 64},
    {"payment_required": "x" * 70000},
])
async def test_rejects_invalid_or_network_override_inputs(change, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Invalid requests must not query a chain")
    monkeypatch.setattr(base_api, "verify_settlement", forbidden)
    body = packet()
    body.update(change)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/base/check", json=body)
    assert response.status_code == 422


@pytest.mark.anyio
async def test_changed_quote_cannot_reuse_valid_expectations():
    body = copy.deepcopy(packet())
    body["payment_required"]["accepts"][0]["amount"] = "10001"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/api/base/check", json=body)
    assert response.status_code == 422

