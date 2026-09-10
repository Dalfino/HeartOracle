import { NextRequest, NextResponse } from "next/server";
import { runPipeline } from "@/lib/engine/geometry";
import { runAllGates } from "@/lib/engine/gates";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json().catch(() => ({}))) as { phenotypeId?: string; seed?: number };
    const phenotypeId = typeof body.phenotypeId === "string" ? body.phenotypeId : "normal";
    const seed = typeof body.seed === "number" && Number.isFinite(body.seed) ? body.seed : 7;

    const run = runPipeline(phenotypeId, seed);
    const gateReport = runAllGates(run);

    return NextResponse.json({
      ok: true,
      run,
      gates: gateReport.gates,
      auditTrail: gateReport.auditTrail,
      overall: gateReport.overall,
      overallHash: gateReport.overallHash,
    });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "pipeline failure" },
      { status: 500 },
    );
  }
}
