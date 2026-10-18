# Reciprocal Partner Return: Evidence Contract

Internal Pryntor policy source: existing ATLAS OMEGA partner playbook (PRY-6, PRY-315, PRY-131). This public **vendor-neutral** helper is intentionally small. It neither executes third-party tools nor contacts an account, and it makes no claims about any named vendor. No personal accounts, customer information, contracts, proprietary partner pricing or private strategy may enter this public repository.

## Use

```bash
python3 pryntor-ops/partner_return.py pryntor-ops/partner_return_sample.json
pytest -q tests/test_partner_return.py
```

The sample is a **fictional local simulation**. Its numbers must not be included in a partner-facing benchmark or a commercial claim. The checker rejects attempts to represent fixture evidence as live test output.

## Operator obligations

1. First write the date-stamped bargaining assessment and official primary-source map in the *existing* Pryntor partnership tracker. Name alternatives only for tasks each can genuinely perform, and state when products serve different roles.
2. Run only on opted-in, licensed, synthetic or rights-cleared data. Never activate trials, cards, recurring subscriptions, credentials, network calls or connected apps via this helper.
3. Enter one record per provider, task and trial. Use **the same** task/trial identifiers and measured environments across providers before interpreting comparative performance. Report every failure, abstention and missing measurement.
4. Use `documentation_only` with `outcome=not_tested` for public documentation research. Use `local_simulation` for mock adapters. Only record `authorized_live` after the corresponding external action actually occurred with proper authorization and evidence. Evidence references are operator supplied and **not verified by this checker**.
5. Keep an independent reviewer and the original reproducible transcript/commit, provider version, licence check, environment, test definition and exact run receipt. This helper does not validate permissions, statistics, authenticity or fairness.
6. Distinguish partner invitation, redemption, available credits, actual integrated product, test result, signed co-marketing and revenue. Manual release permission is required for every public partner mention, comparative chart or attributable report. No purchased favourable review.

`public_claim_allowed` is **always false** by design: independent review and authorised publication are separate human decisions. A passing CLI run proves only schema, denominator and evidence-class checks. It never verifies vendor speed, cost, quality or security, and never triggers autonomous outreach.

## Data contract

Root fields: `schema_version` (1), `niche`, `environment`, `independent_reviewed` (bool, human attestation), and `records` (1 to 2000). Record fields: `provider`, `task_id`, `trial`, `mode`, `outcome`, `latency_ms` (nonnegative number or null), `cost_usd` (nonnegative decimal string or null) and `evidence_ref` (operator-controlled locator). Unknown keys are refused to reduce accidental disclosure. There is no secret field.

Outputs include per-provider observed denominators, success fraction, observed p50/p95 latency and cost per success only when every measured attempt has known cost. Unknowns remain null. The checker never asserts significance or a winner.
