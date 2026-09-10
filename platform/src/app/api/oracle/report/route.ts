import { NextRequest, NextResponse } from "next/server";
import ZAI from "z-ai-web-dev-sdk";
import { runPipeline } from "@/lib/engine/geometry";
import { auditGate5ReportGrounding } from "@/lib/engine/gates";
import { KB } from "@/lib/data/kb";

export const runtime = "nodejs";
export const maxDuration = 300;

const SYSTEM_PROMPT = `You are ORACLE's report composer for a Research-Use-Only cardiac MRI quantification pipeline.
Rules you MUST follow:
1. Compose a concise structured clinical-style report (max ~350 words) using ONLY the metrics provided in the user message. Never invent other numbers.
2. Cite the provided guideline excerpts inline with [1]..[N] markers where relevant.
3. Use these exact section headers: ## Findings, ## Quantification, ## Interpretation Context, ## Limitations.
4. In Limitations, state that this is a Research-Use-Only advisory output, not a medical device, and that interpretation belongs to a qualified physician.
5. Tone: neutral, factual, no treatment recommendations.`;

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json().catch(() => ({}))) as { phenotypeId?: string; seed?: number };
    const phenotypeId = typeof body.phenotypeId === "string" ? body.phenotypeId : "normal";
    const seed = typeof body.seed === "number" && Number.isFinite(body.seed) ? body.seed : 7;

    // Rebuild the run server-side so the report can only use pipeline-computed values.
    const run = runPipeline(phenotypeId, seed);

    const kbBlock = KB.map((c) => `[${c.id}] ${c.source} — "${c.title}": ${c.text}`).join("\n\n");

    const userPrompt = `Pipeline-computed metrics (authoritative; do not alter):
- Phenotype: ${run.phenotype.label} (${run.phenotype.description})
- Heart rate: ${run.phenotype.hr} bpm
- EDV: ${run.edvMl} mL
- ESV: ${run.esvMl} mL
- Stroke volume: ${run.strokeVolumeMl} mL
- Ejection fraction: ${run.efPct}% (${run.efClass})
- Method: Simpson's rule disk summation over ${run.nFrames} cine frames
- Audit gates G1–G4: all executed

Guideline knowledge base (cite with [id]):
${kbBlock}

Compose the report now.`;

    const zai = await ZAI.create();
    const completion = await zai.chat.completions.create({
      messages: [
        { role: "assistant", content: SYSTEM_PROMPT },
        { role: "user", content: userPrompt },
      ],
      thinking: { type: "disabled" },
    });

    const report = completion.choices[0]?.message?.content ?? "";
    if (!report.trim()) {
      return NextResponse.json({ ok: false, error: "empty completion" }, { status: 502 });
    }

    const gate5 = auditGate5ReportGrounding(report, run, KB.length);

    return NextResponse.json({
      ok: true,
      report,
      gate5,
      metrics: {
        edvMl: run.edvMl,
        esvMl: run.esvMl,
        strokeVolumeMl: run.strokeVolumeMl,
        efPct: run.efPct,
        efClass: run.efClass,
      },
      citations: KB.map((c) => ({ id: c.id, source: c.source, title: c.title })),
    });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : "report failure" },
      { status: 500 },
    );
  }
}
