# Live Celo test gate — 14 October 2026

**Budget authority:** Operator approved **R50 total across all real-world tests**. This is a maximum, not a requirement to spend. **R0 has been spent by this project as of writing.** No stablecoin funding or payment has occurred.

## Safety first

- Wallet setup must run on the owner's trusted computer and use the OS keychain, **never a key or seed phrase pasted into ChatGPT, a public issue, CI, or GitHub**.
- Celo buy documentation: `npx --yes @celo/buy@0.8.2 setup --name buy` creates a local keychain wallet; `npx --yes @celo/buy@0.8.2 mcp install --client all` is optional. Confirm the installed version and docs before using.
- Before any mainnet purchase: (1) verify the **official** live vendor catalog, (2) inspect the exact request JSON, (3) obtain the unpaid 402 quote, (4) confirm amount **and stablecoin token** and wallet balance, (5) ensure combined wallet funding/bridging/service fees and the purchase remain below R50 equivalent at contemporaneous rates, (6) confirm correct Loops registration, ERC-8004 identity and attribution/PayTo details.
- Never use the demo merchant allowlist as a live vendor allowlist; never regard a simulated quote as price authority.
- Never autofund, autosign, autobuy, blind-retry a purchase, or attempt to manufacture independent users or transaction volume.
- If a paid call returns a timeout, 500, `settle_uncertain`, or `retryable:false`, STOP. Investigate the actual transaction via an explorer/read-only RPC, retain correlation IDs and all receipts, and never repeat the purchase on a guess.
- All actual expenses and their ZAR equivalents must be recorded. At the ceiling, stop automatically and seek new express approval.
- Do not post personal details or payment authorizations publicly. Token transfer amounts and tx hashes are public onchain and suitable for evidence.

## Tested integration capabilities

- `proof.buy_quote.inspect_quote`: makes a POST to exact HTTPS `gateway.usebuy.ai` URL using **no wallet keys**, reads 402, freezes exact body hash. Not a live payment.
- `proof.celo_receipt.verify_transfer`: read-only confirmation that the expected **token, payer, recipient and atomic amount** match a successful Celo mainnet Transfer event, after at least 12 blocks. A valid receipt is not proof of a purchased result, independent users, ERC-8004 registration, or hackathon tagging.

Example (read-only quote, does not spend):

```python
from proof.buy_quote import inspect_quote
body = {"model":"maximo-atlas-1.3","max_tokens":256,
        "messages":[{"role":"user","content":"Reply OK"}]}
print(inspect_quote(url="https://gateway.usebuy.ai/cencori/v1/chat/completions",body=body))
```

If the upstream route or price differs from the **live catalog**, update the request before quoting. The code rejects unexpected 200s and 500s as insufficient quote evidence.

Example (read-only receipt validation after a payment, not before):

```python
from proof.celo_receipt import verify_transfer
# All six entries must come from independent verified payment evidence.
print(verify_transfer(tx_hash="0x<actual 64 hex>", token="0x<actual token>",
                      payer="0x<actual payer>", pay_to="0x<actual merchant>",
                      amount_atomic=12345))
```

## Eligibility

- Loops: https://www.loops.house/agents-on-open-rails. Deadline **9 November 2026, 09:00 GMT**.
- Celo `buy` skills: https://github.com/celo-org/buy-skill
- Grant eligibility: https://forum.celo.org/t/prezenti-season-3-is-open-frontier-anchor-and-boost-grants-for-celo/13714 ; mainnet evidence, credible distribution and reusable public infrastructure required before Frontier submission.
- Mainnet ERC-8004 identity and a registration-issued tag must precede credited mainnet transactions. For x402, the hackathon specifically requests a PayTo wallet because tags are not supported by x402 as of the published rules.
- No cash or prize is guaranteed. No hackathon entry or grant application can be called submitted until a provider receipt is retained.
