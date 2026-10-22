# Agents on Open Rails — draft, NOT submitted

**Project:** Agent Spend Proof

**Track:** Build with `buy` (working target)

**Problem:** Agent developers lack a clear audit trail linking a tool purchase to authorisation, actual settlement, fulfilment and a user task. With ambiguous payment responses, naive retries can double-spend.

**Approach:** An explicit spending policy evaluates vendor, per-task budget, service price and idempotency; a receipt ledger records the action and a distinct service-delivery status. Ambiguous settlement states require an operator's review before further action.

**Current implementation:** Functional local FastAPI + SQLite prototype with policy rules, a dashboard, synthetic demo activity and automated tests. **No onchain actions yet.**

**Intended Celo integration:** `buy` x402 client purchasing independently hosted services on Celo; ERC-8004 agent identity; PayTo/attribution according to final Loops instructions. Real use is essential and remains to be built and documented.

**Evidence TO OBTAIN before submission:** Loops registration/project URL; public repository URL; registered ERC-8004 identity URL; real consumer/operator (consenting); independent provider name; mainnet transaction URL and receipt; content or result of purchased service; quote/price; a working demo; metrics based only on verifiable transactions.

**Status:** Draft only. Do not submit this as completed or claim any mainnet usage.
