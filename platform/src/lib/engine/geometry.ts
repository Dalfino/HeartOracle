/**
 * ORACLE quantification engine — demonstration build.
 *
 * HONESTY CONTRACT (mirrors docs/compliance/TRACEABILITY-MATRIX.md):
 *  - The GEOMETRY + VOLUMETRIC math below is the real pipeline math
 *    (Simpson's-rule disk summation over short-axis contours).
 *  - The INPUT is a simulated prolate-ellipsoid left ventricle with
 *    documented phenotypes. It is NOT a real patient scan.
 *  - The demo exists to make the pipeline's behaviour visible and auditable
 *    end-to-end while the 199 MB ensemble model is not resident in this
 *    environment. Measured real-scan results live separately in
 *    src/lib/data/eval-results.ts (provenance: HeartOracle P8T3).
 */

export interface PatientPhenotype {
  id: string;
  label: string;
  description: string;
  edvTarget: number; // mL
  esvTarget: number; // mL
  hr: number; // bpm
  notes: string;
}

export const PHENOTYPES: PatientPhenotype[] = [
  {
    id: "normal",
    label: "Normal Adult",
    description: "Healthy volunteer, sinus rhythm",
    edvTarget: 118,
    esvTarget: 47,
    hr: 62,
    notes: "Expected EF ≈ 60% (normal range 55–70%)",
  },
  {
    id: "hfref",
    label: "HFrEF Phenotype",
    description: "Dilated LV, reduced systolic function",
    edvTarget: 213,
    esvTarget: 152,
    hr: 84,
    notes: "Expected EF ≈ 28% — matches the measured real-patient sandbox run (EDV 213.0 / ESV 152.6 / EF 28.4%)",
  },
  {
    id: "athlete",
    label: "Athlete's Heart",
    description: "Eccentric hypertrophy, large stroke volume",
    edvTarget: 142,
    esvTarget: 52,
    hr: 50,
    notes: "Expected EF ≈ 63% with enlarged cavity",
  },
];

export interface FrameGeom {
  /** phase 0..1 across the cardiac cycle */
  t: number;
  /** LV endocardial radius (mm) at this frame (base radius; profile scales it) */
  lvR: number;
  /** myocardium shell thickness (mm) */
  myo: number;
  /** RV crescent extent factor (0..1 of LV radius) */
  rv: number;
  /** LV cavity volume at this frame (mL) via Simpson's rule */
  lvVolume: number;
}

export interface PipelineRun {
  runId: string;
  createdAt: string;
  phenotype: PatientPhenotype;
  nFrames: number;
  edvMl: number;
  esvMl: number;
  strokeVolumeMl: number;
  efPct: number;
  efClass: string;
  frames: FrameGeom[];
  contours: Record<string, number[][]>; // frameIndex -> 48 [x,y] pairs for LV cavity (short-axis, mm)
  volumeCurveMl: number[];
  warnings: string[];
}

const N_FRAMES = 25;
const CONTOUR_POINTS = 48;

function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Simpson's-rule disk summation — the real volumetric method of the pipeline. */
export function simpsonVolume(diskRadii: number[], sliceThickness: number): number {
  const n = diskRadii.length;
  if (n < 3 || n % 2 === 0) throw new Error("Simpson's rule requires an odd number of disks");
  let area = diskRadii[0] ** 2 + diskRadii[n - 1] ** 2;
  for (let i = 1; i < n - 1; i++) {
    area += diskRadii[i] ** 2 * (i % 2 === 1 ? 4 : 2);
  }
  area *= (sliceThickness / 3) * Math.PI;
  return area / 1000; // mm^3 -> mL
}

/**
 * Cardiac contraction curve: systole occupies ~40% of the cycle,
 * ejection runs 1 → 0 (full recoil to ESV), filling returns 0 → 1
 * (fast early filling + diastasis). c=0 at end-systole, c=1 at end-diastole,
 * so calibrated EDV/ESV targets are hit exactly.
 */
function contraction(t: number): number {
  const sys = 0.4;
  if (t <= sys) {
    const u = t / sys;
    const e = u * u * (3 - 2 * u); // smoothstep ejection
    return 1 - e; // 1 → 0
  }
  const u = (t - sys) / (1 - sys);
  const fill = 1 - Math.exp(-3.2 * u) * Math.cos(1.2 * u);
  return Math.min(1, Math.max(0, fill));
}

function buildDiskRadii(baseR: number, scale: number, nDisks = 21, noise: () => number): number[] {
  const radii: number[] = [];
  for (let i = 0; i < nDisks; i++) {
    const u = i / (nDisks - 1); // 0 = apex, 1 = base
    // truncated prolate ellipsoid profile
    const profile = Math.sin(Math.PI * (0.06 + 0.94 * u)) ** 0.72;
    radii.push(baseR * scale * profile * (1 + 0.015 * (noise() - 0.5)));
  }
  return radii;
}

function efClassOf(ef: number): string {
  if (ef >= 55) return "Normal / hyperdynamic range (≥55%)";
  if (ef >= 41) return "Mildly reduced (41–54%)";
  if (ef >= 31) return "Moderately reduced (31–40%) — HFrEF threshold zone";
  return "Severely reduced (≤30%)";
}

export function runPipeline(phenotypeId: string, seed = 7): PipelineRun {
  const phenotype = PHENOTYPES.find((p) => p.id === phenotypeId) ?? PHENOTYPES[0];
  const rng = mulberry32(seed + phenotype.edvTarget);
  const baseR = 28; // mm — typical LV short-axis radius at ED
  const sliceT = 8; // mm

  // Calibrate baseR scale so ED Simpson volume hits the phenotype target.
  // NOTE: volume scales with the SQUARE of the radius scale (area ∝ r²),
  // hence sqrt calibration.
  const edRadii = buildDiskRadii(baseR, 1, 21, rng);
  const edRaw = simpsonVolume(edRadii, sliceT);
  const scale = Math.sqrt(phenotype.edvTarget / edRaw);

  // ESV scale from the phenotype's EDV/ESV pair.
  const esScale = Math.sqrt(phenotype.esvTarget / edRaw);

  const frames: FrameGeom[] = [];
  const contours: Record<string, number[][]> = {};
  const volumeCurveMl: number[] = [];

  for (let f = 0; f < N_FRAMES; f++) {
    const t = f / (N_FRAMES - 1);
    const c = contraction(t);
    const s = esScale + (scale - esScale) * c;
    const radii = buildDiskRadii(baseR, s, 21, rng);
    const vol = simpsonVolume(radii, sliceT);
    volumeCurveMl.push(Math.round(vol * 10) / 10);
    frames.push({
      t,
      lvR: baseR * s,
      myo: 7.5 + 3.2 * (1 - s / scale), // wall thickens in systole
      rv: 0.92 * s,
      lvVolume: Math.round(vol * 10) / 10,
    });

    // Mid-ventricular short-axis contour (client renders polygon).
    const pts: number[][] = [];
    for (let k = 0; k < CONTOUR_POINTS; k++) {
      const a = (k / CONTOUR_POINTS) * Math.PI * 2;
      const wob = 1 + 0.035 * Math.sin(3 * a + f * 0.4) + 0.02 * (rng() - 0.5);
      pts.push([Math.round(Math.cos(a) * baseR * s * wob * 100) / 100, Math.round(Math.sin(a) * baseR * s * wob * 100) / 100]);
    }
    contours[String(f)] = pts;
  }

  const edvMl = Math.max(...volumeCurveMl);
  const esvMl = Math.min(...volumeCurveMl);
  const efPct = ((edvMl - esvMl) / edvMl) * 100;

  return {
    runId: `ORC-${Date.now().toString(36).toUpperCase()}-${seed}`,
    createdAt: new Date().toISOString(),
    phenotype,
    nFrames: N_FRAMES,
    edvMl: Math.round(edvMl * 10) / 10,
    esvMl: Math.round(esvMl * 10) / 10,
    strokeVolumeMl: Math.round((edvMl - esvMl) * 10) / 10,
    efPct: Math.round(efPct * 10) / 10,
    efClass: efClassOf(efPct),
    frames,
    contours,
    volumeCurveMl,
    warnings: [
      "DEMONSTRATION MODE: geometry engine is real (Simpson disk summation), input is a simulated phantom — not a patient scan.",
      "Measured real-scan results (ACDC holdout, 5-fold ensemble) are shown separately with provenance.",
    ],
  };
}
