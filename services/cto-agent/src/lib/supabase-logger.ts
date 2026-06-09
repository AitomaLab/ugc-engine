/**
 * Best-effort Supabase logger for conversations and messages.
 *
 * Writes are non-blocking from the chat API path: if the Supabase write
 * fails for any reason, the chat request still succeeds. We never let a
 * logging failure break the user experience.
 */
import { createClient, SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

function getClient(): SupabaseClient | null {
  if (client) return client;
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_SERVICE_KEY;
  if (!url || !key) {
    console.warn(
      "[cto-agent] SUPABASE_URL or SUPABASE_SERVICE_KEY missing; logging disabled",
    );
    return null;
  }
  client = createClient(url, key, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  return client;
}

export interface ConversationStart {
  sessionId: string;
  visitorLabel: string | null;
  userAgent: string | null;
  ipHash: string | null;
}

export interface MessageLog {
  conversationId: string;
  role: "user" | "assistant";
  content: string;
  tokensIn?: number;
  tokensOut?: number;
  latencyMs?: number;
}

export async function ensureConversation(
  start: ConversationStart,
): Promise<string | null> {
  const sb = getClient();
  if (!sb) return null;

  const { data: existing } = await sb
    .from("cto_agent_conversations")
    .select("id")
    .eq("session_id", start.sessionId)
    .maybeSingle();

  if (existing?.id) return existing.id as string;

  const { data, error } = await sb
    .from("cto_agent_conversations")
    .insert({
      session_id: start.sessionId,
      visitor_label: start.visitorLabel,
      user_agent: start.userAgent,
      ip_hash: start.ipHash,
    })
    .select("id")
    .single();

  if (error) {
    console.warn("[cto-agent] failed to create conversation:", error.message);
    return null;
  }
  return data.id as string;
}

export async function logMessage(msg: MessageLog): Promise<void> {
  const sb = getClient();
  if (!sb) return;
  const { error } = await sb.from("cto_agent_messages").insert({
    conversation_id: msg.conversationId,
    role: msg.role,
    content: msg.content,
    tokens_in: msg.tokensIn ?? null,
    tokens_out: msg.tokensOut ?? null,
    latency_ms: msg.latencyMs ?? null,
  });
  if (error) {
    console.warn("[cto-agent] failed to log message:", error.message);
  }
}
