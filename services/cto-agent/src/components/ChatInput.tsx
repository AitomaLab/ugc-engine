"use client";

import { ArrowUp, Square } from "lucide-react";
import { useEffect, useRef } from "react";

interface ChatInputProps {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  onStop: () => void;
  isStreaming: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export default function ChatInput({
  value,
  onChange,
  onSubmit,
  onStop,
  isStreaming,
  disabled,
  placeholder = "Ask anything about the architecture, moat, scaling, or roadmap…",
}: ChatInputProps) {
  const ref = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "0px";
    const next = Math.min(el.scrollHeight, 240);
    el.style.height = next + "px";
  }, [value]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      if (!isStreaming && value.trim().length > 0) onSubmit();
    }
  };

  return (
    <div
      className="relative rounded-2xl"
      style={{
        background: "var(--color-surface)",
        border: "1px solid var(--color-border-strong)",
        boxShadow: "0 8px 32px rgba(0, 0, 0, 0.35)",
      }}
    >
      <textarea
        ref={ref}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled}
        rows={1}
        style={{
          width: "100%",
          padding: "16px 56px 16px 18px",
          background: "transparent",
          border: "none",
          color: "var(--color-text-1)",
          fontSize: "15px",
          lineHeight: "1.5",
          resize: "none",
          minHeight: "56px",
          maxHeight: "240px",
        }}
      />
      <button
        onClick={isStreaming ? onStop : onSubmit}
        disabled={!isStreaming && value.trim().length === 0}
        aria-label={isStreaming ? "Stop" : "Send"}
        className="absolute"
        style={{
          right: "10px",
          bottom: "10px",
          width: "36px",
          height: "36px",
          borderRadius: "50%",
          border: "none",
          background: isStreaming
            ? "rgba(239, 68, 68, 0.18)"
            : value.trim().length > 0
            ? "var(--color-accent)"
            : "rgba(255, 255, 255, 0.08)",
          color:
            isStreaming || value.trim().length > 0
              ? "white"
              : "var(--color-text-3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transition: "background 0.15s ease",
        }}
      >
        {isStreaming ? <Square size={14} fill="currentColor" /> : <ArrowUp size={18} />}
      </button>
    </div>
  );
}
