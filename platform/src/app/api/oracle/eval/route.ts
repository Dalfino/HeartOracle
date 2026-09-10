import { NextResponse } from "next/server";
import { ENSEMBLE, EF_MEASURED, SEG_GATES, EVAL_PROVENANCE } from "@/lib/data/eval-results";

export const runtime = "nodejs";

export async function GET() {
  return NextResponse.json({
    ok: true,
    provenance: EVAL_PROVENANCE,
    ensemble: ENSEMBLE,
    ef: EF_MEASURED,
    gates: SEG_GATES,
  });
}
