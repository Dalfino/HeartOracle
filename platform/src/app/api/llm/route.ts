import { NextRequest, NextResponse } from 'next/server';
import ZAI from 'z-ai-web-dev-sdk';

export const runtime = 'nodejs';
export const maxDuration = 300;

interface SidecarMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export async function POST(req: NextRequest) {
  try {
    const body = (await req.json()) as { messages?: SidecarMessage[] };
    const incoming = Array.isArray(body.messages) ? body.messages : [];
    if (incoming.length === 0) {
      return NextResponse.json({ ok: false, error: 'messages required' }, { status: 400 });
    }

    // z-ai SDK contract: system prompt goes with role 'assistant' as the leading message.
    const messages = incoming.map((m, i) => ({
      role: i === 0 && m.role === 'system' ? ('assistant' as const) : m.role,
      content: m.content,
    }));

    const zai = await ZAI.create();
    const completion = await zai.chat.completions.create({
      messages,
      thinking: { type: 'disabled' },
    });

    const text = completion.choices[0]?.message?.content ?? '';
    if (!text.trim()) {
      return NextResponse.json({ ok: false, error: 'empty completion' }, { status: 502 });
    }
    return NextResponse.json({ ok: true, text });
  } catch (err) {
    return NextResponse.json(
      { ok: false, error: err instanceof Error ? err.message : 'sidecar failure' },
      { status: 500 },
    );
  }
}
