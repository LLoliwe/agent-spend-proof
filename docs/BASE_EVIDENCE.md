# Base payment evidence

This increment adds a read-only Base evidence workflow to the existing Agent Spend Proof prototype. It does not migrate the Celo competition entry, create an account, register a Builder Code, deploy a contract, sign a payment or establish genuine user adoption.

## Use

Start the existing local app with `python -m proof`, then open `http://127.0.0.1:8000/base`.

The synthetic example demonstrates quote validation without making a network request. It deliberately uses fixture addresses. Replace it with the exact public x402 payment requirement and your independently established operator expectations to inspect a real quote.

`POST /api/base/check` validates the original x402 V2 payment requirement against the selected network, token, recipient, resource URL and maximum atomic amount. Supplying both `tx_hash` and `payer` additionally queries the fixed RPC for that selected Base network. The browser can export the result as JSON. The endpoint accepts no user-selected RPC URL and never fetches the merchant URL.

Supported networks are explicitly separate:

| Network | Chain identifier |
| --- | --- |
| Base mainnet | `eip155:8453` |
| Base Sepolia | `eip155:84532` |

The existing local simulation ledger is not modified by evidence checks. A successful quote check is not spending approval. Caller-supplied quotes and injected test RPC results are inputs, not independently authenticated proof.

## Evidence boundaries

A matching ERC-20 transfer can establish that the selected chain observed a transfer matching the supplied token, payer, recipient and atomic amount. It does not establish that the transfer paid for this request. The current output explicitly preserves missing evidence for:

- The cryptographic relationship between the quote, request and payment.
- Registered Builder Code ownership and attribution in settlement calldata.
- Provider delivery, output acceptance and customer utility.
- Genuine customer counts, revenue or volume caused by this product.

Confirmation count and reported finality are distinct. Canonical-block checks and a finalised RPC head are evidence from the selected RPC, not an independent multi-provider audit. The whole application remains a local prototype. Keep it on `127.0.0.1`; existing authentication and public-hosting restrictions still apply.

## Standards and implementation references

- https://docs.x402.org/core-concepts/http-402
- https://docs.x402.org/extensions/builder-code
- https://docs.x402.org/extensions/payment-identifier
- https://docs.x402.org/extensions/offer-receipt
- https://docs.base.org/base-chain/network-information

These references describe capabilities in the wider ecosystem. A reference in this document is not a claim that every extension is implemented here. In particular, x402 already provides idempotency and signed offers/receipts; this prototype makes no novelty claim for those concepts.

## Next independently verifiable milestones

1. Bind the official signed offer, payment identifier and settlement into a single evidence packet.
2. Integrate the official Builder Code client extension using an actually registered code, and verify its actual onchain suffix.
3. Verify delivery evidence against a real provider's response and the user's acceptance criteria.
4. Observe a real independent user task, with consent and accurate usage accounting.

No chain write or financial transaction is part of this change.
