"use client";

import { motion } from "framer-motion";
import { ClipboardCheck, FileWarning, ScrollText, GitBranch } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { SectionTitle, GlassCard, fadeUp } from "./bits";
import { GMLP_MATRIX, RISK_REGISTER } from "@/lib/data/governance";
import { cn } from "@/lib/utils";

function StatusDot({ status }: { status: "done" | "partial" | "gap" }) {
  const cls = status === "done" ? "bg-emerald-400" : status === "partial" ? "bg-amber-400" : "bg-rose-400";
  const label = status === "done" ? "EVIDENCED" : status === "partial" ? "PARTIAL" : "GAP";
  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-[9px] font-semibold tracking-widest text-muted-foreground">
      <span className={cn("h-1.5 w-1.5 rounded-full", cls)} /> {label}
    </span>
  );
}

export function ComplianceTab() {
  const done = GMLP_MATRIX.filter((g) => g.status === "done").length;
  const partial = GMLP_MATRIX.filter((g) => g.status === "partial").length;
  const highRisks = RISK_REGISTER.filter((r) => r.residual === "high").length;

  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 md:px-6">
      <SectionTitle
        eyebrow="Compliance center"
        title="Regulatory-by-design, in public"
        sub="FDA's GMLP principles and the EU AI Act are the blueprint we build against today — so a future 510(k)/CE file is assembled from evidence that already exists, not reconstructed from memory. Statuses below are live from the governance data model."
      />

      {/* summary chips */}
      <div className="mb-6 grid grid-cols-3 gap-3">
        {[
          { label: "GMLP principles evidenced", v: `${done}/10`, sub: `${partial} partial — gaps owned, not hidden`, icon: ClipboardCheck },
          { label: "ISO 14971 risks in register", v: `${RISK_REGISTER.length}`, sub: `${highRisks} residual-high (tracked, honestly)`, icon: FileWarning },
          { label: "PCCP retraining governance", v: "DRAFTED", sub: "triggers · acceptance · rollback", icon: ScrollText },
        ].map((s, i) => (
          <motion.div key={s.label} {...fadeUp} transition={{ duration: 0.45, delay: i * 0.07 }}>
            <Card className="border-white/10 bg-white/[0.04]">
              <CardContent className="p-4">
                <s.icon className="h-4 w-4 text-emerald-400" />
                <div className="mt-2 text-xl font-bold tracking-tight text-emerald-300 md:text-2xl">{s.v}</div>
                <div className="mt-0.5 text-[11px] font-medium">{s.label}</div>
                <div className="mt-0.5 text-[10px] leading-snug text-muted-foreground">{s.sub}</div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>

      {/* GMLP matrix */}
      <SectionTitle eyebrow="FDA · Health Canada · MHRA (2021)" title="GMLP gap matrix" sub="Ten Good Machine Learning Practice principles × current artifact × owned gap. The master dashboard for the entire regulatory posture." />
      <Card className="mb-8 border-white/10 bg-white/[0.03]">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-3 font-medium">#</th>
                  <th className="px-4 py-3 font-medium">Principle</th>
                  <th className="px-4 py-3 font-medium">Current artifact</th>
                  <th className="px-4 py-3 font-medium">Owned gap</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {GMLP_MATRIX.map((g) => (
                  <tr key={g.id} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 align-top font-mono text-emerald-400/70">{g.id}</td>
                    <td className="max-w-[210px] px-4 py-3 align-top font-medium leading-snug">{g.principle}</td>
                    <td className="max-w-[260px] px-4 py-3 align-top leading-relaxed text-muted-foreground">{g.artifact}</td>
                    <td className="max-w-[210px] px-4 py-3 align-top leading-relaxed text-muted-foreground/80">{g.gap}</td>
                    <td className="px-4 py-3 align-top"><StatusDot status={g.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* Risk register */}
      <SectionTitle eyebrow="ISO 14971" title="Risk management file" sub="Hazards, causes, effects, and the controls that already run in the pipeline (the 5 audit gates are registered mitigations). Residual ratings are our honest current view." />
      <div className="mb-8 space-y-2.5">
        {RISK_REGISTER.map((r, i) => {
          const rpn = r.severity * r.probability;
          return (
            <motion.div key={r.id} {...fadeUp} transition={{ duration: 0.4, delay: (i % 5) * 0.04 }}>
              <Card className={cn(
                "border-white/10 bg-white/[0.03]",
                r.residual === "high" && "border-amber-400/30 bg-amber-400/[0.04]",
              )}>
                <CardContent className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-xs text-emerald-400/70">{r.id}</span>
                    <span className="text-sm font-semibold">{r.hazard}</span>
                    <span className={cn(
                      "ml-auto rounded-full border px-2 py-0.5 font-mono text-[9px] font-bold tracking-widest",
                      r.residual === "low" && "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
                      r.residual === "medium" && "border-amber-400/40 bg-amber-400/10 text-amber-300",
                      r.residual === "high" && "border-rose-400/40 bg-rose-400/10 text-rose-300",
                    )}>
                      RESIDUAL {r.residual.toUpperCase()}
                    </span>
                  </div>
                  <div className="mt-2 grid gap-2 text-[11px] leading-relaxed text-muted-foreground md:grid-cols-3">
                    <div><span className="text-foreground/80">Cause:</span> {r.cause}</div>
                    <div><span className="text-foreground/80">Effect:</span> {r.effect}</div>
                    <div className="font-mono text-[10px]"><span className="text-foreground/80">S{r.severity}×P{r.probability} = RPN {rpn}</span> · {r.iso}</div>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {r.controls.map((c) => (
                      <span key={c} className="rounded-md border border-white/10 bg-black/25 px-2 py-0.5 text-[10px] text-muted-foreground">{c}</span>
                    ))}
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* PCCP + traceability */}
      <div className="grid gap-3 md:grid-cols-2">
        <motion.div {...fadeUp}>
          <GlassCard className="h-full">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <ScrollText className="h-4 w-4 text-emerald-400" /> PCCP draft — FDA final guidance (Dec 3, 2024)
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              A Predetermined Change Control Plan lets a model improve without a new submission per retrain. Our draft
              defines: retraining triggers (new data cohorts, drift alarms), acceptance thresholds (all three Dice
              gates + HD95 gate must re-pass on the frozen holdout before release), and rollback (previous ONNX bundle
              retained, argmax-consistency re-verified). Versioned model cards accompany every release.
            </p>
          </GlassCard>
        </motion.div>
        <motion.div {...fadeUp} transition={{ duration: 0.45, delay: 0.08 }}>
          <GlassCard className="h-full">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold">
              <GitBranch className="h-4 w-4 text-emerald-400" /> Traceability — ORACLE-P{"{n}"}T{"{m}"}
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              Every commit maps requirement → implementation → verification. The spec-driven commit format plus 100+
              passing tests are the raw material of the IEC 62304 V&amp;V file: requirements are traceable to code and
              to test evidence without archaeology. evaluation/ holds the frozen measurement protocol; BLOCKERS.md
              holds the honest gap ledger.
            </p>
          </GlassCard>
        </motion.div>
      </div>
    </div>
  );
}
