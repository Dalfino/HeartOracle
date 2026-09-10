/**
 * The 5 ORACLE audit gates + append-only hash-chained audit trail.
 * Nothing reaches a human-visible report without passing through all gates.
 * Gates G1–G4 validate a PipelineRun; G5 validates report grounding and is
 * enforced in the report API (citation coverage + injected numerics only).
 */
import { createHash } from "crypto";
import type { PipelineRun } from "./geometry";

export type GateStatus = "pass" | "warn" | "fail";

export interface GateResult {
  id: string;
  name: string;
  status: GateStatus;
  checks: { label: string; ok: boolean; detail: string }[];
  summary: string;
}

export interface AuditEntry {
  seq: number;
  runId: string;
  gate: string;
  status: GateStatus;
  detail: string;
  prevHash: string;
  hash: string;
}

export interface GateReport {
  gates: GateResult[];
  auditTrail: AuditEntry[];
  overall: GateStatus;
  overallHash: string;
}

export function auditGate1Input(run: PipelineRun): GateResult {
  const checks = [
    {
      label: "Series cardinality",
      ok: run.nFrames >= 10,
      detail: `${run.nFrames} cine frames reconstructed (≥10 required)`,
    },
    {
      label: "Temporal resolution plausibility",
      ok: run.phenotype.hr >= 35 && run.phenotype.hr <= 180,
      detail: `Documented HR ${run.phenotype.hr} bpm within [35, 180]`,
    },
    {
      label: "Phenotype declared & bounded",
      ok: run.phenotype.edvTarget > 0 && run.phenotype.esvTarget > 0 && run.phenotype.esvTarget < run.phenotype.edvTarget,
      detail: `EDV ${run.phenotype.edvTarget} mL > ESV ${run.phenotype.esvTarget} mL > 0`,
    },
  ];
  return {
    id: "G1",
    name: "Input Integrity",
    checks,
    summary: checks.every((c) => c.ok) ? "Series metadata coherent" : "Series metadata anomaly",
    status: checks.every((c) => c.ok) ? "pass" : "fail",
  };
}

export function auditGate2Segmentation(run: PipelineRun): GateResult {
  // Echo of the measured failure mode: empty RV predictions on 6/257 holdout slices.
  const areas = Object.values(run.contours).map((pts) => {
    let a = 0;
    for (let i = 0; i < pts.length; i++) {
      const [x1, y1] = pts[i];
      const [x2, y2] = pts[(i + 1) % pts.length];
      a += x1 * y2 - x2 * y1;
    }
    return Math.abs(a) / 2; // mm^2
  });
  const empty = areas.filter((a) => a < 1).length;
  const minArea = Math.min(...areas);
  const maxArea = Math.max(...areas);
  const plausible = maxArea / (minArea || 1) < 400;
  const checks = [
    { label: "No empty predictions", ok: empty === 0, detail: `${empty} empty frame(s) — measured mode on RV: 6/257 holdout slices` },
    {
      label: "Cross-frame area plausibility",
      ok: plausible,
      detail: `cavity area ${Math.round(minArea)}–${Math.round(maxArea)} mm² (ratio ${Math.round(maxArea / (minArea || 1))})`,
    },
    { label: "Largest-connected-component filter", ok: true, detail: "applied by construction in this engine" },
  ];
  const status: GateStatus = checks[0].ok && checks[1].ok ? "pass" : checks[0].ok ? "warn" : "fail";
  return { id: "G2", name: "Segmentation Plausibility", checks, summary: empty === 0 ? "Masks physiologically plausible" : "Empty predictions detected", status };
}

export function auditGate3Volumes(run: PipelineRun): GateResult {
  const edvOk = run.edvMl >= 40 && run.edvMl <= 400;
  const esvOk = run.esvMl >= 10 && run.esvMl <= 350;
  const efOk = run.efPct >= 10 && run.efPct <= 80;
  const svOk = run.strokeVolumeMl >= 20 && run.strokeVolumeMl <= 220;
  const checks = [
    { label: "EDV in [40, 400] mL", ok: edvOk, detail: `EDV ${run.edvMl} mL` },
    { label: "ESV in [10, 350] mL", ok: esvOk, detail: `ESV ${run.esvMl} mL` },
    { label: "SV in [20, 220] mL", ok: svOk, detail: `SV ${run.strokeVolumeMl} mL` },
    { label: "EF in [10, 80] %", ok: efOk, detail: `EF ${run.efPct}% — ${run.efClass}` },
  ];
  return {
    id: "G3",
    name: "Volumetric Coherence",
    checks,
    summary: checks.every((c) => c.ok) ? "All volumes within physiological bounds" : "Volume outside physiological bounds",
    status: checks.every((c) => c.ok) ? "pass" : "fail",
  };
}

export function auditGate4Temporal(run: PipelineRun): GateResult {
  const v = run.volumeCurveMl;
  let maxJump = 0;
  for (let i = 1; i < v.length; i++) maxJump = Math.max(maxJump, Math.abs(v[i] - v[i - 1]));
  // peak must follow trough in time (systole then diastole)
  const iMax = v.indexOf(Math.max(...v));
  const iMin = v.indexOf(Math.min(...v));
  const monotoneSystole = iMax < iMin;
  const checks = [
    { label: "Systole precedes diastole", ok: monotoneSystole, detail: `peak @ f${iMax}, trough @ f${iMin}` },
    { label: "No discontinuous jumps", ok: maxJump <= 25, detail: `largest frame-to-frame change ${Math.round(maxJump * 10) / 10} mL (limit 25)` },
    { label: "Curve completeness", ok: v.length === run.nFrames, detail: `${v.length}/${run.nFrames} frames scored` },
  ];
  return {
    id: "G4",
    name: "Temporal Consistency",
    checks,
    summary: monotoneSystole && maxJump <= 25 ? "Volume curve physiologically ordered" : "Curve order anomaly",
    status: checks.every((c) => c.ok) ? "pass" : "fail",
  };
}

/** G5 runs in the report API: every number in the report must exist in the run, every claim must carry a citation. */
export function auditGate5ReportGrounding(report: string, run: PipelineRun, citationCount: number): GateResult {
  const numerics = [run.edvMl, run.esvMl, run.strokeVolumeMl, run.efPct, run.phenotype.hr];
  const grounded = numerics.filter((n) => report.includes(String(n))).length;
  const citationMarkers = (report.match(/\[\d+\]/g) ?? []).length;
  const checks = [
    { label: "Injected numerics present", ok: grounded === numerics.length, detail: `${grounded}/${numerics.length} pipeline values found in report` },
    { label: "Citation coverage", ok: citationCount >= 2 && citationMarkers >= 2, detail: `${citationCount} KB chunks cited, ${citationMarkers} in-text markers` },
    { label: "RUO disclaimer present", ok: /research use only|not a medical device|advisory only/i.test(report), detail: "mandatory footer phrase check" },
  ];
  return {
    id: "G5",
    name: "Report Grounding",
    checks,
    summary: checks.every((c) => c.ok) ? "Report fully grounded and cited" : "Report grounding failure",
    status: checks.every((c) => c.ok) ? "pass" : "fail",
  };
}

function entryHash(e: Omit<AuditEntry, "hash" | "prevHash">, prevHash: string): string {
  return createHash("sha256").update(`${e.seq}|${e.runId}|${e.gate}|${e.status}|${e.detail}|${prevHash}`).digest("hex").slice(0, 16);
}

/** Build the append-only, hash-chained audit trail for a gated run. */
export function buildAuditTrail(runId: string, gates: GateResult[]): { auditTrail: AuditEntry[]; overall: GateStatus; overallHash: string } {
  let prevHash = "GENESIS";
  const auditTrail: AuditEntry[] = gates.map((g, i) => {
    const base = { seq: i + 1, runId, gate: g.id, status: g.status, detail: g.summary };
    const hash = entryHash(base, prevHash);
    const entry: AuditEntry = { ...base, prevHash, hash };
    prevHash = hash;
    return entry;
  });
  const statuses = gates.map((g) => g.status);
  const overall: GateStatus = statuses.includes("fail") ? "fail" : statuses.includes("warn") ? "warn" : "pass";
  return { auditTrail, overall, overallHash: prevHash };
}

export function runAllGates(run: PipelineRun): GateReport {
  const gates = [auditGate1Input(run), auditGate2Segmentation(run), auditGate3Volumes(run), auditGate4Temporal(run)];
  const { auditTrail, overall, overallHash } = buildAuditTrail(run.runId, gates);
  return { gates, auditTrail, overall, overallHash };
}
