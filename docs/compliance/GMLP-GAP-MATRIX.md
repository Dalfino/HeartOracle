# GMLP Gap Matrix

Framework: **Good Machine Learning Practice for Medical Device Development:
Guiding Principles** (FDA · Health Canada · MHRA, October 2021).
Purpose: the master dashboard of our regulatory posture. This file and the
Compliance tab render from the same data model (`src/lib/data/governance.ts`)
— update both together.

| # | Principle | Current artifact | Owned gap | Status |
|---|---|---|---|---|
| 1 | Multidisciplinary expertise leveraged throughout | AGENTS.md + docs/governance/AI-GOVERNANCE.md define roles | named clinical advisor + governance board charter | PARTIAL |
| 2 | Good software security practices | SECURITY-CONTROLS.md + STRIDE + SBOM plan | SBOM wired into CI | PARTIAL |
| 3 | Clinical study & data collection match intended use | DATA-SOURCES.md maps datasets to claims; ACDC holdout matches quantification intent | intended-use statement freeze (PCCP annex) | PARTIAL |
| 4 | Training/test sets independent & representative | patient-level ACDC splits (101–115 held out); M&Ms planned for vendor shift | external cohort representability pending M&Ms | EVIDENCED |
| 5 | Reference standard clinically accepted | ACDC expert tracings + reference volumes; frozen protocol in evaluation/ | multi-reader reference for clinical study | EVIDENCED |
| 6 | Human–AI team performance | physician sign-off is architectural; autonomy excluded by design | formal reader study with clinicians | EVIDENCED |
| 7 | Clinically meaningful performance | Dice/HD95 gates + EF MAE 2.72 pp on official holdout | outcome-linked utility needs cohort data (MESA) | EVIDENCED |
| 8 | Usability for intended users | RUO labeling, cited reports, audit UX | IEC 62366-1 use-file seed | PARTIAL |
| 9 | Clear essential model information to users | model cards + provenance blocks + in-product limitation ledger | IFU document formatting | EVIDENCED |
| 10 | Deployed-model monitoring for re-training risk | PCCP draft (triggers, acceptance, rollback) | production drift telemetry | PARTIAL |

Score: **5/10 evidenced · 5/10 partial · 0 unknown** — every gap is owned with
an owner-path, none hidden.

## What this matrix does NOT claim

Possession of this matrix does not equal certification. Certification
additionally requires: an audited ISO 13485 QMS organization, a multi-reader
multi-case clinical study under IRB, notified body / FDA review and fees.
This matrix exists so that **none of that future work requires archaeology**.
