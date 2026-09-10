"use client";

import Image from "next/image";
import { motion } from "framer-motion";
import { Activity, ShieldCheck, Layers, HeartPulse, FileCheck2, Lock, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CountUp, GlassCard, SectionTitle, StatusBadge, fadeUp } from "./bits";
import { ENSEMBLE, EF_MEASURED, EVAL_PROVENANCE, SEG_GATES, LIMITATION_LEDGER } from "@/lib/data/eval-results";
import { ADAPTERS } from "@/lib/data/platform";
import { cn } from "@/lib/utils";

const STATUS_MAP: Record<string, { kind: "pass" | "info" | "warn" | "amber" | "fail"; label: string }> = {
  "achieved-here": { kind: "pass", label: "MEASURED HERE" },
  "engineering-path": { kind: "info", label: "ENGINEERING PATH" },
  "physics-bound": { kind: "warn", label: "PHYSICS-BOUND" },
  "regulatory-path": { kind: "amber", label: "REGULATORY PATH" },
  "by-design": { kind: "pass", label: "BY DESIGN" },
};

export function Overview({ onEnterDemo }: { onEnterDemo: () => void }) {
  const dice = ENSEMBLE.per_frame_mean;
  const allPass = Object.values(SEG_GATES).every((g) => g.ensemble_pass);

  return (
    <div>
      {/* ---------- HERO ---------- */}
      <section className="relative overflow-hidden">
        <div className="absolute inset-0">
          <Image
            src="/brand/hero-heart.png"
            alt="Holographic cardiac visualization"
            fill
            priority
            className="object-cover opacity-45"
          />
          <div className="absolute inset-0 bg-gradient-to-b from-background/70 via-background/55 to-background" />
          <div className="absolute inset-0 bg-gradient-to-r from-background/80 via-transparent to-background/60" />
        </div>

        <div className="relative mx-auto flex max-w-6xl flex-col items-start gap-6 px-4 pb-16 pt-14 md:px-6 md:pb-24 md:pt-20">
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }} className="flex flex-wrap items-center gap-2">
            <StatusBadge kind="amber">RESEARCH USE ONLY</StatusBadge>
            <StatusBadge kind="pass">ALL 3 DICE GATES PASS</StatusBadge>
            <StatusBadge kind="info">HD95 MEASURED · EF MAE 2.72 pp</StatusBadge>
          </motion.div>

          <motion.h1
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.08 }}
            className="max-w-4xl text-4xl font-bold leading-[1.06] tracking-tight md:text-6xl"
          >
            Cardiac intelligence,
            <span className="bg-gradient-to-r from-emerald-300 via-teal-200 to-emerald-400 bg-clip-text text-transparent"> measured, audited, cited.</span>
          </motion.h1>

          <motion.p
            initial={{ opacity: 0, y: 18 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6, delay: 0.16 }}
            className="max-w-2xl text-base leading-relaxed text-muted-foreground md:text-lg"
          >
            HeartOracle is a multimodal cardiac advisory platform built regulatory-by-design: a 5-fold attention U-Net
            ensemble quantifies ventricular function on CPU, five audit gates stand between model and report, and every
            claim carries a guideline citation. <span className="text-emerald-300">ORACLE advises — physicians decide.</span>
          </motion.p>

          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.24 }} className="flex flex-wrap items-center gap-3">
            <Button size="lg" onClick={onEnterDemo} className="h-11 gap-2 bg-emerald-400 px-6 text-emerald-950 hover:bg-emerald-300 ho-glow">
              <HeartPulse className="h-5 w-5" /> Run the live pipeline
            </Button>
            <Button size="lg" variant="outline" asChild className="h-11 gap-2 border-white/15 bg-white/5 backdrop-blur hover:bg-white/10">
              <a href="#provenance">Verify the evidence <ArrowRight className="h-4 w-4" /></a>
            </Button>
          </motion.div>
        </div>
      </section>

      {/* ---------- MEASURED STATS ---------- */}
      <section className="mx-auto max-w-6xl px-4 pb-14 md:px-6">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4 md:gap-4">
          {[
            { label: "LV Dice (frame-level)", value: dice.LV, gate: SEG_GATES.LV.gate, decimals: 3, suffix: "" },
            { label: "MYO Dice", value: dice.MYO, gate: SEG_GATES.MYO.gate, decimals: 3, suffix: "" },
            { label: "RV Dice", value: dice.RV, gate: SEG_GATES.RV.gate, decimals: 3, suffix: "" },
            { label: "EF error (MAE)", value: EF_MEASURED.mae_pp, gate: null, decimals: 2, suffix: " pp" },
          ].map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5, delay: 0.3 + i * 0.08 }}>
              <Card className="border-white/10 bg-white/[0.04] backdrop-blur">
                <CardContent className="p-4 md:p-5">
                  <div className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground">{s.label}</div>
                  <div className="mt-1 text-3xl font-bold tracking-tight text-emerald-300 md:text-4xl">
                    <CountUp value={s.value} decimals={s.decimals} suffix={s.suffix} />
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {s.gate != null ? `gate ≥ ${s.gate.toFixed(2)} · ensemble PASS` : `bias ${EF_MEASURED.bias_pp > 0 ? "+" : ""}${EF_MEASURED.bias_pp} pp vs reference`}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>

        {/* provenance strip */}
        <div id="provenance" className="mt-4">
          <GlassCard className="flex flex-col gap-3 border-emerald-400/15 md:flex-row md:items-center md:justify-between">
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
              <div>
                <div className="text-sm font-semibold">Measured, not mocked</div>
                <div className="mt-0.5 text-xs leading-relaxed text-muted-foreground">
                  {ENSEMBLE.model} · {ENSEMBLE.n_frames} frames · {EVAL_PROVENANCE.split} · {EVAL_PROVENANCE.protocol}
                </div>
              </div>
            </div>
            <div className="shrink-0 font-mono text-[11px] text-muted-foreground">
              {EVAL_PROVENANCE.repo}@{EVAL_PROVENANCE.commit.split(" ")[1]?.replace(/[()]/g, "")}
            </div>
          </GlassCard>
        </div>
      </section>

      {/* ---------- ADAPTER MATRIX ---------- */}
      <section className="mx-auto max-w-6xl px-4 pb-14 md:px-6">
        <SectionTitle
          eyebrow="Platform"
          title="One core, seven modality adapters"
          sub="The reusable core (ingestion, audit gates, cited reporting, physician sign-off, regulatory documentation machine) is built once. Each cardiac pillar plugs in as an adapter with its own validation dossier and regulatory claim."
        />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {ADAPTERS.map((a, i) => (
            <motion.div key={a.id} {...fadeUp} transition={{ duration: 0.45, delay: (i % 4) * 0.06 }}>
              <Card className={cn(
                "group h-full border-white/10 bg-white/[0.03] transition-colors hover:border-emerald-400/30 hover:bg-white/[0.05]",
                a.status === "live" && "border-emerald-400/25",
                a.status === "moonshot" && "border-dashed",
              )}>
                <CardContent className="flex h-full flex-col gap-2.5 p-4">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">{a.pillar}</span>
                    <AdapterStatusChip status={a.status} />
                  </div>
                  <div className="text-[15px] font-semibold leading-snug">{a.name}</div>
                  <p className="text-xs leading-relaxed text-muted-foreground">{a.description}</p>
                  <div className="mt-auto space-y-1 border-t border-white/5 pt-2.5 font-mono text-[10px] leading-relaxed text-muted-foreground/80">
                    <div><span className="text-emerald-400/70">data:</span> {a.data}</div>
                    <div><span className="text-emerald-400/70">reg:</span> {a.regulatory}</div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ---------- LIMITATION LEDGER ---------- */}
      <section className="mx-auto max-w-6xl px-4 pb-16 md:px-6">
        <SectionTitle
          eyebrow="Honest engineering"
          title="The limitation ledger"
          sub="Every published limitation of v0, with its exact status. Nothing hidden — the RV tail risk and single-dataset training are stated on the same page as the wins."
        />
        <div className="space-y-2.5">
          {LIMITATION_LEDGER.map((l, i) => {
            const chip = STATUS_MAP[l.status];
            return (
              <motion.div key={l.id} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
                <Card className="border-white/10 bg-white/[0.03]">
                  <CardContent className="flex flex-col gap-2 p-4 md:flex-row md:items-start md:gap-4 md:p-5">
                    <div className="flex shrink-0 items-center gap-2 md:w-56 md:flex-col md:items-start">
                      <span className="font-mono text-xs text-muted-foreground">{l.id}</span>
                      <StatusBadge kind={chip.kind}>{chip.label}</StatusBadge>
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-semibold leading-snug">{l.limitation}</div>
                      <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{l.detail}</p>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            );
          })}
        </div>
      </section>

      {/* ---------- TRUST STRIP ---------- */}
      <section className="border-y border-white/5 bg-white/[0.02]">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-4 px-4 py-8 sm:grid-cols-3 md:px-6">
          {[
            { icon: Layers, title: "Adapter architecture", text: "Each modality ships independently with its own evidence file — one weak module never blocks the platform." },
            { icon: FileCheck2, title: "Regulatory-by-design", text: "GMLP gap matrix, ISO 14971 risk file, PCCP draft, traceability matrix — evidence generated continuously, not crammed at submission." },
            { icon: Lock, title: "Security by construction", text: "PHI never leaves the deployment; the LLM sidecar sees de-identified metrics only; the audit trail is append-only and hash-chained." },
          ].map((t, i) => (
            <motion.div key={t.title} {...fadeUp} transition={{ duration: 0.45, delay: i * 0.08 }} className="flex gap-3">
              <t.icon className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
              <div>
                <div className="text-sm font-semibold">{t.title}</div>
                <p className="mt-1 text-xs leading-relaxed text-muted-foreground">{t.text}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ---------- MISSION ---------- */}
      <section className="mx-auto max-w-6xl px-4 py-14 md:px-6">
        <GlassCard className="relative overflow-hidden border-emerald-400/15">
          <div className="absolute -right-16 -top-16 h-48 w-48 rounded-full bg-emerald-400/10 blur-3xl" />
          <div className="relative flex flex-col items-start gap-4">
            <Activity className="h-6 w-6 text-emerald-400" />
            <h3 className="max-w-3xl text-xl font-semibold leading-snug md:text-2xl">
              Not a hype project. A documentation machine that happens to run a heart model — built so that accuracy,
              compliance and patient safety compound with every commit.
            </h3>
            <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
              {allPass ? "All three segmentation gates currently PASS under the documented protocol on the official holdout. " : ""}
              The RV tail (p95 HD95 {ENSEMBLE.hd95_p95_mm.RV} mm) and single-dataset training are open workstreams with funded paths — not secrets.
            </p>
          </div>
        </GlassCard>
      </section>
    </div>
  );
}

function AdapterStatusChip({ status }: { status: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    live: { label: "LIVE", cls: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300" },
    next: { label: "NEXT", cls: "border-teal-400/40 bg-teal-400/10 text-teal-200" },
    planned: { label: "PLANNED", cls: "border-white/20 bg-white/5 text-muted-foreground" },
    moonshot: { label: "MOONSHOT", cls: "border-amber-400/40 bg-amber-400/10 text-amber-300" },
    "by-design": { label: "BY DESIGN", cls: "border-white/20 bg-white/5 text-muted-foreground" },
  };
  const s = map[status] ?? map.planned;
  return <span className={cn("rounded-full border px-2 py-0.5 font-mono text-[9px] font-semibold tracking-widest", s.cls)}>{s.label}</span>;
}
