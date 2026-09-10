"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView, useSpring, useTransform } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/** Animated count-up number (springs when scrolled into view). */
export function CountUp({
  value,
  decimals = 1,
  suffix = "",
  className,
}: {
  value: number;
  decimals?: number;
  suffix?: string;
  className?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const spring = useSpring(0, { stiffness: 60, damping: 18 });
  const display = useTransform(spring, (v) => `${v.toFixed(decimals)}${suffix}`);
  const [, force] = useState(0);

  useEffect(() => {
    if (inView) spring.set(value);
  }, [inView, spring, value]);

  useEffect(() => display.on("change", () => force((n) => n + 1)), [display]);

  return (
    <span ref={ref} className={className}>
      {display.get()}
    </span>
  );
}

export type StatusKind = "pass" | "warn" | "fail" | "info" | "amber";

export function StatusBadge({ kind, children, className }: { kind: StatusKind; children: React.ReactNode; className?: string }) {
  const styles: Record<StatusKind, string> = {
    pass: "border-emerald-400/40 bg-emerald-400/10 text-emerald-300",
    warn: "border-amber-400/40 bg-amber-400/10 text-amber-300",
    fail: "border-rose-400/40 bg-rose-400/10 text-rose-300",
    info: "border-teal-400/30 bg-teal-400/10 text-teal-200",
    amber: "border-amber-300/50 bg-amber-300/10 text-amber-200",
  };
  return (
    <Badge variant="outline" className={cn("font-medium tracking-wide", styles[kind], className)}>
      {children}
    </Badge>
  );
}

export function SectionTitle({ eyebrow, title, sub }: { eyebrow: string; title: string; sub?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.5 }}
      className="mb-6"
    >
      <div className="text-[11px] font-mono uppercase tracking-[0.28em] text-emerald-400/80">{eyebrow}</div>
      <h2 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-3xl">{title}</h2>
      {sub ? <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground md:text-[15px]">{sub}</p> : null}
    </motion.div>
  );
}

export function GlassCard({ className, children }: { className?: string; children: React.ReactNode }) {
  return <div className={cn("rounded-2xl ho-glass p-5 md:p-6", className)}>{children}</div>;
}

export const fadeUp = {
  initial: { opacity: 0, y: 16 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-50px" },
  transition: { duration: 0.5 },
} as const;
