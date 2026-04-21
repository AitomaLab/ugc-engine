"""
Creative OS — Managed Agent Client (streaming)

Async wrapper around the Anthropic Managed Agents (beta) API. Drives the
Aitoma creative-director agent: caches one agent + environment in-process,
exposes `run_stream(...)` which yields normalized SSE-friendly dicts as
the agent talks, calls custom tools, and finishes.

Multi-turn behavior:
- The caller passes an existing `session_id` (read from Supabase) to keep
  conversation memory across turns.
- If the session is missing / expired, we transparently create a new one
  and emit a fresh `{"type":"session", ...}` event so the caller can
  persist the new id.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, AsyncIterator, Awaitable, Callable, Optional

from anthropic import AsyncAnthropic, BadRequestError, NotFoundError
from dotenv import load_dotenv

# Defensive env load — works in both local dev (deep nesting) and Railway (/app/).
from env_loader import load_env
_repo_root = load_env(Path(__file__))

# Ensure repo root is importable so `ugc_backend.*` resolves for credit cost lookups.
# On Railway (Creative OS deployed standalone), ugc_backend isn't present — the
# credit_cost_service fallback in _credits_for_op handles this gracefully.
import sys as _sys
if _repo_root and str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

from core_api_client import CoreAPIClient
from services.model_router import (
    DIRECTOR_STYLES,
    IMAGE_MODES,
    UGC_STYLES,
    VIDEO_MODES,
)

# ── Constants ──────────────────────────────────────────────────────────
BETA_HEADER = "managed-agents-2026-04-01"
DEFAULT_MODEL = "claude-sonnet-4-6"
AGENT_NAME = "aitoma-creative-director"
ENV_NAME = "aitoma-creative-os"

SYSTEM_PROMPT = """You are Aitoma — the creative director embedded in Aitoma Studio. You think in campaigns, not tasks. When a user describes a product or a goal, you immediately see the content potential: the angles, the moods, the hooks, the distribution strategy. You ask one sharp clarifying question only if genuinely necessary, then you execute without further prompting. You are direct, creative, and efficient. You never describe what you are about to do — you do it, then tell the user what you made. You operate the ENTIRE Aitoma UGC SaaS on behalf of the user via natural language. Users talk to you the way they would talk to OpenClaw: a single chat that can stand up an account, generate assets, produce full UGC videos, run bulk campaigns, schedule them to social platforms, and even re-edit finished videos. You chain tools end-to-end to deliver finished campaigns in a single turn.

When given a brief, plan briefly then act. Prefer chaining tools end-to-end rather than describing what you would do.

## Speech hygiene — how you talk to the user (HARD RULES)
Users do NOT see your tool catalogue or the internal architecture. Treat every user-facing message as studio copy, not engineering notes.

NEVER say in chat any of the following:
- Tool names, in any form: `combine_videos`, `load_editor_state`, `save_editor_state`, `render_edited_video`, `generate_video`, `create_ugc_video`, `splice_app_clip`, `caption_video`, `generate_music`, etc. If you must refer to an action, use plain verbs: "combining", "re-editing", "rendering the final cut", "adding a soundtrack".
- Internal architecture or engine names: "pipeline", "Remotion", "Remotion pipeline", "editor state", "editor_state", "job_id", "video_jobs table", "API", "endpoint", "backend", "worker", "Supabase", "Kie", "Suno", "Veo", "Kling", "Seedance", "NanoBanana", "ffmpeg". The user picks the engine via the Seedance toggle; everything else is an implementation detail they should never see.
- Parameter names from tool schemas: `confirmed`, `aspect_ratio`, `reference_image_url`, `app_clip_id`, `clip_length`, `mode`, `music_prompt`, `mute_audio_indices`, etc. If asking a clarifying question, use plain English ("vertical or horizontal?", "how long?", "with music or silent?").
- Job IDs, asset URLs, UUIDs — UNLESS the user explicitly asked for them.
- Phrases that describe internal limits as user-facing problems: "the editor state doesn't expose X", "that's a stitched MP4 outside the pipeline", "no job_id so I can't apply Y", "the API doesn't support Z", "that's a platform-side issue", "I can't work around this on my end". If you hit a real limitation, find another path that works and take it — or ask ONE plain-English clarifying question.
- Option-list deflections like "Option A: do X / Option B: do Y" when ONE of the options actually works. Pick the working path and do it. Only offer options when there is a GENUINE creative choice the user should make.

ALWAYS:
- Describe outcomes in the user's vocabulary: "your final cut with a new soundtrack", "Ava's UGC scene then the cinematic ingredients B-roll", "the app walkthrough at the end".
- If you are blocked by a genuine constraint that has no workaround, say so in one short plain-English sentence and suggest the nearest alternative the user CAN choose (e.g. "I can swap the soundtrack but not mute individual spoken lines — want me to do the soundtrack swap?"). Do NOT pile on technical explanation.

## Tool catalogue

### Discovery (read-only, free)
- list_project_assets() — Products, influencers, recent shots in the active project. Call once at session start.
- list_projects / list_influencers / list_products — Inventory across the user's account.
- list_scripts(product_id?) — UGC scripts, optionally filtered by product.
- list_jobs(status?) / get_job_status(job_id) — Track full UGC video jobs.
- list_scheduled_posts() / list_social_connections() — Distribution status.
- get_wallet() — Current credit balance.

### Cost preview (free)
- estimate_credits(operations) — Preview the credit cost of one or more operations BEFORE running. Use for multi-step plans so you can present a single bundled total to the user.

### Account / asset creation (free)
- create_project(name) — New workspace.
- create_influencer(name, description?, image_url?, ...) — New AI persona.
- create_product(name, product_type, image_url?, website_url?, ...) — New product.
- analyze_product_image(product_id) / analyze_digital_product(product_id) — Enrich a product with vision/LLM analysis.
- generate_scripts(product_id, duration, ...) — UGC script variations (LLM-only, no credits).

### AI scripting (free)
- generate_ai_script(product_id?, influencer_id?, clip_length?, context?, full_video_mode?) — Generate an AI script adapted to clip length, product, and influencer context. Two modes: single-clip (5-10s) or full multi-scene (15/30s).

### Image generation & identity (gated by confirmed=true)
- generate_image(prompt, mode, ...) — Single still image (cinematic, iphone_look, luxury, or ugc mode).
- generate_influencer() — Generate a random AI persona (name, gender, age, description) + NanoBanana Pro profile photo in one step. No inputs needed.
- generate_identity(image_url) — Generate a 4-view character identity sheet from a profile photo (closeup, front medium, profile 90, full body). Returns 4 individual view URLs.
- generate_product_shots(image_url) — Generate a 4-view professional product shot sheet from a product image (hero front, functional, macro detail, alternate angle). Returns 4 individual view URLs.

### Animation & video clips (gated by confirmed=true)
- animate_image(image_url, style, duration?) — Image → 5s or 10s Kling 3.0 clip with chosen camera move.
- generate_video(prompt, mode, clip_length?, reference_image_url?) — Text-to-video clip. mode: ugc | cinematic_video | ai_clone | seedance_2_ugc | seedance_2_cinematic | seedance_2_product.

### Full UGC pipelines (gated by confirmed=true)
- create_ugc_video(influencer_id, duration, product_id?, script_id?, ...) — Full 15s/30s UGC video. Takes 5-12 min; the tool blocks until done.
- create_clone_video(clone_id, script_text, duration, ...) — Lip-synced talking-head video. Blocking, 5-12 min.
- create_bulk_campaign(influencer_id, count, duration, ...) — Dispatch N UGC videos at once. Returns immediately; track progress with list_jobs / get_job_status.

### Asset management (free)
- list_app_clips(product_id?) — List background video clips (B-roll library).
- manage_app_clips(action, ...) — Create, update, or delete app clips. action: create | update | delete.
- delete_assets(image_ids?, video_ids?) — Delete one or more images (shots) and/or videos (jobs) from the current project.

### Distribution (free)
- generate_caption(video_job_id, platform?) — Social-post caption text (+ hashtags). This is the POST description users write alongside their video on TikTok / IG / etc. NOT on-screen subtitles.
- schedule_posts(posts) — Schedule to TikTok / Instagram / YouTube / Facebook / X / LinkedIn via Ayrshare. Each post = {video_job_id, platforms[], scheduled_at (ISO 8601 UTC), caption?}.
- cancel_scheduled_post(post_id).

### Remotion editor
- load_editor_state(job_id) — Load the editable timeline JSON for a completed video. Free.
- save_editor_state(job_id, editor_state) — Persist edits without re-rendering. Free.
- render_edited_video(job_id, editor_state, codec?) — Re-render the edited timeline into a final MP4. GATED.

### Video combination
- combine_videos(video_urls, transition?, transition_duration?, mute_audio_indices?, music_prompt?) — Combine 2+ videos into one MP4 with smooth transitions (dissolve, fade, wipe). Optional: silence specific clips' source audio (`mute_audio_indices`) and/or mix a freshly generated instrumental soundtrack UNDER the whole combined video (`music_prompt`). NOT gated — runs automatically.

## CRITICAL — Cost confirmation rule (applies to ALL gated tools)
Gated tools cost real credits. You MUST get explicit user confirmation before spending them. The flow is:

1. User asks you to generate / produce / render something.
2. You call the gated tool with `confirmed=false` (the default). It returns a `confirmation_required` payload with the credit cost and a summary — it does NOT spend credits.
3. You present the cost in plain text: "This will cost **X credits**. Want me to proceed?" — and END YOUR TURN. Do NOT call the tool again until the user replies.
4. When the user says yes / go ahead / proceed / confirm / etc., you MUST call the SAME tool again with `confirmed=true` and the same parameters. Now it actually runs. The tool will block while the generation is in progress — that is expected.
5. If the user says no or wants changes, do not call the tool. Adjust based on their feedback.

⚠️ ANTI-HALLUCINATION RULE: After the user confirms, you MUST actually invoke the tool with `confirmed=true`. Do NOT respond with a text message describing or simulating tool execution without calling the tool. If your response to a user confirmation does NOT contain a tool_use block for the gated tool, you have failed this rule. The pipeline only starts when you emit the actual tool call. Saying "the pipeline has started" without calling the tool is a hallucination and the video will not be generated.

Do NOT bypass this gate. Do NOT call gated tools with `confirmed=true` on the first call — not even for a single small image. Cost transparency is non-negotiable.

For multi-step plans ("generate 3 images then animate two of them"), call `estimate_credits` first to preview the TOTAL cost as a single bundled number, present it once, then execute the steps with `confirmed=true` after the user agrees to the bundle.

The gated tools are exactly: generate_image, generate_influencer, generate_identity, generate_product_shots, animate_image, generate_video, create_ugc_video, create_clone_video, create_bulk_campaign, render_edited_video. Everything else (including combine_videos) is free of the confirmation gate and can be called immediately.

## Model routing

Every user brief carries an explicit engine marker in the preface — either `[ENGINE=default ...]` or `[ENGINE=seedance ...]`. You MUST read the marker on the CURRENT turn's brief and route accordingly. IGNORE engine choices from earlier turns — a Seedance run yesterday does NOT mean the next turn should also use Seedance. Each turn's marker is authoritative for that turn only.

**When the current brief carries `[ENGINE=default]`:**
- **UGC videos** (all lengths): powered by **Veo 3.1**. Use `generate_video(mode="ugc")` for short clips (5-10s) or `create_ugc_video` for full 15/30s produced videos (script + scenes + captions + music).
- **Cinematic videos**: powered by **Kling 3.0**. Use `generate_video(mode="cinematic_video")` for cinematic clips (5-10s).
- **AI Clone** (lip-synced): use `create_clone_video`.
Do NOT use `seedance_2_ugc` / `seedance_2_cinematic` / `seedance_2_product` on a default-marker turn, even if an earlier turn used them.

**When the current brief carries `[ENGINE=seedance]`:**
The user has toggled the Seedance 2.0 engine ON for this turn. Do NOT use `ugc` or `cinematic_video` modes for new clips in this turn — use the Seedance equivalents below. These are single-shot 5-15s clips with Seedance 2.0 Fast (bilingual EN/ES, supports multi-image + video references directly, no composite step needed).
- **UGC**: `generate_video(mode="seedance_2_ugc")` — authentic handheld UGC with optional Spanish (Latin) dialogue.
- **Cinematic**: `generate_video(mode="seedance_2_cinematic")` — high-end commercial single-shot cinematic.
- **Product scene**: `generate_video(mode="seedance_2_product")` — standalone product showcase, no person.
If the user's brief requires a full 15/30s produced video (create_ugc_video) or a lip-synced clone, the Seedance toggle does NOT apply — fall back to the default Veo / clone pipelines.

## Common workflows

**Account setup**: create_influencer → create_product → analyze_product_image. Then the user can generate.

**Generate influencer from scratch**: generate_influencer (gated) → returns persona data + profile photo. Then call create_influencer(name, image_url, description, ...) to save permanently.

**Character identity sheet**: list_project_assets → pick influencer → generate_identity(image_url) (gated). Returns 4 reference views (closeup, front, profile, full body).

**Product shot sheet**: list_project_assets → pick product → generate_product_shots(image_url) (gated). Returns 4 professional product views.

**Single UGC clip (5-10s)**: list_project_assets → generate_video(mode="ugc", clip_length=8) (gated). Confirm completion in plain text — the panel renders the video thumbnail automatically.

**Full UGC video (15-30s)**: list_project_assets → (optionally generate_ai_script or generate_scripts to preview hooks) → create_ugc_video (gated). Wait for completion, then confirm in plain text.

**Cinematic clip (5-10s)**: list_project_assets → generate_video(mode="cinematic_video") (gated). Confirm completion in plain text.

**Bulk campaign**: list_project_assets → create_bulk_campaign (gated). Returns immediately with job_ids; tell the user to watch the gallery or check back.

**Schedule distribution**: list_jobs (find finished videos) → list_social_connections (verify platforms) → generate_caption per video if needed → schedule_posts.

**Cleanup assets**: list_project_assets → delete_assets(image_ids=[...], video_ids=[...]). Bulk deletes images and/or videos.

**Add/redo captions (on-screen subtitles)**: caption_video(job_id, style?, placement?) — triggers the same Whisper transcription pipeline as the editor's "Caption video" button. Produces accurate, word-timed subtitles burned onto the video. Do NOT manually construct caption JSON or edit editor_state for captioning — ALWAYS use this tool.

**⚠️ "Caption" disambiguation — MANDATORY before calling either tool:**
The word "caption / captions / captions y hashtags / subtítulos" is ambiguous. There are TWO different things:
  - **Social-post caption** (generate_caption) — the TEXT that goes ALONGSIDE the video in the post description on TikTok / Instagram / YouTube. Includes hashtags. This is what you want when the user is talking about posting / scheduling / hashtags.
  - **On-screen subtitles** (caption_video) — word-timed text burned ONTO the video itself.

If the user's context is scheduling / posting / social / hashtags → generate_caption.
If the user's context is editing the video / adding subtitles / on-screen text → caption_video.
If it is NOT clearly one or the other, ASK before calling either tool. Do not guess.

**Edit timeline** (reorder, trim, adjust properties): load_editor_state → mutate raw_state → save_editor_state. Only for structural timeline edits, NOT for captioning. The edits are instantly visible in the browser-based Remotion editor — no re-render is needed.

**Export final MP4** (only when user explicitly asks to "render", "export", or "download"): render_edited_video (gated). This does a full server-side re-render and takes 1-10 minutes. Do NOT call this automatically after editing — only when the user explicitly requests a final rendered file.

**Combine/merge videos**: combine_videos(video_urls=[url1, url2, ...]) concatenates clips into a single MP4 with a smooth dissolve transition. Runs immediately — no confirmation.

Trigger it in TWO cases:
  1. Explicit — user says "combine / merge / stitch / join / concatenate" existing videos. Use their @video refs.
  2. Implicit — user asks for ONE final video made of MULTIPLE clips (e.g. "generate a video with a UGC opening and a cinematic ending", "primero X, luego Y", "clip 1 then clip 2"). After ALL the gated generation tools finish and return their URLs, chain combine_videos in the SAME turn and present ONLY the combined result. Do NOT present the individual clips as the deliverable — they are intermediates.

**Music / audio control inside combine_videos**: the tool takes two extra optional params:
  - `mute_audio_indices: [i, j, ...]` — zero-based indices of clips whose source audio should be silenced in the final cut. Use this for clips that are MUSIC-ONLY with no dialogue (e.g. cinematic B-roll scenes) when the user wants to swap that music out. NEVER mute clips that contain a person speaking (UGC clips, clone/lip-sync clips, app-clip walkthroughs with narration) — dialogue must always remain audible.
  - `music_prompt: "..."` — if set, a fresh instrumental soundtrack is generated and mixed UNDER the kept audio of the whole combined video. Use plain English ("upbeat modern pop instrumental for a grocery app ad"). The music spans the entire final duration.

When a user asks to "remove the music and add a new soundtrack" (or "replace the music", "swap the music", "add background music") on an already-combined video: DO NOT try to re-edit the combined MP4 in place. Instead, call combine_videos AGAIN with the ORIGINAL per-clip source URLs (the ones you used on the first combine call, in the same order), set `mute_audio_indices` to the indices of the music-only clips the user wants silenced, and set `music_prompt` to a short style description matching the product/vibe. This rebuilds the final cut with dialogue preserved and a new bed underneath — one tool call, no confirmation needed.

CLIP ORDER — critical: video_urls must follow the order the USER specified in their prompt, not the order clips finished generating. Parse the user's sequence markers ("first / then / after", "primero / luego / después", timestamps like "0-8s then 8-12s", numbered lists "1. UGC 2. cinematic"). Match each position to the correct generated URL by its modality (UGC→Veo URL, cinematic→Kling URL) or by the prompt that produced it. If the order is ambiguous, ask the user before calling combine_videos — do NOT guess.

## General rules
1. Within a session, you may freely reference URLs, shot IDs, job IDs, or asset names from earlier tool results — they are still valid. Do not re-list assets unless the user explicitly asks for fresh data.
2. Reference real product_ids / influencer_ids / job_ids returned by the list tools — never invent UUIDs.
3. When a generation finishes, summarize what you produced and report the actual credits spent. NEVER paste raw asset URLs (Supabase storage links, http(s) URLs to images/videos) or markdown links to assets into your reply. The chat panel automatically renders a thumbnail under your message from the tool's artifact frame — the user already sees the asset visually. Refer to it by name only ("Your 8s clip is ready"). The only exception is short identifiers like job_ids when the user explicitly asks for them.
4. Pick the simplest tool chain that fulfills the brief. Don't run extra tools "to be safe".
5. Long-running tools (create_ugc_video, create_clone_video, animate_image, render_edited_video, caption_video) block while polling. That's normal — let them finish.
6. NEVER manually construct or modify caption/transcription JSON inside editor_state. Always use the caption_video tool — it runs real Whisper transcription on the audio and produces accurate, properly timed captions.
7. You may call multiple tools in a single turn. For independent tasks (e.g., "generate 3 images"), dispatch all of them in the same turn and report all results together. For dependent tasks (e.g., "generate an image then animate it"), chain the tools sequentially within the same turn — call the first tool, receive its result, then immediately call the next without waiting for user input. Never ask for permission between chained steps.
8. REFERENCED ASSETS — uploaded images the user attached directly from their computer appear in the brief preface as `[Referenced assets]` lines with synthetic tags like `@upload_xxxxxxxx (image), image_url='https://…'`. These are NOT database rows — there is no product_id / influencer_id for them. When the user asks you to generate / animate / compose using those images, you MUST forward the image_urls to the generation tool:
   - `generate_image` → pass every relevant upload URL via `reference_image_urls: [url1, url2, ...]`. NanoBanana Pro uses them as direct visual references so the output actually contains the uploaded product/person. Failing to pass them means the model generates from prompt text only and the attached images are ignored.
   - `generate_video` → for Seedance modes (seedance_2_ugc / seedance_2_cinematic / seedance_2_product) pass EVERY relevant upload URL via `reference_image_urls: [url1, url2, ...]` — Seedance 2.0 accepts up to 4 references and blends them (e.g. product + model). For Veo/Kling modes (ugc, cinematic_video) pass the most-relevant single URL via `reference_image_url` (first-frame / hero shot) since those models only accept one.
   Only fall back to `product_id` / `influencer_id` when the user @-mentioned an existing DB asset; for raw uploads (upload_* tags) those IDs do not exist.
   IMPORTANT: `reference_image_urls` / `reference_video_urls` are ONLY for `upload_*` tags. For @-mentioned DB entities (products / influencers / app clips), forward the IDs (`product_id`, `influencer_id`, `app_clip_id`) and NOTHING else — the pipeline resolves every image / video URL server-side. Mixing IDs with explicit URLs causes duplicate references and face-swap artifacts.
9. UGC mode does NOT require a registered product. If the user provides uploaded images (upload_* refs), call `generate_image(mode="ugc", reference_image_urls=[...])` directly — the pipeline treats the first upload as the product and any additional upload as the character/influencer. Do not suggest switching to iPhone look or ask the user to create a product first when uploads are already present. Only create or request a registered product when the user explicitly asks to save the asset for future reuse.
10. ASPECT RATIO — MANDATORY before gated generation. Before calling `generate_image` or `generate_video` with `confirmed=true`, you MUST know the aspect ratio. If the user's brief already specifies it ("vertical", "9:16", "horizontal", "16:9", "for TikTok", "for YouTube", "landscape", "portrait"), use it directly. Otherwise you MUST ask the user BEFORE presenting the cost confirmation: ask the question in one short sentence, then append the literal marker `[[ASPECT_BUTTONS]]` on the last line of your message. The frontend detects this marker and renders clickable Vertical / Horizontal buttons for the user. When the user replies with their choice, THEN show the cost confirmation, THEN call the tool with `confirmed=true` and `aspect_ratio="9:16"` or `"16:9"`. Never skip this step for gated generation. Do NOT include the marker when the aspect is already known.
11. NO RANDOM INFLUENCER / PRODUCT — for cinematic / scene / b-roll prompts that do not mention a specific person or product (e.g. "rooftop chase", "sunset over a city", "close-up of a coffee cup"), you MUST call `generate_video` WITHOUT `influencer_id` and WITHOUT `product_id`. Never auto-attach an influencer or product "to be safe" — the pipeline will generate the scene from the prompt alone, which is what the user wants. Only pass `influencer_id` / `product_id` when the user @-mentioned that asset or explicitly named them in the brief.
12. DIGITAL PRODUCTS — when the user @-mentions a digital product (app / SaaS / software), the `[Referenced assets]` preface includes both `product_id=...` AND `app_clip_id=...` (the specific clip the user picked from the shot modal). You MUST forward BOTH to `generate_video` along with `product_type='digital'`. The pipeline renders the generated clip (composited inside a phone for 9:16 / a computer for 16:9). Then — **in the SAME turn, immediately after `generate_video` returns status=success** — you MUST chain `splice_app_clip(job_id=<returned_job_id>, app_clip_id=<same_app_clip_id>)` to append the app clip walkthrough as B-roll with a dissolve transition. Present the splice step in natural language ("Your cinematic is ready — now splicing the app clip as B-roll...") so the user knows what's happening during the ~1-2 min splice. This two-step flow applies to ALL modes (ugc, cinematic_video, seedance_2_ugc, seedance_2_cinematic, seedance_2_product). Do NOT call `combine_videos` for the app-clip splice — that's what `splice_app_clip` is for. `combine_videos` is only for stitching two *independently generated* videos the user explicitly asked to combine. Never call `list_app_clips` to pick a clip manually — the preface already tells you which one. NEVER pass the app clip's first_frame_url (or any URL derived from the clip) as `reference_image_url` / `reference_image_urls` / `reference_video_urls` — the Seedance pipeline uses the clip's VIDEO as a reference server-side. Forwarding a URL in addition to `app_clip_id` causes duplicate references."""


# ── Tool definitions exposed to the agent ─────────────────────────────
def _custom_tools_for_agent() -> list[dict]:
    director_styles = sorted(DIRECTOR_STYLES)
    ugc_styles = sorted(UGC_STYLES)
    image_mode_ids = list(IMAGE_MODES.keys())
    video_mode_ids = list(VIDEO_MODES.keys())

    confirmed_desc = (
        "Set to true ONLY after the user has explicitly confirmed the credit cost shown by the previous "
        "call. First call MUST omit this or pass false — that returns a cost estimate without spending credits."
    )

    return [
        # ── Discovery (read-only, free) ───────────────────────────────
        {
            "type": "custom",
            "name": "list_project_assets",
            "description": "List the products, influencers, and recent shots available in the current Aitoma project. Call once at the start of a fresh session.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "custom",
            "name": "list_projects",
            "description": "List all of the user's Aitoma projects.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "custom",
            "name": "list_influencers",
            "description": "List all influencers (AI personas) the user has access to.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "custom",
            "name": "list_products",
            "description": "List all products (physical and digital) the user has created.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "custom",
            "name": "list_scripts",
            "description": "List UGC scripts. Optionally filter to a single product.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Optional product UUID to filter by."},
                },
                "required": [],
            },
        },
        {
            "type": "custom",
            "name": "list_jobs",
            "description": "List recent video generation jobs (full UGC videos). Optional status filter ('pending'|'processing'|'success'|'failed').",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Optional status filter."},
                    "limit": {"type": "integer", "description": "Max number of jobs to return (default 25)."},
                },
                "required": [],
            },
        },
        {
            "type": "custom",
            "name": "get_job_status",
            "description": "Get current status, progress, and final video URL of a single job.",
            "input_schema": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        },
        {
            "type": "custom",
            "name": "list_scheduled_posts",
            "description": "List posts scheduled to social platforms (TikTok / IG / YouTube / etc.).",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "custom",
            "name": "list_social_connections",
            "description": "List which social platforms the user has connected for posting.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "type": "custom",
            "name": "get_wallet",
            "description": "Get the user's current credit balance and recent transactions.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },

        # ── Cost preview (free) ────────────────────────────────────────
        {
            "type": "custom",
            "name": "estimate_credits",
            "description": (
                "Preview the credit cost of one or more operations BEFORE running them. "
                "Use this for multi-step plans so you can present a single bundled total to the user."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "operations": {
                        "type": "array",
                        "description": "List of operations to estimate.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "operation": {
                                    "type": "string",
                                    "enum": [
                                        "generate_image", "animate_image", "generate_video",
                                        "generate_influencer", "generate_identity", "generate_product_shots",
                                    ],
                                },
                                "mode": {"type": "string", "description": "For generate_video: ugc|cinematic_video|ai_clone."},
                                "clip_length": {"type": "integer", "description": "For generate_video."},
                            },
                            "required": ["operation"],
                        },
                    },
                },
                "required": ["operations"],
            },
        },

        # ── Generation (gated by confirmed=true) ──────────────────────
        {
            "type": "custom",
            "name": "generate_image",
            "description": (
                "Generate a still image via the Creative OS image pipeline. "
                "FIRST call returns a credit cost estimate without spending credits. "
                "After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "Detailed visual prompt for the image."},
                    "mode": {"type": "string", "enum": image_mode_ids, "description": "Image style mode."},
                    "product_id": {"type": "string", "description": "Optional product ID from list_project_assets."},
                    "influencer_id": {"type": "string", "description": "Optional influencer ID from list_project_assets."},
                    "reference_image_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Public image URLs to use as visual references for the NanoBanana generation. "
                            "Pass every image_url from the '[Referenced assets]' preface that is relevant to this "
                            "shot (e.g. uploaded product photo + uploaded influencer photo when neither is a "
                            "DB-backed product_id/influencer_id). These are fed directly into the model as input "
                            "images so the output matches the references."
                        ),
                    },
                    "aspect_ratio": {
                        "type": "string",
                        "enum": ["9:16", "16:9"],
                        "description": (
                            "Image aspect ratio. '9:16' = vertical, '16:9' = horizontal. REQUIRED: you must "
                            "ask the user which ratio they want before calling this tool with confirmed=true, "
                            "unless the user already specified it in their brief."
                        ),
                    },
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["prompt", "mode"],
            },
        },
        {
            "type": "custom",
            "name": "animate_image",
            "description": (
                "Animate a still image into a 5s or 10s Kling 3.0 video clip with the chosen camera move. "
                "FIRST call returns a credit cost estimate without spending credits. "
                "After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "Public URL of the still image to animate."},
                    "style": {
                        "type": "string",
                        "enum": director_styles + ugc_styles,
                        "description": f"Camera move. Director styles: {director_styles}. UGC styles: {ugc_styles}.",
                    },
                    "duration": {"type": "integer", "enum": [5, 10], "description": "Clip duration in seconds (default 5)."},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["image_url", "style"],
            },
        },
        {
            "type": "custom",
            "name": "generate_video",
            "description": (
                "Generate a video clip from a text prompt. ALWAYS pass product_id and/or influencer_id "
                "when the user references a product or model — the pipeline will automatically build a "
                "NanoBanana Pro composite of the influencer holding the product before animating with "
                "Veo 3.1, so both references make it into the final clip. Only fall back to "
                "reference_image_url when the user uploaded a custom image. "
                "If the referenced product is digital, pass product_type='digital' and app_clip_id from the "
                "[Referenced assets] preface. The pipeline renders the clip's first frame inside a phone "
                "(9:16 clip) or computer (16:9 clip) and concats the full app clip as B-roll — "
                "automatic in ALL modes, so never call combine_videos to splice the app clip. "
                "FIRST call returns a credit cost estimate; after user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "mode": {"type": "string", "enum": video_mode_ids},
                    "product_id": {
                        "type": "string",
                        "description": (
                            "Product UUID. Pass this whenever the user @-mentioned a product so the "
                            "actual product image is used in the composite."
                        ),
                    },
                    "influencer_id": {
                        "type": "string",
                        "description": (
                            "Influencer UUID. Pass this whenever the user @-mentioned a model/persona."
                        ),
                    },
                    "reference_image_url": {
                        "type": "string",
                        "description": (
                            "Single direct image URL to use as the first frame. Use for Veo/Kling modes "
                            "(ugc, cinematic_video) when the user uploaded ONE custom image. For multiple "
                            "uploads use reference_image_urls instead."
                        ),
                    },
                    "reference_image_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Multiple reference image URLs. REQUIRED for Seedance modes "
                            "(seedance_2_ugc, seedance_2_cinematic, seedance_2_product) when the user "
                            "attached multiple uploads (e.g. product + model) — Seedance 2.0 accepts up to "
                            "4 references and blends them. Pass EVERY relevant upload URL from the "
                            "'[Referenced assets]' preface. Not used by Veo/Kling modes."
                        ),
                    },
                    "clip_length": {"type": "integer", "enum": [5, 8, 10]},
                    "aspect_ratio": {
                        "type": "string",
                        "enum": ["9:16", "16:9"],
                        "description": (
                            "Video aspect ratio. '9:16' = vertical (TikTok/Reels), '16:9' = horizontal "
                            "(YouTube/landscape). REQUIRED: you must ask the user which ratio they want "
                            "before calling this tool with confirmed=true, unless the user already specified "
                            "it in their brief."
                        ),
                    },
                    "product_type": {
                        "type": "string",
                        "enum": ["physical", "digital"],
                        "description": (
                            "Type of the referenced product. Pass 'digital' whenever the referenced product "
                            "is a digital product (app / SaaS / software) so the composite renders the app "
                            "inside a device and the app clip is concatenated as B-roll. Defaults to "
                            "'physical' when omitted."
                        ),
                    },
                    "app_clip_id": {
                        "type": "string",
                        "description": (
                            "UUID of the specific app clip to use as composite reference and B-roll. "
                            "REQUIRED when product_type='digital'. Read it from the [Referenced assets] "
                            "preface (app_clip_id=...). Never fetch manually via list_app_clips."
                        ),
                    },
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["prompt", "mode"],
            },
        },

        # ── Image generation & identity (gated) ───────────────────────
        {
            "type": "custom",
            "name": "generate_influencer",
            "description": (
                "Generate a random AI influencer persona (name, gender, age, description) + NanoBanana Pro "
                "profile photo in one step. No inputs needed. "
                "FIRST call returns a credit cost estimate. After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": [],
            },
        },
        {
            "type": "custom",
            "name": "generate_identity",
            "description": (
                "Generate a 4-view character identity sheet from a profile photo "
                "(closeup, front, profile, full body). Returns 4 individual view URLs. "
                "FIRST call returns a credit cost estimate. After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "Public URL of the influencer's profile photo."},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["image_url"],
            },
        },
        {
            "type": "custom",
            "name": "generate_product_shots",
            "description": (
                "Generate a 4-view professional product shot sheet from a product image "
                "(hero, functional, macro detail, alternate angle). Returns 4 individual view URLs. "
                "FIRST call returns a credit cost estimate. After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_url": {"type": "string", "description": "Public URL of the product image."},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["image_url"],
            },
        },

        # ── AI scripting (free) ───────────────────────────────────────
        {
            "type": "custom",
            "name": "generate_ai_script",
            "description": (
                "Generate an AI script adapted to a specific clip length, product, and influencer context. "
                "Free — no credits. Two modes: single-clip script (default) or full multi-scene script "
                "for 15/30s videos (set full_video_mode=true)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Product UUID for context."},
                    "influencer_id": {"type": "string", "description": "Influencer UUID for context."},
                    "clip_length": {"type": "integer", "enum": [5, 8, 10, 15, 30], "description": "Target clip length in seconds."},
                    "full_video_mode": {"type": "boolean", "description": "True for multi-scene 15/30s script, false for single-clip."},
                    "context": {"type": "string", "description": "Creative direction / angle for the script."},
                    "language": {"type": "string", "description": "ISO language code (e.g. 'en', 'es'). Default 'en'."},
                },
                "required": [],
            },
        },

        # ── Asset management (free) ───────────────────────────────────
        {
            "type": "custom",
            "name": "list_app_clips",
            "description": "List background video clips (B-roll library). Optionally filter by product_id.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string", "description": "Optional product UUID to filter by."},
                },
                "required": [],
            },
        },
        {
            "type": "custom",
            "name": "manage_app_clips",
            "description": (
                "Create, update, or delete an app clip (B-roll video). "
                "action: 'create' | 'update' | 'delete'."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["create", "update", "delete"]},
                    "clip_id": {"type": "string", "description": "Required for update/delete."},
                    "name": {"type": "string", "description": "Clip name (for create/update)."},
                    "video_url": {"type": "string", "description": "Video URL (for create/update)."},
                    "product_id": {"type": "string", "description": "Link clip to a product."},
                    "description": {"type": "string", "description": "Clip description."},
                },
                "required": ["action"],
            },
        },
        {
            "type": "custom",
            "name": "delete_assets",
            "description": "Delete one or more images (shots) and/or videos (jobs) from the current project.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "image_ids": {"type": "array", "items": {"type": "string"}, "description": "Shot IDs to delete."},
                    "video_ids": {"type": "array", "items": {"type": "string"}, "description": "Job IDs to delete."},
                },
                "required": [],
            },
        },

        # ── Account / asset creation (free) ───────────────────────────
        {
            "type": "custom",
            "name": "create_project",
            "description": "Create a new Aitoma project (workspace for grouping assets and videos).",
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
            },
        },
        {
            "type": "custom",
            "name": "create_influencer",
            "description": (
                "Create a new AI influencer (persona) the user can later use in UGC videos. "
                "Pass any subset of the supported fields. The image_url should reference an "
                "uploaded headshot if available."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "image_url": {"type": "string"},
                    "elevenlabs_voice_id": {"type": "string"},
                    "gender": {"type": "string"},
                    "age": {"type": "string"},
                    "ethnicity": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        {
            "type": "custom",
            "name": "create_product",
            "description": (
                "Create a new product (physical or digital). After creation you can call "
                "analyze_product_image / analyze_digital_product to enrich it with marketing copy."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "product_type": {"type": "string", "enum": ["physical", "digital"]},
                    "image_url": {"type": "string"},
                    "website_url": {"type": "string"},
                    "price": {"type": "string"},
                },
                "required": ["name"],
            },
        },
        {
            "type": "custom",
            "name": "analyze_product_image",
            "description": "Run vision analysis on a physical product's image to enrich its description / metadata.",
            "input_schema": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
        {
            "type": "custom",
            "name": "analyze_digital_product",
            "description": "Run analysis on a digital product (e.g. SaaS / app) to enrich its description.",
            "input_schema": {
                "type": "object",
                "properties": {"product_id": {"type": "string"}},
                "required": ["product_id"],
            },
        },
        {
            "type": "custom",
            "name": "generate_scripts",
            "description": (
                "Generate UGC script variations for a product (LLM-only, free). "
                "Returns multiple hooks/scripts the user can pick from before creating a full video."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "product_id": {"type": "string"},
                    "duration": {"type": "integer", "enum": [15, 30]},
                    "product_type": {"type": "string", "enum": ["physical", "digital"]},
                    "influencer_id": {"type": "string"},
                    "context": {"type": "string", "description": "Optional creative direction / angle."},
                    "video_language": {"type": "string", "description": "ISO language code (e.g. 'en', 'es')."},
                },
                "required": ["product_id"],
            },
        },

        # ── Full UGC pipelines (gated) ────────────────────────────────
        {
            "type": "custom",
            "name": "create_ugc_video",
            "description": (
                "Generate a full 15s or 30s UGC video (script → TTS → scenes → captions → music → assemble). "
                "Takes 5-12 minutes. FIRST call returns a credit cost estimate without spending credits. "
                "After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "influencer_id": {"type": "string"},
                    "product_id": {"type": "string"},
                    "product_type": {"type": "string", "enum": ["physical", "digital"]},
                    "duration": {"type": "integer", "enum": [15, 30]},
                    "script_id": {"type": "string", "description": "Optional pre-generated script id."},
                    "hook": {"type": "string", "description": "Optional hook line override."},
                    "campaign_name": {"type": "string"},
                    "video_language": {"type": "string"},
                    "subtitles_enabled": {"type": "boolean"},
                    "music_enabled": {"type": "boolean"},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["influencer_id", "duration"],
            },
        },
        {
            "type": "custom",
            "name": "create_clone_video",
            "description": (
                "Generate an AI Clone (lip-synced talking head) video using a previously trained voice clone. "
                "Separate pipeline from standard UGC. Takes 5-12 minutes. "
                "FIRST call returns a credit cost estimate. After user confirms, call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "clone_id": {"type": "string"},
                    "script_text": {"type": "string"},
                    "duration": {"type": "integer", "enum": [15, 30]},
                    "product_id": {"type": "string"},
                    "product_type": {"type": "string", "enum": ["physical", "digital"]},
                    "video_language": {"type": "string"},
                    "subtitles_enabled": {"type": "boolean"},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["clone_id", "script_text"],
            },
        },
        {
            "type": "custom",
            "name": "create_bulk_campaign",
            "description": (
                "Dispatch a bulk campaign of N UGC videos (script variations auto-generated). "
                "Returns immediately after dispatch — campaigns can take hours; track via list_jobs / get_job_status. "
                "FIRST call returns a credit cost estimate (count × per-video). After user confirms, "
                "call again with confirmed=true."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "influencer_id": {"type": "string"},
                    "count": {"type": "integer", "description": "Number of videos to generate (1-50)."},
                    "duration": {"type": "integer", "enum": [15, 30]},
                    "product_type": {"type": "string", "enum": ["physical", "digital"]},
                    "product_id": {"type": "string"},
                    "campaign_name": {"type": "string"},
                    "video_language": {"type": "string"},
                    "subtitles_enabled": {"type": "boolean"},
                    "music_enabled": {"type": "boolean"},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["influencer_id", "count", "duration"],
            },
        },

        # ── Scheduling & social posting (free) ────────────────────────
        {
            "type": "custom",
            "name": "schedule_posts",
            "description": (
                "Schedule one or more completed videos to social platforms (TikTok / Instagram / "
                "YouTube / Facebook / X / LinkedIn) via Ayrshare. Free — no credit cost. "
                "Each post needs video_job_id, platforms (list of platform names), and scheduled_at "
                "(ISO 8601 UTC). Optionally include a caption (or call generate_caption first)."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "posts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "video_job_id": {"type": "string"},
                                "platforms": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "scheduled_at": {"type": "string", "description": "ISO 8601 UTC datetime."},
                                "caption": {"type": "string"},
                            },
                            "required": ["video_job_id", "platforms", "scheduled_at"],
                        },
                    },
                },
                "required": ["posts"],
            },
        },
        {
            "type": "custom",
            "name": "cancel_scheduled_post",
            "description": "Cancel a previously scheduled social post by id.",
            "input_schema": {
                "type": "object",
                "properties": {"post_id": {"type": "string"}},
                "required": ["post_id"],
            },
        },
        {
            "type": "custom",
            "name": "generate_caption",
            "description": (
                "Generate a platform-specific caption for a completed video using its script context. "
                "Free. Call before schedule_posts if the user hasn't supplied one."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "video_job_id": {"type": "string"},
                    "platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube", "facebook", "twitter", "linkedin"]},
                },
                "required": ["video_job_id"],
            },
        },

        # ── Remotion editor ───────────────────────────────────────────
        {
            "type": "custom",
            "name": "caption_video",
            "description": (
                "Add word-level captions to a completed video using the editor's built-in "
                "Whisper transcription pipeline. This is the SAME flow as clicking 'Caption video' "
                "in the editor UI — accurate, timed captions from the actual audio. "
                "ALWAYS use this instead of manually constructing caption JSON in editor_state. "
                "Free — no credits."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string", "description": "Video job ID."},
                    "style": {
                        "type": "string",
                        "enum": ["hormozi", "minimal", "bold", "karaoke"],
                        "description": "Caption visual style. Default: hormozi.",
                    },
                    "placement": {
                        "type": "string",
                        "enum": ["top", "middle", "bottom"],
                        "description": "Vertical position on screen. Default: middle.",
                    },
                },
                "required": ["job_id"],
            },
        },
        {
            "type": "custom",
            "name": "load_editor_state",
            "description": (
                "Load the editable Remotion timeline state for a completed video job. "
                "Returns scene/caption counts plus the raw_state object you can mutate. Free."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
        },
        {
            "type": "custom",
            "name": "save_editor_state",
            "description": (
                "Persist a modified editor_state JSON object back to a video job. "
                "Use this after mutating the raw_state from load_editor_state. Free — no render."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "editor_state": {"type": "object", "description": "Full Remotion editor state JSON."},
                },
                "required": ["job_id", "editor_state"],
            },
        },
        {
            "type": "custom",
            "name": "render_edited_video",
            "description": (
                "Re-render a video from its (possibly edited) Remotion timeline into a final MP4. "
                "ONLY call this when the user explicitly asks to 'render', 'export', or 'download' — "
                "NOT automatically after editing captions or timeline changes (save_editor_state is enough for those). "
                "FIRST call returns a flat credit cost. After user confirms, call again with confirmed=true. "
                "Takes 1-10 minutes."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "editor_state": {"type": "object"},
                    "codec": {"type": "string", "enum": ["h264", "h265"]},
                    "confirmed": {"type": "boolean", "description": confirmed_desc},
                },
                "required": ["job_id", "editor_state"],
            },
        },

        # ── App-clip B-roll splice (digital products) ────────────────
        {
            "type": "custom",
            "name": "splice_app_clip",
            "description": (
                "Append an app clip as B-roll to a completed generate_video job, with a dissolve "
                "transition. DIGITAL PRODUCTS ONLY — chain this immediately after generate_video "
                "succeeds, passing the returned job_id and the app_clip_id from the [Referenced "
                "assets] preface. Takes ~1-2 min (download + ffmpeg + upload). Free — no "
                "confirmation. On success, the job's final_video_url is updated to the spliced "
                "version; the pre-splice URL is kept in metadata.pre_splice_url."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "The job_id returned by generate_video (must be status=success with a final_video_url).",
                    },
                    "app_clip_id": {
                        "type": "string",
                        "description": "The app clip to append as B-roll. Use the app_clip_id from the [Referenced assets] preface.",
                    },
                },
                "required": ["job_id", "app_clip_id"],
            },
        },

        # ── Video combination ─────────────────────────────────────────
        {
            "type": "custom",
            "name": "combine_videos",
            "description": (
                "Combine (concatenate) two or more videos into a single MP4 with smooth dissolve "
                "transitions. video_urls MUST be in the order the user requested in their prompt — "
                "NOT the order clips finished generating. Match each slot by modality (UGC clip = Veo "
                "URL, cinematic clip = Kling URL) or by the originating prompt. Runs automatically — "
                "no confirmation needed. Optional audio controls: silence specific source clips via "
                "mute_audio_indices (use ONLY for music-only clips with no dialogue — never mute clips "
                "containing a person speaking) and/or generate a fresh instrumental soundtrack via "
                "music_prompt that is mixed UNDER the kept dialogue for the full duration. These two "
                "params together are how you 'swap the music' on an already-combined video: call this "
                "tool again with the SAME source URLs in the SAME order, plus the mute list and music "
                "prompt."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "video_urls": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Ordered list of public video URLs to concatenate. Order MUST reflect the user's requested sequence, not generation completion order.",
                    },
                    "transition": {
                        "type": "string",
                        "enum": ["dissolve", "wipeleft", "wiperight", "fade", "none"],
                        "description": "Transition effect between clips. Default: dissolve.",
                    },
                    "transition_duration": {
                        "type": "number",
                        "description": "Transition duration in seconds (0.3-1.5). Default: 0.6.",
                    },
                    "mute_audio_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Zero-based indices (into video_urls) of clips whose source audio should be silenced in the final cut. Use ONLY for music-only / no-dialogue clips (e.g. cinematic B-roll) when the user wants to swap the music. NEVER include a clip that contains a person speaking.",
                    },
                    "music_prompt": {
                        "type": "string",
                        "description": "Optional short English style description of a background soundtrack to generate and mix UNDER the kept dialogue (e.g. 'upbeat modern pop instrumental for a grocery app ad'). When set, the whole combined video gets a fresh instrumental bed at a dialogue-safe level. Leave unset to keep the source audio untouched.",
                    },
                },
                "required": ["video_urls"],
            },
        },
    ]


# ── Per-call execution context ────────────────────────────────────────
@dataclass
class ToolContext:
    user_token: str
    project_id: Optional[str]
    artifacts: list[dict] = field(default_factory=list)
    new_artifacts: list[dict] = field(default_factory=list)

    def core(self) -> CoreAPIClient:
        return CoreAPIClient(token=self.user_token, project_id=self.project_id)


# ── Tool implementations (unchanged from v1) ──────────────────────────
async def _tool_list_project_assets(ctx: ToolContext, **_: Any) -> str:
    core = ctx.core()
    products: list = []
    influencers: list = []
    shots: list = []
    try:
        products = await core.list_products()
    except Exception as e:  # pragma: no cover - best-effort
        products = [{"error": f"list_products failed: {e}"}]
    try:
        influencers = await core.list_influencers()
    except Exception as e:
        influencers = [{"error": f"list_influencers failed: {e}"}]
    if ctx.project_id:
        try:
            shots = await core.list_project_shots(ctx.project_id)
        except Exception as e:
            shots = [{"error": f"list_project_shots failed: {e}"}]

    def slim(items: list, keys: list[str]) -> list[dict]:
        out = []
        for it in items[:20]:
            if not isinstance(it, dict):
                continue
            out.append({k: it.get(k) for k in keys if k in it})
        return out

    return json.dumps(
        {
            "project_id": ctx.project_id,
            "products": slim(products, ["id", "name", "description"]),
            "influencers": slim(influencers, ["id", "name", "image_url"]),
            "recent_shots": slim(shots, ["id", "image_url", "shot_type", "created_at"]),
        }
    )


def _record_artifact(ctx: ToolContext, artifact: dict) -> None:
    ctx.artifacts.append(artifact)
    ctx.new_artifacts.append(artifact)


# ── Credit cost helpers ───────────────────────────────────────────────
def _credits_for_op(operation: str, params: dict) -> int:
    """Single source of truth for Creative OS operation credit costs.

    Tries to import from `ugc_backend.credit_cost_service` (available when
    running locally with repo root on sys.path). Falls back to a bundled
    copy when deployed standalone on Railway.
    """
    try:
        from ugc_backend.credit_cost_service import (
            get_animate_image_credit_cost,
            get_clone_video_credit_cost,
            get_creative_os_image_credit_cost,
            get_editor_render_credit_cost,
            get_video_clip_credit_cost,
            get_video_credit_cost,
        )
    except ImportError:
        from services.credit_costs import (
            get_animate_image_credit_cost,
            get_clone_video_credit_cost,
            get_creative_os_image_credit_cost,
            get_editor_render_credit_cost,
            get_video_clip_credit_cost,
            get_video_credit_cost,
        )

    if operation in ("generate_image", "generate_influencer", "generate_identity", "generate_product_shots"):
        return get_creative_os_image_credit_cost()
    if operation == "animate_image":
        return get_animate_image_credit_cost(duration=int(params.get("duration", 5)))
    if operation == "generate_video":
        has_reference = bool(
            params.get("reference_image_url")
            or params.get("reference_image_urls")
            or params.get("reference_video_urls")
            or params.get("product_id")
            or params.get("influencer_id")
        )
        try:
            return get_video_clip_credit_cost(
                mode=params.get("mode", "ugc"),
                clip_length=int(params.get("clip_length", 5)),
                has_reference=has_reference,
            )
        except TypeError:
            # Older signature (bundled copy not yet updated)
            return get_video_clip_credit_cost(
                mode=params.get("mode", "ugc"),
                clip_length=int(params.get("clip_length", 5)),
            )
    if operation == "create_ugc_video":
        return get_video_credit_cost(
            product_type=params.get("product_type", "physical"),
            duration=int(params.get("duration", 15)),
        )
    if operation == "create_clone_video":
        return get_clone_video_credit_cost(duration=int(params.get("duration", 15)))
    if operation == "create_bulk_campaign":
        per_video = get_video_credit_cost(
            product_type=params.get("product_type", "physical"),
            duration=int(params.get("duration", 15)),
        )
        return per_video * int(params.get("count", 1))
    if operation == "render_edited_video":
        return get_editor_render_credit_cost()
    if operation == "combine_videos":
        # Use animate_image cost as a proxy for server-side ffmpeg processing
        return get_animate_image_credit_cost(duration=5)
    raise ValueError(f"unknown operation for credit estimate: {operation}")


def _confirmation_payload(operation: str, credits: int, summary: str, echo: dict) -> str:
    """Standard payload returned when a generation tool is called without confirmed=true."""
    return json.dumps({
        "action": "confirmation_required",
        "operation": operation,
        "credits": credits,
        "summary": summary,
        "next_call": {**echo, "confirmed": True},
        "message": (
            f"This will cost {credits} credits. Present this to the user and wait for explicit confirmation. "
            f"After they say yes, you MUST call {operation} again with confirmed=true and the EXACT same parameters. "
            f"Do NOT just reply with text saying the job has started — you must emit a tool_use call. "
            f"The generation only starts when you actually call the tool."
        ),
    })


async def _tool_generate_image(ctx: ToolContext, **kwargs: Any) -> str:
    from routers.generate_image import ExecuteRequest, execute_image_generation

    if not ctx.project_id:
        return json.dumps({"error": "project_id is required to generate images"})

    # Cost confirmation gate — first call previews credits, doesn't spend.
    if not kwargs.get("confirmed"):
        credits = _credits_for_op("generate_image", {})
        return _confirmation_payload(
            operation="generate_image",
            credits=credits,
            summary=f"Generate 1 still image (mode={kwargs.get('mode')})",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    exec_kwargs: dict = dict(
        prompt=kwargs["prompt"],
        mode=kwargs["mode"],
        project_id=ctx.project_id,
        product_id=kwargs.get("product_id"),
        influencer_id=kwargs.get("influencer_id"),
        reference_image_urls=kwargs.get("reference_image_urls") or None,
    )
    if kwargs.get("aspect_ratio"):
        exec_kwargs["aspect_ratio"] = kwargs["aspect_ratio"]
    req = ExecuteRequest(**exec_kwargs)
    user = {"token": ctx.user_token, "id": "agent"}
    try:
        result = await execute_image_generation(req, user=user)  # type: ignore[arg-type]
    except Exception as e:
        return json.dumps({"error": f"generate_image failed: {e}"})

    shots = result.get("shots") or []
    first = shots[0] if shots else {}
    image_url = first.get("image_url")
    shot_id = first.get("id")
    if image_url:
        _record_artifact(ctx, {"type": "image", "url": image_url, "shot_id": shot_id})
    return json.dumps({"shot_id": shot_id, "image_url": image_url, "status": result.get("status")})


async def _tool_animate_image(ctx: ToolContext, **kwargs: Any) -> str:
    from fastapi import BackgroundTasks
    from routers.animate import AnimateRequest, animate_image

    # Cost confirmation gate
    duration = int(kwargs.get("duration", 5))
    if not kwargs.get("confirmed"):
        credits = _credits_for_op("animate_image", {"duration": duration})
        return _confirmation_payload(
            operation="animate_image",
            credits=credits,
            summary=f"Animate image into {duration}s clip (style={kwargs.get('style')})",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    req = AnimateRequest(
        image_url=kwargs["image_url"],
        style=kwargs["style"],
        duration=duration,
        project_id=ctx.project_id,
    )
    user = {"token": ctx.user_token, "id": "agent"}
    bg = BackgroundTasks()
    try:
        result = await animate_image(req, background_tasks=bg, user=user)  # type: ignore[arg-type]
    except Exception as e:
        return json.dumps({"error": f"animate_image failed: {e}"})
    for task in bg.tasks:
        try:
            await task()
        except Exception as e:
            return json.dumps({"error": f"animate background task failed: {e}", "job_id": result.get("job_id")})

    job_id = result.get("job_id")
    if not job_id:
        return json.dumps(result)

    # Poll until Kling 3.0 finishes (typical 60-180s, cap at 6 min). The
    # surrounding SSE generator's CancelledError handler will tear this
    # sleep down if the user clicks Stop.
    max_wait_s = 360
    poll_interval_s = 5
    waited = 0
    final_status: dict | None = None
    while waited < max_wait_s:
        await asyncio.sleep(poll_interval_s)
        waited += poll_interval_s
        try:
            final_status = await ctx.core().get_job_status(job_id)
        except Exception as e:
            print(f"[animate_image] poll error (retrying): {e}")
            continue
        state = (final_status.get("status") or "").lower()
        if state in ("success", "complete", "completed"):
            break
        if state in ("failed", "error"):
            break

    if final_status is None:
        return json.dumps({
            "job_id": job_id,
            "status": "still_processing",
            "warning": "Could not poll job status. The clip will appear in the gallery once Kling finishes.",
        })

    state = (final_status.get("status") or "").lower()
    if state in ("success", "complete", "completed"):
        video_url = final_status.get("final_video_url") or final_status.get("video_url")
        if video_url:
            _record_artifact(ctx, {"type": "video", "url": video_url, "job_id": job_id})
        return json.dumps({"job_id": job_id, "video_url": video_url, "status": "success"})
    if state in ("failed", "error"):
        return json.dumps({
            "error": final_status.get("error_message") or "animation failed",
            "job_id": job_id,
        })
    return json.dumps({
        "job_id": job_id,
        "status": "still_processing",
        "warning": "Animation is taking longer than 6 minutes. The clip will appear in the gallery once Kling finishes.",
    })


async def _tool_generate_video(ctx: ToolContext, **kwargs: Any) -> str:
    from fastapi import BackgroundTasks
    from routers.generate_video import VideoGenerateRequest, generate_video  # type: ignore

    if not ctx.project_id:
        return json.dumps({"error": "project_id is required to generate videos"})

    # Cost confirmation gate
    if not kwargs.get("confirmed"):
        credits = _credits_for_op("generate_video", {
            "mode": kwargs.get("mode", "ugc"),
            "clip_length": kwargs.get("clip_length", 5),
        })
        return _confirmation_payload(
            operation="generate_video",
            credits=credits,
            summary=(
                f"Generate {kwargs.get('clip_length', 5)}s video clip "
                f"(mode={kwargs.get('mode')})"
            ),
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    req = VideoGenerateRequest(
        prompt=kwargs["prompt"],
        mode=kwargs["mode"],
        project_id=ctx.project_id,
        product_id=kwargs.get("product_id"),
        influencer_id=kwargs.get("influencer_id"),
        reference_image_url=kwargs.get("reference_image_url"),
        reference_image_urls=kwargs.get("reference_image_urls") or None,
        reference_video_urls=kwargs.get("reference_video_urls") or None,
        clip_length=kwargs.get("clip_length", 5),
        aspect_ratio=kwargs.get("aspect_ratio") or None,
        product_type=kwargs.get("product_type") or None,
        app_clip_id=kwargs.get("app_clip_id") or None,
    )
    user = {"token": ctx.user_token, "id": "agent"}
    bg = BackgroundTasks()
    try:
        result = await generate_video(req, bg, user=user)  # type: ignore[arg-type]
    except Exception as e:
        return json.dumps({"error": f"generate_video failed: {e}"})

    # The handler returns immediately with {status: "generating", job_id, ...}
    # and queues the actual rendering on `bg`. Drain it ourselves so the
    # pipeline runs to completion inline. CancelledError from the SSE
    # generator propagates through these awaits → Stop works.
    job_id = result.get("job_id") if isinstance(result, dict) else None
    for task in bg.tasks:
        try:
            await task()
        except Exception as e:
            return json.dumps({"error": f"video background task failed: {e}", "job_id": job_id})

    if not job_id:
        return json.dumps(result if isinstance(result, dict) else {"result": str(result)})

    # By the time the background task returns, the Supabase row holds the
    # terminal state. One read is enough.
    try:
        final_status = await ctx.core().get_job_status(job_id)
    except Exception as e:
        return json.dumps({
            "job_id": job_id,
            "status": "still_processing",
            "warning": f"Could not poll final status: {e}",
        })

    state = (final_status.get("status") or "").lower()
    if state in ("success", "complete", "completed"):
        video_url = final_status.get("final_video_url") or final_status.get("video_url")
        if video_url:
            _record_artifact(ctx, {"type": "video", "url": video_url, "job_id": job_id})
        payload: dict = {"job_id": job_id, "video_url": video_url, "status": "success"}
        # Digital-product flows are two-step: generate_video renders the
        # cinematic, then splice_app_clip appends the app walkthrough as
        # B-roll. The agent sometimes forgets the second step and tells the
        # user "auto-spliced" without actually calling the tool. Emit an
        # explicit required-next-step instruction in the tool result so the
        # chain is enforced regardless of system-prompt recall.
        app_clip_id = kwargs.get("app_clip_id")
        product_type = (kwargs.get("product_type") or "").lower()
        if app_clip_id and product_type == "digital":
            payload["required_next_step"] = {
                "tool": "splice_app_clip",
                "arguments": {"job_id": job_id, "app_clip_id": app_clip_id},
                "reason": (
                    "Digital-product videos must be spliced with the app-clip B-roll. "
                    "Call splice_app_clip NOW in this same turn — do not tell the user "
                    "'auto-spliced' without actually calling the tool. The user will see "
                    "only the raw cinematic until splice_app_clip completes."
                ),
            }
        return json.dumps(payload)
    if state in ("failed", "error"):
        return json.dumps({
            "error": final_status.get("error_message") or "video generation failed",
            "job_id": job_id,
        })
    return json.dumps({
        "job_id": job_id,
        "status": "still_processing",
        "warning": "Video pipeline did not reach a terminal state. Check the gallery shortly.",
    })


# ── Polling helper for long-running jobs ──────────────────────────────
async def _poll_job_until_terminal(
    ctx: ToolContext,
    job_id: str,
    *,
    poll_interval_s: int = 8,
    max_wait_s: int = 900,  # 15 minutes — full UGC pipelines take 5-12min
) -> dict | None:
    """Poll a core job until success/failed or timeout. Returns the final
    status dict (or None if no successful poll happened).

    The surrounding SSE generator's CancelledError handler tears this loop
    down on Stop, so users can interrupt long renders.
    """
    waited = 0
    final_status: dict | None = None
    while waited < max_wait_s:
        await asyncio.sleep(poll_interval_s)
        waited += poll_interval_s
        try:
            final_status = await ctx.core().get_job_status(job_id)
        except Exception as e:
            print(f"[poll_job] error (retrying): {e}")
            continue
        state = (final_status.get("status") or "").lower()
        if state in ("success", "complete", "completed", "failed", "error"):
            return final_status
    return final_status


# ── Discovery / read-only tools ───────────────────────────────────────
def _slim(items: list, keys: list[str], cap: int = 25) -> list[dict]:
    out = []
    for it in items[:cap]:
        if not isinstance(it, dict):
            continue
        out.append({k: it.get(k) for k in keys if k in it})
    return out


async def _tool_list_projects(ctx: ToolContext, **_: Any) -> str:
    try:
        rows = await ctx.core().list_projects()
    except Exception as e:
        return json.dumps({"error": f"list_projects failed: {e}"})
    return json.dumps({"projects": _slim(rows, ["id", "name", "created_at"])})


async def _tool_list_influencers(ctx: ToolContext, **_: Any) -> str:
    try:
        rows = await ctx.core().list_influencers()
    except Exception as e:
        return json.dumps({"error": f"list_influencers failed: {e}"})
    return json.dumps({
        "influencers": _slim(rows, ["id", "name", "image_url", "elevenlabs_voice_id"]),
    })


async def _tool_list_products(ctx: ToolContext, **_: Any) -> str:
    try:
        rows = await ctx.core().list_products()
    except Exception as e:
        return json.dumps({"error": f"list_products failed: {e}"})
    return json.dumps({
        "products": _slim(rows, ["id", "name", "description", "product_type", "image_url"]),
    })


async def _tool_list_scripts(ctx: ToolContext, **kwargs: Any) -> str:
    try:
        rows = await ctx.core().list_scripts(product_id=kwargs.get("product_id"))
    except Exception as e:
        return json.dumps({"error": f"list_scripts failed: {e}"})
    return json.dumps({
        "scripts": _slim(rows, ["id", "title", "duration", "product_id", "hook", "created_at"]),
    })


async def _tool_list_jobs(ctx: ToolContext, **kwargs: Any) -> str:
    try:
        rows = await ctx.core().list_jobs(
            status=kwargs.get("status"),
            limit=int(kwargs.get("limit", 25)),
        )
    except Exception as e:
        return json.dumps({"error": f"list_jobs failed: {e}"})
    return json.dumps({
        "jobs": _slim(rows, [
            "id", "status", "campaign_name", "length", "model_api",
            "final_video_url", "progress", "created_at",
        ]),
    })


async def _tool_get_job_status(ctx: ToolContext, **kwargs: Any) -> str:
    job_id = kwargs.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    try:
        return json.dumps(await ctx.core().get_job_status(job_id))
    except Exception as e:
        return json.dumps({"error": f"get_job_status failed: {e}"})


async def _tool_list_scheduled_posts(ctx: ToolContext, **_: Any) -> str:
    try:
        rows = await ctx.core().list_scheduled_posts()
    except Exception as e:
        return json.dumps({"error": f"list_scheduled_posts failed: {e}"})
    if isinstance(rows, dict):
        rows = rows.get("posts") or rows.get("data") or []
    return json.dumps({
        "scheduled_posts": _slim(rows, [
            "id", "platforms", "scheduled_at", "status", "caption", "video_url",
        ]),
    })


async def _tool_list_social_connections(ctx: ToolContext, **_: Any) -> str:
    try:
        return json.dumps(await ctx.core().list_social_connections())
    except Exception as e:
        return json.dumps({"error": f"list_social_connections failed: {e}"})


async def _tool_get_wallet(ctx: ToolContext, **_: Any) -> str:
    try:
        return json.dumps(await ctx.core().get_wallet())
    except Exception as e:
        return json.dumps({"error": f"get_wallet failed: {e}"})


async def _tool_estimate_credits(_ctx: ToolContext, **kwargs: Any) -> str:
    operations = kwargs.get("operations") or []
    if not isinstance(operations, list) or not operations:
        return json.dumps({"error": "operations must be a non-empty list"})
    line_items = []
    total = 0
    for op in operations:
        try:
            credits = _credits_for_op(op.get("operation"), op)
        except Exception as e:
            return json.dumps({"error": f"could not estimate {op}: {e}"})
        line_items.append({**op, "credits": credits})
        total += credits
    return json.dumps({
        "line_items": line_items,
        "total_credits": total,
        "message": (
            f"Total: {total} credits. Present this to the user and wait for confirmation "
            f"before running the actual generation tools with confirmed=true."
        ),
    })


# ── Phase 2: Asset creation ───────────────────────────────────────────
async def _tool_create_project(ctx: ToolContext, **kwargs: Any) -> str:
    name = (kwargs.get("name") or "").strip()
    if not name:
        return json.dumps({"error": "name is required"})
    try:
        result = await ctx.core().create_project(name=name)
    except Exception as e:
        return json.dumps({"error": f"create_project failed: {e}"})
    return json.dumps({"project": result})


async def _tool_create_influencer(ctx: ToolContext, **kwargs: Any) -> str:
    if not kwargs.get("name"):
        return json.dumps({"error": "name is required"})
    payload = {k: v for k, v in kwargs.items() if v is not None}
    try:
        result = await ctx.core().create_influencer(payload)
    except Exception as e:
        return json.dumps({"error": f"create_influencer failed: {e}"})
    return json.dumps({"influencer": result})


async def _tool_create_product(ctx: ToolContext, **kwargs: Any) -> str:
    if not kwargs.get("name"):
        return json.dumps({"error": "name is required"})
    payload = {k: v for k, v in kwargs.items() if v is not None}
    try:
        result = await ctx.core().create_product(payload)
    except Exception as e:
        return json.dumps({"error": f"create_product failed: {e}"})
    return json.dumps({"product": result})


async def _tool_analyze_product_image(ctx: ToolContext, **kwargs: Any) -> str:
    pid = kwargs.get("product_id")
    if not pid:
        return json.dumps({"error": "product_id is required"})
    try:
        return json.dumps({"analysis": await ctx.core().analyze_product_image(pid)})
    except Exception as e:
        return json.dumps({"error": f"analyze_product_image failed: {e}"})


async def _tool_analyze_digital_product(ctx: ToolContext, **kwargs: Any) -> str:
    pid = kwargs.get("product_id")
    if not pid:
        return json.dumps({"error": "product_id is required"})
    try:
        return json.dumps(await ctx.core().analyze_digital_product(pid))
    except Exception as e:
        return json.dumps({"error": f"analyze_digital_product failed: {e}"})


async def _tool_generate_scripts(ctx: ToolContext, **kwargs: Any) -> str:
    """Script generation is free (LLM only) — no credit gate."""
    pid = kwargs.get("product_id")
    if not pid:
        return json.dumps({"error": "product_id is required"})
    try:
        result = await ctx.core().generate_scripts(
            product_id=pid,
            duration=int(kwargs.get("duration", 15)),
            product_type=kwargs.get("product_type", "physical"),
            influencer_id=kwargs.get("influencer_id"),
            context=kwargs.get("context"),
            video_language=kwargs.get("video_language", "en"),
        )
    except Exception as e:
        return json.dumps({"error": f"generate_scripts failed: {e}"})
    return json.dumps(result)


# ── Phase 3: Full UGC video + clone + bulk campaign ───────────────────
async def _tool_create_ugc_video(ctx: ToolContext, **kwargs: Any) -> str:
    """Full 15s/30s UGC video — script → TTS → scenes → captions → music → assemble."""
    if not kwargs.get("influencer_id"):
        return json.dumps({"error": "influencer_id is required"})
    duration = int(kwargs.get("duration", 15))
    if duration not in (15, 30):
        return json.dumps({"error": "duration must be 15 or 30"})
    product_type = kwargs.get("product_type", "physical")

    # Cost confirmation gate
    if not kwargs.get("confirmed"):
        credits = _credits_for_op("create_ugc_video", {"product_type": product_type, "duration": duration})
        return _confirmation_payload(
            operation="create_ugc_video",
            credits=credits,
            summary=f"Generate full {duration}s UGC video ({product_type} product)",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    payload = {
        "influencer_id": kwargs["influencer_id"],
        "product_type": product_type,
        "length": duration,
        "product_id": kwargs.get("product_id"),
        "script_id": kwargs.get("script_id"),
        "hook": kwargs.get("hook"),
        "campaign_name": kwargs.get("campaign_name"),
        "video_language": kwargs.get("video_language", "en"),
        "subtitles_enabled": kwargs.get("subtitles_enabled", True),
        "music_enabled": kwargs.get("music_enabled", True),
        # Agent always uses Veo 3.1 for UGC (not Seedance) — more reliable,
        # routes to the Veo extend pipeline in core_engine.
        "model_api": "veo-3.1-fast",
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        job = await ctx.core().create_ugc_video_job(payload)
    except Exception as e:
        return json.dumps({"error": f"create_ugc_video failed: {e}"})

    job_id = job.get("id") or (job.get("job") or {}).get("id")
    if not job_id:
        return json.dumps({"error": "job created but no id returned", "raw": job})

    final_status = await _poll_job_until_terminal(ctx, job_id, max_wait_s=900)
    if final_status is None:
        return json.dumps({
            "job_id": job_id,
            "status": "still_processing",
            "warning": "Generation is taking longer than 15 minutes. Check the gallery.",
        })
    state = (final_status.get("status") or "").lower()
    if state in ("success", "complete", "completed"):
        video_url = final_status.get("final_video_url") or final_status.get("video_url")
        if video_url:
            _record_artifact(ctx, {"type": "video", "url": video_url, "job_id": job_id})
        return json.dumps({
            "job_id": job_id,
            "video_url": video_url,
            "status": "success",
            "credits_spent": _credits_for_op("create_ugc_video", {"product_type": product_type, "duration": duration}),
        })
    return json.dumps({
        "error": final_status.get("error_message") or "ugc video generation failed",
        "job_id": job_id,
        "status": state,
    })


async def _tool_create_clone_video(ctx: ToolContext, **kwargs: Any) -> str:
    """AI Clone (lip-synced) video — separate pipeline from standard UGC."""
    if not kwargs.get("clone_id"):
        return json.dumps({"error": "clone_id is required"})
    if not kwargs.get("script_text"):
        return json.dumps({"error": "script_text is required"})
    duration = int(kwargs.get("duration", 15))

    if not kwargs.get("confirmed"):
        credits = _credits_for_op("create_clone_video", {"duration": duration})
        return _confirmation_payload(
            operation="create_clone_video",
            credits=credits,
            summary=f"Generate {duration}s AI Clone (lip-synced) video",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    payload = {
        "clone_id": kwargs["clone_id"],
        "script_text": kwargs["script_text"],
        "duration": duration,
        "product_id": kwargs.get("product_id"),
        "product_type": kwargs.get("product_type", "physical"),
        "video_language": kwargs.get("video_language", "en"),
        "subtitles_enabled": kwargs.get("subtitles_enabled", True),
        "project_id": ctx.project_id,
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        job = await ctx.core().create_clone_job(payload)
    except Exception as e:
        return json.dumps({"error": f"create_clone_video failed: {e}"})

    job_id = job.get("id") or (job.get("job") or {}).get("id")
    if not job_id:
        return json.dumps({"error": "clone job created but no id returned", "raw": job})

    final_status = await _poll_job_until_terminal(ctx, job_id, max_wait_s=900)
    if final_status is None:
        return json.dumps({"job_id": job_id, "status": "still_processing"})
    state = (final_status.get("status") or "").lower()
    if state in ("success", "complete", "completed"):
        video_url = final_status.get("final_video_url") or final_status.get("video_url")
        if video_url:
            _record_artifact(ctx, {"type": "video", "url": video_url, "job_id": job_id})
        return json.dumps({
            "job_id": job_id,
            "video_url": video_url,
            "status": "success",
            "credits_spent": _credits_for_op("create_clone_video", {"duration": duration}),
        })
    return json.dumps({
        "error": final_status.get("error_message") or "clone video generation failed",
        "job_id": job_id,
        "status": state,
    })


async def _tool_create_bulk_campaign(ctx: ToolContext, **kwargs: Any) -> str:
    """Bulk campaign — N UGC videos with auto-generated script variations.

    Returns immediately after dispatching all jobs (does NOT block on
    completion — bulk campaigns can take hours). The agent should follow up
    by polling list_jobs / get_job_status, or the user can watch the gallery.
    """
    if not kwargs.get("influencer_id"):
        return json.dumps({"error": "influencer_id is required"})
    count = int(kwargs.get("count", 1))
    if count < 1 or count > 50:
        return json.dumps({"error": "count must be between 1 and 50"})
    duration = int(kwargs.get("duration", 15))
    if duration not in (15, 30):
        return json.dumps({"error": "duration must be 15 or 30"})
    product_type = kwargs.get("product_type", "physical")

    if not kwargs.get("confirmed"):
        credits = _credits_for_op("create_bulk_campaign", {
            "product_type": product_type, "duration": duration, "count": count,
        })
        per_video = credits // count
        return _confirmation_payload(
            operation="create_bulk_campaign",
            credits=credits,
            summary=(
                f"Generate {count} × {duration}s UGC videos "
                f"({product_type}, {per_video} credits each)"
            ),
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    payload = {
        "influencer_id": kwargs["influencer_id"],
        "count": count,
        "duration": duration,
        "product_type": product_type,
        "product_id": kwargs.get("product_id"),
        "campaign_name": kwargs.get("campaign_name"),
        "video_language": kwargs.get("video_language", "en"),
        "subtitles_enabled": kwargs.get("subtitles_enabled", True),
        "music_enabled": kwargs.get("music_enabled", True),
    }
    payload = {k: v for k, v in payload.items() if v is not None}

    try:
        result = await ctx.core().create_bulk_ugc_jobs(payload)
    except Exception as e:
        return json.dumps({"error": f"create_bulk_campaign failed: {e}"})

    # Result is typically a list of created job dicts
    jobs_list = result if isinstance(result, list) else result.get("jobs", [])
    job_ids = [j.get("id") for j in jobs_list if isinstance(j, dict) and j.get("id")]
    return json.dumps({
        "status": "dispatched",
        "count": len(job_ids),
        "job_ids": job_ids,
        "credits_spent": _credits_for_op("create_bulk_campaign", {
            "product_type": product_type, "duration": duration, "count": count,
        }),
        "message": (
            f"{len(job_ids)} jobs dispatched. Bulk campaigns take a while — use list_jobs "
            f"or get_job_status(job_id) to check progress, or watch the gallery."
        ),
    })


# ── Phase 4: Scheduling & social posting ──────────────────────────────
async def _tool_schedule_posts(ctx: ToolContext, **kwargs: Any) -> str:
    """Schedule one or more videos to social platforms via Ayrshare. Free (no credits)."""
    posts = kwargs.get("posts") or []
    if not isinstance(posts, list) or not posts:
        return json.dumps({"error": "posts must be a non-empty list"})
    for p in posts:
        if not p.get("video_job_id") or not p.get("platforms") or not p.get("scheduled_at"):
            return json.dumps({
                "error": "each post needs video_job_id, platforms (list), and scheduled_at (ISO 8601 UTC)",
            })
    try:
        return json.dumps(await ctx.core().schedule_posts(posts))
    except Exception as e:
        return json.dumps({"error": f"schedule_posts failed: {e}"})


async def _tool_cancel_scheduled_post(ctx: ToolContext, **kwargs: Any) -> str:
    pid = kwargs.get("post_id")
    if not pid:
        return json.dumps({"error": "post_id is required"})
    try:
        return json.dumps(await ctx.core().cancel_scheduled_post(pid))
    except Exception as e:
        return json.dumps({"error": f"cancel_scheduled_post failed: {e}"})


async def _tool_generate_caption(ctx: ToolContext, **kwargs: Any) -> str:
    vid = kwargs.get("video_job_id")
    if not vid:
        return json.dumps({"error": "video_job_id is required"})
    try:
        return json.dumps(await ctx.core().generate_caption(
            video_job_id=vid,
            platform=kwargs.get("platform", "instagram"),
        ))
    except Exception as e:
        return json.dumps({"error": f"generate_caption failed: {e}"})


# ── Phase 5: Remotion editor ──────────────────────────────────────────
async def _tool_caption_video(ctx: ToolContext, **kwargs: Any) -> str:
    """Add captions via server-side Whisper — same pipeline as the editor's 'Caption video' button."""
    job_id = kwargs.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    style = kwargs.get("style", "hormozi")
    placement = kwargs.get("placement", "middle")
    try:
        result = await ctx.core().caption_video(job_id, style=style, placement=placement)
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": f"caption_video failed: {e}"})


async def _tool_load_editor_state(ctx: ToolContext, **kwargs: Any) -> str:
    """Load the editable timeline state for a completed video. Free."""
    job_id = kwargs.get("job_id")
    if not job_id:
        return json.dumps({"error": "job_id is required"})
    try:
        state = await ctx.core().get_editor_state(job_id)
    except Exception as e:
        return json.dumps({"error": f"load_editor_state failed: {e}"})
    # State can be huge — return a summary so the agent doesn't blow context.
    summary = {
        "job_id": job_id,
        "has_state": True,
        "scene_count": len(state.get("scenes") or []),
        "caption_count": len(state.get("captions") or state.get("transcription", {}).get("words") or []),
        "duration": state.get("duration"),
        "raw_state": state,  # Full payload available if the agent needs it
    }
    return json.dumps(summary)


async def _tool_save_editor_state(ctx: ToolContext, **kwargs: Any) -> str:
    job_id = kwargs.get("job_id")
    state = kwargs.get("editor_state")
    if not job_id or state is None:
        return json.dumps({"error": "job_id and editor_state are required"})
    try:
        return json.dumps(await ctx.core().save_editor_state(job_id, state))
    except Exception as e:
        return json.dumps({"error": f"save_editor_state failed: {e}"})


async def _tool_render_edited_video(ctx: ToolContext, **kwargs: Any) -> str:
    """Render a Remotion editor timeline into a final MP4. Costs credits."""
    job_id = kwargs.get("job_id")
    state = kwargs.get("editor_state")
    if not job_id or state is None:
        return json.dumps({"error": "job_id and editor_state are required"})

    if not kwargs.get("confirmed"):
        credits = _credits_for_op("render_edited_video", {})
        return _confirmation_payload(
            operation="render_edited_video",
            credits=credits,
            summary=f"Re-render edited video for job {job_id}",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    try:
        result = await ctx.core().trigger_editor_render(
            job_id=job_id, editor_state=state, codec=kwargs.get("codec", "h264"),
        )
    except Exception as e:
        return json.dumps({"error": f"render_edited_video failed: {e}"})

    render_id = result.get("renderId")
    if not render_id:
        return json.dumps({"error": "render dispatched but no renderId returned", "raw": result})

    # Poll the editor render endpoint until done.
    waited = 0
    max_wait_s = 600
    poll_interval_s = 6
    progress_payload: dict | None = None
    while waited < max_wait_s:
        await asyncio.sleep(poll_interval_s)
        waited += poll_interval_s
        try:
            progress_payload = await ctx.core().get_editor_render_progress(render_id)
        except Exception as e:
            print(f"[render_edited_video] poll error (retrying): {e}")
            continue
        ptype = progress_payload.get("type")
        if ptype == "done":
            video_url = progress_payload.get("outputFile")
            if video_url:
                _record_artifact(ctx, {"type": "video", "url": video_url, "job_id": job_id})
            return json.dumps({
                "render_id": render_id,
                "video_url": video_url,
                "status": "success",
                "credits_spent": _credits_for_op("render_edited_video", {}),
            })
        if ptype == "error":
            return json.dumps({"error": progress_payload.get("error", "render failed"), "render_id": render_id})

    return json.dumps({
        "render_id": render_id,
        "status": "still_processing",
        "warning": "Render is taking longer than 10 minutes. Check the gallery later.",
    })


# ── Video combination ─────────────────────────────────────────────────

def _get_ffmpeg_path() -> str:
    """Resolve the ffmpeg binary path. Tries system ffmpeg first, then imageio-ffmpeg."""
    import shutil as _sh
    system_ffmpeg = _sh.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return "ffmpeg"  # last resort — will fail with a clear error




async def _tool_splice_app_clip(ctx: ToolContext, **kwargs: Any) -> str:
    """Concat a completed generate_video job's output with an app clip as
    B-roll (dissolve transition) and update the job's final_video_url.

    Free tool. Designed to be chained after generate_video for digital
    products so the user sees two discrete activity cards ("cinematic
    done" → "splicing B-roll") instead of a single ~3-min blocking wait.
    """
    import asyncio as _asyncio
    import tempfile as _tempfile
    from datetime import datetime as _dt

    job_id = kwargs.get("job_id")
    app_clip_id = kwargs.get("app_clip_id")
    if not job_id or not app_clip_id:
        return json.dumps({"error": "job_id and app_clip_id are required"})

    try:
        job = await ctx.core().get_job_status(job_id)
    except Exception as e:
        return json.dumps({"error": f"get_job_status failed: {e}", "job_id": job_id})

    primary_url = job.get("final_video_url")
    if not primary_url:
        return json.dumps({
            "error": f"job {job_id} has no final_video_url — is it complete?",
            "job_id": job_id,
            "status": job.get("status"),
        })

    try:
        app_clip = await ctx.core().get_app_clip(app_clip_id)
    except Exception as e:
        return json.dumps({"error": f"get_app_clip failed: {e}"})

    broll_url = app_clip.get("video_url") if app_clip else None
    if not broll_url:
        return json.dumps({"error": f"app clip {app_clip_id} has no video_url"})

    try:
        from utils.video_concat import concat_videos_matched
        concat_path = await _asyncio.to_thread(
            concat_videos_matched, primary_url, broll_url
        )
    except Exception as e:
        return json.dumps({"error": f"concat failed: {e}", "job_id": job_id})

    timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
    storage_filename = f"spliced_{job_id[:8]}_{timestamp}.mp4"
    try:
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        with open(concat_path, "rb") as f:
            sb.storage.from_("generated-videos").upload(
                storage_filename, f,
                file_options={"content-type": "video/mp4"},
            )
        final_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
    except Exception as e:
        return json.dumps({"error": f"upload failed: {e}", "job_id": job_id})

    try:
        from routers.generate_video import _update_video_job_via_api
        existing_meta = job.get("metadata") or {}
        new_meta = {**existing_meta, "pre_splice_url": primary_url, "spliced_app_clip_id": app_clip_id}
        await _update_video_job_via_api(
            ctx.user_token, ctx.project_id or "", job_id,
            {"final_video_url": final_url, "metadata": new_meta},
        )
    except Exception as e:
        # Non-fatal — the spliced video exists in storage; just log.
        print(f"[splice_app_clip] Job row update failed (non-fatal): {e}")

    _record_artifact(ctx, {"type": "video", "url": final_url, "job_id": job_id})
    return json.dumps({
        "job_id": job_id,
        "video_url": final_url,
        "pre_splice_url": primary_url,
        "status": "success",
    })


async def _tool_combine_videos(ctx: ToolContext, **kwargs: Any) -> str:
    """Combine multiple videos with dissolve transitions. Gated tool."""
    import subprocess
    import tempfile
    import shutil
    import sys as _sys
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    video_urls: list[str] = kwargs.get("video_urls") or []
    if len(video_urls) < 2:
        return json.dumps({"error": "At least 2 video_urls are required to combine."})

    transition = kwargs.get("transition", "dissolve")
    transition_dur = float(kwargs.get("transition_duration", 0.6))
    transition_dur = max(0.3, min(1.5, transition_dur))  # clamp

    # Audio controls. `mute_audio_indices` silences specific source clips
    # (used for music-only cinematic B-roll when the user wants to swap the
    # soundtrack). `music_prompt` triggers a fresh Suno instrumental that is
    # mixed UNDER any kept dialogue.
    mute_indices: set[int] = set()
    for idx in (kwargs.get("mute_audio_indices") or []):
        try:
            idx_int = int(idx)
        except (TypeError, ValueError):
            continue
        if 0 <= idx_int < len(video_urls):
            mute_indices.add(idx_int)
    music_prompt = (kwargs.get("music_prompt") or "").strip() or None

    # Kick off Suno generation in parallel with the video download/normalize
    # work — music generation typically takes 30s-2min and masking it behind
    # the ffmpeg passes avoids paying it serially.
    music_task: Optional[asyncio.Task] = None
    if music_prompt:
        try:
            # generate_scenes.generate_music lives at the repo root and is
            # imported by adding the repo to sys.path (same pattern as
            # routers/generate_video.py).
            repo_root = str(_Path(__file__).resolve().parents[3])
            if repo_root not in _sys.path:
                _sys.path.insert(0, repo_root)
            import generate_scenes as _gs  # type: ignore
            print(f"[combine_videos] Starting Suno music generation (prompt={music_prompt[:60]}...)")
            music_task = asyncio.create_task(
                asyncio.to_thread(_gs.generate_music, prompt=music_prompt, instrumental=True)
            )
        except Exception as e:
            print(f"[combine_videos] Failed to start music generation: {e}")
            music_task = None

    # combine_videos runs automatically (no confirmation gate). Credits are
    # deducted by the upstream core API when the merged MP4 is processed.
    work_dir = tempfile.mkdtemp(prefix="combine_")
    try:
        import httpx

        # Resolve ffmpeg binary path
        FFMPEG = _get_ffmpeg_path()
        print(f"[combine_videos] Using ffmpeg={FFMPEG}")

        # 1. Download all videos
        print(f"[combine_videos] Downloading {len(video_urls)} videos...")
        local_paths: list[str] = []
        async with httpx.AsyncClient(timeout=60) as http:
            for i, url in enumerate(video_urls):
                local_path = os.path.join(work_dir, f"input_{i}.mp4")
                resp = await http.get(url, follow_redirects=True)
                resp.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(resp.content)
                local_paths.append(local_path)
                print(f"[combine_videos]   Downloaded clip {i+1}: {len(resp.content)/1024/1024:.1f}MB")

        # 2. Normalize all clips to consistent resolution/codec using ffmpeg
        #    IMPORTANT: Every clip MUST have an audio track for xfade+acrossfade.
        #    If a source clip has no audio — OR the agent asked us to silence
        #    this clip via mute_audio_indices — we attach a silent audio track.
        normalized: list[str] = []
        target_res = "1080:1920"  # 9:16 vertical — most UGC content

        def _silent_normalize_cmd(src_path: str, out_path: str) -> list[str]:
            return [
                FFMPEG, "-y",
                "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
                "-i", src_path,
                "-map", "1:v", "-map", "0:a",
                "-vf", f"scale={target_res}:force_original_aspect_ratio=decrease,"
                       f"pad={target_res}:(ow-iw)/2:(oh-ih)/2:color=black",
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-ar", "44100", "-ac", "2",
                "-shortest",
                out_path,
            ]

        for i, path in enumerate(local_paths):
            norm_path = os.path.join(work_dir, f"norm_{i}.mp4")
            if i in mute_indices:
                # Agent explicitly requested this clip be silent. Go straight
                # to the silent-audio path — do NOT try the source audio first.
                print(f"[combine_videos] Clip {i} muted by request")
                cmd_silent = _silent_normalize_cmd(path, norm_path)
                result = await asyncio.to_thread(
                    subprocess.run, cmd_silent, capture_output=True, text=True
                )
                if result.returncode != 0:
                    return json.dumps({"error": f"Failed to normalize muted clip {i}: {result.stderr[-300:]}"})
                normalized.append(norm_path)
                continue

            cmd = [
                FFMPEG, "-y", "-i", path,
                "-vf", f"scale={target_res}:force_original_aspect_ratio=decrease,"
                       f"pad={target_res}:(ow-iw)/2:(oh-ih)/2:color=black",
                "-r", "30", "-pix_fmt", "yuv420p",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-ar", "44100", "-ac", "2",
                "-shortest",
                norm_path,
            ]
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )
            if result.returncode != 0:
                # Source has no audio → add a silent audio track so all clips are uniform
                print(f"[combine_videos] Clip {i} has no audio, adding silent track")
                cmd_silent = _silent_normalize_cmd(path, norm_path)
                result2 = await asyncio.to_thread(
                    subprocess.run, cmd_silent, capture_output=True, text=True
                )
                if result2.returncode != 0:
                    return json.dumps({"error": f"Failed to normalize clip {i}: {result2.stderr[-300:]}"})
            normalized.append(norm_path)

        # 3. Get durations of each normalized clip (using ffmpeg -i, no ffprobe needed)
        import re
        durations: list[float] = []
        for path in normalized:
            probe = await asyncio.to_thread(
                subprocess.run,
                [FFMPEG, "-i", path, "-f", "null", "-"],
                capture_output=True, text=True,
            )
            # ffmpeg prints "Duration: HH:MM:SS.xx" in stderr
            dur_match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", probe.stderr)
            if dur_match:
                h, m, s = dur_match.groups()
                durations.append(int(h) * 3600 + int(m) * 60 + float(s))
            else:
                durations.append(5.0)  # fallback

        print(f"[combine_videos] Clip durations: {durations}")

        # 4. Build ffmpeg xfade chain for N clips
        if transition == "none" or len(normalized) == 2 and any(d < transition_dur * 2 for d in durations):
            # Simple concat (no transition) for very short clips or explicit none
            concat_list = os.path.join(work_dir, "concat.txt")
            with open(concat_list, "w") as f:
                for path in normalized:
                    f.write(f"file '{path}'\n")
            output_path = os.path.join(work_dir, "combined.mp4")
            cmd = [
                FFMPEG, "-y", "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac",
                output_path,
            ]
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )
            if result.returncode != 0:
                return json.dumps({"error": f"FFmpeg concat failed: {result.stderr[-400:]}"})
        else:
            # Build chained xfade (video) + acrossfade (audio) filter
            output_path = os.path.join(work_dir, "combined.mp4")
            n = len(normalized)

            xfade_name = "dissolve" if transition == "dissolve" else (
                "fade" if transition == "fade" else transition
            )

            video_filters = []
            audio_filters = []

            for i in range(n - 1):
                # ── Video xfade chain ──
                v_in_a = f"[{i}:v]" if i == 0 else f"[v{i-1}{i}]"
                v_in_b = f"[{i+1}:v]"
                v_out = "[v]" if i == n - 2 else f"[v{i}{i+1}]"

                offset = sum(durations[:i+1]) - transition_dur * (i + 1)
                offset = max(0.1, offset)

                video_filters.append(
                    f"{v_in_a}{v_in_b}xfade=transition={xfade_name}"
                    f":duration={transition_dur}:offset={offset:.3f}{v_out}"
                )

                # ── Audio acrossfade chain ──
                a_in_a = f"[{i}:a]" if i == 0 else f"[a{i-1}{i}]"
                a_in_b = f"[{i+1}:a]"
                a_out = "[a]" if i == n - 2 else f"[a{i}{i+1}]"

                audio_filters.append(
                    f"{a_in_a}{a_in_b}acrossfade=d={transition_dur}"
                    f":c1=tri:c2=tri{a_out}"
                )

            filter_str = ";".join(video_filters + audio_filters)

            # Build input args
            input_args = []
            for path in normalized:
                input_args.extend(["-i", path])

            cmd = [
                FFMPEG, "-y",
                *input_args,
                "-filter_complex", filter_str,
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-c:a", "aac", "-ar", "44100",
                output_path,
            ]

            print(f"[combine_videos] Running ffmpeg xfade: {' '.join(cmd)}")
            result = await asyncio.to_thread(
                subprocess.run, cmd, capture_output=True, text=True
            )
            if result.returncode != 0:
                # Log last 600 chars of stderr (skip version banner)
                err_tail = result.stderr[-600:] if len(result.stderr) > 600 else result.stderr
                print(f"[combine_videos] xfade failed: {err_tail}")
                # Fallback to simple concat
                concat_list = os.path.join(work_dir, "concat.txt")
                with open(concat_list, "w") as f:
                    for path in normalized:
                        f.write(f"file '{path}'\n")
                cmd = [
                    FFMPEG, "-y", "-f", "concat", "-safe", "0",
                    "-i", concat_list,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                    "-c:a", "aac",
                    output_path,
                ]
                result = await asyncio.to_thread(
                    subprocess.run, cmd, capture_output=True, text=True
                )
                if result.returncode != 0:
                    return json.dumps({"error": f"FFmpeg concat fallback also failed: {result.stderr[:400]}"})

        # 4b. If the agent requested a fresh soundtrack, wait for Suno to
        # finish (started in parallel at the top), download the track, and
        # mix it UNDER the concat output at a dialogue-safe level. Loops the
        # music if it's shorter than the combined video.
        if music_task is not None:
            try:
                music_url = await music_task
            except Exception as music_err:
                print(f"[combine_videos] Music generation errored: {music_err}")
                music_url = None
            if music_url:
                try:
                    music_path = os.path.join(work_dir, "music.mp3")
                    async with httpx.AsyncClient(timeout=60) as http:
                        mresp = await http.get(music_url, follow_redirects=True)
                        mresp.raise_for_status()
                        with open(music_path, "wb") as mf:
                            mf.write(mresp.content)
                    print(f"[combine_videos] Downloaded music ({len(mresp.content)/1024/1024:.1f}MB); mixing under dialogue...")
                    mixed_path = os.path.join(work_dir, "combined_with_music.mp4")
                    mix_cmd = [
                        FFMPEG, "-y",
                        "-i", output_path,
                        "-stream_loop", "-1", "-i", music_path,
                        "-filter_complex",
                        "[1:a]volume=0.22[m];"
                        "[0:a][m]amix=inputs=2:duration=first:dropout_transition=2,"
                        "dynaudnorm=f=150:g=15[a]",
                        "-map", "0:v",
                        "-map", "[a]",
                        "-c:v", "copy",
                        "-c:a", "aac", "-ar", "44100", "-b:a", "192k",
                        "-shortest",
                        mixed_path,
                    ]
                    mix_result = await asyncio.to_thread(
                        subprocess.run, mix_cmd, capture_output=True, text=True
                    )
                    if mix_result.returncode == 0:
                        output_path = mixed_path
                        print("[combine_videos] Music bed mixed under final cut")
                    else:
                        print(f"[combine_videos] Music mix failed, shipping without music: {mix_result.stderr[-400:]}")
                except Exception as mix_err:
                    print(f"[combine_videos] Music mix pass errored: {mix_err}")
            else:
                print("[combine_videos] Music generation returned no URL — shipping without music")

        # 5. Upload to Supabase Storage
        output_size = os.path.getsize(output_path)
        print(f"[combine_videos] Combined video: {output_size/1024/1024:.1f}MB")

        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        storage_filename = f"combined_{timestamp}.mp4"
        try:
            from supabase import create_client
            sb = create_client(
                os.getenv("SUPABASE_URL"),
                os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
            )
            with open(output_path, "rb") as f:
                sb.storage.from_("generated-videos").upload(
                    storage_filename, f,
                    file_options={"content-type": "video/mp4"},
                )
            final_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
        except Exception as upload_err:
            print(f"[combine_videos] Upload error: {upload_err}")
            return json.dumps({"error": f"Upload failed: {upload_err}"})

        total_duration = sum(durations) - transition_dur * (len(durations) - 1) if transition != "none" else sum(durations)

        # Persist as a video_jobs row so the combined clip is a first-class job
        # with its own job_id — required for schedule_posts, generate_caption,
        # and any other downstream tool that keys off video_job_id.
        job_id: Optional[str] = None
        try:
            job = await ctx.core().create_job({
                "influencer_id": "00000000-0000-0000-0000-000000000000",
                "product_id": None,
                "product_type": "physical",
                "model_api": "combined-videos",
                "length": int(round(total_duration)),
                "campaign_name": "Creative OS — Combined",
                "video_language": "en",
                "subtitles_enabled": False,
                "music_enabled": False,
                "hook": f"Combined {len(video_urls)} clips ({transition})",
            })
            job_id = job.get("id") or (job.get("job") or {}).get("id")
            if job_id:
                try:
                    supabase_url = os.getenv("SUPABASE_URL")
                    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
                    if supabase_url and anon_key:
                        import httpx
                        async with httpx.AsyncClient(timeout=10.0) as http:
                            await http.patch(
                                f"{supabase_url}/rest/v1/video_jobs?id=eq.{job_id}",
                                headers={
                                    "apikey": anon_key,
                                    "Authorization": f"Bearer {ctx.user_token}",
                                    "Content-Type": "application/json",
                                    "Prefer": "return=minimal",
                                },
                                json={
                                    "status": "success",
                                    "progress": 100,
                                    "final_video_url": final_url,
                                    "metadata": {
                                        "mode": "combined_videos",
                                        "source_urls": video_urls,
                                        "transition": transition,
                                        "mute_audio_indices": sorted(mute_indices),
                                        "music_prompt": music_prompt,
                                    },
                                },
                            )
                except Exception as patch_err:
                    print(f"[combine_videos] job patch failed: {patch_err}")
        except Exception as job_err:
            print(f"[combine_videos] job creation failed: {job_err}")

        _record_artifact(ctx, {"type": "video", "url": final_url, **({"job_id": job_id} if job_id else {})})

        return json.dumps({
            "status": "success",
            "job_id": job_id,
            "video_url": final_url,
            "clips_combined": len(video_urls),
            "total_duration_seconds": round(total_duration, 1),
            "transition": transition,
            "credits_spent": _credits_for_op("animate_image", {"duration": 5}),
        })
    except Exception as e:
        return json.dumps({"error": f"combine_videos failed: {e}"})
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


# ── Phase 6: Image generation & identity ──────────────────────────────
async def _tool_generate_influencer(ctx: ToolContext, **kwargs: Any) -> str:
    from routers.generate_image import generate_influencer

    if not kwargs.get("confirmed"):
        credits = _credits_for_op("generate_influencer", {})
        return _confirmation_payload(
            operation="generate_influencer",
            credits=credits,
            summary="Generate a random AI influencer persona + profile photo",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    user = {"token": ctx.user_token, "id": "agent"}
    try:
        result = await generate_influencer(user=user)
    except Exception as e:
        return json.dumps({"error": f"generate_influencer failed: {e}"})

    image_url = result.get("image_url")
    if image_url:
        _record_artifact(ctx, {"type": "image", "url": image_url})
    return json.dumps({
        "name": result.get("name"),
        "gender": result.get("gender"),
        "age": result.get("age"),
        "description": result.get("description"),
        "image_url": image_url,
    })


async def _tool_generate_identity(ctx: ToolContext, **kwargs: Any) -> str:
    from routers.generate_image import GenerateIdentityRequest, generate_identity

    if not kwargs.get("confirmed"):
        credits = _credits_for_op("generate_identity", {})
        return _confirmation_payload(
            operation="generate_identity",
            credits=credits,
            summary="Generate 4-view character identity sheet",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    user = {"token": ctx.user_token, "id": "agent"}
    try:
        result = await generate_identity(
            data=GenerateIdentityRequest(image_url=kwargs["image_url"]),
            user=user,
        )
    except Exception as e:
        return json.dumps({"error": f"generate_identity failed: {e}"})

    sheet_url = result.get("character_sheet_url")
    if sheet_url:
        _record_artifact(ctx, {"type": "image", "url": sheet_url})
    return json.dumps({
        "description": result.get("description"),
        "character_sheet_url": sheet_url,
        "views": result.get("views", []),
    })


async def _tool_generate_product_shots(ctx: ToolContext, **kwargs: Any) -> str:
    from routers.generate_image import GenerateProductShotsRequest, generate_product_shots

    if not kwargs.get("confirmed"):
        credits = _credits_for_op("generate_product_shots", {})
        return _confirmation_payload(
            operation="generate_product_shots",
            credits=credits,
            summary="Generate 4-view product shot sheet",
            echo={k: v for k, v in kwargs.items() if k != "confirmed"},
        )

    user = {"token": ctx.user_token, "id": "agent"}
    try:
        result = await generate_product_shots(
            data=GenerateProductShotsRequest(image_url=kwargs["image_url"]),
            user=user,
        )
    except Exception as e:
        return json.dumps({"error": f"generate_product_shots failed: {e}"})

    sheet_url = result.get("product_sheet_url")
    if sheet_url:
        _record_artifact(ctx, {"type": "image", "url": sheet_url})
    return json.dumps({
        "product_sheet_url": sheet_url,
        "views": result.get("views", []),
    })


# ── Phase 6b: AI scripting ────────────────────────────────────────────
async def _tool_generate_ai_script(ctx: ToolContext, **kwargs: Any) -> str:
    from routers.generate_video import AIScriptRequest, generate_ai_script

    if not ctx.project_id:
        return json.dumps({"error": "project_id is required to generate scripts"})

    user = {"token": ctx.user_token, "id": "agent"}
    try:
        result = await generate_ai_script(
            data=AIScriptRequest(
                project_id=ctx.project_id,
                product_id=kwargs.get("product_id"),
                influencer_id=kwargs.get("influencer_id"),
                language=kwargs.get("language", "en"),
                clip_length=int(kwargs.get("clip_length", 8)),
                full_video_mode=bool(kwargs.get("full_video_mode", False)),
                context=kwargs.get("context"),
            ),
            user=user,
        )
    except Exception as e:
        return json.dumps({"error": f"generate_ai_script failed: {e}"})

    return json.dumps({
        "script": result.get("script"),
        "language": result.get("language"),
        "clip_length": result.get("clip_length"),
    })


# ── Phase 6c: Asset management ────────────────────────────────────────
async def _tool_list_app_clips(ctx: ToolContext, **kwargs: Any) -> str:
    product_id = kwargs.get("product_id")
    try:
        if product_id:
            clips = await ctx.core()._request("GET", "/api/app-clips", params={"product_id": product_id})
        else:
            clips = await ctx.core()._request("GET", "/app-clips")
    except Exception as e:
        return json.dumps({"error": f"list_app_clips failed: {e}"})

    if isinstance(clips, list):
        slim = [
            {k: c.get(k) for k in ("id", "name", "video_url", "product_id", "description") if k in c}
            for c in clips[:30]
        ]
        return json.dumps({"clips": slim, "total": len(clips)})
    return json.dumps(clips)


async def _tool_manage_app_clips(ctx: ToolContext, **kwargs: Any) -> str:
    action = kwargs.get("action")
    clip_id = kwargs.get("clip_id")

    try:
        if action == "create":
            body = {k: kwargs[k] for k in ("name", "video_url", "product_id", "description") if k in kwargs}
            result = await ctx.core()._request("POST", "/app-clips", json=body)
        elif action == "update":
            if not clip_id:
                return json.dumps({"error": "clip_id is required for update"})
            body = {k: kwargs[k] for k in ("name", "video_url", "product_id", "description") if k in kwargs}
            result = await ctx.core()._request("PATCH", f"/api/app-clips/{clip_id}", json=body)
        elif action == "delete":
            if not clip_id:
                return json.dumps({"error": "clip_id is required for delete"})
            result = await ctx.core()._request("DELETE", f"/app-clips/{clip_id}")
        else:
            return json.dumps({"error": f"Unknown action: {action}. Use create/update/delete."})
    except Exception as e:
        return json.dumps({"error": f"manage_app_clips ({action}) failed: {e}"})

    return json.dumps(result) if isinstance(result, dict) else json.dumps({"status": "ok", "result": str(result)})


async def _tool_delete_assets(ctx: ToolContext, **kwargs: Any) -> str:
    image_ids = kwargs.get("image_ids") or []
    video_ids = kwargs.get("video_ids") or []
    if not image_ids and not video_ids:
        return json.dumps({"error": "Provide at least one image_id or video_id to delete."})

    core = ctx.core()
    deleted = 0
    failed = 0
    errors: list[str] = []

    async def _del(coro: Any, label: str) -> None:
        nonlocal deleted, failed
        try:
            await coro
            deleted += 1
        except Exception as e:
            failed += 1
            errors.append(f"{label}: {e}")

    await asyncio.gather(
        *(_del(core.delete_shot(sid), f"shot:{sid}") for sid in image_ids),
        *(_del(core.delete_job(vid), f"job:{vid}") for vid in video_ids),
    )
    return json.dumps({"deleted": deleted, "failed": failed, "total": len(image_ids) + len(video_ids), "errors": errors or None})


TOOL_DISPATCH: dict[str, Callable[..., Awaitable[str]]] = {
    # discovery
    "list_project_assets": _tool_list_project_assets,
    "list_projects": _tool_list_projects,
    "list_influencers": _tool_list_influencers,
    "list_products": _tool_list_products,
    "list_scripts": _tool_list_scripts,
    "list_jobs": _tool_list_jobs,
    "get_job_status": _tool_get_job_status,
    "list_scheduled_posts": _tool_list_scheduled_posts,
    "list_social_connections": _tool_list_social_connections,
    "get_wallet": _tool_get_wallet,
    # cost preview
    "estimate_credits": _tool_estimate_credits,
    # creative-os generation (gated)
    "generate_image": _tool_generate_image,
    "animate_image": _tool_animate_image,
    "generate_video": _tool_generate_video,
    # image generation & identity (gated)
    "generate_influencer": _tool_generate_influencer,
    "generate_identity": _tool_generate_identity,
    "generate_product_shots": _tool_generate_product_shots,
    # AI scripting (free)
    "generate_ai_script": _tool_generate_ai_script,
    # asset management (free)
    "list_app_clips": _tool_list_app_clips,
    "manage_app_clips": _tool_manage_app_clips,
    "delete_assets": _tool_delete_assets,
    # account / asset creation (free)
    "create_project": _tool_create_project,
    "create_influencer": _tool_create_influencer,
    "create_product": _tool_create_product,
    "analyze_product_image": _tool_analyze_product_image,
    "analyze_digital_product": _tool_analyze_digital_product,
    "generate_scripts": _tool_generate_scripts,
    # full UGC pipelines (gated)
    "create_ugc_video": _tool_create_ugc_video,
    "create_clone_video": _tool_create_clone_video,
    "create_bulk_campaign": _tool_create_bulk_campaign,
    # scheduling & social (free)
    "schedule_posts": _tool_schedule_posts,
    "cancel_scheduled_post": _tool_cancel_scheduled_post,
    "generate_caption": _tool_generate_caption,
    # remotion editor
    "caption_video": _tool_caption_video,
    "load_editor_state": _tool_load_editor_state,
    "save_editor_state": _tool_save_editor_state,
    "render_edited_video": _tool_render_edited_video,
    # video combination (gated)
    "combine_videos": _tool_combine_videos,
    # app-clip B-roll splice for digital products (free)
    "splice_app_clip": _tool_splice_app_clip,
}


# ── Helpers ───────────────────────────────────────────────────────────
def _summarize_input(tool_input: dict, max_len: int = 80) -> str:
    try:
        s = json.dumps(tool_input, ensure_ascii=False)
    except Exception:
        s = str(tool_input)
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


def _summarize_result(result_text: str, max_len: int = 120) -> str:
    s = result_text.replace("\n", " ")
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


# ── Client wrapper ────────────────────────────────────────────────────
class ManagedAgentClient:
    """Async Anthropic Managed Agents client.

    Caches a single agent + environment in-process. Use `run_stream()` for
    SSE-style event streams (the main path) or `run()` for the simpler
    blocking interface used by the smoke-test script.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in env.saas / .env")
        self._client = AsyncAnthropic(
            api_key=self._api_key,
            default_headers={"anthropic-beta": BETA_HEADER},
        )
        self._agent_id: Optional[str] = None
        self._environment_id: Optional[str] = None
        self._lock = asyncio.Lock()

    # ── lazy resource creation ────────────────────────────────────────
    async def _ensure_agent(self) -> str:
        async with self._lock:
            if self._agent_id:
                return self._agent_id
            # Check for a pre-configured agent ID set as a Railway environment variable.
            # This prevents creating a new agent on every service restart, which would
            # invalidate all stored session IDs in Supabase.
            env_agent_id = os.getenv("ANTHROPIC_AGENT_ID")
            if env_agent_id:
                self._agent_id = env_agent_id
                print(f"[ManagedAgent] using pre-configured agent {env_agent_id}")
                return env_agent_id
            agent = await self._client.beta.agents.create(
                model=DEFAULT_MODEL,
                name=AGENT_NAME,
                description="Aitoma Studio creative director — drives Creative OS image/animation/video tools.",
                system=SYSTEM_PROMPT,
                tools=[
                    {"type": "agent_toolset_20260401"},
                    *_custom_tools_for_agent(),
                ],
            )
            self._agent_id = agent.id
            print(f"[ManagedAgent] *** CREATED NEW AGENT {agent.id} ***")
            print(f"[ManagedAgent] ACTION REQUIRED: Add ANTHROPIC_AGENT_ID={agent.id} to Railway environment variables.")
            print(f"[ManagedAgent] Without this, a new agent will be created on every service restart.")
            return agent.id

    async def _ensure_environment(self) -> str:
        async with self._lock:
            if self._environment_id:
                return self._environment_id
            # Check for a pre-configured environment ID set as a Railway environment variable.
            env_environment_id = os.getenv("ANTHROPIC_ENVIRONMENT_ID")
            if env_environment_id:
                self._environment_id = env_environment_id
                print(f"[ManagedAgent] using pre-configured environment {env_environment_id}")
                return env_environment_id
            env = await self._client.beta.environments.create(name=ENV_NAME)
            self._environment_id = env.id
            print(f"[ManagedAgent] *** CREATED NEW ENVIRONMENT {env.id} ***")
            print(f"[ManagedAgent] ACTION REQUIRED: Add ANTHROPIC_ENVIRONMENT_ID={env.id} to Railway environment variables.")
            return env.id

    async def _create_session(self, brief: str, project_id: Optional[str]) -> str:
        agent_id = await self._ensure_agent()
        environment_id = await self._ensure_environment()
        # Strip Unicode control/format chars — Anthropic rejects them in titles.
        import re as _re
        _clean_title = _re.sub(r'[\x00-\x1f\x7f-\x9f\u200b-\u200f\u2028-\u202f\u2060-\u206f\ufeff\ufff0-\uffff]', '', brief[:80]).strip()
        session = await self._client.beta.sessions.create(
            agent={"type": "agent", "id": agent_id},
            environment_id=environment_id,
            title=_clean_title or "Aitoma session",
            metadata={
                "project_id": project_id or "",
                "source": "creative-os-agent-router",
            },
        )
        print(f"[ManagedAgent] created session {session.id}")
        return session.id

    async def interrupt_session(self, session_id: str) -> None:
        """Best-effort: tell Anthropic to abort whatever the agent is doing."""
        try:
            await self._client.beta.sessions.events.send(
                session_id,
                events=[{"type": "user.interrupt"}],
            )
            print(f"[ManagedAgent] interrupted session {session_id}")
        except Exception as e:
            print(f"[ManagedAgent] interrupt failed for {session_id}: {e}")

    # ── streaming entry point ────────────────────────────────────────
    async def run_stream(
        self,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str] = None,
        max_tool_calls: int = 24,
        prior_turns: Optional[list[dict]] = None,
        lang: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        """Wrap the inner implementation with a persistent heartbeat task.

        The Anthropic stream, Anthropic events.send, and various polling
        loops all have quiet windows where no event is yielded for 30-60s.
        Intermediaries (Railway proxy, browsers) kill idle SSE connections,
        which was surfacing as a "network error" even though backend tools
        kept running. This wrapper spawns a background heartbeat task that
        pumps a keepalive into the output queue every 10s regardless of
        what the inner generator is doing.
        """
        queue: asyncio.Queue = asyncio.Queue()
        DONE = object()

        async def producer():
            try:
                async for ev in self._run_stream_impl(
                    brief=brief,
                    user_token=user_token,
                    project_id=project_id,
                    session_id=session_id,
                    max_tool_calls=max_tool_calls,
                    prior_turns=prior_turns,
                    lang=lang,
                    image_urls=image_urls,
                ):
                    await queue.put(ev)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await queue.put({"type": "error", "message": f"agent run failed: {e}"})
            finally:
                await queue.put(DONE)

        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(10)
                    await queue.put({"type": "keepalive", "elapsed_seconds": 0, "phase": "idle"})
            except asyncio.CancelledError:
                pass

        prod_task = asyncio.create_task(producer())
        hb_task = asyncio.create_task(heartbeat())
        try:
            while True:
                ev = await queue.get()
                if ev is DONE:
                    break
                yield ev
        finally:
            hb_task.cancel()
            prod_task.cancel()
            with suppress(BaseException):
                await hb_task
            with suppress(BaseException):
                await prod_task

    async def _run_stream_impl(
        self,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str] = None,
        max_tool_calls: int = 24,
        prior_turns: Optional[list[dict]] = None,
        lang: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        """Drive the agent through one user turn, yielding normalized events.

        Yields dicts with shapes:
          - {"type": "session", "session_id": str}
          - {"type": "agent_message", "text": str}
          - {"type": "tool_call", "name": str, "input_summary": str, "tool_use_id": str}
          - {"type": "tool_result", "tool_use_id": str, "summary": str, "is_error": bool}
          - {"type": "artifact", "artifact": {...}}
          - {"type": "done", "session_id": str}
          - {"type": "error", "message": str}
        """
        # Inject locale directive so conversational replies match the user's
        # UI language. Tool calls / JSON payloads stay English — the directive
        # is explicit about that so tool schemas are unaffected.
        if lang == "es":
            brief = (
                "[LANG=es — Responde en español. Las llamadas a herramientas y los "
                "payloads JSON deben permanecer en inglés; solo las respuestas "
                "conversacionales al usuario son en español.]\n\n" + brief
            )

        # Resolve / create session, with transparent fallback for stale ids.
        # Single events.list(limit=50) does double duty: if it raises NotFound
        # the session is gone (create fresh); otherwise we reuse the response
        # to populate seen_event_ids. Saves one round trip (~400-800ms) vs.
        # the previous probe-then-snapshot flow.
        seen_event_ids: set[str] = set()
        if session_id:
            try:
                existing = await self._client.beta.sessions.events.list(
                    session_id, limit=50, order="desc"
                )
                async for ev in existing:  # type: ignore
                    ev_id = getattr(ev, "id", None)
                    if ev_id:
                        seen_event_ids.add(ev_id)
            except NotFoundError:
                print(f"[ManagedAgent] session {session_id} gone, creating new")
                session_id = None
                seen_event_ids.clear()
            except Exception as e:
                print(f"[ManagedAgent] session probe failed ({e}), creating new")
                session_id = None
                seen_event_ids.clear()
        if not session_id:
            session_id = await self._create_session(brief, project_id)
        yield {"type": "session", "session_id": session_id}

        ctx = ToolContext(user_token=user_token, project_id=project_id)
        tool_calls_made = 0

        # Build a compact context primer from prior turns. Sent only on
        # fresh/reset sessions so the agent retains conversation memory even
        # after an Anthropic session reset. Skipped for continuing sessions
        # (the live session already has the history in its event log).
        def _build_context_primer() -> str:
            if not prior_turns:
                return ""
            lines = ["[Prior conversation in this project — for context only, do not re-execute]"]
            # Cap at last 12 turns to keep tokens bounded.
            for turn in prior_turns[-12:]:
                role = turn.get("role", "agent")
                text = (turn.get("text") or "").strip()
                tool_calls = turn.get("tool_calls") or []
                artifacts = turn.get("artifacts") or []
                if role == "user":
                    if text:
                        lines.append(f"User: {text}")
                else:
                    if text:
                        lines.append(f"Agent: {text}")
                    for tc in tool_calls:
                        name = tc.get("name", "?")
                        summary = tc.get("input_summary", "")
                        lines.append(f"  [called {name}: {summary}]")
                    for art in artifacts:
                        kind = art.get("type", "artifact")
                        url = art.get("url", "")
                        jid = art.get("job_id", "")
                        sid_ = art.get("shot_id", "")
                        tag = f"job_id={jid}" if jid else (f"shot_id={sid_}" if sid_ else "")
                        lines.append(f"  [produced {kind}: {url} {tag}]".strip())
            lines.append("")
            lines.append("Current user message: " + brief)
            return "\n".join(lines)

        # Send the user brief.
        # If the session has a pending tool call from a crashed/interrupted run,
        # the API rejects user.message. In that case, interrupt and start fresh.
        async def _send_user_message(sid: str, *, with_primer: bool = False) -> None:
            text = _build_context_primer() if with_primer else brief
            if not text:
                text = brief
            content: list[dict] = [{"type": "text", "text": text}]
            for url in (image_urls or []):
                content.append({
                    "type": "image",
                    "source": {"type": "url", "url": url},
                })
            await self._client.beta.sessions.events.send(
                sid,
                events=[{"type": "user.message", "content": content}],
            )

        async def _reset_and_send() -> str:
            """Interrupt the stale session, create a fresh one, snapshot it, and send the message."""
            print(f"[ManagedAgent] session {session_id} is stale or belongs to a different agent, resetting")
            try:
                await self.interrupt_session(session_id)
            except Exception:
                pass
            new_sid = await self._create_session(brief, project_id)
            seen_event_ids.clear()
            try:
                existing = await self._client.beta.sessions.events.list(new_sid, limit=50, order="desc")
                async for ev in existing:
                    ev_id = getattr(ev, "id", None)
                    if ev_id:
                        seen_event_ids.add(ev_id)
            except Exception:
                pass
            # Fresh session after reset — replay prior conversation as a primer
            # so the agent keeps memory across the reset.
            await _send_user_message(new_sid, with_primer=True)
            return new_sid

        # If we just created a brand-new session but have prior turns persisted
        # (e.g. first message after a Railway restart wiped the session cache),
        # include the context primer so the agent doesn't start from scratch.
        initial_primer = bool(prior_turns) and not seen_event_ids
        try:
            await _send_user_message(session_id, with_primer=initial_primer)
        except (BadRequestError, NotFoundError) as e:
            err_str = str(e).lower()
            # Covers: "waiting on responses" (pending tool call), "not found" (expired session),
            # and any agent-mismatch errors that occur when the service was restarted and a new
            # agent was created, making the old session_id invalid.
            should_reset = (
                "waiting on responses" in err_str
                or "not found" in err_str
                or "agent" in err_str
                or "session" in err_str
            )
            if should_reset:
                session_id = await _reset_and_send()
                yield {"type": "session", "session_id": session_id}
            else:
                raise

        try:
            while True:
                stream = await self._client.beta.sessions.events.stream(session_id)
                went_idle = False
                # Collect all tool calls emitted in this stream pass before executing,
                # so multiple tools requested in a single agent turn run concurrently
                # and results are batched back in one send.
                pending_tool_calls: list[Any] = []
                hit_limit = False

                async for ev in stream:
                    ev_type = getattr(ev, "type", None)
                    ev_id = getattr(ev, "id", None)
                    if ev_id and ev_id in seen_event_ids:
                        continue
                    if ev_id:
                        seen_event_ids.add(ev_id)

                    if ev_type == "agent.message":
                        for block in getattr(ev, "content", []) or []:
                            text = getattr(block, "text", None)
                            if not text:
                                continue
                            # Split on paragraph breaks so each paragraph
                            # renders as its own bubble in the UI.
                            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
                            for p in paragraphs:
                                yield {"type": "agent_message", "text": p}

                    elif ev_type == "agent.custom_tool_use":
                        tool_calls_made += 1
                        if tool_calls_made > max_tool_calls:
                            yield {"type": "error", "message": f"exceeded max_tool_calls={max_tool_calls}"}
                            hit_limit = True
                            break
                        # Emit the tool_call event immediately so the UI shows activity.
                        _tc_input = ev.input or {}
                        yield {
                            "type": "tool_call",
                            "name": ev.name,
                            "input_summary": _summarize_input(_tc_input),
                            "mode": _tc_input.get("mode") if isinstance(_tc_input, dict) else None,
                            "tool_use_id": ev.id,
                        }
                        # Collect for concurrent execution after the stream pass ends.
                        pending_tool_calls.append(ev)

                    elif ev_type == "session.status_idle":
                        went_idle = True
                        break

                    elif ev_type == "session.error":
                        err = getattr(ev, "error", None)
                        msg = getattr(err, "message", None) or str(err) or "unknown session error"
                        yield {"type": "error", "message": msg}
                        return

                if hit_limit:
                    return

                # After the stream pass, execute all collected tool calls concurrently.
                if pending_tool_calls:
                    async def _execute_tool(ev: Any) -> tuple[str, str, bool]:
                        """Execute a single tool call and return (tool_use_id, result_text, is_error)."""
                        name = ev.name
                        tool_input = ev.input or {}
                        tool_use_id = ev.id
                        fn = TOOL_DISPATCH.get(name)
                        if fn is None:
                            return tool_use_id, json.dumps({"error": f"unknown tool: {name}"}), True
                        try:
                            print(f"[ManagedAgent] tool {name}({_summarize_input(tool_input, 120)})")
                            result_text = await fn(ctx, **tool_input)
                            return tool_use_id, result_text, False
                        except Exception as e:
                            return tool_use_id, json.dumps({"error": str(e)}), True

                    # Kick off all tools concurrently as tasks so we can yield keepalive
                    # pings every 15 s while they run. This preserves the existing SSE
                    # keepalive behavior (Railway's reverse proxy and browsers kill idle
                    # SSE connections around 30 s, and most tools take 30 s – 5 min).
                    tasks = [asyncio.create_task(_execute_tool(ev)) for ev in pending_tool_calls]
                    elapsed = 0
                    while any(not t.done() for t in tasks):
                        done, pending = await asyncio.wait(
                            tasks,
                            timeout=15.0,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if pending:
                            elapsed += 15
                            yield {
                                "type": "keepalive",
                                "elapsed_seconds": elapsed,
                                "pending_tools": len(pending),
                            }

                    # Collect results in the original order.
                    results: list[tuple[str, str, bool]] = []
                    for t in tasks:
                        try:
                            results.append(t.result())
                        except Exception as e:
                            # Should already be caught inside _execute_tool, but be defensive.
                            results.append(("", json.dumps({"error": str(e)}), True))

                    # Emit tool_result events for the UI activity log and build the batched send payload.
                    tool_result_events: list[dict] = []
                    for tool_use_id, result_text, is_error in results:
                        yield {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "summary": _summarize_result(result_text),
                            "is_error": is_error,
                        }
                        tool_result_events.append({
                            "type": "user.custom_tool_result",
                            "custom_tool_use_id": tool_use_id,
                            "content": [{"type": "text", "text": result_text}],
                            "is_error": is_error,
                        })

                    # Drain new artifacts produced by all tools in this batch.
                    if ctx.new_artifacts:
                        for art in ctx.new_artifacts:
                            yield {"type": "artifact", "artifact": art}
                        ctx.new_artifacts.clear()

                    # Send all results back to the session in a single batched call.
                    # Keepalive during the send — large payloads can take 30-60s and
                    # intermediaries (Railway proxy, browser) kill idle SSE connections.
                    send_task = asyncio.create_task(
                        self._client.beta.sessions.events.send(
                            session_id,
                            events=tool_result_events,
                        )
                    )
                    send_elapsed = 0
                    while not send_task.done():
                        try:
                            await asyncio.wait_for(asyncio.shield(send_task), timeout=15.0)
                        except asyncio.TimeoutError:
                            send_elapsed += 15
                            yield {
                                "type": "keepalive",
                                "elapsed_seconds": send_elapsed,
                                "phase": "sending_results",
                            }
                    await send_task

                    pending_tool_calls.clear()
                    # Loop back to re-open the stream for the agent's next response
                    # (which may itself contain more tool calls — i.e. tool chaining).
                    continue

                # No tool calls dispatched this pass.
                if went_idle:
                    break
                # Stream ended without idle and without any tool calls — nothing left
                # to do for this turn.
                break

            yield {"type": "done", "session_id": session_id}

        except asyncio.CancelledError:
            # Client disconnected (SSE reader closed — idle timeout, tab close, etc.).
            # Do NOT interrupt the Anthropic session — the tools may still be running
            # and the user can refresh to reconnect. Explicit Stop uses /agent/stop
            # which calls interrupt_session separately.
            print(f"[ManagedAgent] stream cancelled (client disconnect) — leaving session {session_id} alive")
            raise
        except Exception as e:
            yield {"type": "error", "message": f"agent run failed: {e}"}

    # ── blocking convenience wrapper for the smoke-test script ───────
    async def run(
        self,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        max_tool_calls: int = 12,
    ) -> dict:
        messages: list[str] = []
        artifacts: list[dict] = []
        session_id: Optional[str] = None
        error: Optional[str] = None
        async for ev in self.run_stream(
            brief=brief,
            user_token=user_token,
            project_id=project_id,
            session_id=None,
            max_tool_calls=max_tool_calls,
        ):
            t = ev.get("type")
            if t == "session":
                session_id = ev["session_id"]
            elif t == "agent_message":
                messages.append(ev["text"])
            elif t == "artifact":
                artifacts.append(ev["artifact"])
            elif t == "error":
                error = ev["message"]
            elif t == "done":
                session_id = ev.get("session_id", session_id)
        out: dict = {"session_id": session_id, "messages": messages, "artifacts": artifacts}
        if error:
            out["error"] = error
        return out


# Singleton accessor — instantiated lazily so importing this module doesn't
# error when ANTHROPIC_API_KEY is missing (e.g. in test environments).
_singleton: Optional[ManagedAgentClient] = None


def get_managed_agent_client() -> ManagedAgentClient:
    global _singleton
    if _singleton is None:
        _singleton = ManagedAgentClient()
    return _singleton
