"use client";

import { ArrowUpRight } from "lucide-react";

const STARTERS: { category: string; question: string }[] = [
  {
    category: "Architecture",
    question:
      "Walk me through the end-to-end topology of the system and where each service lives.",
  },
  {
    category: "Resilience",
    question:
      "How does the three-tier worker dispatch work in practice, and what happens if Modal goes down?",
  },
  {
    category: "Scaling",
    question:
      "At what point does the current architecture break, and what's the path to 100k concurrent users?",
  },
  {
    category: "AI moat",
    question:
      "What's the actual defensibility of the AI moat — be specific about the layers and switching costs.",
  },
  {
    category: "Model strategy",
    question:
      "Why model-agnostic? Doesn't that mean you have no real edge over any well-funded competitor?",
  },
  {
    category: "AWS migration",
    question:
      "Why migrate to AWS now and what does the phased plan look like? What are the risks?",
  },
  {
    category: "Tech debt",
    question:
      "What's the biggest piece of architectural debt today, and how does it impact your roadmap?",
  },
  {
    category: "Roadmap",
    question:
      "What ships in the next two quarters and which items materially deepen the moat?",
  },
];

export default function SuggestedQuestions({
  onPick,
}: {
  onPick: (q: string) => void;
}) {
  return (
    <div
      className="grid"
      style={{
        gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
        gap: "10px",
      }}
    >
      {STARTERS.map((s) => (
        <button
          key={s.question}
          onClick={() => onPick(s.question)}
          className="text-left rounded-xl group"
          style={{
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            padding: "13px 14px",
            transition: "all 0.15s ease",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--color-surface-2)";
            e.currentTarget.style.borderColor = "var(--color-border-strong)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "var(--color-surface)";
            e.currentTarget.style.borderColor = "var(--color-border)";
          }}
        >
          <div
            className="flex items-center justify-between mb-1.5"
            style={{
              color: "var(--color-accent-2)",
              fontSize: "11px",
              letterSpacing: "0.04em",
              textTransform: "uppercase",
              fontWeight: 600,
            }}
          >
            <span>{s.category}</span>
            <ArrowUpRight
              size={13}
              style={{
                opacity: 0.6,
                transition: "opacity 0.15s",
              }}
            />
          </div>
          <div
            style={{
              color: "var(--color-text-1)",
              fontSize: "14px",
              lineHeight: "1.45",
            }}
          >
            {s.question}
          </div>
        </button>
      ))}
    </div>
  );
}
