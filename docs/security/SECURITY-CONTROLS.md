# Security Controls — Implemented & Planned

Live copy of `src/lib/data/governance.ts` SECURITY_CONTROLS — update together.

## Implemented

1. **PHI containment** — local inference; LLM sidecar receives de-identified
   metrics only. DICOM de-identification at ingestion (repo spec §3).
2. **Audit integrity** — append-only, SHA-256 hash-chained audit trail for
   every gated run; chain head rendered in UI.
3. **Gate enforcement** — 5 audit gates between model output and any
   human-visible report (G1 input, G2 segmentation, G3 volumes, G4 temporal,
   G5 report grounding).
4. **Supply-chain pins** — frozen lockfiles (bun.lock / requirements.txt),
   checksum-verified model exports, signed commits, `ORACLE-P{n}T{m}`
   traceable commit format.
5. **Container hardening** — non-root users, `no-new-privileges`, resource
   limits, healthchecks gating dependency start order.

## Planned (Phase-0 closeout / Phase 1)

6. SBOM (CycloneDX) wired into CI + drift alerts.
7. NextAuth role model: clinician / admin / auditor; auth on mutating routes.
8. Encrypted at-rest store for generated reports (app-level).
9. SECURITY.md coordinated vulnerability disclosure + security advisories.
10. read_only rootfs + tmpfs mounts; cosign image signing; gateway TLS/HSTS
    policy; centralized log retention with PHI-scrub verification.

## Responsible disclosure

Report vulnerabilities via GitHub security advisories on
`github.com/Dalfino/HeartOracle` (Security → Report a vulnerability).
Please do not open public issues for exploitable findings. Targeted response:
acknowledgment ≤ 72 h, fix-or-mitigation plan ≤ 14 days for high severity.

## Data protection summary (HIPAA/GDPR shape)

- De-identification at the earliest boundary (ingest).
- No PHI to third-party model APIs; LLM prompts contain pipeline metrics and
  guideline excerpts only.
- Right-to-erasure in a research context = delete study artifacts + audit
  entries remain (hash chain integrity) with identifier-free payloads only.
