# TIER B — COPILOT HANDOFF (human/agent-executed, GPU required)

Everything that **cannot** be done inside a CPU-only sandbox is packaged here
so a human, or a delegated coding agent, can execute it without context loss.

## What Tier B is

Per PRD-002 §14: the ACDC evaluation + ONNX INT8 export runs **on Kaggle's
free T4 GPU** and publishes dataset `oracle-seg-v1`
(`seg.onnx` · `seg_int8.onnx` · `meta.json` · `metrics.csv`).

## Prerequisites (the only things delegation cannot supply)

1. A Kaggle account with **phone verification** (required by Kaggle for GPU
   notebooks). No API can bypass this — it is Kaggle's gate, not ours.
2. A Kaggle API token: kaggle.com → Settings → **Create New Token** →
   yields `KAGGLE_USERNAME` + `KAGGLE_KEY`.

## Delegation recipe (no interactive steps beyond credentials)

```bash
export KAGGLE_USERNAME=...   # your token
export KAGGLE_KEY=...

bash tools/run_tier_b_kaggle.sh all          # push → poll (≤6 h) → pull → models/
bash tools/fetch_model_meta.sh               # checks metrics.csv against P2 gates
```

Or step-by-step: `push` → `status` → `pull` (see script header). To resume
waiting after an interruption: `bash tools/run_tier_b_kaggle.sh --poll-only`.

**Physical constraint (verified):** Codespaces/sandbox VMs have **no GPU**.
They serve as the control room only — push, poll, pull. All training/
evaluation/export compute happens on Kaggle T4.

## Acceptance gates (PRD §9 P2)

| Metric | Threshold |
|---|---|
| Dice LV | ≥ 0.90 |
| Dice MYO | ≥ 0.82 |
| Dice RV | ≥ 0.85 |
| HD95 (LV) | ≤ 6 mm |

Recorded B-009 evidence (INT8, min-max normalization): LV 0.905 ✅ ·
RV 0.875 ✅ · **MYO 0.818 ❌ (short 0.002)** · HD95 pending. Preferred fix:
five-fold softmax-averaged ensemble export — see `BLOCKERS.md` B-009.
If `fetch_model_meta.sh` prints `GATES FAILED`, file it under B-009 and
consult the fix ladder there.

## Paste-ready prompt for a delegated agent

> You are executing ORACLE-PRD-002 Tier B. Read `PRD.md` §14, `AGENTS.md`,
> `BLOCKERS.md` B-009, and `tools/run_tier_b_kaggle.sh` header first.
> Environment: `KAGGLE_USERNAME` and `KAGGLE_KEY` are provided; the machine
> has no GPU (control room only). Run `bash tools/run_tier_b_kaggle.sh all`,
> then `bash tools/fetch_model_meta.sh`. Report the P2 gate table verbatim
> from `models/metrics.csv`. If any gate fails, STOP and append a BLOCKERS.md
> entry (code B-009, cause, evidence) — do not improvise substitutes (§0
> rule 5). Commit convention: `ORACLE-TIERB: <verb> <object>`.
