# HeartOracle — Documentation Index

> Research Use Only. Not a medical device. ORACLE advises — physicians decide.

This tree is the regulatory-by-design evidence base. Every artifact here is
generated continuously during development (not crammed at submission time),
which is what makes a future FDA/CE file assembleable instead of
archaeological.

| Path | Purpose | Framework anchor |
|---|---|---|
| [architecture/PLATFORM.md](architecture/PLATFORM.md) | Modality-adapter architecture + multimodal fusion roadmap | — |
| [architecture/INFRASTRUCTURE.md](architecture/INFRASTRUCTURE.md) | Docker, ports, gateway, deployment topology, SBOM | FDA Premarket Cybersecurity 2023 |
| [compliance/GMLP-GAP-MATRIX.md](compliance/GMLP-GAP-MATRIX.md) | 10 GMLP principles × artifact × owned gap | FDA/HC/MHRA GMLP 2021 |
| [compliance/RISK-REGISTER-ISO14971.md](compliance/RISK-REGISTER-ISO14971.md) | Hazard analysis, RPN, controls, residual risk | ISO 14971 |
| [compliance/PCCP-DRAFT.md](compliance/PCCP-DRAFT.md) | Predetermined Change Control Plan (retraining governance) | FDA PCCP final guidance, Dec 2024 |
| [compliance/TRACEABILITY-MATRIX.md](compliance/TRACEABILITY-MATRIX.md) | Requirement → code → test evidence chain | IEC 62304, 21 CFR 820.30 |
| [security/THREAT-MODEL-STRIDE.md](security/THREAT-MODEL-STRIDE.md) | STRIDE analysis of the platform surface | FDA cyber guidance |
| [security/SECURITY-CONTROLS.md](security/SECURITY-CONTROLS.md) | Implemented vs planned controls, disclosure policy | ISO 27001 (shaped) |
| [governance/AI-GOVERNANCE.md](governance/AI-GOVERNANCE.md) | Oversight principles, autonomy boundary, EU AI Act mapping | EU AI Act Art. 14 |
| [data/DATA-SOURCES.md](data/DATA-SOURCES.md) | Dataset acquisition map, licenses, provenance rules | GMLP #3–5, AI Act data governance |

## Golden rules

1. **Measured, not mocked.** Every number shown anywhere traces to
   `evaluation/eval_summary.json` (commit ORACLE-P8T3) or is explicitly
   labeled as simulation with the method disclosed.
2. **The limitation ledger is sacred.** Published limitations are tracked
   with status (`achieved-here / engineering-path / physics-bound /
   regulatory-path / by-design`) — never silently removed.
3. **No claim without a citation.** Report text must pass Gate G5
   (grounding + citation coverage + RUO disclaimer).
4. **Human oversight is architecture.** No autonomous treatment logic —
   see AI-GOVERNANCE.md before proposing features that cross this line.
