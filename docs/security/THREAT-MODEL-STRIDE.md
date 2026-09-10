# STRIDE Threat Model — HeartOracle Platform

Method: STRIDE per trust boundary. Boundaries: (1) internet ↔ gateway,
(2) gateway ↔ platform container, (3) platform ↔ oracle-api,
(4) platform ↔ LLM sidecar, (5) containers ↔ mounted model/data volumes.

Live copy of `src/lib/data/governance.ts` THREAT_MODEL — update together.

| ID | Category | Boundary | Scenario | Control | Status |
|---|---|---|---|---|---|
| S-1 | Spoofing | 1–2 | forged analyst identity submits analyses / signs reports | session auth (NextAuth planned) + auth on mutating routes + signed commits for model artifacts | PARTIAL |
| T-1 | Tampering | 3,5 | model weights or KB chunks swapped for behaviour change | checksum-verified exports; INT8 argmax-consistency gate; pinned deps; SBOM drift detection (CI planned) | PARTIAL |
| T-2 | Tampering | 2 | audit trail edited after the fact | append-only entries; SHA-256 hash chain (`engine/gates.ts buildAuditTrail`); head hash surfaced in UI | CONTROLLED |
| R-1 | Repudiation | 2 | user denies generating/altering a report | report binds run ID + gate verdicts + model version + timestamp; local retention | CONTROLLED |
| I-1 | Info Disclosure | 4 | PHI escapes to external LLM endpoint | local-first inference; LLM sidecar receives de-identified metrics only — never images/identifiers | CONTROLLED |
| I-2 | Info Disclosure | 2 | verbose errors leak stack/paths | generic client errors; detail server-side (dev.log) | CONTROLLED |
| D-1 | DoS | 1–2 | pipeline endpoint flooded with oversized/invalid payloads | strict typing + body validation + bounded synthetic pipeline cost; no unbounded loops | CONTROLLED |
| E-1 | Elevation | 2–3 | client triggers privileged retrain/file IO via API | no such capability exposed over HTTP by design; heavy jobs offline (Kaggle Tier B) | CONTROLLED |

## Assumptions

- deployment host disk/volume encryption is an ops responsibility (documented
  in SECURITY-CONTROLS planned items)
- the LLM sidecar is a trusted local component; network egress from it is
  deny-by-default in hardened deployments (to be enforced via compose net
  policy — tracked)

## Review cadence

Re-review at every phase boundary and on any new adapter. New boundary?
New table rows before code merge.
