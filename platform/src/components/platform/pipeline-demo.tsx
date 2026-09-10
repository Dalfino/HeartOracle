"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Play, Loader2, FileText, ScanLine, Calculator, ShieldCheck, FileCheck2, Database,
  AlertTriangle, CheckCircle2, XCircle, Link2, Quote,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import ReactMarkdown from "react-markdown";
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, ReferenceLine } from "recharts";
import { HeartViewer } from "./heart-viewer";
import { SectionTitle, StatusBadge, GlassCard, fadeUp } from "./bits";
import { PHENOTYPES, type PipelineRun } from "@/lib/engine/geometry";
import type { GateResult, AuditEntry, GateStatus } from "@/lib/engine/gates";
import { cn } from "@/lib/utils";

type Stage = "idle" | "ingest" | "segment" | "quantify" | "audit" | "ready";
type Gate5 = { id: string; name: string; status: GateStatus; checks: { label: string; ok: boolean; detail: string }[]; summary: string };

interface PipelineResponse {
  ok: boolean;
  run: PipelineRun;
  gates: GateResult[];
  auditTrail: AuditEntry[];
  overall: GateStatus;
  overallHash: string;
  error?: string;
}

interface ReportResponse {
  ok: boolean;
  report?: string;
  gate5?: Gate5;
  citations?: { id: number; source: string; title: string }[];
  error?: string;
}

const STAGE_STEPS: { id: Stage; label: string; icon: typeof Database; ms: number }[] = [
  { id: "ingest", label: "Ingest & de-identify", icon: Database, ms: 1100 },
  { id: "segment", label: "Segment (5-fold ensemble)", icon: ScanLine, ms: 1800 },
  { id: "quantify", label: "Quantify (Simpson)", icon: Calculator, ms: 1300 },
  { id: "audit", label: "Audit (5 gates)", icon: ShieldCheck, ms: 1600 },
  { id: "ready", label: "Report", icon: FileCheck2, ms: 0 },
];

export function PipelineDemo() {
  const [phenotypeId, setPhenotypeId] = useState("hfref");
  const [stage, setStage] = useState<Stage>("idle");
  const [running, setRunning] = useState(false);
  const [data, setData] = useState<PipelineResponse | null>(null);
  const [frameIndex, setFrameIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [report, setReport] = useState<ReportResponse | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const frameTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => {
    timers.current.forEach(clearTimeout);
    if (frameTimer.current) clearInterval(frameTimer.current);
  }, []);

  const startFrameLoop = useCallback((n: number) => {
    if (frameTimer.current) clearInterval(frameTimer.current);
    let f = 0;
    frameTimer.current = setInterval(() => {
      f = (f + 1) % n;
      setFrameIndex(f);
    }, 70);
  }, []);

  const stopFrameLoop = useCallback(() => {
    if (frameTimer.current) {
      clearInterval(frameTimer.current);
      frameTimer.current = null;
    }
  }, []);

  const run = useCallback(async () => {
    if (running) return;
    setRunning(true);
    setReport(null);
    setData(null);
    setStage("ingest");
    setFrameIndex(0);
    timers.current.forEach(clearTimeout);
    timers.current = [];

    try {
      const res = await fetch("/api/oracle/pipeline", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phenotypeId, seed: 7 }),
      });
      const json = (await res.json()) as PipelineResponse;
      if (!json.ok) throw new Error(json.error || "pipeline failed");
      setData(json);

      let acc = 0;
      STAGE_STEPS.forEach((s) => {
        acc += s.ms;
        timers.current.push(
          setTimeout(() => {
            setStage(s.id);
            if (s.id === "segment") {
              setPlaying(true);
              startFrameLoop(json.run.nFrames);
            }
            if (s.id === "ready") {
              setRunning(false);
            }
          }, acc),
        );
      });
    } catch {
      setStage("idle");
      setRunning(false);
    }
  }, [phenotypeId, running, startFrameLoop]);

  const composeReport = useCallback(async () => {
    if (reportLoading) return;
    setReportLoading(true);
    setReport(null);
    try {
      const res = await fetch("/api/oracle/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ phenotypeId, seed: 7 }),
      });
      const json = (await res.json()) as ReportResponse;
      setReport(json);
    } catch (err) {
      setReport({ ok: false, error: err instanceof Error ? err.message : "report failed" });
    } finally {
      setReportLoading(false);
    }
  }, [phenotypeId, reportLoading]);

  const phase = data?.run;
  const stageIdx = STAGE_STEPS.findIndex((s) => s.id === stage);

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 md:px-6">
      <SectionTitle
        eyebrow="Live demo"
        title="The ORACLE pipeline, end to end"
        sub="Ingest → segment → quantify → audit → cited report. The volumetric math (Simpson disk summation) and all five audit gates are the real pipeline logic; the input is a simulated cardiac phantom while the 199 MB ensemble is not resident in this environment. Measured real-scan results are shown separately with provenance."
      />

      {/* honesty banner */}
      <GlassCard className="mb-5 border-amber-400/25 ho-glow-amber">
        <div className="flex items-start gap-3">
          <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" />
          <div className="text-xs leading-relaxed text-amber-200/90">
            <span className="font-semibold text-amber-300">Demonstration mode.</span> Geometry engine is real (Simpson
            disk summation) and all five audit gates execute; the input is a simulated cardiac phantom — not a patient
            scan. Measured real-scan results live in the Overview provenance block.
          </div>
        </div>
      </GlassCard>

      {/* phenotype selector + run */}
      <div className="mb-5 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div className="flex flex-wrap gap-2">
          {PHENOTYPES.map((p) => (
            <button
              key={p.id}
              onClick={() => { setPhenotypeId(p.id); setStage("idle"); setData(null); setReport(null); stopFrameLoop(); }}
              disabled={running}
              className={cn(
                "rounded-xl border px-3.5 py-2.5 text-left transition-all disabled:opacity-50",
                phenotypeId === p.id
                  ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-200 ho-glow"
                  : "border-white/10 bg-white/[0.03] text-muted-foreground hover:border-white/20 hover:bg-white/[0.06]",
              )}
            >
              <div className="text-sm font-semibold">{p.label}</div>
              <div className="text-[10px] font-mono text-muted-foreground">{p.description}</div>
            </button>
          ))}
        </div>
        <Button
          onClick={run}
          disabled={running}
          size="lg"
          className="h-11 gap-2 bg-emerald-400 px-6 text-emerald-950 hover:bg-emerald-300 ho-glow"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
          {running ? "Running…" : stage === "idle" ? "Run pipeline" : "Re-run"}
        </Button>
      </div>

      {/* stage rail */}
      <div className="mb-5 grid grid-cols-2 gap-2 sm:grid-cols-5">
        {STAGE_STEPS.map((s, i) => {
          const active = i === stageIdx;
          const done = stageIdx > i;
          const Icon = s.icon;
          return (
            <div
              key={s.id}
              className={cn(
                "relative overflow-hidden rounded-xl border px-3 py-2.5 transition-all",
                active && "border-emerald-400/50 bg-emerald-400/10",
                done && "border-emerald-400/20 bg-emerald-400/[0.04]",
                !active && !done && "border-white/8 bg-white/[0.02] opacity-50",
              )}
            >
              {active ? <div className="absolute bottom-0 left-0 right-0 h-0.5 ho-flow-line" /> : null}
              <div className="flex items-center gap-2">
                <Icon className={cn("h-4 w-4", active ? "text-emerald-300" : done ? "text-emerald-400/60" : "text-muted-foreground")} />
                <span className={cn("text-[11px] font-medium leading-tight", active ? "text-emerald-200" : "text-muted-foreground")}>{s.label}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        {/* viewer + curve */}
        <div className="flex flex-col gap-4 lg:col-span-3">
          <AnimatePresence mode="wait">
            {phase && stageIdx >= 1 ? (
              <motion.div key="viewer" initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.4 }}>
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                  <HeartViewer frames={phase.frames} contours={phase.contours} frameIndex={frameIndex} className="aspect-square" />
                  <div className="flex flex-col gap-3">
                    <div className="grid grid-cols-2 gap-2">
                      {[
                        { l: "EDV", v: `${phase.edvMl}`, u: "mL", c: "text-emerald-300" },
                        { l: "ESV", v: `${phase.esvMl}`, u: "mL", c: "text-teal-300" },
                        { l: "SV", v: `${phase.strokeVolumeMl}`, u: "mL", c: "text-amber-300" },
                        { l: "EF", v: `${phase.efPct}`, u: "%", c: "text-emerald-300" },
                      ].map((m) => (
                        <div key={m.l} className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
                          <div className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{m.l}</div>
                          <div className={cn("mt-0.5 text-2xl font-bold tabular-nums", stageIdx >= 2 ? m.c : "text-muted-foreground/40")}>
                            {stageIdx >= 2 ? m.v : "—"}<span className="text-sm font-medium text-muted-foreground"> {m.u}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs leading-relaxed text-muted-foreground">
                      <span className="text-foreground font-medium">{phase.phenotype.label}</span> — {phase.phenotype.notes}
                    </div>
                  </div>
                </div>
              </motion.div>
            ) : (
              <motion.div key="empty-viewer" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                <div className="flex aspect-[2/1] items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.02] sm:aspect-[2.4/1]">
                  <div className="text-center">
                    <ScanLine className="mx-auto h-8 w-8 text-muted-foreground/40" />
                    <p className="mt-2 font-mono text-xs text-muted-foreground/60">AWAITING SERIES — press &quot;Run pipeline&quot;</p>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* volume curve */}
          {phase && stageIdx >= 2 ? (
            <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
              <Card className="border-white/10 bg-white/[0.03]">
                <CardContent className="p-4">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="text-sm font-semibold">LV volume curve — {phase.nFrames} frames</div>
                    <button onClick={() => (playing ? (stopFrameLoop(), setPlaying(false)) : (startFrameLoop(phase.nFrames), setPlaying(true)))} className="font-mono text-[10px] uppercase tracking-widest text-emerald-300 hover:underline">
                      {playing ? "pause cine" : "play cine"}
                    </button>
                  </div>
                  <VolumeChart curve={phase.volumeCurveMl} frameIndex={frameIndex} edv={phase.edvMl} esv={phase.esvMl} />
                </CardContent>
              </Card>
            </motion.div>
          ) : null}
        </div>

        {/* gates + audit trail */}
        <div className="flex flex-col gap-4 lg:col-span-2">
          <Card className="border-white/10 bg-white/[0.03]">
            <CardContent className="space-y-2 p-4">
              <div className="flex items-center justify-between">
                <div className="text-sm font-semibold">Audit gates</div>
                {data && stageIdx >= 4 ? (
                  <StatusBadge kind={data.overall === "pass" ? "pass" : data.overall === "warn" ? "warn" : "fail"}>
                    {data.overall === "pass" ? "ALL GATES PASS" : data.overall === "warn" ? "PASS W/ WARNINGS" : "FAIL — WITHHELD"}
                  </StatusBadge>
                ) : null}
              </div>
              {stageIdx >= 4 && data
                ? data.gates.map((g, i) => <GateCard key={g.id} gate={g} index={i} />)
                : (
                  <div className="space-y-2">
                    {[0, 1, 2, 3].map((i) => (
                      <div key={i} className="h-[52px] animate-pulse rounded-lg border border-white/5 bg-white/[0.02]" />
                    ))}
                  </div>
                )}
            </CardContent>
          </Card>

          {/* hash-chained audit trail */}
          {data && stageIdx >= 4 ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              <Card className="border-white/10 bg-white/[0.03]">
                <CardContent className="p-4">
                  <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
                    <Link2 className="h-4 w-4 text-emerald-400" /> Audit trail
                    <span className="ml-auto font-mono text-[9px] text-muted-foreground">SHA-256 chained</span>
                  </div>
                  <div className="max-h-44 space-y-1.5 overflow-y-auto oracle-scroll pr-1">
                    {data.auditTrail.map((e) => (
                      <div key={e.seq} className="rounded-md border border-white/5 bg-black/30 px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-muted-foreground">
                        <span className="text-emerald-400/80">#{e.seq}</span> {e.gate} <StatusBadge kind={e.status === "pass" ? "pass" : e.status === "warn" ? "warn" : "fail"} className="mx-1 !px-1 !py-0 !text-[8px]">{e.status.toUpperCase()}</StatusBadge>
                        <span className="text-[9px] opacity-70">· {e.hash}</span>
                      </div>
                    ))}
                  </div>
                  <div className="mt-2 truncate font-mono text-[9px] text-muted-foreground/70">head: {data.overallHash} · run: {data.run.runId}</div>
                </CardContent>
              </Card>
            </motion.div>
          ) : null}
        </div>
      </div>

      {/* report */}
      {stage === "ready" && data ? (
        <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} className="mt-5">
          <Card className="border-emerald-400/20 bg-white/[0.03]">
            <CardContent className="p-4 md:p-6">
              <div className="flex flex-col items-start justify-between gap-3 md:flex-row md:items-center">
                <div>
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <FileText className="h-4 w-4 text-emerald-400" /> Step 5 — Cited advisory report (Gate G5 enforced)
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    LLM composes the report from injected pipeline numerics only; G5 verifies grounding, citation coverage and the RUO disclaimer.
                  </p>
                </div>
                <Button onClick={composeReport} disabled={reportLoading} className="gap-2 bg-emerald-400 text-emerald-950 hover:bg-emerald-300">
                  {reportLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Quote className="h-4 w-4" />}
                  {reportLoading ? "Composing…" : report ? "Recompose" : "Compose report"}
                </Button>
              </div>

              {report?.ok && report.report ? (
                <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-4 grid gap-4 lg:grid-cols-3">
                  <div className="rounded-xl border border-white/10 bg-black/30 p-4 lg:col-span-2">
                    <div className="prose prose-sm prose-invert max-h-80 max-w-none overflow-y-auto oracle-scroll text-sm leading-relaxed [&_h2]:mt-3 [&_h2]:mb-1.5 [&_h2]:text-sm [&_h2]:font-semibold [&_h2]:text-emerald-200 [&_p]:my-1.5">
                      <ReactMarkdown>{report.report}</ReactMarkdown>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {report.gate5 ? <GateCard gate={report.gate5} index={4} /> : null}
                    <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3">
                      <div className="mb-1.5 text-xs font-semibold">Citations (local KB)</div>
                      <ul className="space-y-1.5">
                        {report.citations?.map((c) => (
                          <li key={c.id} className="text-[10px] leading-relaxed text-muted-foreground">
                            <span className="font-mono text-emerald-400/80">[{c.id}]</span> {c.source}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </motion.div>
              ) : report && !report.ok ? (
                <div className="mt-4 rounded-xl border border-rose-400/30 bg-rose-400/5 p-3 text-xs text-rose-200">
                  Report generation failed: {report.error}. (LLM sidecar — retry usually resolves.)
                </div>
              ) : null}
            </CardContent>
          </Card>
        </motion.div>
      ) : null}
    </div>
  );
}

function GateCard({ gate, index }: { gate: GateResult; index: number }) {
  const [open, setOpen] = useState(true);
  const Icon = gate.status === "pass" ? CheckCircle2 : gate.status === "warn" ? AlertTriangle : XCircle;
  const color = gate.status === "pass" ? "text-emerald-400" : gate.status === "warn" ? "text-amber-400" : "text-rose-400";
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: index * 0.28, duration: 0.35 }}
      className={cn(
        "rounded-lg border px-3 py-2.5",
        gate.status === "pass" && "border-emerald-400/20 bg-emerald-400/[0.05]",
        gate.status === "warn" && "border-amber-400/25 bg-amber-400/[0.05]",
        gate.status === "fail" && "border-rose-400/25 bg-rose-400/[0.05]",
      )}
    >
      <button onClick={() => setOpen((o) => !o)} className="flex w-full items-center gap-2 text-left">
        <Icon className={cn("h-4 w-4 shrink-0", color)} />
        <span className="font-mono text-[10px] text-muted-foreground">{gate.id}</span>
        <span className="text-xs font-semibold">{gate.name}</span>
        <span className={cn("ml-auto text-[9px] font-bold tracking-widest", color)}>{gate.status.toUpperCase()}</span>
      </button>
      {open ? (
        <div className="mt-1.5 space-y-1 border-l border-white/10 pl-3">
          {gate.checks.map((c) => (
            <div key={c.label} className="flex items-start gap-1.5 text-[10px] leading-relaxed">
              <span className={cn("mt-0.5", c.ok ? "text-emerald-400" : "text-rose-400")}>{c.ok ? "✓" : "✗"}</span>
              <span className="text-muted-foreground"><span className="text-foreground/90">{c.label}</span> — {c.detail}</span>
            </div>
          ))}
        </div>
      ) : null}
    </motion.div>
  );
}

function VolumeChart({ curve, frameIndex, edv, esv }: { curve: number[]; frameIndex: number; edv: number; esv: number }) {
  const data = curve.map((v, i) => ({ f: i + 1, v }));
  return (
    <div className="h-40">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -18 }}>
          <defs>
            <linearGradient id="volGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="oklch(0.78 0.15 165)" stopOpacity={0.5} />
              <stop offset="100%" stopColor="oklch(0.78 0.15 165)" stopOpacity={0.03} />
            </linearGradient>
          </defs>
          <XAxis dataKey="f" tick={{ fontSize: 9, fill: "oklch(0.68 0.015 170)" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 9, fill: "oklch(0.68 0.015 170)" }} axisLine={false} tickLine={false} domain={[0, "dataMax + 20"]} />
          <Tooltip
            contentStyle={{ background: "oklch(0.17 0.012 170)", border: "1px solid oklch(1 0 0 / 0.1)", borderRadius: 10, fontSize: 12 }}
            labelFormatter={(l) => `frame ${l}`}
            formatter={(v) => [`${v} mL`, "LV volume"]}
          />
          <ReferenceLine y={edv} stroke="oklch(0.78 0.15 165 / 0.5)" strokeDasharray="4 4" />
          <ReferenceLine y={esv} stroke="oklch(0.8 0.14 85 / 0.5)" strokeDasharray="4 4" />
          <ReferenceLine x={frameIndex + 1} stroke="oklch(0.9 0.1 165 / 0.7)" strokeWidth={1.2} />
          <Area type="monotone" dataKey="v" stroke="oklch(0.82 0.13 165)" strokeWidth={2} fill="url(#volGrad)" isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
