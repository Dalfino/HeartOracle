# BLOCKERS — ORACLE

Per PRD §0 rule 5: impossible-on-CPU or missing-asset → entry here (code,
cause, proposed fix), then stop. Never improvise substitutes.

---

## B-009 — segmentation model acquisition ladder + MYO gate (OPEN)

**Code:** B-009 · **Status:** OPEN (MYO gate 0.002 short) · **First raised:** pre-rebuild session, re-verified in rebuild session

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

## How to file a new blocker

```markdown
## B-0XX — <one-line title> (OPEN)
**Code:** B-0XX · **Status:** OPEN
**Cause.** <what is impossible / missing, with evidence>
**Proposed fix(es).** <ordered, with trade-offs>
```
