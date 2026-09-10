"use client";

import { motion } from "framer-motion";
import { CheckCircle2, Clock, FlaskConical, Rocket, Cpu, Layers3, Workflow, Boxes } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { SectionTitle, GlassCard, StatusBadge, fadeUp } from "./bits";
import { ADAPTERS, ROADMAP, FUSION_MAPPING, DATA_SOURCES } from "@/lib/data/platform";
import { cn } from "@/lib/utils";

export function PlatformTab() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 md:px-6">
      <SectionTitle
        eyebrow="Architecture"
        title="Platform: a reusable core with pluggable modality adapters"
        sub="The strategic move that makes HeartOracle holistic without making it fragile: each cardiac pillar enters through its own adapter with its own validation dossier and regulatory claim. One weak module can never block the platform."
      />

      {/* core diagram */}
      <motion.div {...fadeUp}>
        <GlassCard className="mb-8 overflow-hidden p-0">
          <div className="ho-grid-bg relative px-4 py-6 md:px-8 md:py-8">
            <div className="grid gap-3 md:grid-cols-[1fr_auto_1.4fr] md:items-center">
              {/* adapters column */}
              <div className="space-y-2">
                <div className="mb-1 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Modality adapters</div>
                {ADAPTERS.slice(0, 5).map((a) => (
                  <div key={a.id} className={cn(
                    "rounded-lg border px-3 py-2 text-xs font-medium",
                    a.status === "live" ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200" : "border-white/10 bg-white/[0.03] text-muted-foreground",
                  )}>
                    {a.name}
                  </div>
                ))}
              </div>
              {/* flow */}
              <div className="hidden h-0.5 w-16 md:block">
                <div className="h-full w-full ho-flow-line" />
              </div>
              <div className="h-0.5 w-full md:hidden" />
              {/* core */}
              <div className="rounded-2xl border border-emerald-400/30 bg-emerald-400/[0.06] p-4 ho-glow">
                <div className="mb-3 flex items-center gap-2">
                  <Layers3 className="h-4 w-4 text-emerald-400" />
                  <span className="text-sm font-semibold">Reusable core — built once, regulated once</span>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {[
                    "Ingestion & normalization (DICOM → EDF/FHIR next)",
                    "5 audit gates between model and report",
                    "RAG-cited reporting engine (local KB)",
                    "Physician sign-off surface (Art. 14 by design)",
                    "Regulatory documentation machine",
                    "Hash-chained audit trail",
                  ].map((c) => (
                    <div key={c} className="flex items-center gap-2 rounded-lg border border-white/5 bg-black/20 px-2.5 py-1.5 text-[11px] leading-snug text-muted-foreground">
                      <CheckCircle2 className="h-3 w-3 shrink-0 text-emerald-400/70" /> {c}
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-4 flex items-center gap-2 font-mono text-[10px] text-muted-foreground">
              <Cpu className="h-3 w-3" /> Each adapter ships independently: model + validation dossier + regulatory claim.
            </div>
          </div>
        </GlassCard>
      </motion.div>

      {/* fusion mapping */}
      <SectionTitle
        eyebrow="Expansion"
        title="Mapping the fusion blueprint onto phased reality"
        sub="The proposed multimodal fusion architecture (raw inputs → cross-attention fusion → physics + radiomics layers → explainable dashboard) is directionally right. Here is each block, honestly priced and sequenced."
      />
      <div className="mb-8 space-y-2.5">
        {FUSION_MAPPING.map((m, i) => (
          <motion.div key={i} {...fadeUp} transition={{ duration: 0.4, delay: i * 0.05 }}>
            <Card className="border-white/10 bg-white/[0.03]">
              <CardContent className="flex flex-col gap-2 p-4 md:flex-row md:items-start md:gap-4">
                <div className="flex items-start gap-2 md:w-64 md:shrink-0">
                  {m.verdict === "adopt-now" ? <Rocket className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" /> : m.verdict === "sequence" ? <Workflow className="mt-0.5 h-4 w-4 shrink-0 text-teal-300" /> : <Clock className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" />}
                  <div className="text-xs font-semibold leading-snug text-foreground/90">{m.gemini}</div>
                </div>
                <div className="min-w-0 text-xs leading-relaxed text-muted-foreground">{m.ours}</div>
                <div className="shrink-0 md:ml-auto">
                  <StatusBadge kind={m.verdict === "adopt-now" ? "pass" : m.verdict === "sequence" ? "info" : "warn"}>
                    {m.verdict === "adopt-now" ? "ADOPT NOW" : m.verdict === "sequence" ? "SEQUENCED" : "PARKED — HONEST"}
                  </StatusBadge>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* roadmap */}
      <SectionTitle eyebrow="Delivery" title="Phased roadmap" sub="Cheapest evidence first. Moonshots require partners — stated plainly instead of pretended." />
      <div className="mb-8 grid gap-3 md:grid-cols-2">
        {ROADMAP.map((p, i) => (
          <motion.div key={p.id} {...fadeUp} transition={{ duration: 0.45, delay: i * 0.06 }}>
            <Card className={cn(
              "h-full border-white/10 bg-white/[0.03]",
              p.state === "now" && "border-emerald-400/25 bg-emerald-400/[0.04]",
              p.state === "moon" && "border-dashed",
            )}>
              <CardContent className="p-4 md:p-5">
                <div className="mb-2.5 flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold">{p.title}</div>
                  <span className="font-mono text-[9px] uppercase tracking-widest text-muted-foreground">{p.window}</span>
                </div>
                <ul className="space-y-1.5">
                  {p.items.map((it) => (
                    <li key={it} className="flex items-start gap-2 text-xs leading-relaxed text-muted-foreground">
                      <span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-emerald-400/70" /> {it}
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* data sources */}
      <SectionTitle
        eyebrow="Evidence pipeline"
        title="Data acquisition map"
        sub="Public-first: benchmark sets for every near-term adapter, outcome-linked cohorts applied for early. Everything research-licensed, reinforcing the RUO posture."
      />
      <Card className="border-white/10 bg-white/[0.03]">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-3 font-medium">Dataset</th>
                  <th className="px-4 py-3 font-medium">What it gives</th>
                  <th className="px-4 py-3 font-medium">Access</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {DATA_SOURCES.map((d) => (
                  <tr key={d.name} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 align-top">
                      <div className="font-semibold text-foreground">{d.name}</div>
                      <div className="mt-0.5 font-mono text-[9px] uppercase tracking-wider text-emerald-400/60">{d.pillar}</div>
                    </td>
                    <td className="max-w-[260px] px-4 py-3 align-top leading-relaxed text-muted-foreground">{d.what}</td>
                    <td className="max-w-[180px] px-4 py-3 align-top leading-relaxed text-muted-foreground">{d.access}</td>
                    <td className="max-w-[220px] px-4 py-3 align-top leading-relaxed text-muted-foreground/90">{d.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="mt-6">
        <GlassCard className="flex items-start gap-3 border-teal-400/20">
          <Boxes className="mt-0.5 h-5 w-5 shrink-0 text-teal-300" />
          <p className="text-xs leading-relaxed text-muted-foreground">
            <span className="font-semibold text-teal-200">Why this wins:</span> single-modality models are commoditized.
            The moat is the linked multimodal evidence layer + the audit trail + the documentation machine — the same
            skeleton HeartFlow validated at commercial scale, built at research scale from day one.
          </p>
        </GlassCard>
      </div>

      <div className="mt-4 flex items-center gap-2 text-[11px] text-muted-foreground">
        <FlaskConical className="h-3.5 w-3.5 text-emerald-400/70" />
        Full architecture details: <span className="font-mono text-emerald-300/80">docs/architecture/PLATFORM.md</span> · infrastructure: <span className="font-mono text-emerald-300/80">docs/architecture/INFRASTRUCTURE.md</span>
      </div>
    </div>
  );
}
