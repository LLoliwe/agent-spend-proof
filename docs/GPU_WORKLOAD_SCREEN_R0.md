# Pryntor GPU workload screen — 17 October 2026

**Founder-confirmed: historical paid GPU invoices: none. Historic realised GPU savings: NOT APPLICABLE.** Never mark advertised price comparisons as realised savings.

Source of truth: [PRY-223](https://linear.app/pryntor/issue/PRY-223) and [company runbook](https://docs.google.com/document/d/1oRi8PG4VPBw08cCllV5fwEHGAUgD1PM9pgdLCb9D4qE/edit). No providers have been authenticated to checkout, no paid instances requested, and zero spend was initiated.

## Actual project triage

- **PRY-182 Robotics R4:** The pinned MuJoCo simulation is CPU-first; lack of authorized RP1 assets and executed holdouts is the obstacle. Do not buy GPUs to repair a scientific verification failure.
- **PRY-191 Motion Director:** Existing FFmpeg CI rendered a synthetic 30-second clip with no evidenced GPU necessity. Maintain CPU/free-CI option; final visual/rightsholder review remains open.
- **PRY-170 FRAMEZERO:** Comfy/SDXL is a possible GPU-bound inference workload but no actual generated output, pinned model checksum, provider entitlement or output QA has been verified. Do not rent GPU to fabricate a comparison.

## Pricing screen — publicly advertised, not checkout or actual cost

Dated quote inputs are in `gpu_quotes_2026-10-17.json`. Runpod official October guide lists A5000 24GB $0.27/h, 3090 24GB $0.50/h, 4090 24GB $0.89/h. Modal officially publishes A10 GPU-only $0.000306/s ($1.1016/h); CPU, RAM, data fees extra. For an *assumed* 15 min GPU-only slice, illustrations are $0.0675, $0.125, $0.2225, $0.2754. These are different GPUs, not measured equivalent successful outcomes or complete bills. No dollar difference is "saved" money.

Vast.ai marketplace has no fixed eligible rate without a selected host and associated storage/bandwidth. Hugging Face ZeroGPU user quota and Modal Starter claimed allowance are *not authenticated account balances* and cannot be treated as company cash, compatible Comfy SDK endpoints or automatic credits. Public GPU Terminal was inaccessible on this follow-up web read; earlier cached snapshot remains historical only.

## Reproduce without credentials or network

```bash
python3 -m unittest discover -s tests -p 'test_gpu_workload_screen.py' -v
python3 scripts/gpu_workload_screen.py --workloads docs/gpu_workloads_2026-10-17.json --quotes docs/gpu_quotes_2026-10-17.json --minutes 15
```

The CLI is intentionally read-only and deterministic. It emits decisions and hypothetical **GPU-only** price illustrations; it cannot provision, reserve, buy, call paid APIs or assert savings. Denies malformed inputs and false historical baselines.

**Release gate:** require FRAMEZERO fixed checkpoint/model rights, original safe test input/output criteria, verified no-cost account balance and spend cap, provider-specific region/inventory/charges, a completed real output, all-in job cost, independent output QA and human signoff before claiming cost-avoidance economics. If none is available R0, explicitly PARK the GPU phase.
