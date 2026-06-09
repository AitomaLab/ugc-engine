/**
 * Loads the Aitoma Studio diligence documents from the repo root and exposes
 * them as a single concatenated knowledge corpus that we pass to Claude as
 * part of the system prompt.
 *
 * Path resolution: this module is at services/cto-agent/src/lib/knowledge-base.ts
 * and the source documents live at the repo root, three levels up.
 */
import fs from "node:fs";
import path from "node:path";

/**
 * Locate the repo root reliably from inside Next.js server runtime.
 *
 * Strategy: walk up from process.cwd() until we find a directory containing
 * the CTO defense pack markdown. process.cwd() in `next dev` is
 * services/cto-agent so the repo root is two levels up; we still scan to
 * tolerate being run from a sub-directory.
 */
function findRepoRoot(): string {
  const sentinel = "Aitoma_Studio_Technical_Architecture_CTO_Defense.md";
  let dir = process.cwd();
  for (let i = 0; i < 6; i++) {
    if (fs.existsSync(path.join(dir, sentinel))) return dir;
    const parent = path.dirname(dir);
    if (parent === dir) break;
    dir = parent;
  }
  return process.cwd();
}

const REPO_ROOT = findRepoRoot();

const DOCS = [
  {
    label: "CTO Defense Pack (primary)",
    filename: "Aitoma_Studio_Technical_Architecture_CTO_Defense.md",
    priority: 1,
  },
  {
    label: "Executive Summary (tone reference)",
    filename: "Aitoma_Studio_Tech_Architecture_Exec_Summary.md",
    priority: 2,
  },
  {
    label: "AWS Migration Architecture (full detail)",
    filename: "Aitoma_Studio_AWS_Migration_Architecture.md",
    priority: 3,
  },
  {
    label: "AWS Migration One-Pager (concise reference)",
    filename: "Aitoma_Studio_AWS_Migration_OnePager.md",
    priority: 4,
  },
  {
    label:
      "Publish & Analytics Architecture (implementation reference: " +
      "Ayrshare publish flow, BrightData scraper, Gemini AI breakdowns, " +
      "agent memory feedback loop, full schema for analytics_posts / " +
      "social_posts / campaigns / agent_memories)",
    filename: "Aitoma_Studio_Publish_Analytics_Architecture.md",
    priority: 5,
  },
] as const;

interface LoadedDoc {
  label: string;
  filename: string;
  content: string;
  bytes: number;
}

let cache: { docs: LoadedDoc[]; corpus: string; loadedAt: number } | null =
  null;

export function loadKnowledgeBase(): {
  docs: LoadedDoc[];
  corpus: string;
} {
  if (cache) return { docs: cache.docs, corpus: cache.corpus };

  const docs: LoadedDoc[] = [];
  for (const d of DOCS) {
    const filePath = path.join(REPO_ROOT, d.filename);
    try {
      const content = fs.readFileSync(filePath, "utf8");
      docs.push({
        label: d.label,
        filename: d.filename,
        content,
        bytes: Buffer.byteLength(content, "utf8"),
      });
    } catch (err) {
      console.warn(
        `[knowledge-base] Could not load ${d.filename}: ${
          (err as Error).message
        }`,
      );
    }
  }

  const corpus = docs
    .map(
      (d) =>
        `=========================================================================\n` +
        `DOCUMENT: ${d.filename}\n` +
        `LABEL: ${d.label}\n` +
        `=========================================================================\n\n` +
        d.content,
    )
    .join("\n\n");

  cache = { docs, corpus, loadedAt: Date.now() };
  return { docs, corpus };
}

export function knowledgeBaseStats() {
  const { docs } = loadKnowledgeBase();
  const totalBytes = docs.reduce((a, d) => a + d.bytes, 0);
  return {
    documentCount: docs.length,
    documents: docs.map((d) => ({ filename: d.filename, bytes: d.bytes })),
    totalBytes,
    estimatedTokens: Math.round(totalBytes / 4),
  };
}
