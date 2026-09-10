"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { HeartPulse, Radio } from "lucide-react";
import { Overview } from "@/components/platform/overview";
import { PipelineDemo } from "@/components/platform/pipeline-demo";
import { PlatformTab } from "@/components/platform/platform-tab";
import { ComplianceTab } from "@/components/platform/compliance-tab";
import { SecurityTab } from "@/components/platform/security-tab";
import { cn } from "@/lib/utils";

const TABS = [
  { id: "overview", label: "Overview" },
  { id: "pipeline", label: "Live Pipeline" },
  { id: "platform", label: "Platform" },
  { id: "compliance", label: "Compliance" },
  { id: "security", label: "Security" },
] as const;

type TabId = (typeof TABS)[number]["id"];

export default function Home() {
  const [tab, setTab] = useState<TabId>("overview");
  const topRef = useRef<HTMLDivElement>(null);

  const goto = useCallback((t: TabId) => {
    setTab(t);
    topRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const enterDemo = useCallback(() => goto("pipeline"), [goto]);

  // keep the doc title honest per tab (light-touch analytics-free UX)
  useEffect(() => {
    const titles: Record<TabId, string> = {
      overview: "HeartOracle — Multimodal Cardiac Intelligence Platform",
      pipeline: "Live Pipeline — HeartOracle",
      platform: "Platform Architecture — HeartOracle",
      compliance: "Compliance Center — HeartOracle",
      security: "Security & Governance — HeartOracle",
    };
    document.title = titles[tab];
  }, [tab]);

  return (
    <div className="flex min-h-screen flex-col">
      {/* ---------- STICKY NAV ---------- */}
      <header className="sticky top-0 z-50 border-b border-white/5 bg-background/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 md:px-6">
          <button onClick={() => goto("overview")} className="flex items-center gap-2.5" aria-label="HeartOracle home">
            <span className="relative flex h-9 w-9 items-center justify-center rounded-xl border border-emerald-400/30 bg-emerald-400/10 ho-pulse-ring">
              <HeartPulse className="h-5 w-5 text-emerald-400" />
            </span>
            <span className="text-left">
              <span className="block text-sm font-bold leading-none tracking-tight">HeartOracle</span>
              <span className="mt-0.5 block font-mono text-[9px] uppercase tracking-[0.22em] text-emerald-400/70">Cardiac Intelligence OS</span>
            </span>
          </button>

          <nav className="ml-auto hidden items-center gap-1 lg:flex" aria-label="Platform sections">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => goto(t.id)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-[13px] font-medium transition-colors",
                  tab === t.id ? "bg-emerald-400/10 text-emerald-300" : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
                )}
                aria-current={tab === t.id ? "page" : undefined}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <div className="ml-auto flex items-center gap-2 lg:ml-2">
            <span className="hidden items-center gap-1.5 rounded-full border border-amber-300/40 bg-amber-300/10 px-2.5 py-1 font-mono text-[9px] font-bold tracking-[0.18em] text-amber-200 sm:flex">
              <Radio className="h-3 w-3" /> RUO · v0.9
            </span>
          </div>
        </div>

        {/* mobile tab bar */}
        <nav className="flex gap-1 overflow-x-auto border-t border-white/5 px-3 py-1.5 lg:hidden" aria-label="Platform sections">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => goto(t.id)}
              className={cn(
                "shrink-0 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                tab === t.id ? "bg-emerald-400/10 text-emerald-300" : "text-muted-foreground",
              )}
            >
              {t.label}
            </button>
          ))}
        </nav>
      </header>

      <div ref={topRef} />

      {/* ---------- CONTENT ---------- */}
      <main className="flex-1">
        <motion.div key={tab} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
          {tab === "overview" && <Overview onEnterDemo={enterDemo} />}
          {tab === "pipeline" && <PipelineDemo />}
          {tab === "platform" && <PlatformTab />}
          {tab === "compliance" && <ComplianceTab />}
          {tab === "security" && <SecurityTab />}
        </motion.div>
      </main>

      {/* ---------- STICKY FOOTER ---------- */}
      <footer className="mt-auto border-t border-white/5 bg-black/30 pb-[env(safe-area-inset-bottom)]">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
          <div className="flex items-center gap-2">
            <HeartPulse className="h-4 w-4 text-emerald-400/80" />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              ORACLE advises — physicians decide
            </span>
          </div>
          <p className="max-w-xl text-[10px] leading-relaxed text-muted-foreground/70">
            Research Use Only. Not a medical device. Not FDA-cleared, not CE-marked. Outputs are advisory analytics for
            qualified-researcher review; no autonomous treatment logic exists by design. Measured claims trace to
            github.com/Dalfino/HeartOracle (ORACLE-P8T3).
          </p>
        </div>
      </footer>
    </div>
  );
}
