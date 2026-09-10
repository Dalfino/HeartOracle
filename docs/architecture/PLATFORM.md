# Platform Architecture — Modality Adapters & Fusion Roadmap

Status: ACTIVE · Owner: platform engineering · Last alignment: this session

## 1. Architectural decision

HeartOracle is a **platform with pluggable modality adapters**, not a
single-model product. The reusable core is built (and regulated) once:

```
                ┌───────────────────────────────────────────────┐
                │              REUSABLE CORE                     │
                │  ingestion & normalization (DICOM→EDF/FHIR)    │
                │  5 audit gates (G1..G5)                        │
                │  RAG-cited reporting engine (local KB)         │
                │  physician sign-off surface (AI Act Art. 14)   │
                │  regulatory documentation machine              │
                │  append-only hash-chained audit trail          │
                └───────────────────────────────────────────────┘
                   ▲            ▲           ▲            ▲
              [MRI v0 ✅]   [ECG next]  [Labs]     [CT-Ca] …
              each adapter = model + validation dossier + regulatory claim
```

Rationale:
- One weak module never blocks the platform.
- Regulators evaluate discrete claims, not one black box.
- Fusion modules **combine validated adapters** — far more defensible than
  an end-to-end multimodal transformer trained on partial data.

## 2. Adapter register (authoritative copy: `src/lib/data/platform.ts`)

| Adapter | Pillar | Status | Data | Regulatory shape |
|---|---|---|---|---|
| CMR Quantification v0 | Anatomy & function | **LIVE** | ACDC (+M&Ms planned) | CADx-style claim, IIa-shaped evidence |
| ECG Rhythm Screening | Electricity | NEXT | PTB-XL (21,837 public ECGs) | many FDA-cleared AI-ECG precedents |
| Biomarker Guideline Engine | Chemistry | NEXT | FHIR/HL7 or manual; MESA/UKBB later | deterministic calculators first (no ML) |
| Calcium Score (Agatston) | Anatomy (CT) | PLANNED | OrCaScore / COCA | deterministic algorithm — auditable |
| CCTA Plaque Segmentation | Anatomy (CT) | PLANNED | ASOCA | CAD-RADS-style reporting assistance |
| Late-Fusion Risk Aggregator | All | PLANNED | MESA / UK Biobank | late fusion first; interpretable |
| Virtual FFR-CT | Plumbing | MOONSHOT | none public | HeartFlow-scale (~$250M, De Novo DEN130045) |
| EHR Text Understanding | Context | MOONSHOT | none public | high-risk data governance |

## 3. Phased roadmap

- **Phase 0 (now):** v0 CMR adapter shipped; enterprise dashboard; Docker
  artifacts; regulatory + security scaffold (this tree).
- **Phase 1:** ECG adapter (PTB-XL) · deterministic lab calculators ·
  Agatston adapter (OrCaScore/COCA) · M&Ms zero-shot domain-shift tables.
- **Phase 2:** CCTA plaque (ASOCA) · late-fusion aggregation (MESA/UKBB
  applications submitted early — lead time is months) · leave-one-vendor-out
  retraining (Tier B Kaggle pipeline).
- **Phase 3 (partnership-gated):** FFR-CT (needs invasive-FFR ground truth) ·
  EHR text · cross-attention multimodal fusion (only after late fusion is
  validated).

## 4. Multimodal fusion blueprint — honest mapping

The proposed "AI-Driven Cardiac Fusion & Diagnostic Architecture"
(raw inputs → multi-scale encoder + cross-attention → physics/CFD +
radiomics layers → explainable dashboard) maps as:

| Blueprint block | Our verdict | Commitment |
|---|---|---|
| Raw multi-modal inputs | **adopt now** | adapter ingestion per modality |
| Cross-attention fusion engine | **sequence** | late fusion first; cross-attention after validation |
| Navier-Stokes FFR physics layer | **park** | no public paired CCTA+FFR data; partnership item |
| Radiomics / FAI layer | **sequence** | research track behind CCTA adapter; claims stay research until reproducible |
| Explainable dashboard (Grad-CAM/SHAP) | **adopt now (already ahead)** | segmentation masks + quantified metrics + cited reports ARE the explanation; Grad-CAM joins with classification heads |

## 5. Why this wins

Single-modality models are commoditized. The moat is the linked multimodal
evidence layer + audit trail + documentation machine — the same skeleton
HeartFlow validated commercially (De Novo 2014 → reimbursement), built at
research scale from day one.
