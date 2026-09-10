# Traceability Matrix — Requirement → Implementation → Verification

Conventions: commits follow `ORACLE-P{phase}T{task}`; tests in `tests/` (repo);
dashboard regression evidence via agent-browser session logs (dev.log).

## A. Measured performance requirements (v0 CMR adapter)

| Req ID | Requirement | Implementation | Verification | Result |
|---|---|---|---|---|
| REQ-SEG-01 | LV frame Dice ≥ 0.90 (ensemble) | 5-fold AttentionUNet logit-mean, ONNX INT8 export | eval harness on ACDC 101–115 holdout | **0.9135 PASS** |
| REQ-SEG-02 | MYO frame Dice ≥ 0.82 | same | same | **0.8428 PASS** |
| REQ-SEG-03 | RV frame Dice ≥ 0.85 | same | same | **0.8776 PASS** |
| REQ-HD95-01 | LV mean HD95 ≤ 6.0 mm | EDT-based surface distance in eval | 30-frame official split | **3.691 mm PASS** |
| REQ-VOL-01 | EF MAE ≤ 5.0 pp vs reference | Simpson disk summation | 15-patient EF comparison | **2.72 pp PASS** |
| REQ-EXP-01 | INT8 export == FP32 argmax on probe set | graph-surgery ensemble merge (element-wise Sum/5) | merge equivalence check | **max_abs_err 0.0 PASS** |

Known tail (tracked, not a gate): RV empty predictions 6/257 slices; HD95 p95
RV 12.73 mm. See RISK-REGISTER R-02/R-03 and BLOCKERS.md.

## B. Platform requirements (this dashboard)

| Req ID | Requirement | Implementation | Verification |
|---|---|---|---|
| REQ-PLT-01 | Eval numbers served with provenance | `GET /api/oracle/eval` reads `src/lib/data/eval-results.ts` (committed copy of eval_summary.json) | curl + UI provenance block |
| REQ-PLT-02 | Pipeline demo executes real volumetric math | `src/lib/engine/geometry.ts` (Simpson, sqrt-calibrated phenotypes) | bun direct run: EDV/ESV hit targets ±1% |
| REQ-PLT-03 | Nothing human-visible without gates G1–G4 | `POST /api/oracle/pipeline` returns gate verdicts + hash-chained trail | browser run: ALL GATES PASS + chain head displayed |
| REQ-PLT-04 | Reports grounded, cited, disclaimed | `POST /api/oracle/report`: numerics injected only; Gate G5 (grounding/citations/RUO) | browser run: G5 PASS, 5 KB chunks cited |
| REQ-PLT-05 | Honest demo labeling | amber demonstration-mode banner; simulated-phantom wording | UI review (this file is the requirement) |
| REQ-PLT-06 | Deployment artifacts | docker/Dockerfile.platform + oracle, compose, non-root, healthchecks | structure-validated (sandbox has no daemon — CI validation tracked) |

## C. Regulatory artifact requirements

| Req ID | Artifact | Location |
|---|---|---|
| REQ-REG-01 | GMLP gap matrix | docs/compliance/GMLP-GAP-MATRIX.md |
| REQ-REG-02 | ISO 14971 risk file | docs/compliance/RISK-REGISTER-ISO14971.md |
| REQ-REG-03 | PCCP draft | docs/compliance/PCCP-DRAFT.md |
| REQ-REG-04 | STRIDE threat model | docs/security/THREAT-MODEL-STRIDE.md |
| REQ-REG-05 | AI governance charter | docs/governance/AI-GOVERNANCE.md |
| REQ-REG-06 | Data provenance & licensing | docs/data/DATA-SOURCES.md |

## D. Evidence retention

Evaluation JSONL (per-frame) + summaries are committed under `evaluation/`.
Dashboard display data is a committed read-only copy with provenance block —
updating it requires re-running the frozen protocol and committing both.
