"use client";

import { Cpu } from "lucide-react";
import { useState } from "react";

export default function PasscodeGate({
  onAccept,
}: {
  onAccept: (passcode: string) => void;
}) {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!value.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          sessionId: "gate-check",
          passcode: value.trim(),
          messages: [{ role: "user", content: "ping" }],
        }),
      });
      if (res.status === 401) {
        setError("That passcode doesn't match. Please try again.");
        setBusy(false);
        return;
      }
      onAccept(value.trim());
    } catch {
      setError("Could not reach the server. Please retry.");
      setBusy(false);
    }
  };

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{
        background: "linear-gradient(180deg, #07091a 0%, #0b1020 100%)",
      }}
    >
      <form
        onSubmit={submit}
        className="w-full max-w-md rounded-2xl p-8"
        style={{
          background: "var(--color-surface)",
          border: "1px solid var(--color-border-strong)",
          boxShadow: "0 16px 48px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center mb-5"
          style={{
            background: "rgba(51, 122, 255, 0.14)",
            border: "1px solid rgba(51, 122, 255, 0.32)",
          }}
        >
          <Cpu size={20} style={{ color: "var(--color-accent-2)" }} />
        </div>
        <h1
          style={{
            fontSize: "22px",
            fontWeight: 600,
            marginBottom: "6px",
            color: "var(--color-text-1)",
          }}
        >
          Aitoma Studio — Engineering Q&amp;A
        </h1>
        <p
          style={{
            color: "var(--color-text-2)",
            fontSize: "14px",
            marginBottom: "20px",
            lineHeight: 1.5,
          }}
        >
          Enter the access passcode shared by the Aitoma team.
        </p>
        <input
          type="text"
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Access passcode"
          disabled={busy}
          style={{
            width: "100%",
            padding: "12px 14px",
            borderRadius: "10px",
            background: "rgba(0, 0, 0, 0.32)",
            border: "1px solid var(--color-border-strong)",
            color: "var(--color-text-1)",
            fontSize: "15px",
          }}
        />
        {error && (
          <p
            style={{
              color: "var(--color-danger)",
              fontSize: "13px",
              marginTop: "10px",
            }}
          >
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={busy || !value.trim()}
          style={{
            width: "100%",
            marginTop: "16px",
            padding: "12px 16px",
            borderRadius: "10px",
            background:
              busy || !value.trim()
                ? "rgba(255, 255, 255, 0.08)"
                : "var(--color-accent)",
            color: busy || !value.trim() ? "var(--color-text-3)" : "white",
            border: "none",
            fontSize: "15px",
            fontWeight: 600,
          }}
        >
          {busy ? "Verifying…" : "Continue"}
        </button>
      </form>
    </div>
  );
}
