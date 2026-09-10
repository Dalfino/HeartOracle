# Risk Management File — ISO 14971 Shape

Scope: ORACLE v0 (CMR quantification adapter + platform). Severity and
probability use a 1–5 ordinal scale; RPN = S×P (pre-control). Residual is the
engineering team's honest current view after listed controls. This register is
reviewed at every `ORACLE-P{n}` phase boundary.

| ID | Hazard | Cause | Effect | S | P | Controls | Residual | Anchor |
|---|---|---|---|---|---|---|---|---|
| R-01 | Systematically biased EF (over/under) | domain shift: unseen vendor/pathology/protocol | HF phenotype misclassification; wrong therapy pathway | 4 | 3 | RUO labeling · cohort provenance in report · physician sign-off · PCCP retraining triggers | **medium** | ISO 14971 §4–7; GMLP #4 |
| R-02 | Segmentation failure on small/edge structures | RV empty-prediction mode (6/257 holdout slices, measured) | wrong volumes → wrong quantification | 4 | 2 | Gate G2 empty/area plausibility · largest-CC filter · flag-and-withhold on fail | **medium** | GMLP #7 |
| R-03 | Boundary error at critical structures | HD95 tails (RV p95 12.73 mm, measured) | misquoted chamber dimensions | 3 | 3 | HD95 gate ≤ 6 mm (LV PASS 3.69 mm) · per-structure verdicts in report | **medium** | GMLP #7 |
| R-04 | Hallucinated clinical content in report | ungrounded LLM generation | false claims attributed to guidelines | 5 | 2 | Gate G5 grounding · numerics injected never generated · citation coverage ≥ 2 · physician review | **low** | AI Act Art. 13–14; GMLP #6 |
| R-05 | Automation bias (clinician over-trust) | confident UI, single-source evidence | reduced independent judgement | 4 | 3 | in-product limitation ledger · uncertainty displayed · advisory-only framing | **medium** | IEC 62366-1; Art. 14 |
| R-06 | PHI leakage via logs/reports/telemetry | identifiers survive de-identification | privacy breach; HIPAA/GDPR violation | 5 | 2 | DICOM de-identification at ingest · local-only inference · LLM receives metrics only · log scrubbing | **low** | HIPAA §164; GDPR Art. 32 |
| R-07 | Model/repo tampering (supply chain) | unsigned artifacts, dependency compromise | silent behaviour change in clinical pipeline | 5 | 1 | checksum-verified exports · INT8 argmax-consistency gate · pinned deps · SBOM drift alerts (CI: planned) | **low** | FDA Premarket Cyber 2023 |
| R-08 | Untracked model drift after retraining | silent weight updates without validation | performance regression reaches clinicians | 4 | 2 | PCCP acceptance thresholds + rollback · versioned model cards · mandatory eval re-run | **low** | FDA PCCP (Dec 2024) |
| R-09 | Misuse as autonomous treatment engine | scope creep beyond advisory intent | patient harm without oversight; regulatory breach | 5 | 1 | by-design exclusion of treatment logic · Art. 14 architecture · intended-use statement | **low** | AI Act Art. 14; GMLP #6 |
| R-10 | Unvalidated cross-vendor deployment | trained/evaluated on ACDC only (today) | unknown accuracy at other-scanner sites | 4 | 4 | honest RUO scoping · domain-shift workstream (M&Ms) prioritized · site onboarding questionnaire (planned) | **HIGH** | GMLP #3–4 |

## Review rules

- **R-10 is deliberately left HIGH** until M&Ms zero-shot per-vendor tables
  exist. We do not launder an open risk with optimistic wording.
- Any hazard reaching S≥4 ∧ P≥4 without a funded control path blocks the phase
  release (enforced in phase review).
- New controls must land with a verification artifact (test, measurement, or
  documented review) — controls without evidence are "planned", not counted.
