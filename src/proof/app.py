"""Simulated agent-payment policy console. NOT an onchain wallet or live payment implementation."""
from __future__ import annotations

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from .core import Ledger, PolicyError

ROOT = Path(__file__).resolve().parents[2]
app = FastAPI(title="Agent Spend Proof", version="0.1.0", description="Simulation only. No funds move.")
ledger = Ledger(os.environ.get("PROOF_DB", "./proof.sqlite3"))
app.mount("/static", StaticFiles(directory=str(ROOT / "static")), name="static")


class NewIntent(BaseModel):
    task_id: str = Field(min_length=2, max_length=64, pattern=r"^[a-zA-Z0-9_.:-]+$")
    merchant: str = Field(min_length=12, max_length=256)
    service: str = Field(min_length=2, max_length=80)
    amount_cents: int = Field(ge=1, le=10000000)
    currency: str = Field(default="USD", max_length=8)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[a-zA-Z0-9_.:-]+$")


class Simulation(BaseModel):
    outcome: str


class Reconciliation(BaseModel):
    status: str
    evidence: str = Field(min_length=3, max_length=500)


def invoke(fn, *args):
    try:
        return fn(*args)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc
    except PolicyError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/api/health")
def health():
    return {"ok": True, "mode": "simulation", "real_money_moved": False}


@app.get("/api/policy")
def policy():
    return ledger.policy()


@app.get("/api/stats")
def stats():
    return ledger.stats()


@app.get("/api/intents")
def intents():
    return ledger.list()


@app.get("/api/intents/{intent_id}")
def intent(intent_id: str):
    item = ledger.get(intent_id)
    if item is None:
        raise HTTPException(404, "Unknown intent")
    return {**item, "events": ledger.events(intent_id)}


@app.post("/api/intents", status_code=201)
def create(body: NewIntent):
    item, duplicate = invoke(ledger.add, body.task_id, body.merchant, body.service, body.amount_cents, body.currency, body.idempotency_key)
    return {**item, "idempotent_replay": duplicate}


@app.post("/api/intents/{intent_id}/simulate")
def simulate(intent_id: str, body: Simulation):
    return invoke(ledger.simulate, intent_id, body.outcome)


@app.post("/api/intents/{intent_id}/reconcile")
def reconcile(intent_id: str, body: Reconciliation):
    return invoke(ledger.resolve, intent_id, body.status, body.evidence)
