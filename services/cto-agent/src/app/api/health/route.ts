import { NextResponse } from "next/server";
import { knowledgeBaseStats } from "@/lib/knowledge-base";
import { isGateEnabled } from "@/lib/passcode";

export const runtime = "nodejs";

export async function GET() {
  const stats = knowledgeBaseStats();
  return NextResponse.json({
    status: "ok",
    gateEnabled: isGateEnabled(),
    knowledgeBase: stats,
    model: process.env.CTO_AGENT_MODEL || "claude-sonnet-4-5",
    hasAnthropicKey: Boolean(process.env.ANTHROPIC_API_KEY),
    hasSupabaseKey: Boolean(
      process.env.SUPABASE_URL && process.env.SUPABASE_SERVICE_KEY,
    ),
  });
}
