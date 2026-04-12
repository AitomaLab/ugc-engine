# Aitoma Studio Creative OS — Codebase Audit

> Completed: 2026-04-07 | Auditor: Antigravity

---

## 1. Repository Structure

```
ugc-engine/
├── ugc_backend/           # FastAPI backend (main.py = 3159 lines, port 8000)
│   ├── main.py            # All API endpoints
│   ├── auth.py            # Supabase JWT validation
│   ├── cost_service.py    # Cost estimation
│   ├── cost_config.json   # Model pricing
│   ├── editor_api.py      # Video editor endpoints
│   ├── ai_script_client.py # AI script generation
│   └── api_clones.py      # AI clone endpoints
├── ugc_db/
│   ├── db_manager.py      # All Supabase CRUD (884 lines)
│   ├── schema.sql          # Base schema
│   ├── migration_scripts_v2.sql
│   ├── migration_stripe.sql
│   └── migrations/         # Incremental migrations
├── frontend/              # Next.js 16 + React 19 + Tailwind 4
│   └── src/
│       ├── app/            # App Router pages
│       ├── components/     # layout/, modals/, ui/
│       ├── providers/      # AppProvider (React Context)
│       ├── lib/            # utils, supabaseClient, i18n, types
│       ├── editor/         # Video editor components
│       └── remotion/       # Remotion video compositions
├── kie_ai/
│   ├── nano_banana_client.py  # Image generation (Nano Banana Pro)
│   └── veo_client.py          # Video generation (Veo 3.1)
├── config.py              # Central config + MODEL_REGISTRY
├── core_engine.py         # Video pipeline orchestrator
├── elevenlabs_client.py   # TTS voiceover client
├── generate_scenes.py     # Scene generation logic
├── scene_builder.py       # Scene planning
├── clone_engine.py        # AI clone pipeline
└── prompts/               # Physical + digital product prompts
```

---

## 2. API Endpoints (Core Backend — port 8000)

### 2.1 SaaS Endpoints (JWT required via `get_current_user`)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/profile` | Get user profile |
| `PUT` | `/api/profile` | Update user profile |
| `GET` | `/api/projects` | List user's projects → `Project[]` |
| `POST` | `/api/projects` | Create project `{name}` → `Project` |
| `PUT` | `/api/projects/{id}` | Update project name |
| `DELETE` | `/api/projects/{id}` | Delete project (blocks default) |
| `GET` | `/api/subscription` | Get user subscription + plan |
| `GET` | `/api/wallet` | Get credit balance (lazy-init 100) |
| `GET` | `/api/wallet/transactions` | Credit transaction history |
| `GET` | `/api/notifications` | Recent activity feed |
| `GET` | `/api/plans` | List subscription plans |
| `GET` | `/api/credits/costs` | Credit cost reference table |
| `POST` | `/api/stripe/checkout/subscription` | Stripe checkout session |
| `POST` | `/api/stripe/checkout/topup` | One-time credit top-up |
| `POST` | `/api/stripe/portal` | Stripe billing portal |
| `POST` | `/api/stripe/webhook` | Stripe webhook handler (no auth) |

### 2.2 Content Endpoints (scoped by `X-Project-Id` header)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/influencers` | List influencers (scoped) |
| `POST` | `/influencers` | Create influencer |
| `GET` | `/scripts` | List scripts (scoped, filtered) |
| `POST` | `/scripts` | Create script |
| `GET` | `/products` | List products (scoped) |
| `POST` | `/products` | Create product |
| `GET` | `/app-clips` | List app clips (scoped) |

### 2.3 Generation Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/jobs` | Create video job + dispatch worker |
| `POST` | `/bulk-jobs` | Bulk create video jobs |
| `GET` | `/jobs` | List jobs (scoped, with clone merge) |
| `GET` | `/jobs/{id}` | Get single job |
| `GET` | `/jobs/{id}/status` | Poll job status |
| `DELETE` | `/jobs/{id}` | Delete job |
| `POST` | `/estimate` | Real-time cost estimation |
| `GET` | `/stats` | Dashboard KPIs |
| `GET` | `/stats/costs` | Aggregate spend stats |

### 2.4 Cinematic Shot Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/products/{id}/shots` | List product shots |
| `POST` | `/api/products/{id}/shots` | Generate shot images |
| `POST` | `/api/shots/{id}/animate` | Animate still → video |
| `GET` | `/api/shots/costs` | Shot cost estimates |
| `DELETE` | `/api/shots/{id}` | Delete shot |
| `POST` | `/api/products/{id}/transition-shot` | Generate transition shot |

### 2.5 AI Clone Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/clone-jobs` | Create AI clone video job |
| `GET` | `/api/clone-jobs/{id}` | Poll clone job status |

### 2.6 AI Hook Generation

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/ai/hook` | Generate template-based hook text |

---

## 3. Database Schema (Supabase PostgreSQL)

### 3.1 Core Tables

| Table | Key Columns | Notes |
|-------|-------------|-------|
| `profiles` | `id (UUID PK → auth.users)`, `full_name`, `company_name`, `stripe_customer_id` | User profile |
| `projects` | `id`, `user_id`, `name`, `is_default`, `created_at` | User workspace projects |
| `influencers` | `id`, `user_id`, `project_id`, `name`, `gender`, `accent`, `tone`, `visual_description`, `reference_image_url`, `elevenlabs_voice_id`, `category` | AI influencer personas |
| `scripts` | `id`, `user_id`, `project_id`, `name`, `text`, `script_json`, `category`, `methodology`, `video_length`, `product_id`, `influencer_id`, `source`, `is_trending`, `times_used` | Video scripts |
| `products` | `id`, `user_id`, `project_id`, `name`, `type`, `description`, `image_url`, `website_url`, `visual_description (JSONB)` | User products |
| `app_clips` | `id`, `user_id`, `project_id`, `name`, `category`, `video_url`, `duration` | Pre-recorded clips |
| `video_jobs` | `id`, `user_id`, `project_id`, `influencer_id`, `script_id`, `app_clip_id`, `product_id`, `product_type`, `model_api`, `campaign_name`, `length`, `status`, `progress`, `final_video_url`, `total_cost`, `metadata (JSONB)`, `error_message` | Video generation jobs |
| `product_shots` | `id`, `product_id`, `shot_type`, `image_url`, `video_url`, `status` | Cinematic product shots |

### 3.2 SaaS/Billing Tables

| Table | Key Columns |
|-------|-------------|
| `subscription_plans` | `id`, `name`, `credits_monthly`, `price_monthly`, `stripe_price_id`, `is_active` |
| `subscriptions` | `id`, `user_id`, `plan_id`, `stripe_subscription_id`, `status`, `current_period_start`, `current_period_end` |
| `credit_wallets` | `id`, `user_id`, `balance` |
| `credit_transactions` | `id`, `wallet_id`, `amount`, `type`, `description`, `metadata`, `stripe_idempotency_key` |

### 3.3 AI Clone Tables

| Table | Key Columns |
|-------|-------------|
| `user_ai_clones` | `id`, `user_id`, `name` |
| `user_ai_clone_looks` | `id`, `image_url` |
| `clone_video_jobs` | `id`, `user_id`, `clone_id`, `look_id`, `product_id`, `script_text`, `duration`, `status`, `progress`, `video_url` |

---

## 4. Model Integration Map

### 4.1 Image Generation

| Model | Client | API | Notes |
|-------|--------|-----|-------|
| **Nano Banana Pro** | `kie_ai/nano_banana_client.py` | `POST {KIE_API_URL}/api/v1/jobs/createTask` + poll `GET /api/v1/jobs/recordInfo` | Composite images: product + influencer reference. Uses `product_image_url` + `reference_image_url`. Polls every 5s, 10min timeout. |

### 4.2 Video Generation

| Model | Client | API | Notes |
|-------|--------|-----|-------|
| **Veo 3.1 Fast** | `kie_ai/veo_client.py` | `POST {KIE_API_URL}/api/v1/veo/generate` + poll `GET /api/v1/veo/record-info` | Text-to-video + image-to-video. Polls every 10s, 20min timeout. Default aspect 9:16. |
| **Seedance 2.0** | via `config.MODEL_REGISTRY` | Same Kie.ai API pattern | Default model for standard pipeline. |
| **Kling 2.6** | via `config.MODEL_REGISTRY["kling-2.6"]` = `"kling-2.6/image-to-video"` | Same Kie.ai API | Silent video only, requires `image_urls`. Legacy. |
| **Kling 3.0** | NEW for Creative OS | `POST {KIE_API_URL}/api/v1/jobs/createTask` model=`kling-3.0/video` + poll `GET /api/v1/jobs/recordInfo` | Multi-shot support, element references (`@element_name`), sound effects, pro/std modes (1080p/720p), 3-15s duration, 9:16/16:9/1:1 aspect ratios. |

### 4.3 Audio/Speech

| Model | Client | Notes |
|-------|--------|-------|
| **ElevenLabs** | `elevenlabs_client.py` | TTS voiceover via `POST /v1/text-to-speech/{voice_id}`. Model: `eleven_multilingual_v2`. |
| **InfiniTalk** | via `clone_engine.py` | Lip-sync model: `infinitalk/from-audio`. Used for AI clone videos. |

### 4.4 Video Assembly

| Component | Location | Notes |
|-----------|----------|-------|
| **Remotion** | `frontend/src/remotion/` + `remotion_renderer/` | Caption rendering, video composition. Uses `@remotion/player` 4.0.433. |
| **FFmpeg** | `assemble_video.py` | Final video assembly, audio mixing, subtitle burn-in. |

---

## 5. Authentication & Authorization

- **Method:** Supabase JWT via `Authorization: Bearer <token>` header
- **Validation:** `ugc_backend/auth.py` → calls `supabase.auth.get_user(token)` with ANON key
- **Dependencies:**
  - `get_current_user` → returns `{id, email}` or raises 401
  - `get_optional_user` → returns `{id, email}` or `None` (no 401)
- **Project Scoping:** `X-Project-Id` header read by `_resolve_project_id()`, stored in `localStorage` as `activeProjectId`
- **Frontend Auth:** `@supabase/ssr` cookie-based client, middleware redirects unauthenticated users

---

## 6. Frontend Architecture

### 6.1 Tech Stack
- **Framework:** Next.js 16.2 (App Router)
- **React:** 19.2.3
- **CSS:** Tailwind 4 + vanilla CSS (`globals.css` = 86KB)
- **UI Libraries:** `@radix-ui/react-select`, `@radix-ui/react-popover`, `@radix-ui/react-context-menu`
- **Icons:** Custom inline SVG components (no external icon library)
- **State Management:** React Context via `AppProvider` (no Redux/Zustand)
- **Font:** Inter (Google Fonts, weights 300-800)

### 6.2 Navigation Structure
- **Header:** `components/layout/Header.tsx` — top horizontal nav bar with:
  - Logo → `/`
  - Nav items: Home, Videos, Influencers, Scripts, Products, Schedule, Editor, Activity
  - Actions: ProjectSwitcher, Create dropdown, Lang toggle (EN/ES), Notifications, Profile
- **Create Dropdown:** Links to `/create` (UGC video) and `/cinematic` (product shots)

### 6.3 Existing Routes
```
/                   Dashboard (home)
/create             UGC video creation
/cinematic          Cinematic product shots
/videos             Video library
/influencers        Influencer management
/scripts            Script management
/products           Product management
/schedule           Social scheduling
/editor/{jobId}     Video editor (full viewport, no header)
/activity           Activity/analytics
/library            Asset library
/projects           Project management
/profile            User profile
/manage             Billing/settings
/upgrade            Subscription plans
/login              Auth: login
/signup             Auth: signup
/checkout/success   Stripe checkout success
```

### 6.4 Key Utility: `apiFetch()`
Located in `frontend/src/lib/utils.ts`. Auto-attaches:
- `Authorization: Bearer <token>` from Supabase session
- `X-Project-Id` from `localStorage.activeProjectId`
- Base URL from `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`)

---

## 7. Design System Tokens

### 7.1 CSS Custom Properties (from `globals.css :root`)

```css
/* Colors */
--blue:       #337AFF;          /* Primary brand */
--blue-dark:  #1A5FD4;          /* Hover/active */
--blue-light: #EBF1FF;          /* Backgrounds */
--blue-glow:  rgba(51,122,255,0.25);
--bg:         #F0F4FF;          /* Page background */
--surface:    rgba(255,255,255,0.72);  /* Cards */
--surface-2:  rgba(255,255,255,0.55);
--border:     rgba(51,122,255,0.14);
--border-soft: rgba(0,0,0,0.07);
--text-1:     #0D1B3E;          /* Primary text */
--text-2:     #4A5578;          /* Secondary text */
--text-3:     #8A93B0;          /* Muted text */
--green:      #22C55E;          /* Success */
--amber:      #F59E0B;          /* Warning */
--red:        #EF4444;          /* Error */

/* Layout */
--radius:     14px;
--radius-sm:  8px;
--shadow:     0 4px 24px rgba(51,122,255,0.10);
--shadow-lg:  0 8px 40px rgba(51,122,255,0.18);
--header-h:   60px;
```

### 7.2 Typography
- **Font:** Inter (Google Fonts)
- **Weights:** 300 (Light), 400 (Regular), 500 (Medium), 600 (SemiBold), 700 (Bold), 800 (ExtraBold)

### 7.3 Button Conventions (from existing CSS classes)
- Primary: `gradient-cta` class (blue gradient), white text, `border-radius: var(--radius)`
- Secondary: `bg: var(--surface)`, border `var(--border)`, text `var(--text-2)`
- Icons: Custom inline SVG, 20×20 default, `stroke="currentColor"`, `strokeWidth="1.5"`

---

## 8. Credit Cost Table

| Asset Type | Credits |
|-----------|---------|
| Digital 15s video | 39 |
| Digital 30s video | 77 |
| Physical 15s video | 100 |
| Physical 30s video | 199 |
| Cinematic image (1K/2K) | 13 |
| Cinematic image (4K) | 16 |
| Cinematic video (8s) | 51 |

---

## 9. Environment Variables Required

From `.env.saas`:
- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL`
- `KIE_API_KEY`, `KIE_API_URL`
- `ELEVENLABS_API_KEY`
- `VIDEO_MODEL` (default: `seedance-1.5-pro`)
- `OPENAI_API_KEY` (used by `ai_script_client.py`)
- Stripe keys: `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_TOPUP_*_PRICE_ID`

---

## 10. Non-Breaking Constraints Summary

The following files/systems are **READ-ONLY** for Creative OS:

| Asset | Reason |
|-------|--------|
| `ugc_backend/main.py` | 3159 lines, all existing endpoints |
| `ugc_backend/auth.py` | Auth middleware shared by all routes |
| `ugc_db/db_manager.py` | All CRUD functions |
| `ugc_db/schema.sql` + migrations | Production schema |
| `config.py` | Shared config |
| `core_engine.py` | Video pipeline |
| `frontend/src/app/page.tsx` | Dashboard |
| `frontend/src/app/create/` | Existing create flow |
| `frontend/src/app/editor/` | Video editor |
| All existing `frontend/src/app/*/` routes | Production pages |

**Allowed modifications:**
- Add ONE nav link to Header.tsx pointing to `/studio`
- Create new files under `services/creative-os/` and `frontend/src/app/studio/`
- Create new components under `frontend/src/components/studio/`
