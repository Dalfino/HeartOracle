
---

# PRD — Project ORACLE (Agent-Executable Specification)

**Doc ID:** ORACLE-PRD-002 · **Supersedes:** v0.1 · **Execution model:** phase-locked, test-gated

## 0. Agent Operating Protocol
1. Read this document fully before any code change. `AGENTS.md` = pointer to this file + §0 rules.
2. Execute phases in order. A phase is **closed** only when every Acceptance Criterion (AC) passes and `pytest -q && ruff check .` is clean.
3. Commit per task: `ORACLE-P{n}T{m}: <verb> <object>`. No mixed-phase commits.
4. Tests run **offline**. No network in `tests/`. Model/LLM files load from env paths only.
5. Impossible-on-CPU or missing-asset → write `BLOCKERS.md` entry (code, cause, proposed fix) and stop. Never improvise substitutes.
6. All timings measured with `time.perf_counter`, median of 3 runs, reported in `bench.json`.

## 1. Scope
Build a local-first, CPU-only pipeline that ingests a cardiac DICOM study, produces (a) deterministic geometry/physics metrics, (b) a fully-cited clinical report draft, and (c) an encrypted local analytics record. Output is advisory only (human clinician decides).
**In:** local CPU pipeline: ingest → segment → physics → RAG → cited report → Gradio UI → encrypted analytics vault (opt-in). **Out:** 3D nnU-Net, CFD/PINN, EHR integration, auth, hosting, real-guideline licensing (synthetic seed set only), mobile.

## 2. Constraints (pinned)
- HW: i5-6500 4c/4t, 16 GB RAM, no GPU, ≥135 GB disk. `ORACLE_THREADS=4`.
- $0 budget. Kaggle (train/export), Groq (`ORACLE_DEV_LLM=1` only), public datasets.
- No PHI in repo/tests/fixtures. Advisory-only outputs (disclaimer mandatory).

## 3. Stack (exact pins)
```
python==3.11.*
pydicom>=3.0.1            numpy>=1.26,<3
onnxruntime>=1.18,<2      (CPU wheel only)
chromadb>=0.5             fastembed>=0.3   (embedder: BAAI/bge-small-en-v1.5 ONNX)
llama-cpp-python>=0.2.90  (GGUF: bartowski/Phi-3.5-mini-instruct-GGUF :: Phi-3.5-mini-instruct-Q4_K_M.gguf
                           fallback: Qwen/Qwen2.5-3B-Instruct-GGUF :: Qwen2.5-3B-Instruct-Q4_K_M.gguf)
fastapi>=0.115  uvicorn>=0.30  gradio>=4.44  pydantic>=2.8
pytest>=8.2  ruff>=0.6   scipy>=1.13
# Kaggle-side only (not in requirements.txt): torch==2.3.*, onnx>=1.16, nnunetv2 or monai
```

## 4. Repository (complete tree, purpose per file)
```
oracle/
├── PRD.md  AGENTS.md  README.md  BLOCKERS.md  VALIDATION_REPORT.md(gen)
├── pyproject.toml  requirements.txt  .env.example  .gitignore
├── src/oracle/
│   ├── config.py          # pydantic-settings; env table §5
│   ├── cli.py             # argparse entry; commands §10
│   ├── logging_util.py    # JSON logger §11
│   ├── errors.py          # OracleError base + codes §12
│   ├── ingest/dicom_io.py deidentify.py
│   ├── seg/onnx_infer.py  metrics.py
│   ├── physics/features.py surrogate.py
│   ├── rag/kb_build.py    retrieve.py
│   ├── synth/prompt.py    report.py  auditor.py
│   ├── analytics/risk.py  vault.py
│   └── api/main.py        ui/gradio_app.py
├── tests/
│   ├── fixtures/  tiny_seg.onnx  mini_guidelines/  expected/
│   ├── make_synthetic_dicom.py  make_mock_onnx.py
│   └── test_ingest.py test_seg.py test_physics.py test_rag.py
│       test_synth.py test_analytics.py test_api.py test_e2e.py
├── notebooks/kaggle_export_onnx.ipynb   # §14 spec
├── tools/fetch_llm.sh  fetch_model_meta.sh
├── models/ (gitignored)  data/ (gitignored)  kb/ (gitignored)
```

## 5. Configuration (env → default → meaning)
| Var | Default | Meaning |
|---|---|---|
| `ORACLE_MODEL_DIR` | `./models` | holds `seg.onnx`, `seg_int8.onnx`, `meta.json` |
| `ORACLE_DATA_DIR` | `./data` | studies, intermediates (`*.json`) |
| `ORACLE_KB_DIR` | `./kb` | Chroma persistent dir |
| `ORACLE_LLM_PATH` | `./models/phi35.Q4_K_M.gguf` | GGUF file |
| `ORACLE_VAULT_PATH` / `ORACLE_VAULT_KEY` | `./vault.db` / unset | analytics vault + key file (0600) |
| `ORACLE_ANALYTICS` | `0` | vault module enabled |
| `ORACLE_DEV_LLM` | `0` | allow Groq API in synth (dev only) |
| `ORACLE_THREADS` | `4` | intra-op threads for ORT + llama.cpp |
| `ORACLE_LOG_LEVEL` | `INFO` | |

`.env.example` mirrors this table verbatim.

## 6. Data Contracts (exact)
**meta.json (model sidecar):** `{"input_name":"input","output_name":"output","input_size":256,"classes":["BG","RV","MYO","LV"],"mean":0.0,"std":1.0,"opset":17,"source":"hf:MohidAbdullah/ACDC-Heart-Segmentation","quant":"int8-dynamic"}`
**Study (ingest out):** `{"study_token":str(12 hex),"modality":"MR"|"CT","n_slices":int,"phases":{"ED":int,"ES":int},"spacing_mm":[sx,sy],"thickness_mm":float,"files":int}`
**Seg out:** `{"study_token","model_id","quant","confidence":float0-1,"structures":{"LV":{"volume_ml":float},"MYO":{...},"RV":{...}},"masks_path":str,"slice_count":int,"inference_ms":int}`
**Physics out:** `{"study_token","EDV_ml","ESV_ml","ejection_fraction":float,"ffr_estimate":null,"ffr_method":"placeholder-v0","wall_stress_mean":null}`
**Report:** markdown, exact 4 H2 headers (§App B) + citations (§8 regex) + disclaimer line.
**AnalyticsRecord:** `{"token","bio_index":float,"risk_window_months":int,"flag":bool,"created_at":iso}`

## 7. Module Specifications (signatures + rules)
**ingest.dicom_io** `load_study(dir)->Study`; group slices by `TemporalPositionIdentifier` (1=ED,2=ES); raise `E-ING-002` if modality∉{MR,CT}; `E-ING-003` if slices<8/phase; `E-ING-004` if tag missing.
**ingest.deidentify** `deidentify(study_dir,out_dir)->token`; blank tags (0010,0010),(0010,0020),(0010,0030),(0008,0080),(0008,0090); token=`sha256(orig PatientID+StudyInstanceUID)[:12]`.
**seg.onnx_infer** `segment(study,model_dir)->SegOut`; per-slice: resize bilinear→256², z-score with meta mean/std, batch 8; ORT session `sess_options.intra_op_num_threads=ORACLE_THREADS`; postprocess argmax + largest-connected-component per class (scipy.ndimage.label); `confidence`=mean max-softmax over slices.
**seg.metrics** `dice(a,b)`, `hd95(a,b,spacing)`; HD95 via `distance_transform_edt`, 95th percentile of surface distances both directions.
**physics.features** `volumes(masks,spacing,thickness)->(EDV,ESV)`; Simpson: `V=Σ area_i×(thickness+gap)`; `EF=(EDV−ESV)/EDV×100`.
**physics.surrogate** v0 returns nulls (see contract); upgrade path documented (Kaggle MLP on synthetic CFD, Phase 9+).
**rag.kb_build** `build(guidelines_dir,kb_dir)`; parse YAML frontmatter `{guideline_id,issuing_body,year,evidence_level,context_tags[]}`; chunk 800 chars/100 overlap; embed bge-small-en-v1.5 (fastembed); collection `oracle_guidelines`.
**rag.retrieve** `retrieve(findings_dict,kb_dir,top_k=3,min_score=0.25)->Chunk[]`; query template: `"cardiac {modality} EF {ef} {abnormal findings} management recommendation"`.
**synth.prompt** `SYSTEM_PROMPT` = Appendix A verbatim. `user_msg(seg,phy,chunks)` = JSON dump + "Write the report per OUTPUT STRUCTURE."
**synth.report** `generate(...)->str`; llama.cpp params: `temp=0.0, top_p=1.0, seed=42, n_threads=4, ctx=4096, max_tokens=1200`.
**synth.auditor** `audit(report,seg,phy,chunks)->AuditResult`; checks: (a) §2 numbers match inputs ±0.05; (b) citation regex `\(Guideline ID: ([A-Z]{2,4}-\d{4}-[A-Z]{2,4}-\d+(?:\.\d+)?), Evidence Level: (Class I|Class IIa|Class IIb|Class III)\)` on every §3/§4 bullet; (c) cited IDs ⊆ retrieved IDs; (d) disclaimer present; (e) if `confidence<0.90` report contains `LOW CONFIDENCE — MANUAL REVIEW`. Fail → regenerate once with failure notes; second fail → `E-SYN-002`, write report with `**AUDIT FAILED**` banner, exit 5.
**analytics.risk** `bio_index(plaque_mm3|None,EF)->float`: `plaque_risk=min(1,(plaque or 0)/200)`; `ef_risk=clamp((60−EF)/60,0,1)`; `idx=round(10*(0.6*plaque_risk+0.4*ef_risk),1)`; `window=clamp(int(24−1.5*idx),6,24)`; `flag=idx>=7.0`.
**analytics.vault** Fernet(key file) + SQLite `records(id INTEGER PK, token TEXT, cipher BLOB, created_at TEXT)`; CLI §10; file perms 0600 enforced.
**api.main** `POST /api/v1/studies` (multipart zip of DICOMs)→202 `{study_id}`; `GET /api/v1/studies/{id}`→`{status:queued|running|done|failed}`; `GET /api/v1/studies/{id}/report`→`{markdown}`; error envelope `{"error":{"code","message"}}`; 404/413/422 mapped.
**ui.gradio_app** blocks: File(upload .zip) → Button Run → Markdown report + Textbox status; footer disclaimer always visible.

## 8. Fixtures (exact generation params)
**Synthetic DICOM** (`make_synthetic_dicom.py`): MR, 2 phases ×20 slices, 256×256 uint16; pixel spacing [1.5,1.5]; thickness 8 mm, gap 2 mm; ED ellipsoid semi-axes (45,35) mm tapering per slice, ES (32,25) mm → analytic EDV≈118 ml, ESV≈53 ml, **EF≈55.1%** (test asserts ±5 pts); background 0, cavity 600, myocardium ring 300 HU-equivalent.
**tiny_seg.onnx** (`make_mock_onnx.py`, artifact committed): Conv2d(1→4,k3,pad1) weights=0, bias=[0,10,0,0]; input `input [1,1,256,256] f32`, output `output [1,4,256,256]`; argmax≡1 (MYO) everywhere → deterministic dice vs fixture labels.
**mini_guidelines/**: 4 verbatim docs (App C) + 6 stub docs with valid frontmatter.

## 9. Acceptance Criteria & Thresholds
| Phase | AC (commands/metrics) |
|---|---|
| P0 | `pytest -q` green; `python -m oracle.cli --version` → `0.1.0` |
| P1 | round-trip load; de-identified tree contains zero original PHI substrings; load ≤30 s |
| P2 | unit: mock ONNX dice(MYO)=1.00±0.00; ACDC test-split (notebook CSV pasted): **Dice LV≥0.90, MYO≥0.82, RV≥0.85; HD95(LV)≤6 mm**; CPU seg ≤240 s/study |
| P3 | EF err ≤5 pts vs analytic fixture; identical outputs across 2 runs (hash-equal JSON) |
| P4 | seeded query returns ESC-2026-VHD-4.2 in top-3 with score≥0.25; latency ≤2 s |
| P5 | 4 sections present; citation coverage 100%; negative test (inject EF 99 in prompt inputs mismatch) → auditor rejects; gen ≤300 s; temp-0 determinism (byte-identical) |
| P6 | e2e CLI ≤600 s; API 202→done→report flow via `test_api.py` (TestClient) |
| P7 | vault ciphertext ≠ plaintext (assert); `ORACLE_ANALYTICS=0` → module import-safe no-op |
| P8 | `VALIDATION_REPORT.md` generated with all tables pass/fail |

## 10. CLI (exact)
```
oracle --version
oracle ingest   --input DIR --out study.json
oracle segment  --study study.json --out seg.json
oracle physics  --seg seg.json --out phy.json
oracle kb build --guidelines DIR
oracle report   --seg seg.json --phy phy.json --out report.md
oracle bench    --input DIR --runs 3 --out bench.json
oracle vault view --key-file PATH --limit 10
oracle serve    --port 8000        # FastAPI
oracle ui       --port 7860        # Gradio
```
Exit codes: 0 ok · 2 ingest/validation · 3 model/seg · 4 rag · 5 synth/audit · 6 vault.

## 11. Logging schema (JSON line)
`{"ts":iso,"level","component","study_token"?,"event","duration_ms"?,"extra":{}}` — one logger per component; no PHI fields ever.

## 12. Error matrix
| Code | Trigger | Exit |
|---|---|---|
| E-ING-001/002/003/004 | missing dir / bad modality / <8 slices / missing temporal tag | 2 |
| E-SEG-001/002 | model/meta missing / tensor shape mismatch | 3 |
| E-RAG-001/002 | empty KB / no chunk ≥0.25 | 4 |
| E-SYN-001/002 | LLM load fail / audit fail ×2 | 5 |
| E-VLT-001/002 | key missing / decrypt fail | 6 |

## 13. Timing budget (i5-6500, median of 3)
ingest ≤30 s · seg ≤240 s · physics ≤2 s · retrieve ≤2 s · synth ≤300 s · **e2e ≤600 s**.

## 14. Kaggle notebook spec (`kaggle_export_onnx.ipynb`, human-run)
Cells: (1) `!pip install torch onnx onnxruntime`; (2) mount ACDC (official challenge mirror; verify slug at runtime; fallback HF `AI-CVM/Cardiac-CT` for CT path); (3) load HF `MohidAbdullah/ACDC-Heart-Segmentation` (alt: Zenodo M&Ms nnU-Net); (4) eval Dice/HD95 on test split → `metrics.csv`; (5) `torch.onnx.export(dynamic_axes={"input":{0:"N"}}, opset_version=17)`; (6) `onnxruntime.quantization.quantize_dynamic(weight_type=QInt8)` → `seg_int8.onnx`; (7) write `meta.json` (§6); (8) CPU-timing cell (2 threads, emulate i5); (9) save all as Kaggle dataset version `oracle-seg-v1`; (10) print `kaggle datasets download` command for local pull.

## 15. Guardrails (MUST NOT)
No recommendation re-ranking/deviation from retrieved guidelines (deviation=defect) · no external LLM in prod path · no weights/datasets/PHI committed · disclaimer mandatory · no autonomous treatment logic · no telemetry.

## Appendices
**A. SYSTEM_PROMPT (verbatim):** ORACLE-SYNTH role block, Grounding Protocols 1–4, Citation Format, Output Structure (4 H2s), confidence gate — as drafted in v0.1 §Prompt, unchanged.
**B. Report template:** `## 1. EXECUTIVE SUMMARY` / `## 2. DETERMINISTIC GEOMETRY & PHYSICS` / `## 3. GUIDELINE-DIRECTED SURGICAL PLAN` / `## 4. CRITICAL WARNINGS & CONTRAINDICATIONS` + final line: `*Advisory output. Final clinical decision rests with the treating physician.*`
**C. Seed guidelines (4 verbatim):** `ESC-2026-VHD-4.2` (annulus 26–29 mm → 29 mm transcatheter valve, Class I) · `ACC-2025-PCI-7.1` (severe iliac calcification → pre-procedural CTA of access route, Class IIa) · `ESC-2024-HF-3.1` (EF<40% → GDMT initiation, Class I) · `ACC-2025-CMR-2.3` (cine SAX volumetrics via Simpson slice-summation, Class I). Plus 6 stubs.
**D. Agent kickoff prompt (per phase):** `"You are executing ORACLE-PRD-002. Close Phase {n} only. Rules §0. Start at task P{n}T1. Report AC results as a table when done."`

---
