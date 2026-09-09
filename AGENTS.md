# AGENTS.md — rules for AI coding agents working in this repo

This file is a pointer. The authoritative specification is **`PRD.md`** (ORACLE-PRD-002).

## Operating protocol (PRD §0, binding)

1. Read `PRD.md` fully before any code change.
2. Execute phases in order. A phase is **closed** only when every Acceptance Criterion
   (PRD §9) passes and `pytest -q && ruff check .` is clean.
3. Commit per task: `ORACLE-P{n}T{m}: <verb> <object>`. No mixed-phase commits.
4. Tests run **offline**. No network in `tests/`. Model/LLM files load from env paths only.
5. Impossible-on-CPU or missing-asset → write a `BLOCKERS.md` entry (code, cause,
   proposed fix) and stop. Never improvise substitutes.
6. All timings measured with `time.perf_counter`, median of 3 runs, reported in `bench.json`.

## Kickoff prompt (per phase, PRD Appendix D)

> "You are executing ORACLE-PRD-002. Close Phase {n} only. Rules §0. Start at task P{n}T1.
> Report AC results as a table when done."

## Guardrails (PRD §15, MUST NOT)

- No recommendation re-ranking / deviation from retrieved guidelines (deviation = defect).
- No external LLM in the production path (`ORACLE_DEV_LLM=1` is a dev-only flag).
- No weights / datasets / PHI committed. `models/`, `data/`, `kb/` are gitignored.
- Disclaimer mandatory on every generated report.
- No autonomous treatment logic. **ORACLE advises. Physicians decide.**
- No telemetry.
