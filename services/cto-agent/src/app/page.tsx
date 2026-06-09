"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ChatMessage, { Message } from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import SuggestedQuestions from "@/components/SuggestedQuestions";
import PasscodeGate from "@/components/PasscodeGate";
import { Cpu, Download, RefreshCw } from "lucide-react";

interface HealthInfo {
  gateEnabled: boolean;
  model: string;
  knowledgeBase: {
    documentCount: number;
    totalBytes: number;
    estimatedTokens: number;
  };
}

function randomId(): string {
  return crypto.randomUUID
    ? crypto.randomUUID()
    : `id-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

export default function StudioCTOPage() {
  const [health, setHealth] = useState<HealthInfo | null>(null);
  const [passcode, setPasscode] = useState<string | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [sessionId] = useState(() => randomId());
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then((data: HealthInfo) => {
        setHealth(data);
        if (!data.gateEnabled) setPasscode("open-access");
        setAuthChecked(true);
      })
      .catch(() => setAuthChecked(true));
  }, []);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
  }, [messages]);

  const sendMessage = useCallback(
    async (text: string) => {
      const trimmed = text.trim();
      if (!trimmed || isStreaming || !passcode) return;

      const userMsg: Message = {
        id: randomId(),
        role: "user",
        content: trimmed,
      };
      const assistantId = randomId();
      const assistantSeed: Message = {
        id: assistantId,
        role: "assistant",
        content: "",
        streaming: true,
      };

      const nextMessages = [...messages, userMsg];
      setMessages([...nextMessages, assistantSeed]);
      setInput("");
      setIsStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "content-type": "application/json" },
          body: JSON.stringify({
            sessionId,
            passcode,
            messages: nextMessages.map((m) => ({
              role: m.role,
              content: m.content,
            })),
          }),
          signal: controller.signal,
        });

        if (!res.ok || !res.body) {
          const errText = await res.text().catch(() => "");
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content:
                      "_Sorry — the engineering agent couldn't respond. " +
                      (errText || `Status ${res.status}.`) +
                      "_",
                    streaming: false,
                  }
                : m,
            ),
          );
          setIsStreaming(false);
          return;
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { value, done } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const events = buffer.split("\n\n");
          buffer = events.pop() || "";

          for (const evt of events) {
            const lines = evt.split("\n");
            let eventName = "message";
            let dataLine = "";
            for (const ln of lines) {
              if (ln.startsWith("event: ")) eventName = ln.slice(7).trim();
              else if (ln.startsWith("data: ")) dataLine = ln.slice(6);
            }
            if (!dataLine) continue;
            try {
              const data = JSON.parse(dataLine);
              if (eventName === "delta" && typeof data.text === "string") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? { ...m, content: m.content + data.text }
                      : m,
                  ),
                );
              } else if (eventName === "done") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId ? { ...m, streaming: false } : m,
                  ),
                );
              } else if (eventName === "error") {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          content:
                            m.content +
                            "\n\n_Stream error: " +
                            (data.message || "unknown") +
                            "_",
                          streaming: false,
                        }
                      : m,
                  ),
                );
              }
            } catch {
              // ignore parse errors on partial buffers
            }
          }
        }
      } catch (err) {
        const aborted = (err as Error).name === "AbortError";
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: aborted
                    ? m.content + "\n\n_Stopped._"
                    : m.content +
                      "\n\n_Connection error: " +
                      (err as Error).message +
                      "_",
                  streaming: false,
                }
              : m,
          ),
        );
      } finally {
        setIsStreaming(false);
        abortRef.current = null;
      }
    },
    [isStreaming, messages, passcode, sessionId],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const reset = useCallback(() => {
    if (isStreaming) abortRef.current?.abort();
    setMessages([]);
    setInput("");
  }, [isStreaming]);

  const downloadTranscript = useCallback(() => {
    const lines: string[] = [
      "# Aitoma Studio — Engineering Q&A Transcript",
      `Session ${sessionId}`,
      `Captured ${new Date().toISOString()}`,
      "",
    ];
    for (const m of messages) {
      lines.push(`## ${m.role === "user" ? "Analyst" : "Aitoma Engineering"}`);
      lines.push("");
      lines.push(m.content);
      lines.push("");
    }
    const blob = new Blob([lines.join("\n")], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `aitoma-engineering-qa-${Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, [messages, sessionId]);

  const headerMeta = useMemo(() => {
    if (!health) return null;
    const { knowledgeBase: kb, model } = health;
    return (
      <div
        className="flex items-center gap-3"
        style={{
          fontSize: "11px",
          color: "var(--color-text-3)",
          letterSpacing: "0.02em",
        }}
      >
        <span>{model}</span>
        <span style={{ opacity: 0.4 }}>·</span>
        <span>
          {kb.documentCount} docs · ~
          {Math.round(kb.estimatedTokens / 1000)}k tokens grounded
        </span>
      </div>
    );
  }, [health]);

  if (!authChecked) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ color: "var(--color-text-3)" }}
      >
        Loading…
      </div>
    );
  }

  if (!passcode) {
    return <PasscodeGate onAccept={(p) => setPasscode(p)} />;
  }

  return (
    <div
      className="flex flex-col"
      style={{
        maxWidth: "880px",
        margin: "0 auto",
        padding: "0 16px",
        height: "100dvh",
      }}
    >
      {/* Header — non-shrinking */}
      <header
        className="flex items-center justify-between py-5"
        style={{
          borderBottom: "1px solid var(--color-border)",
          flexShrink: 0,
        }}
      >
        <div className="flex items-center gap-3">
          <div
            className="w-9 h-9 rounded-xl flex items-center justify-center"
            style={{
              background: "rgba(51, 122, 255, 0.14)",
              border: "1px solid rgba(51, 122, 255, 0.32)",
            }}
          >
            <Cpu size={17} style={{ color: "var(--color-accent-2)" }} />
          </div>
          <div>
            <div
              style={{
                fontSize: "15px",
                fontWeight: 600,
                color: "var(--color-text-1)",
                lineHeight: 1.2,
              }}
            >
              Aitoma Studio — Engineering Q&amp;A
            </div>
            {headerMeta}
          </div>
        </div>
        <div className="flex items-center gap-2">
          {messages.length > 0 && (
            <>
              <button
                onClick={downloadTranscript}
                title="Download transcript"
                aria-label="Download transcript"
                className="flex items-center gap-1.5 rounded-lg"
                style={{
                  padding: "7px 11px",
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-2)",
                  fontSize: "12px",
                }}
              >
                <Download size={13} />
                <span>Transcript</span>
              </button>
              <button
                onClick={reset}
                title="New conversation"
                aria-label="New conversation"
                className="flex items-center gap-1.5 rounded-lg"
                style={{
                  padding: "7px 11px",
                  background: "var(--color-surface)",
                  border: "1px solid var(--color-border)",
                  color: "var(--color-text-2)",
                  fontSize: "12px",
                }}
              >
                <RefreshCw size={13} />
                <span>New</span>
              </button>
            </>
          )}
        </div>
      </header>

      {/* Conversation — only this area scrolls */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto"
        style={{ padding: "28px 0 32px 0", minHeight: 0 }}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col gap-7">
            <div>
              <h1
                style={{
                  fontSize: "26px",
                  fontWeight: 600,
                  letterSpacing: "-0.01em",
                  color: "var(--color-text-1)",
                  marginBottom: "8px",
                }}
              >
                Talk to Aitoma's engineering lead.
              </h1>
              <p
                style={{
                  color: "var(--color-text-2)",
                  fontSize: "15px",
                  lineHeight: 1.55,
                  maxWidth: "640px",
                }}
              >
                You can ask anything about the architecture, scalability,
                AI moat, AWS migration, roadmap, security posture, or
                engineering tradeoffs. Every answer is grounded in our
                internal diligence documents and codebase.
              </p>
            </div>
            <div>
              <div
                style={{
                  fontSize: "12px",
                  letterSpacing: "0.04em",
                  textTransform: "uppercase",
                  color: "var(--color-text-3)",
                  marginBottom: "12px",
                  fontWeight: 600,
                }}
              >
                Suggested starting points
              </div>
              <SuggestedQuestions onPick={(q) => sendMessage(q)} />
            </div>
            <div
              style={{
                fontSize: "12px",
                color: "var(--color-text-3)",
                borderTop: "1px solid var(--color-border)",
                paddingTop: "14px",
                lineHeight: 1.5,
              }}
            >
              This is an AI agent set up by the Aitoma team to handle
              technical Q&amp;A in between live sessions. It is grounded in
              the company's engineering documents and code. Anything it
              tells you can be confirmed live with the founders.
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-5">
            {messages.map((m) => (
              <ChatMessage key={m.id} message={m} />
            ))}
          </div>
        )}
      </div>

      {/* Input — always pinned to bottom of viewport */}
      <div
        style={{
          padding: "12px 0 20px 0",
          flexShrink: 0,
          position: "relative",
          background:
            "linear-gradient(180deg, transparent 0%, rgba(7, 9, 26, 0.85) 18%, #07091a 35%)",
        }}
      >
        <ChatInput
          value={input}
          onChange={setInput}
          onSubmit={() => sendMessage(input)}
          onStop={stop}
          isStreaming={isStreaming}
        />
        <div
          style={{
            fontSize: "11px",
            color: "var(--color-text-3)",
            marginTop: "8px",
            textAlign: "center",
          }}
        >
          Enter to send · Shift+Enter for newline
        </div>
      </div>
    </div>
  );
}
