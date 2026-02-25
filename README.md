# 🎬 UGC Engine SaaS

An AI-powered video generation platform that creates realistic User-Generated Content (UGC) videos featuring AI influencers promoting digital and physical products. The engine handles end-to-end video creation — from AI scene generation and voice synthesis to subtitle overlay and cinematic product shots — all orchestrated through a modern web dashboard.

---

## Tech Stack

| Category | Technology | Version |
|----------|-----------|---------|
| **Backend** | Python | 3.10+ |
| | FastAPI | Latest |
| | Celery | Latest |
| | Uvicorn | Latest |
| **Frontend** | Next.js | 16.1.6 |
| | React | 19.2.3 |
| | TypeScript | 5.x |
| | TailwindCSS | 4.x |
| **Database** | Supabase (PostgreSQL) | — |
| | Supabase JS Client | 2.96+ |
| **Task Queue** | Redis | Latest |
| **Video Processing** | FFmpeg / FFprobe | Latest |
| | MoviePy | Latest |
| **AI Services** | Kie.ai (Seedance, Veo, Suno) | REST API |
| | ElevenLabs (Voice) | REST API |
| | OpenAI Whisper (Transcription) | REST API |
| **Storage** | Supabase Storage | — |
| **Package Managers** | pip (backend) / npm (frontend) | — |

---

## Prerequisites

Before cloning, make sure you have the following installed:

| Tool | Minimum Version | Download |
|------|----------------|----------|
| **Python** | 3.10+ | [python.org](https://www.python.org/downloads/) |
| **Node.js** | 18+ | [nodejs.org](https://nodejs.org/) |
| **FFmpeg** (includes FFprobe) | Latest | [ffmpeg.org](https://ffmpeg.org/download.html) |
| **Git** | Latest | [git-scm.com](https://git-scm.com/) |

> **Optional:** [Redis](https://redis.io/download) is required only for production task queuing. The backend automatically falls back to in-process background threads when Redis is unavailable (local development).

### FFmpeg Setup (Windows)

1. Download a release from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) → **ffmpeg-release-essentials.zip**
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system `PATH`
4. Verify: `ffmpeg -version` and `ffprobe -version`

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/AitomaLab/ugc-engine.git
cd ugc-engine
```

### 2. Backend Setup

```bash
# Create a Python virtual environment
python -m venv .venv

# Activate it
# Windows:
.\.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Environment Variables

```bash
# Copy the example files
cp .env.saas.example .env.saas
```

Open `.env.saas` and fill in your API keys (see [Environment Variables Reference](#environment-variables-reference) below).

### 4. Database Setup (Supabase)

1. Create a free project at [supabase.com](https://supabase.com)
2. Copy your **Project URL**, **Service Key**, and **Anon Key** from Dashboard → Settings → API
3. Add them to `.env.saas`
4. Run the SQL migrations in order via the **Supabase SQL Editor**:

```
ugc_db/migrations/004_add_products.sql
ugc_db/migrations/005_add_visual_analysis.sql
ugc_db/migrations/006_add_visual_description.sql
ugc_db/migrations/007_add_product_shots.sql
```

> **Note:** Migrations 001-003 are handled by the initial Supabase schema. Start from `004`.

### 5. Frontend Setup

```bash
cd frontend
npm install
cd ..
```

### 6. Start the Development Servers

You need **two terminals** running simultaneously:

**Terminal 1 — Backend API** (from project root):
```bash
python app.py
```
The API will be available at `http://localhost:8000`

**Terminal 2 — Frontend** (from project root):
```bash
cd frontend
npm run dev
```
The dashboard will open at `http://localhost:3000`

---

## Available Scripts / Commands

### Backend (from project root)

| Command | Description |
|---------|-------------|
| `python app.py` | Start the FastAPI backend with hot-reload on port 8000 |
| `python seed_supabase.py` | Seed the database with sample influencers, scripts, and app clips |
| `python hygiene_check.py` | Run a health check on the database and validate data integrity |

### Frontend (from `frontend/` directory)

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Next.js dev server with hot-reload on port 3000 |
| `npm run build` | Create an optimized production build |
| `npm run start` | Serve the production build |
| `npm run lint` | Run ESLint on the codebase |

### Production (Celery Worker)

| Command | Description |
|---------|-------------|
| `celery -A ugc_worker.tasks worker --loglevel=info` | Start the Celery background worker (requires Redis) |

---

## Project Structure

```
ugc-engine/
├── app.py                  # Entry point — starts the FastAPI server
├── config.py               # Global configuration and constants
├── requirements.txt        # Python dependencies
├── runtime.txt             # Python version for deployment
│
├── ugc_backend/            # FastAPI REST API
│   ├── main.py             # All API routes and endpoint handlers
│   └── cost_service.py     # Cost estimation for video generation
│
├── ugc_worker/             # Background task processing
│   └── tasks.py            # Celery tasks (video generation, shot animation)
│
├── ugc_db/                 # Database layer
│   ├── db_manager.py       # Supabase CRUD operations
│   └── migrations/         # SQL migration files (run in Supabase SQL Editor)
│
├── prompts/                # AI prompt engineering
│   ├── digital_prompts.py  # Prompts for digital product (app) videos
│   ├── physical_prompts.py # Prompts for physical product videos
│   └── cinematic_shots.py  # SEALCaM prompts for cinematic product stills
│
├── core_engine.py          # Core video generation pipeline orchestrator
├── generate_scenes.py      # Scene generation (image + video via AI APIs)
├── scene_builder.py        # Scene sequence builder (hooks, app clips, shots)
├── assemble_video.py       # Final video assembly with FFmpeg
├── subtitle_engine.py      # Whisper-based subtitle generation and overlay
├── elevenlabs_client.py    # ElevenLabs voice synthesis integration
├── storage_helper.py       # Supabase Storage upload utilities
│
├── frontend/               # Next.js web dashboard
│   ├── src/app/            # App Router pages
│   │   ├── page.tsx        # Dashboard home
│   │   ├── create/         # Video creation wizard
│   │   ├── library/        # Asset library (videos, influencers, products)
│   │   ├── activity/       # Job monitoring and progress
│   │   └── Sidebar.tsx     # Navigation sidebar
│   └── src/lib/            # Shared utilities and types
│
├── Procfile                # Heroku/Railway process definitions
├── railway.toml            # Railway deployment configuration
└── render.yaml             # Render deployment configuration
```

---

## Environment Variables Reference

Create a `.env.saas` file in the project root with the following variables:

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `KIE_API_KEY` | API key for Kie.ai (video generation, music) | ✅ | `af33...a66` |
| `ELEVENLABS_API_KEY` | API key for ElevenLabs (voice synthesis) | ✅ | `sk_e0a0...` |
| `OPENAI_API_KEY` | API key for OpenAI (Whisper transcription) | ✅ | `sk-proj-...` |
| `SUPABASE_URL` | Your Supabase project URL | ✅ | `https://xxx.supabase.co` |
| `SUPABASE_SERVICE_KEY` | Supabase service role key (server-side) | ✅ | `sb_secret_...` |
| `DATABASE_URL` | PostgreSQL connection string (from Supabase) | ⬜ | `postgresql://...` |
| `CELERY_BROKER_URL` | Redis URL for Celery task queue | ⬜ | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery result store | ⬜ | `redis://localhost:6379/0` |
| `NEXT_PUBLIC_API_URL` | Backend URL for the frontend to connect to | ✅ | `http://localhost:8000` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase URL (client-side) | ✅ | `https://xxx.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anon key (client-side) | ✅ | `eyJhbG...` |

> **⬜ = Optional for local dev.** Redis vars are only needed in production. The backend auto-detects Redis availability and falls back to in-process threads.

---

## Deployment

### Railway (recommended)

The project includes `railway.toml` with pre-configured services:

| Service | Purpose |
|---------|---------|
| **web** | FastAPI backend via Uvicorn |
| **worker** | Celery background task processor |

Deploy with:
```bash
railway up
```

Set all environment variables in the Railway dashboard under your project's **Variables** tab.

### Render

The project also includes `render.yaml` for Render Blueprints:
- **Web service** — FastAPI API
- **Redis instance** — Task queue
- **PostgreSQL database** — Primary data store

Deploy with:
```bash
render blueprint launch
```

### Production Notes

- In production, **Redis is required** for the Celery task queue
- The `Procfile` defines `web` and `worker` processes for platforms that use it (Heroku, Railway)
- The frontend should be deployed separately (Vercel recommended) with `NEXT_PUBLIC_*` env vars

---

## Troubleshooting

### "FFmpeg not found in PATH"

The backend validates FFmpeg at startup. If you see this error:
- Ensure `ffmpeg` and `ffprobe` are in your system PATH
- Run `ffmpeg -version` to verify
- On Windows: Add `C:\ffmpeg\bin` to your PATH environment variable

### "Retry limit exceeded while trying to reconnect to the Celery redis result store"

This means Redis is not running. **For local development, this is fine** — the backend automatically falls back to in-process background threads. Just restart the backend and try again.

### Frontend can't connect to the API

- Ensure the backend is running on port 8000
- Check that `NEXT_PUBLIC_API_URL` is set to `http://localhost:8000` in your frontend `.env.local` or in `.env.saas`
- Check for CORS errors in the browser console

### Database migration errors

- Run migrations in numerical order (004, 005, 006, 007)
- Each migration is idempotent (uses `IF NOT EXISTS`) so re-running is safe
- Run them in the **Supabase SQL Editor**, not via command line

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/my-feature`)
3. Commit your changes (`git commit -m 'feat: add my feature'`)
4. Push to the branch (`git push origin feature/my-feature`)
5. Open a Pull Request

---

## License

This project is proprietary software developed by AitomaLab. All rights reserved.
