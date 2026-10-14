# AGENT / SPEND PROOF

**Non-custodial agent spending policy and receipt ledger.** Proof of concept for Celo's [Agents on Open Rails hackathon](https://www.loops.house/agents-on-open-rails), targeting **Build with `buy`**.

> **IMPORTANT: SIMULATION ONLY.** This repository does NOT send Celo transactions, integrate a wallet, call live `buy` services, or claim mainnet activity. All `SIM-` transaction references are fictional demonstration markers. No prizes/grants/customers have been secured.

## Why it exists

When an AI agent pays a third-party API, its operator needs three answers: **Was the spend allowed? Did the payment settle? Was the service delivered?** Proof records each request against strict policy rules and produces an auditable decision trail. If the settlement state is unknown, it **blocks retry**, pending reconciliation. This is a deliberately narrow prototype, not a production-safe payment platform.

## Quick start

```sh
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m proof
# open http://127.0.0.1:8000
```

On Windows use `.venv\\Scripts\\activate`. Run `pytest -q` to execute policy/ledger tests. No credentials or blockchain funds required.

## API

- `GET /api/health`, `/api/policy`, `/api/stats`, `/api/intents`
- `POST /api/intents` - evaluate allowlist, per-call cap, per-task budget, unique idempotency key. Log both approved and rejected requests.
- `POST /api/intents/{id}/simulate` - one-shot demo of delivered, missing delivery, or ambiguous settlement; **never executes a payment**.
- `POST /api/intents/{id}/reconcile` - add demo evidence and resolve ambiguity. No retry automation.
- `GET /api/intents/{id}` - full auditable event history.

Example:

```sh
curl -X POST http://127.0.0.1:8000/api/intents \
  -H 'Content-Type: application/json' \
  -d '{"task_id":"creator-brief-01","merchant":"https://data.example.org","service":"public-data-brief","amount_cents":30,"currency":"USD","idempotency_key":"creator-brief-call-001"}'
```

## Limits by design

- **No mainnet wallet integration, user authentication, encryption-at-rest, hosted access control, or production-grade reconciliation.** Only run it on `127.0.0.1`, never expose a public mutable demo without adding authentication/rate limiting.
- Allowlisted URLs are illustrative `.example.org` domains, not functioning merchant services.
- An allowed demo intent is **NOT** permission to spend real money.
- Not yet competition-eligible: real independent third-party paid calls, real users, registered ERC-8004 identity, Loops registration and qualifying mainnet transaction evidence are outstanding.
- Adapt the real payment layer to the **official** [`buy` reference implementation](https://github.com/celo-org/buy-skill) after separately obtaining documented user spending authorization. Verify merchant quote, final settlement proof, pay-to wallet, ERC-8004 identity, attribution rules, and double-spend controls **before** going live.

## Proposed commercial thesis (untested)

Hosted enterprise audit and policy layer for teams of autonomous agents. Test demand with actual operators before charging. Prototype software is MIT licensed, no warranty. See [execution plan](docs/ROADMAP.md), [threat model](docs/THREAT_MODEL.md), and [submission draft](docs/SUBMISSION_DRAFT.md).

## Public disclosure

This repository deliberately excludes private company strategy, clients, application credentials, wallet keys and any paid-service tokens. Created during the October-November 2026 hackathon build period.
