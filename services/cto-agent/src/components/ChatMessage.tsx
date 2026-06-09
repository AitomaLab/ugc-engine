"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Cpu, User } from "lucide-react";

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

export default function ChatMessage({ message }: { message: Message }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex gap-3 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{
            background: "rgba(51, 122, 255, 0.14)",
            border: "1px solid rgba(51, 122, 255, 0.32)",
          }}
        >
          <Cpu size={15} style={{ color: "var(--color-accent-2)" }} />
        </div>
      )}
      <div
        className={
          isUser
            ? "max-w-[80%] rounded-2xl px-4 py-2.5 text-[15px]"
            : "max-w-[85%] rounded-2xl px-4 py-3"
        }
        style={
          isUser
            ? {
                background: "var(--color-accent)",
                color: "white",
              }
            : {
                background: "var(--color-surface)",
                border: "1px solid var(--color-border)",
              }
        }
      >
        {isUser ? (
          <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{message.content}</p>
        ) : (
          <div className="prose-msg">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || ""}
            </ReactMarkdown>
            {message.streaming && <span className="stream-cursor" />}
          </div>
        )}
      </div>
      {isUser && (
        <div
          className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
          style={{
            background: "rgba(255, 255, 255, 0.06)",
            border: "1px solid var(--color-border)",
          }}
        >
          <User size={15} style={{ color: "var(--color-text-2)" }} />
        </div>
      )}
    </div>
  );
}
