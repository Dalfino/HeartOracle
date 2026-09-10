# AI Governance Charter — HeartOracle / ORACLE

Version: 0.9 · Status: ACTIVE · Review: every phase boundary

## 1. Prime directive

**ORACLE advises — physicians decide.** The system produces quantified,
audited, cited *advisory* analytics. It does not diagnose, does not
prescribe, and contains **no autonomous treatment logic by design**.

This is a safety property and a regulatory requirement, not a missing
feature: EU AI Act Article 14 mandates effective human oversight for
high-risk AI systems; FDA GMLP principle 6 evaluates the human–AI team;
the liability model (clinician-in-loop) is the adoption precondition of
the hospitals we serve.

## 2. Autonomy boundary — what may and may not ship

| Allowed (advisor pattern) | Forbidden (autonomy pattern) |
|---|---|
| guideline surfacing with verbatim citations | "system recommends drug X at dose Y" |
| draft documentation for physician signature | auto-signed orders or auto-executed orders |
| triage/workflow flags (e.g., "EF < 35% — consider referral pathways") | autonomous treatment escalation |
| serial monitoring alerts (EF trajectory decline) | autonomous diagnosis claims without human review |
| what-if guideline pathway visualization | closed-loop therapy of any kind |

Escalation to "earned autonomy" in a *narrow screening* sense (IDx-DR-style)
is a multi-year, pivotal-trial path and explicitly out of scope for v0–v2.

## 3. Governance mechanisms implemented today

1. **Audit gates G1–G5** — technical enforcement between model output and
   human-visible report; G5 blocks ungrounded/uncited/disclaimer-less text.
2. **Hash-chained audit trail** — every gated run is append-only recorded.
3. **In-product honesty surfaces** — limitation ledger, provenance blocks,
   demonstration-mode labeling, per-structure gate verdicts.
4. **Measured claims policy** — numbers trace to `evaluation/eval_summary.json`
   (ORACLE-P8T3) or are labeled as simulation with method disclosed.

## 4. Governance mechanisms owed (tracked)

- Named clinical advisor + advisory board charter (GMLP #1 gap)
- Formal reader study (GMLP #6 evidence beyond design)
- Incident reporting channel for clinical-adjacent deployments
- Quarterly governance review against EU AI Act high-risk obligation list
  (risk management, data governance, logging, transparency, oversight,
  accuracy/robustness, cybersecurity)

## 5. Intended use (RUO framing)

Research Use Only analytical software for qualified researchers studying
cardiac image quantification. Not a medical device; not cleared by FDA; not
CE-marked. No clinical decisions without qualified-physician interpretation.
Deployment into any clinical workflow is prohibited until the regulatory
dossier and QMS mature — see docs/compliance/GMLP-GAP-MATRIX.md for the gap
register that gates that decision.

## 6. Change policy

Any PR that (a) adds treatment-logic of any kind, (b) removes a gate,
(c) weakens RUO labeling, or (d) widens intended use requires a governance
review flag in the commit message and BLOCKERS.md entry — before merge.
