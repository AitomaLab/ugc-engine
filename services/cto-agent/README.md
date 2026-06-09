# CTO Agent — Aitoma Studio Engineering Q&A

A standalone web app that lets external technical analysts (typically VC
due-diligence analysts) chat with a virtual version of Aitoma Studio's
engineering lead. Every answer is grounded in the company's diligence
documents and codebase patterns.

## Why this exists

We don't yet have a full-time CTO, and VC technical analysts increasingly
want deep technical Q&A access between formal sessions with the
founders. This agent gives them a high-fidelity asynchronous channel for
those questions while keeping the founders' time focused on the live
conversations that matter.

## How it works

```
Browser ──► Next.js page (chat UI)
              │
              │  POST /api/chat (streaming SSE)
              ▼
          Server route
              │
              ├─ Loads diligence documents from the repo root
              │  (CTO Defense Pack, Exec Summary, AWS Migration docs)
              │
              ├─ Builds the system prompt = CTO persona + full document corpus
              │
              ├─ Calls Anthropic Claude Sonnet 4.6 with streaming
              │
              └─ Logs every Q&A pair to Supabase
                 (cto_agent_conversations + cto_agent_messages)
```

The model never sees production secrets or customer data — it only sees
the public-facing diligence documents and is instructed to defer hard
questions to the founders.

## Local development

### 1. Install dependencies

```bash
cd services/cto-agent
pnpm install
```

### 2. Configure environment

```bash
cp .env.local.example .env.local
```

Then fill in:

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | ✅ | Same key as the main `frontend/` app uses |
| `SUPABASE_URL` | ✅ | Same Supabase project as the main app |
| `SUPABASE_SERVICE_KEY` | ✅ | Service role key — bypasses RLS for logging |
| `CTO_AGENT_PASSCODES` | ⬜ | Comma-separated `Label=passcode` pairs. Leave empty to disable the gate (local-first default) |
| `CTO_AGENT_MODEL` | ⬜ | Defaults to `claude-sonnet-4-5` |
| `CTO_AGENT_MAX_TOKENS` | ⬜ | Defaults to `4096` |

### 3. Run the Supabase migration

In the Supabase SQL editor, run:

```
ugc_db/migrations/033_add_cto_agent_logs.sql
```

This creates the `cto_agent_conversations` and `cto_agent_messages`
tables that capture every Q&A pair for review.

### 4. Start the dev server

```bash
pnpm dev
```

The app runs at `http://localhost:3100` so it doesn't conflict with the
main frontend on `:3000`.

### 5. Quick health check

```bash
curl http://localhost:3100/api/health | jq
```

Verifies that the knowledge-base loaded, the Anthropic key is set, and
Supabase logging is configured.

## Persona tuning

The entire personality lives in `src/lib/persona.ts`. Edit that file to
adjust tone, hard guardrails, what the agent can speak to, and what it
must defer. Changes take effect on the next request (no rebuild needed
in dev mode).

## Reviewing what was asked

In Supabase SQL editor:

```sql
SELECT
    c.created_at,
    c.visitor_label,
    m.role,
    m.content,
    m.latency_ms,
    m.tokens_out
FROM cto_agent_messages m
JOIN cto_agent_conversations c ON c.id = m.conversation_id
ORDER BY m.created_at DESC
LIMIT 50;
```

To flag an answer that needs persona tuning:

```sql
UPDATE cto_agent_messages
SET flagged = TRUE, notes = 'Overpromised on multi-region timing'
WHERE id = '...';
```

Then revisit `persona.ts` to harden the guardrails that produced the
bad answer.

## Deployment (when ready)

The app is a vanilla Next.js 16 app. Deploy to Vercel:

```bash
vercel --prod
```

Important deployment notes:

1. **Bundle the diligence docs.** Local dev reads them from the repo
   root via `fs.readFileSync`. For Vercel deployment, either copy them
   into `services/cto-agent/src/data/` and update
   `knowledge-base.ts` to read from there, or include them via a build
   step.
2. **Enable the passcode gate.** Set `CTO_AGENT_PASSCODES` in Vercel
   project env vars so the public URL isn't open access.
3. **Set robots.txt to deny all** — the `metadata.robots` directive
   already does this at the page level.
4. **Custom domain optional** — e.g. `engineering.aitoma.studio` or
   `cto.aitoma.studio` via Vercel custom domain.

## Files

```
services/cto-agent/
├── package.json
├── tsconfig.json
├── next.config.ts
├── postcss.config.mjs
├── .env.local.example
├── README.md (this file)
└── src/
    ├── app/
    │   ├── layout.tsx           Root layout + metadata
    │   ├── page.tsx             Chat UI (client component)
    │   ├── globals.css          Tailwind v4 + design tokens
    │   └── api/
    │       ├── chat/route.ts    Anthropic streaming + logging
    │       └── health/route.ts  Diagnostics endpoint
    ├── lib/
    │   ├── persona.ts           CTO persona system prompt
    │   ├── knowledge-base.ts    Loads diligence docs from repo root
    │   ├── supabase-logger.ts   Best-effort conversation logging
    │   └── passcode.ts          Optional access gate
    └── components/
        ├── ChatMessage.tsx
        ├── ChatInput.tsx
        ├── SuggestedQuestions.tsx
        └── PasscodeGate.tsx
```
