"""SQLite-backed simulated spend ledger. There is deliberately no live payment executor."""
from __future__ import annotations

import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

DEFAULT_DB = os.environ.get("PROOF_DB", "./proof.sqlite3")
MAX_SINGLE_CENTS = 250
MAX_TASK_CENTS = 1000
ALLOWED_VENDOR_HOSTS = ("api.example.org", "browser.example.org", "data.example.org")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PolicyError(Exception):
    pass


class Ledger:
    def __init__(self, path: str = DEFAULT_DB):
        self.path = path
        self._lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA busy_timeout=5000")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS intents (
            id TEXT PRIMARY KEY,
            idempotency_key TEXT UNIQUE NOT NULL,
            task_id TEXT NOT NULL,
            merchant TEXT NOT NULL,
            service TEXT NOT NULL,
            amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
            currency TEXT NOT NULL,
            mode TEXT NOT NULL CHECK(mode = 'simulation'),
            status TEXT NOT NULL,
            reason TEXT NOT NULL DEFAULT '',
            tx_hash TEXT,
            delivery_status TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intent_id TEXT NOT NULL REFERENCES intents(id),
            event_type TEXT NOT NULL,
            details TEXT NOT NULL,
            occurred_at TEXT NOT NULL
        );
        """)

    @contextmanager
    def transaction(self):
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def _event(self, intent_id: str, name: str, detail: str):
        self.db.execute("INSERT INTO events(intent_id,event_type,details,occurred_at) VALUES(?,?,?,?)", (intent_id, name, detail, now()))

    def policy(self) -> dict[str, Any]:
        return {"mode": "simulation", "live_enabled": False, "merchant_allowlist": list(ALLOWED_VENDOR_HOSTS),
                "max_single_cents": MAX_SINGLE_CENTS, "max_task_cents": MAX_TASK_CENTS,
                "currency": "USD", "manual_mainnet_approval_required": True,
                "key_custody": "none; this service never stores or handles wallet keys"}

    def get(self, intent_id: str) -> dict[str, Any] | None:
        row = self.db.execute("SELECT * FROM intents WHERE id=?", (intent_id,)).fetchone()
        return dict(row) if row else None

    def add(self, task_id: str, merchant: str, service: str, amount_cents: int, currency: str, idempotency_key: str) -> tuple[dict, bool]:
        with self.transaction():
            prev = self.db.execute("SELECT * FROM intents WHERE idempotency_key=?", (idempotency_key,)).fetchone()
            if prev:
                if (prev["task_id"], prev["merchant"], prev["service"], prev["amount_cents"], prev["currency"]) != (task_id, merchant, service, amount_cents, currency):
                    raise PolicyError("Idempotency key is already bound to a different request")
                return dict(prev), True

            spent = self.db.execute("SELECT COALESCE(SUM(amount_cents),0) FROM intents WHERE task_id=? AND status IN ('approved','settled','delivery_failed','uncertain')", (task_id,)).fetchone()[0]
            from urllib.parse import urlparse
            parsed = urlparse(merchant)
            if parsed.scheme != "https" or parsed.hostname not in ALLOWED_VENDOR_HOSTS or parsed.username or parsed.password or parsed.port:
                reason = "Merchant not on approved HTTPS allowlist"
            elif currency != "USD":
                reason = "Only simulated USD is supported in this prototype"
            elif amount_cents > MAX_SINGLE_CENTS:
                reason = "Per-request maximum exceeded"
            elif spent + amount_cents > MAX_TASK_CENTS:
                reason = "Task budget exceeded"
            else:
                reason = "Approved for DEMO ONLY; no payment was authorised or made"

            status = "approved" if reason.startswith("Approved") else "rejected"
            intent_id = str(uuid.uuid4())
            timestamp = now()
            self.db.execute("INSERT INTO intents(id,idempotency_key,task_id,merchant,service,amount_cents,currency,mode,status,reason,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                            (intent_id,idempotency_key,task_id,merchant,service,amount_cents,currency,"simulation",status,reason,timestamp,timestamp))
            self._event(intent_id, "policy_decision", reason)
            return self.get(intent_id), False

    def simulate(self, intent_id: str, outcome: str) -> dict[str, Any]:
        outcomes = {"delivered": ("settled", "delivered"),
                    "missing_delivery": ("delivery_failed", "missing"),
                    "unknown_settlement": ("uncertain", "unknown")}
        if outcome not in outcomes:
            raise PolicyError("Unsupported simulation outcome")
        with self.transaction():
            intent = self.get(intent_id)
            if intent is None:
                raise KeyError("Unknown intent")
            if intent["status"] != "approved":
                raise PolicyError("Intent cannot be executed twice or while in this state")
            status, delivery = outcomes[outcome]
            # This is a synthetic identifier, NOT a blockchain transaction hash.
            synthetic_ref = "SIM-" + uuid.uuid4().hex[:20].upper()
            self.db.execute("UPDATE intents SET status=?,delivery_status=?,tx_hash=?,updated_at=? WHERE id=?", (status,delivery,synthetic_ref,now(),intent_id))
            self._event(intent_id, "simulation", f"SIMULATED: {outcome}. No funds moved. Reference {synthetic_ref}")
            return self.get(intent_id)

    def resolve(self, intent_id: str, resolved_status: str, evidence: str) -> dict[str, Any]:
        if resolved_status not in ("settled", "not_settled"):
            raise PolicyError("Resolution must be settled or not_settled")
        if not evidence.strip() or len(evidence)>500:
            raise PolicyError("Concise reconciliation evidence is required")
        with self.transaction():
            intent = self.get(intent_id)
            if intent is None:
                raise KeyError("Unknown intent")
            if intent["status"] != "uncertain":
                raise PolicyError("Only uncertain payments can be reconciled")
            self.db.execute("UPDATE intents SET status=?,updated_at=? WHERE id=?", (resolved_status,now(),intent_id))
            self._event(intent_id,"manual_reconciliation", f"DEMO reconciliation: {resolved_status}; operator evidence: {evidence}")
            return self.get(intent_id)

    def list(self, limit: int = 100) -> list[dict[str,Any]]:
        return [dict(r) for r in self.db.execute("SELECT * FROM intents ORDER BY created_at DESC, rowid DESC LIMIT ?", (limit,))]

    def events(self, intent_id: str) -> list[dict[str,Any]]:
        return [dict(r) for r in self.db.execute("SELECT event_type,details,occurred_at FROM events WHERE intent_id=? ORDER BY id", (intent_id,))]

    def stats(self) -> dict[str,Any]:
        data = self.db.execute("SELECT COUNT(*),COALESCE(SUM(CASE WHEN status IN ('settled','delivery_failed') THEN amount_cents ELSE 0 END),0),COALESCE(SUM(CASE WHEN status='rejected' THEN amount_cents ELSE 0 END),0),SUM(CASE WHEN status='uncertain' THEN 1 ELSE 0 END) FROM intents").fetchone()
        return {"intents":data[0], "simulated_settled_cents":data[1], "rejected_requested_cents":data[2], "uncertain":data[3] or 0, "real_money_moved":False}
