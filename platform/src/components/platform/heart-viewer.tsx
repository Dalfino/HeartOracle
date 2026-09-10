"use client";

import { useMemo } from "react";
import type { FrameGeom } from "@/lib/engine/geometry";

/**
 * Short-axis cardiac viewer: renders LV cavity (from engine contours),
 * myocardium shell, RV crescent. Pure SVG driven by pipeline data.
 */
export function HeartViewer({
  frames,
  contours,
  frameIndex,
  showScan = true,
  className,
}: {
  frames: FrameGeom[];
  contours: Record<string, number[][]>;
  frameIndex: number;
  showScan?: boolean;
  className?: string;
}) {
  const frame = frames[Math.min(frameIndex, frames.length - 1)];
  const pts = contours[String(Math.min(frameIndex, frames.length - 1))] ?? [];

  const { cavityPath, myoPath, rvPath } = useMemo(() => {
    if (!pts.length || !frame) return { cavityPath: "", myoPath: "", rvPath: "" };
    const toStr = (p: number[][]) => p.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ") + " Z";
    const outer = pts.map(([x, y]) => {
      const r = Math.hypot(x, y) || 1;
      const s = (r + frame.myo) / r;
      return [x * s, y * s];
    });
    // RV crescent: sector arc hugging the septum (left of screen = patient right)
    const rIn = frame.lvR * 1.02;
    const rOut = frame.lvR + frame.myo * 0.9 + frame.rv * 6;
    const a0 = (-152 * Math.PI) / 180;
    const a1 = (18 * Math.PI) / 180;
    const cx = -6;
    const p0in = [cx + rIn * Math.cos(a0), rIn * Math.sin(a0)];
    const p1in = [cx + rIn * Math.cos(a1), rIn * Math.sin(a1)];
    const p1out = [cx + rOut * Math.cos(a1), rOut * Math.sin(a1)];
    const p0out = [cx + rOut * Math.cos(a0), rOut * Math.sin(a0)];
    const rv = `M${p0in[0].toFixed(1)},${p0in[1].toFixed(1)} L${p0out[0].toFixed(1)},${p0out[1].toFixed(1)} A${rOut.toFixed(1)},${rOut.toFixed(1)} 0 0 0 ${p1out[0].toFixed(1)},${p1out[1].toFixed(1)} L${p1in[0].toFixed(1)},${p1in[1].toFixed(1)} A${rIn.toFixed(1)},${rIn.toFixed(1)} 0 0 1 ${p0in[0].toFixed(1)},${p0in[1].toFixed(1)} Z`;
    return { cavityPath: toStr(pts), myoPath: toStr(outer), rvPath: rv };
  }, [pts, frame]);

  return (
    <div className={`relative overflow-hidden rounded-xl border border-white/10 bg-black/50 ho-grid-bg ${className ?? ""}`}>
      {showScan ? <div className="ho-scanline" /> : null}
      <svg viewBox="-62 -62 124 124" className="h-full w-full" role="img" aria-label="Short-axis cardiac segmentation view">
        <defs>
          <radialGradient id="hoCavity" cx="50%" cy="45%" r="65%">
            <stop offset="0%" stopColor="oklch(0.85 0.14 165 / 0.95)" />
            <stop offset="100%" stopColor="oklch(0.7 0.13 172 / 0.55)" />
          </radialGradient>
          <linearGradient id="hoMyo" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="oklch(0.62 0.16 25 / 0.85)" />
            <stop offset="100%" stopColor="oklch(0.5 0.12 20 / 0.7)" />
          </linearGradient>
        </defs>
        {/* epicardial halo */}
        <circle cx="0" cy="0" r="52" fill="none" stroke="oklch(1 0 0 / 0.05)" strokeWidth="0.6" />
        <circle cx="0" cy="0" r="58" fill="none" stroke="oklch(1 0 0 / 0.03)" strokeWidth="0.6" />
        {/* RV crescent */}
        {rvPath ? <path d={rvPath} fill="oklch(0.72 0.13 300 / 0.42)" stroke="oklch(0.72 0.13 300 / 0.55)" strokeWidth="0.7" /> : null}
        {/* myocardium */}
        {myoPath ? <path d={myoPath} fill="url(#hoMyo)" stroke="oklch(0.66 0.19 25 / 0.9)" strokeWidth="0.8" /> : null}
        {/* LV cavity */}
        {cavityPath ? (
          <g className="transition-all duration-100">
            <path d={cavityPath} fill="url(#hoCavity)" stroke="oklch(0.9 0.1 165 / 0.95)" strokeWidth="0.8" />
          </g>
        ) : null}
        {/* crosshair ticks */}
        {[0, 90, 180, 270].map((a) => {
          const rad = (a * Math.PI) / 180;
          return (
            <line
              key={a}
              x1={56 * Math.cos(rad)}
              y1={56 * Math.sin(rad)}
              x2={60 * Math.cos(rad)}
              y2={60 * Math.sin(rad)}
              stroke="oklch(1 0 0 / 0.25)"
              strokeWidth="0.8"
            />
          );
        })}
      </svg>
      <div className="absolute bottom-2 right-3 font-mono text-[10px] uppercase tracking-widest text-emerald-300/70">
        SA-mid · frame {Math.min(frameIndex, frames.length - 1) + 1}/{frames.length}
      </div>
    </div>
  );
}
