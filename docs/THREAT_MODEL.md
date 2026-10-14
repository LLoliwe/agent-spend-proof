# Threat model (0.1 demo)

**Scope:** local simulation service only. No funded wallets, no merchant execution, no signing keys, no permission to spend.

| Risk | Demonstration mitigation | Production gap |
|---|---|---|
| Double request | Unique `idempotency_key`, payload mismatch rejected | Distributed wallet/provider idempotency and finality proof |
| Payment settled despite HTTP 500 | `uncertain` blocks repeat execution | Read live chain receipts/provider state first |
| Malicious merchant | HTTPS host allowlist, no user-info or explicit ports | DNS pinning, service verification, quote signatures, URL normalisation |
| Agent budget overrun | Atomic SQLite write lock and caps | Multi-tenant holds, expirations, concurrency on chain |
| Forged settlement evidence | Events clearly labelled `SIMULATED`, fake `SIM-` IDs | Validate transaction hash, chainId 42220, sender, recipient, amount, finality |
| Secret exposure | No environment keys needed | Secure signing + key custody separated from web server |
| Unauthorised user access | Bound to localhost by default | Authentication, authorisation, CSRF, rate limits, tenant isolation |
| Privacy | Demo-only synthetic data, no PII collected | Data retention, audit encryption, access control |
| SDK supply-chain compromise | Minimal dependencies | Lockfiles, SBOM, dependency scanning |

**Kill switch:** There is no mainnet executor in the product. Adding one requires an independent security review and the operator's explicit approval. 
