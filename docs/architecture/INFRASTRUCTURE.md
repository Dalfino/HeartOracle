# Infrastructure — Docker, Topology, Supply Chain

Status: ACTIVE · Applies to: platform (Next.js) + oracle-api (FastAPI)

## 1. Topology

```
┌──────────────────────────── docker compose ────────────────────────────┐
│  platform (:3000)  ──ORACLE_API_URL──▶  oracle (:3030)                  │
│  Next.js 16 standalone                    FastAPI · ONNX INT8 (CPU)     │
│  dashboards, audit UX, LLM-sidecar        segmentation + volumetrics   │
│  via z-ai SDK (server-side only)          + RAG + gates (reference)    │
└─────────────────────────────────────────────────────────────────────────┘
       ▲ /models:ro (ensemble ONNX bundle) — mounted, never baked in
```

- `docker/Dockerfile.platform` — multi-stage bun build → standalone, non-root
  user (`oracle`, uid 1001), HEALTHCHECK on `/api/oracle/eval`.
- `docker/Dockerfile.oracle` — python:3.11-slim, non-root, healthcheck `/health`,
  CPU-only inference (deterministic threads), resource limits in compose.
- Model weights are **mounted read-only** at `/models` — images stay slim and
  artifact provenance is explicit (checksum-verify before mounting).

## 2. Sandbox note (honesty)

The development sandbox has **no Docker daemon**; these files are deployment
artifacts structured for CI validation (lint via `docker compose config` in a
CI runner with Docker). Runtime verification on cloud VM is a Phase-0 closeout
item tracked in BLOCKERS.md.

## 3. Ports & gateway

| Service | Port | Exposure |
|---|---|---|
| platform dashboard | 3000 | public (gateway-fronted) |
| oracle API | 3030 | internal-only in prod; gateway `XTransformPort` in sandbox |

All client-side requests use **relative paths only** (no absolute
`http://host:port` calls) — enforced by review + grep gate in CI (planned).

## 4. Supply chain (FDA premarket cybersecurity shape)

- **SBOM**: CycloneDX from `bun.lock` (JS) + `pip freeze`/`requirements.txt`
  (python). CI job (planned Phase-0 closeout) emits `sbom.cdx.json` per build
  and diffs against previous — drift alerts.
- **Pinning**: `bun.lock` frozen installs; python deps pinned in
  requirements.txt.
- **Integrity**: model exports carry checksums + INT8 argmax-consistency
  evidence (see evaluation/ notes in repo); commits signed; `ORACLE-P{n}T{m}`
  format gives requirement→commit traceability.
- **Vulnerability policy**: see security/SECURITY-CONTROLS.md (disclosure).

## 5. Hardening baseline (current)

- non-root container users, `no-new-privileges`, CPU/memory limits
- healthchecks wired into compose dependency ordering
- error responses generic client-side; detail stays in server logs
- no privileged operations exposed over HTTP (retraining runs offline)

## 6. Production TODO (tracked)

- read_only rootfs + tmpfs for `/tmp` and `.next/cache`
- image signing (cosign) + registry pinning
- centralized log retention with PHI scrubbing verification
- gateway TLS termination policy + HSTS
