import { NextRequest } from "next/server";
import Anthropic from "@anthropic-ai/sdk";
import crypto from "node:crypto";
import { buildSystemPrompt } from "@/lib/persona";
import {
  ensureConversation,
  logMessage,
} from "@/lib/supabase-logger";
import { validatePasscode } from "@/lib/passcode";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";
export const maxDuration = 300;

interface ChatRequest {
  sessionId: string;
  passcode?: string | null;
  messages: Array<{ role: "user" | "assistant"; content: string }>;
}

function hashIp(ip: string | null): string | null {
  if (!ip) return null;
  return crypto.createHash("sha256").update(ip).digest("hex").slice(0, 16);
}

function sseEvent(event: string, data: Record<string, unknown>): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function POST(req: NextRequest) {
  const startedAt = Date.now();
  let body: ChatRequest;
  try {
    body = (await req.json()) as ChatRequest;
  } catch {
    return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
      status: 400,
      headers: { "content-type": "application/json" },
    });
  }

  const visitorLabel = validatePasscode(body.passcode ?? null);
  if (!visitorLabel) {
    return new Response(
      JSON.stringify({ error: "Invalid or missing passcode" }),
      { status: 401, headers: { "content-type": "application/json" } },
    );
  }

  if (!body.sessionId || !Array.isArray(body.messages) || body.messages.length === 0) {
    return new Response(
      JSON.stringify({ error: "Missing sessionId or messages" }),
      { status: 400, headers: { "content-type": "application/json" } },
    );
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return new Response(
      JSON.stringify({ error: "ANTHROPIC_API_KEY is not configured" }),
      { status: 500, headers: { "content-type": "application/json" } },
    );
  }

  const model = process.env.CTO_AGENT_MODEL || "claude-sonnet-4-5";
  const maxTokens = Number(process.env.CTO_AGENT_MAX_TOKENS || "4096");
  const systemPrompt = buildSystemPrompt();

  const userAgent = req.headers.get("user-agent");
  const forwardedFor = req.headers.get("x-forwarded-for");
  const ip = forwardedFor?.split(",")[0]?.trim() || null;

  const conversationId = await ensureConversation({
    sessionId: body.sessionId,
    visitorLabel,
    userAgent,
    ipHash: hashIp(ip),
  });

  const lastUser = [...body.messages].reverse().find((m) => m.role === "user");
  if (lastUser && conversationId) {
    await logMessage({
      conversationId,
      role: "user",
      content: lastUser.content,
    });
  }

  const anthropic = new Anthropic({ apiKey });

  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    async start(controller) {
      let assistantText = "";
      let tokensIn = 0;
      let tokensOut = 0;

      try {
        const upstream = await anthropic.messages.stream({
          model,
          max_tokens: maxTokens,
          system: systemPrompt,
          messages: body.messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
        });

        for await (const event of upstream) {
          if (event.type === "content_block_delta") {
            const delta = event.delta;
            if (delta.type === "text_delta") {
              assistantText += delta.text;
              controller.enqueue(
                encoder.encode(sseEvent("delta", { text: delta.text })),
              );
            }
          } else if (event.type === "message_delta") {
            const usage = event.usage;
            if (usage) {
              tokensOut = usage.output_tokens ?? tokensOut;
            }
          } else if (event.type === "message_start") {
            const usage = event.message.usage;
            if (usage) {
              tokensIn = usage.input_tokens ?? tokensIn;
            }
          }
        }

        const finalMessage = await upstream.finalMessage();
        if (finalMessage.usage) {
          tokensIn = finalMessage.usage.input_tokens;
          tokensOut = finalMessage.usage.output_tokens;
        }

        const latencyMs = Date.now() - startedAt;

        controller.enqueue(
          encoder.encode(
            sseEvent("done", {
              tokensIn,
              tokensOut,
              latencyMs,
            }),
          ),
        );

        if (conversationId) {
          await logMessage({
            conversationId,
            role: "assistant",
            content: assistantText,
            tokensIn,
            tokensOut,
            latencyMs,
          });
        }
      } catch (err) {
        const message = (err as Error).message || "Unknown error";
        console.error("[cto-agent] stream failed:", message);
        controller.enqueue(
          encoder.encode(sseEvent("error", { message })),
        );
      } finally {
        controller.close();
      }
    },
  });

  return new Response(stream, {
    headers: {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
      connection: "keep-alive",
    },
  });
}
