"use client";

import { motion } from "framer-motion";
import { ShieldCheck, Server, Lock, Eye, Scale } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { SectionTitle, GlassCard, fadeUp } from "./bits";
import { THREAT_MODEL, SECURITY_CONTROLS } from "@/lib/data/governance";
import { cn } from "@/lib/utils";

export function SecurityTab() {
  return (
    <div className="mx-auto max-w-6xl px-4 pb-16 md:px-6">
      <SectionTitle
        eyebrow="Security & governance"
        title="AI governance, engineered in"
        sub="Healthcare AI fails on trust before it fails on accuracy. This center documents the threat model, the controls that already run, and the governance principles that will not be traded for features."
      />

      {/* principles */}
      <div className="mb-8 grid gap-3 md:grid-cols-3">
        {[
          { icon: Scale, title: "Advises, never decides", text: "No autonomous treatment logic — excluded by design. EU AI Act Art. 14 human oversight is architecture, not policy text. Value ships as guideline surfacing, draft documentation and triage flags." },
          { icon: Eye, title: "Transparency in-product", text: "The limitation ledger, model provenance, gate verdicts and citation lists render on the same page as the results. No spreadsheet-only caveats." },
          { icon: Lock, title: "Local-first privacy", text: "Inference runs on-prem (ONNX INT8, CPU). The LLM sidecar receives de-identified metrics only — never images or identifiers. DICOMs are de-identified at ingest." },
        ].map((p, i) => (
          <motion.div key={p.title} {...fadeUp} transition={{ duration: 0.45, delay: i * 0.07 }}>
            <GlassCard className="h-full">
              <p.icon className="h-5 w-5 text-emerald-400" />
              <div className="mt-2.5 text-sm font-semibold">{p.title}</div>
              <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">{p.text}</p>
            </GlassCard>
          </motion.div>
        ))}
      </div>

      {/* STRIDE */}
      <SectionTitle eyebrow="Threat model" title="STRIDE analysis" sub="Attacker-view review of the platform surface. Statuses are honest: two partials wait on CI and auth workstream." />
      <Card className="mb-8 border-white/10 bg-white/[0.03]">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-left text-xs">
              <thead>
                <tr className="border-b border-white/10 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-3 font-medium">ID</th>
                  <th className="px-4 py-3 font-medium">Category</th>
                  <th className="px-4 py-3 font-medium">Scenario</th>
                  <th className="px-4 py-3 font-medium">Control</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {THREAT_MODEL.map((t) => (
                  <tr key={t.id} className="border-b border-white/5 last:border-0 hover:bg-white/[0.02]">
                    <td className="px-4 py-3 align-top font-mono text-emerald-400/70">{t.id}</td>
                    <td className="px-4 py-3 align-top font-medium">{t.category}</td>
                    <td className="max-w-[240px] px-4 py-3 align-top leading-relaxed">{t.scenario}</td>
                    <td className="max-w-[300px] px-4 py-3 align-top leading-relaxed text-muted-foreground">{t.control}</td>
                    <td className="px-4 py-3 align-top">
                      <span className={cn(
                        "font-mono text-[9px] font-bold tracking-widest",
                        t.status === "controlled" && "text-emerald-300",
                        t.status === "partial" && "text-amber-300",
                        t.status === "planned" && "text-muted-foreground",
                      )}>
                        {t.status.toUpperCase()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      {/* controls checklist */}
      <SectionTitle eyebrow="Posture" title="Security controls" sub="Implemented vs planned. Planned items are scheduled with owners in docs/security/SECURITY-CONTROLS.md." />
      <div className="mb-8 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {SECURITY_CONTROLS.map((c, i) => (
          <motion.div key={c.name} {...fadeUp} transition={{ duration: 0.35, delay: (i % 6) * 0.04 }}>
            <div className={cn(
              "flex h-full items-start gap-2.5 rounded-xl border px-3.5 py-3",
              c.status === "done" ? "border-emerald-400/20 bg-emerald-400/[0.05]" : "border-white/10 bg-white/[0.02]",
            )}>
              {c.status === "done" ? (
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
              ) : (
                <Server className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              )}
              <div>
                <div className="text-xs font-medium leading-snug">{c.name}</div>
                <div className={cn("mt-0.5 font-mono text-[9px] font-bold tracking-widest", c.status === "done" ? "text-emerald-300" : "text-muted-foreground")}>
                  {c.status.toUpperCase()}
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </div>

      {/* disclosure */}
      <GlassCard className="border-white/10">
        <div className="text-sm font-semibold">Responsible disclosure & governance contact</div>
        <p className="mt-1.5 text-xs leading-relaxed text-muted-foreground">
          Found a vulnerability? Report via the repository security advisory (github.com/Dalfino/HeartOracle → Security →
          Report a vulnerability). Governance questions, model concerns and intended-use boundary requests are tracked
          in docs/governance/AI-GOVERNANCE.md. All model artifacts are checksum-verified; verify against the SBOM before
          clinical-adjacent deployment.
        </p>
      </GlassCard>
    </div>
  );
}
