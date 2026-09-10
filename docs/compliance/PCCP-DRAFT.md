# Predetermined Change Control Plan (PCCP) — DRAFT

Anchored to: **Marketing Submission Recommendations for a Predetermined Change
Control Plan for Artificial Intelligence-Enabled Device Software Functions**
(FDA final guidance, December 3, 2024). This draft is written now so that
retraining is a governed, pre-authorized procedure rather than a submission
event later.

## 1. Description of modifications (what may change)

| Component | Modifiable within this PCCP | Out of scope (new submission) |
|---|---|---|
| Segmentation ensemble (ONNX INT8 bundle) | weight refresh via approved retraining protocol | architecture family change; output class contract change (["BG","RV","MYO","LV"]) |
| Knowledge base (RAG chunks) | adding/chunking guideline excerpts (verbatim, sourced) | guideline interpretation summaries written by the vendor |
| Post-processing | largest-CC filter params, plausibility bounds | new derived clinical metrics (e.g., strain) |
| Calibration | slice thickness / normalization constants | modality expansion (CT, ECG adapters carry own dossiers) |

## 2. Modification protocol (how changes are made)

1. **Trigger** — one of: (a) new public cohort ingested (M&Ms wave);
   (b) drift alarm (Section 4); (c) protocol amendment approved in review.
2. **Retrain** — Tier B Kaggle pipeline (`tools/run_tier_b_kaggle.sh`),
   frozen split enforcement: ACDC 101–115 remains **test-only forever**.
3. **Export** — per-fold ONNX INT8 + argmax-consistency check vs FP32
   (requirement: 100% argmax agreement on a 30-frame probe set).
4. **Acceptance testing (all mandatory, on frozen holdout):**
   - LV Dice ≥ 0.90 · MYO Dice ≥ 0.82 · RV Dice ≥ 0.85 (frame-level, ensemble)
   - HD95(LV) mean ≤ 6.0 mm
   - EF MAE ≤ 5.0 pp vs reference volumes
   - Gates G1–G5 pass on the synthetic regression suite
   - no empty-prediction regression vs incumbent (RV 6/257 baseline)
5. **Release** — versioned model card + checksum; previous bundle retained
   for instant rollback; audit-trail entry with hashes.
6. **Rollback** — any post-release breach of acceptance ⇒ revert to previous
   bundle, log incident in BLOCKERS.md, root-cause before re-release.

## 3. Versioning

`ORACLE-model-v{major}.{minor}` — major: architecture/contract change (outside
PCCP); minor: PCCP-authorized weight/KB refresh. Model cards live in
`evaluation/modelcards/`.

## 4. Drift monitoring (deployed state)

- input statistics monitor: intensity histograms, spacing, phase-count mixes
- output statistics monitor: volume/EF distributions vs reference bands
- alarm thresholds set from holdout distributions (p99 envelope)
- quarterly KB freshness review (guideline versions)

## 5. Status

DRAFT — ready to be annexed to an intended-use statement freeze. Not a
submission document; no regulatory submission has been made.
