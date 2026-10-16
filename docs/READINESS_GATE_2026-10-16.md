# Agent Spend Proof — release and evidence gate (16 October 2026)

**Disposition: REVISE, NOT A SUBMISSION.** This R0 engineering branch performs offline validation only. It never signs, buys, generates a wallet, sends mainnet funds, registers ERC-8004 identity or sends an entry.

## Direct organiser and live-repository facts

- Loops House confirmed participant enrollment by email 14 October 2026; their 16 October support reply says the **submission tab is in the sidebar** after enrollment at https://www.loops.house/agents-on-open-rails/playground/ideate .
- Official registration and submission close **9 November 2026 at 09:00 GMT (11:00 SAST)**; evidence-review target is 8 November.
- The **Build with buy** track allocates **$1,000 across five projects**, judges genuine third-party paid API usage and meaningful independent users, and requires Celo mainnet and **ERC-8004** agent identity.
- The track FAQ says **no tag needed for Build with buy**, but general rules say to tag every transaction and that **x402 requires the PayTo wallet address**. Confirm wallet/project association and any portal fields. Email enrollment is NOT project submission.
- Celo main branch already implements a simulated ledger, unpaid quote inspector and read-only ERC-20 receipt verifier; none of those proves a purchase or fulfilled service.

## What's implemented in this branch

- `proof.purchase_gate.prepare_purchase`: verifies that the selected **unpaid 402 quote** matches the exact request-body hash, is Celo chain 42220, has a valid token/payer/payTo, is non-self-payment, and is below an explicitly supplied operator ceiling. It returns a cryptographic **preflight fingerprint** without enabling any payment. A value from the 402 challenge is not, by itself, proof of an independently verified token or legitimate merchant.
- `proof.eligibility_gate.audit_evidence`: checks whether a packet includes enrollment confirmation, portal project URL, ERC-8004 identity URL, wallet, independent provider, mainnet tx, purchased result, independent user, demo, external signoff, and a final accepted submission receipt. The function **never** claims an independently verified or submitted project.
- `python -m proof.readiness_cli /path/to/private-evidence.json`: read-only offline packet check. Starts from `docs/EVIDENCE_PACKET.example.json`; never put user credentials, personal details, or payment authorisations on public GitHub.
- 39 new targeted offline tests for chain, URL, quote mutation, amount, replay-resistant quote fingerprint, fake receipts and no premature release. CI runs full repo `pytest -q` on PR.

## Outstanding evidence / actions

1. **Portal:** sign into Loops with enrolled account, inspect the submission sidebar, create/link the **project entry** and record track, project URL, wallet/PayTo and any ID. Retain evidence.
2. **Wallet & identity:** on **owner's trusted computer**, configure the official `@celo/buy` keychain client and a Celo mainnet wallet. Register the agent using the official ERC-8004 flow. Verify chain ID 42220 and linked identity on an independent explorer. Never paste keys or seeds in chat, CI or a public issue.
3. **Provider & quote:** read https://gateway.usebuy.ai/v1/catalog, choose an available genuinely independent service, construct exact commercial task body, obtain **unpaid HTTP 402** and select its exact token/amount/recipient. Check quote expiry, token decimals, trusted vendor legitimacy and complete ZAR budget including funding/bridging/fees. The recorded historical **R50 combined ceiling is not automatic transaction authorisation**.
4. **Purchase:** after exact owner approval, execute the *single* requested payment on the trusted owner machine via verified official `buy`. Keep hash, buy receipt, chosen token, PayTo, response/delivery proof and timestamp. Never automatically retry a request after timeout, unknown settlement, HTTP 500 or `retryable:false`; reconcile via `buy receipts --resolve` and read-only explorer evidence first.
5. **Real user:** obtain a voluntary independent tester with useful task activity and consent. No fabricated volume or founder-funded pseudo-wallets; organizer FAQ distinguishes qualifying historical wallets from newly onboarded users.
6. **Submission:** independent review of every claim and a reproducible demo, then submit via Loops and retain its accepted submission receipt before deadline.

Source of official `buy` workflow and failure semantics: https://github.com/celo-org/buy-skill/blob/main/skills/use-api-gateway/SKILL.md . Organizer: https://www.loops.house/agents-on-open-rails .

**R0 CODE CAN PASS CI WHILE OFFICIAL ENTRY REMAINS BLOCKED. No payments, registrations or submissions were made by this branch.**
