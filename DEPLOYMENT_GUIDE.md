# UGC Engine — Production Deployment Guide

> **Multi-Cloud Architecture:** Vercel (frontend) + Railway (API + worker) + Supabase (DB) + Upstash (Redis) + Modal (serverless video processing)

---

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Phase 1: Frontend & Database](#phase-1-frontend--database)
3. [Phase 2: Backend API & Task Broker](#phase-2-backend-api--task-broker)
4. [Phase 3: Serverless Video Worker](#phase-3-serverless-video-worker)
5. [Environment Variable Reference](#environment-variable-reference)
6. [Testing & Validation](#testing--validation)
7. [Rollback Plan](#rollback-plan)

---

## Prerequisites

Before starting, ensure you have:
- A GitHub repository with the latest `main` branch pushed
- Active accounts on: [Supabase](https://supabase.com), [Vercel](https://vercel.com), [Railway](https://railway.app), [Upstash](https://upstash.com), [Modal](https://modal.com)
- Node.js 18+ and Python 3.11+ installed locally

---

## Phase 1: Frontend & Database

### 1.1 — Supabase Connection Pooler (No action needed)

Supavisor is **enabled by default** on all modern Supabase projects. Since the UGC Engine uses Supabase's REST API (PostgREST) — not raw PostgreSQL TCP connections — connection pooling is handled transparently at the infrastructure level.

**To confirm it's active:** Go to Supabase Dashboard → **Settings** → **Database** → scroll to **Connection String**. If you see "Session mode" / "Transaction mode" options with a `pooler.supabase.com` hostname, Supavisor is already on.

Your existing `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` remain unchanged. No code or config changes needed.

### 1.2 — Deploy Frontend to Vercel

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your GitHub repository
3. Set the **Root Directory** to `frontend`
4. Set the **Framework Preset** to `Next.js`
5. Add these **Environment Variables** in the Vercel project settings:

| Variable | Value | Example |
|----------|-------|---------|
| `NEXT_PUBLIC_API_URL` | Your Railway API URL (set after Phase 2) | `https://ugc-engine-api-production.up.railway.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL | `https://kzvdfponrzwfwdbkpfjf.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon/public key | `eyJhbGciOiJ...` |

6. Click **Deploy**
7. Note your Vercel deployment URL (e.g., `https://your-app.vercel.app`)

### 1.3 — Verify Phase 1

- Visit your Vercel URL — the frontend should load
- It won't be fully functional yet (API not deployed), but the UI should render

---

## Phase 2: Backend API & Task Broker

### 2.1 — Provision Redis on Upstash

1. Go to [console.upstash.com](https://console.upstash.com)
2. Create a new **Redis Database**
3. Choose the region closest to your Railway deployment
4. Copy the **Redis URL** (format: `rediss://default:PASSWORD@HOST:PORT`)

> **Important:** Upstash uses `rediss://` (with double-s) for TLS. Celery supports this natively.

### 2.2 — Deploy Backend API to Railway

1. Go to [railway.app/new](https://railway.app/new)
2. Create a new project from your GitHub repository
3. Railway will auto-detect the `railway.toml` configuration

**Create two services:**

#### Service 1: API Server
- **Name:** `ugc-api`
- **Start Command:** `PYTHONPATH=. uvicorn app:app --host 0.0.0.0 --port $PORT`
- Railway reads this from `railway.toml` automatically

#### Service 2: Celery Worker (Temporary)
- **Name:** `ugc-worker`
- **Start Command:** `PYTHONPATH=. celery -A ugc_worker.tasks worker --loglevel=info`

**Add these environment variables to BOTH services:**

| Variable | Value |
|----------|-------|
| `SUPABASE_URL` | `https://kzvdfponrzwfwdbkpfjf.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Your Supabase service role key |
| `SUPABASE_ANON_KEY` | Your Supabase anon key |
| `KIE_API_KEY` | Your Kie.ai API key |
| `ELEVENLABS_API_KEY` | Your ElevenLabs API key |
| `OPENAI_API_KEY` | Your OpenAI API key |
| `CELERY_BROKER_URL` | Your Upstash Redis URL |
| `CELERY_RESULT_BACKEND` | Your Upstash Redis URL |
| `CORS_ORIGINS` | `http://localhost:3000,https://your-app.vercel.app` |
| `ADMIN_EMAIL` | `max@aitoma.ai` |

### 2.3 — Update Vercel with Railway URL

1. Once Railway deploys, copy the API server's public URL
2. Go back to Vercel → **Settings** → **Environment Variables**
3. Update `NEXT_PUBLIC_API_URL` to the Railway URL
4. Redeploy the frontend

### 2.4 — Verify Phase 2

- Visit your Vercel frontend
- Try logging in — authentication should work via Supabase
- Try creating a video job — it should be picked up by the Railway Celery worker
- Monitor Railway logs for `[OK] Job ... dispatched to Celery worker`

---

## Phase 3: Serverless Video Worker

### 3.1 — Set Up Modal

1. Go to [modal.com](https://modal.com) and create an account
2. Install the Modal CLI: `pip install modal`
3. Authenticate: `modal token new`

### 3.2 — Create Modal Secrets

In the Modal dashboard or CLI, create a secret group called `ugc-engine-secrets` with these values:

```bash
modal secret create ugc-engine-secrets \
  SUPABASE_URL="https://kzvdfponrzwfwdbkpfjf.supabase.co" \
  SUPABASE_SERVICE_KEY="your-service-key" \
  KIE_API_KEY="your-kie-key" \
  ELEVENLABS_API_KEY="your-elevenlabs-key" \
  OPENAI_API_KEY="your-openai-key"
```

### 3.3 — Deploy the Modal Worker

From the project root:

```bash
modal deploy modal_worker.py
```

This will print a webhook URL like:
```
https://your-workspace--ugc-engine-worker-trigger-job.modal.run
```

Copy this URL.

### 3.4 — Enable Modal in Railway

Add these environment variables to the **Railway API Server** (`ugc-api`) service:

| Variable | Value |
|----------|-------|
| `USE_MODAL_WORKER` | `true` |
| `MODAL_WEBHOOK_URL` | The webhook URL from step 3.3 |

### 3.5 — Decommission the Railway Worker (Optional)

Once you've verified Modal is handling jobs correctly:

1. Go to Railway → your project
2. **Delete** the `ugc-worker` Celery service
3. This removes the expensive always-on worker — all processing now happens on-demand via Modal

> **Safety:** If you ever need to go back, just set `USE_MODAL_WORKER=false` in Railway. The backend will automatically fall back to Celery (if Redis is available) or in-process threading.

### 3.6 — Verify Phase 3

- Create a video job from the frontend
- Check Railway API logs for: `[OK] Job ... dispatched to Modal worker`
- Check Modal dashboard for the function execution
- Verify the finished video appears in the Activity page

---

## Environment Variable Reference

### Vercel (Frontend)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Railway API server URL |
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Supabase public/anon key |

### Railway — API Server

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key |
| `SUPABASE_ANON_KEY` | ✅ | Supabase anon key |
| `KIE_API_KEY` | ✅ | Kie.ai video generation API key |
| `ELEVENLABS_API_KEY` | ✅ | ElevenLabs TTS API key |
| `OPENAI_API_KEY` | ✅ | OpenAI API key (Whisper) |
| `CELERY_BROKER_URL` | ✅ | Upstash Redis URL |
| `CELERY_RESULT_BACKEND` | ✅ | Upstash Redis URL (same) |
| `CORS_ORIGINS` | ✅ | Comma-separated allowed frontend URLs |
| `ADMIN_EMAIL` | ✅ | Admin user email |
| `USE_MODAL_WORKER` | ❌ | Set to `true` to use Modal (default: `false`) |
| `MODAL_WEBHOOK_URL` | ❌ | Modal trigger_job webhook URL |

### Railway — Celery Worker (Temporary)

Same as API Server variables, minus `CORS_ORIGINS`, `USE_MODAL_WORKER`, and `MODAL_WEBHOOK_URL`.

### Modal — Serverless Worker

All secrets are managed via the `ugc-engine-secrets` secret group in Modal's dashboard:

| Secret | Required | Description |
|--------|----------|-------------|
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key |
| `KIE_API_KEY` | ✅ | Kie.ai API key |
| `ELEVENLABS_API_KEY` | ✅ | ElevenLabs API key |
| `OPENAI_API_KEY` | ✅ | OpenAI API key |

---

## Testing & Validation

### Quick Smoke Test

```bash
# 1. Verify backend starts without errors
PYTHONPATH=. python -c "from ugc_backend.main import app; print('✅ Backend OK')"

# 2. Verify Celery worker can be imported
PYTHONPATH=. python -c "from ugc_worker.tasks import celery; print('✅ Celery OK')"

# 3. Verify Modal worker syntax
python -c "import modal_worker; print('✅ Modal worker OK')"
```

### Dispatch Fallback Chain Test

| Scenario | Expected Behavior |
|----------|-------------------|
| `USE_MODAL_WORKER=true` + valid `MODAL_WEBHOOK_URL` | Job dispatched to Modal |
| `USE_MODAL_WORKER=true` + Modal unreachable | Falls back to Celery |
| `USE_MODAL_WORKER` unset + Redis running | Job dispatched to Celery |
| `USE_MODAL_WORKER` unset + no Redis | Job runs in background thread |

---

## Rollback Plan

If anything goes wrong at any phase:

1. **Frontend:** Revert `NEXT_PUBLIC_API_URL` to `http://localhost:8000` in Vercel
2. **Backend:** The local `python app.py` command still works identically
3. **Modal → Celery:** Set `USE_MODAL_WORKER=false` in Railway — instant fallback
4. **Full rollback:** Run the engine locally exactly as before — zero code was removed

> The existing local-first, Celery-based system remains the default when no cloud-specific environment variables are set.
