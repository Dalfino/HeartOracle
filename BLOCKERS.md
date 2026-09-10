# BLOCKERS — ORACLE

Per PRD §0 rule 5: impossible-on-CPU or missing-asset → entry here (code,
cause, proposed fix), then stop. Never improvise substitutes.

---

## B-009 — segmentation model acquisition ladder + gate status (AMENDED → near-close)

**Code:** B-009 · **Status:** AMENDED (Update 3: all gates pass under the documented volume-level protocol; closure pending protocol review + 50-patient extension) · **First raised:** pre-rebuild session, re-verified in rebuild session

**Cause.** PRD §3 pins a $0 budget and CPU-only local inference, but the
ACDC-trained U-Net weights are not distributable through this repo and no
ready-made `.onnx` exists. A probe ladder was evaluated (session evidence,
commit history of the pre-rebuild workspace):

| Probe | Result |
|---|---|
| P2 — ready-made `.onnx` from HF ACDC repos | **Dead end.** All 32 relevant ACDC repos expose zero `.onnx` files |
| P1 — HF weights → export on Kaggle | **Viable.** `MohidAbdullah/ACDC-Heart-Segmentation` (MIT): strict load 160/160 tensors; ONNX export opset 17 OK; INT8 125.5 MB → 39.8 MB; argmax consistency 100% |
| P4 — overnight CPU training / Kaggle GPU training | Guaranteed-but-slow fallback |

**Critical preprocessing finding.** The upstream model expects **min-max
[0,1] normalization** — z-score normalization collapses MYO Dice from 0.889
to 0.495. Shape-only smoke tests cannot catch this; `meta.json` therefore
carries a documented `"norm": "minmax01"` field that `seg.onnx_infer`
honors (§6 default remains z-score with mean/std).

**Holdout evaluation (30 frames, INT8, min-max):**

| Class | Dice | PRD §9 P2 gate |
|---|---|---|
| LV | **0.905** | ≥ 0.90 ✅ |
| RV | **0.875** | ≥ 0.85 ✅ |
| MYO | **0.818** | ≥ 0.82 ❌ (short by 0.002) |

Class order verified native `["BG","RV","MYO","LV"]` = §6 contract; no
remapping needed. HD95(LV) not yet fully evaluated against the ≤6 mm gate.

**Proposed fixes (in preference order).**
1. **Five-fold ensemble export** — softmax-average the folds, export as a
   single ONNX INT8. Expected +1–2 Dice points; most likely to close the
   MYO gap. (Note: ensemble improves calibration/margin; it does not raise
   the single-model accuracy ceiling.)
2. Probe folds 2–5 for a best single fold — *rejected as primary*: test-set
   selection bias; only acceptable as a reported diagnostic, never as the
   shipped number.
3. P4 overnight CPU training / Kaggle GPU training — guaranteed compliance,
   highest time cost.

**Why this stays a blocker instead of "close enough".** The repo's own
guardrails (§15) and the advisory mission ("ORACLE advises, physicians
decide") are only trustworthy if the deterministic core meets its published
gates. Shipping 0.818 against a 0.82 gate — even 0.002 short — would mean
the VALIDATION_REPORT lies. The gate is the contract.

**Update 3 — sandbox rebuild session (ensemble rebuilt, HD95 measured).**
The 5-fold ensemble was rebuilt from the HF checkpoints on torch 2.14
(dynamo export, opset 17, per-fold INT8 39.8 MB → merged logit-mean
`seg_int8.onnx` 199.1 MB, bitwise-identical to mean-of-sessions
`max_abs_err=0.0`). Two merge bugs were caught and fixed during rebuild:
unnamed-node collisions after renaming, and a fatal `ReduceMean(axes=[0])`
that collapsed the batch axis (blending logits across slices — caught by
eval, LV Dice 0.23). The eval then ran on the official ACDC testing split,
patients 101–115 (30 ED/ES frames, 255–257 slices/class scored), volume-level
Dice over all slices of each frame (`tools/sandbox_eval/`, results in
`evaluation/`):

| Metric | LV | MYO | RV | Gate |
|---|---|---|---|---|
| Dice (per-frame mean) | **0.9135** | **0.8428** | **0.8776** | 0.90 / 0.82 / 0.85 |
| Dice (median frame) | 0.9414 | 0.8475 | 0.9145 | — |
| HD95 mean, mm | **3.69** | 4.89 | 5.84 | LV ≤ 6 mm |
| HD95 p95, mm | 8.87 | 9.56 | 12.73 | — |

EF (Simpson, 15 patients): MAE **2.72 pp**, bias +0.68 pp, worst 12.32 pp.

**Status after Update 3:** under the documented volume-level protocol, all
three Dice gates pass and HD95(LV) passes. This is *stronger* than Update 2's
protocol (per-frame aggregation on a 24-frame consistent subset; RV 0.8257
then) — the protocol difference is recorded, not hidden. B-009 is amended
toward closure pending (a) review of the Dice aggregation protocol against
PRD §9 wording, and (b) extension to the full 50-patient testing split.
Tail risk is honestly recorded: RV produced empty predictions on 6 slices
(smallest structure), and boundary p95 for RV reaches 12.7 mm — Dice gates
alone do not certify boundary quality, which is why HD95 is now part of the
eval. Latency: ~13.4 s/slice ensemble on 2 vCPU (5× a single fold).

---

## Historical note — B-001…B-008 (pre-rebuild session)

Eight spec gaps were resolved as pre-approved decisions in the original
build session (recorded in that session's BLOCKERS.md, which did not survive
the sandbox reset). They were re-absorbed into the rebuilt code where they
recur (e.g. `meta.json` extensions, contract-extra keys `phases`,
`study_dir`, `gap_mm`; hash-embedder offline fallback for tests). Any of
these decisions that surface as contentious during review should be
re-filed here with fresh evidence.

---

## Limitation ledger — what "fixing the limits" would actually take

Five limitations are published on the dashboard. Each was assessed for
whether engineering effort can remove it. Recorded here so nobody confuses
"rebuild and re-measure" with "clear the device".

| # | Limitation | Verdict | Path | Horizon |
|---|---|---|---|---|
| 1 | HD95 boundary error not fully evaluated | **Resolved this session** — measured (Update 3 table) | done in sandbox | done |
| 2 | Trained/evaluated on one dataset (ACDC) | Measurable — needs external data | run `tools/sandbox_eval/eval_seg.py` against M&Ms / M&Ms-2 (multi-vendor, public on application); script already consumes any NIfTI cohort | days of compute + dataset application |
| 3 | No plaque / FFR / calcium scoring | **Physics-bound, not a code gap** — cine MRI cannot image coronary plaque/calcium; CT-FFR needs CCTA fluid dynamics or an invasive wire | a separate CT-modality product; v0 returns honest nulls by design | a new project |
| 4 | Not FDA-cleared / CE-marked | **Regulatory, not engineering** — no sandbox produces clearance | IEC 62304 lifecycle + ISO 13485 QMS + clinical investigation + 510(k)/CE submission; requires a company, funding, clinical partners. This repo keeps the evidence chain audit-ready | years + institutional backing |
| 5 | No autonomous treatment logic | **By design — a safety property, not a gap** | none; removing the physician changes the device class and violates the PRD core rule ("ORACLE advises, physicians decide") | permanent by specification |

---

## How to file a new blocker

```markdown
## B-0XX — <one-line title> (OPEN)
**Code:** B-0XX · **Status:** OPEN
**Cause.** <what is impossible / missing, with evidence>
**Proposed fix(es).** <ordered, with trade-offs>
```
