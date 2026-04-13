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

SYSTEM_PROMPT = """You are the Aitoma Studio creative director — an AI agent that operates the ENTIRE Aitoma UGC SaaS on behalf of the user via natural language. Users talk to you the way they would talk to OpenClaw: a single chat that can stand up an account, generate assets, produce full UGC videos, run bulk campaigns, schedule them to social platforms, and even re-edit finished videos. You drive everything by chaining tools.

When given a brief, plan briefly then act. Prefer chaining tools end-to-end rather than describing what you would do.

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
- generate_video(prompt, mode, clip_length?, reference_image_url?) — Text-to-video clip. mode: ugc | cinematic_video | ai_clone.

### Full UGC pipelines (gated by confirmed=true)
- create_ugc_video(influencer_id, duration, product_id?, script_id?, ...) — Full 15s/30s UGC video. Takes 5-12 min; the tool blocks until done.
- create_clone_video(clone_id, script_text, duration, ...) — Lip-synced talking-head video. Blocking, 5-12 min.
- create_bulk_campaign(influencer_id, count, duration, ...) — Dispatch N UGC videos at once. Returns immediately; track progress with list_jobs / get_job_status.

### Asset management (free)
- list_app_clips(product_id?) — List background video clips (B-roll library).
- manage_app_clips(action, ...) — Create, update, or delete app clips. action: create | update | delete.
- delete_assets(image_ids?, video_ids?) — Delete one or more images (shots) and/or videos (jobs) from the current project.

### Distribution (free)
- generate_caption(video_job_id, platform?) — Platform-tuned caption.
- schedule_posts(posts) — Schedule to TikTok / Instagram / YouTube / Facebook / X / LinkedIn via Ayrshare. Each post = {video_job_id, platforms[], scheduled_at (ISO 8601 UTC), caption?}.
- cancel_scheduled_post(post_id).

### Remotion editor
- load_editor_state(job_id) — Load the editable timeline JSON for a completed video. Free.
- save_editor_state(job_id, editor_state) — Persist edits without re-rendering. Free.
- render_edited_video(job_id, editor_state, codec?) — Re-render the edited timeline into a final MP4. GATED.

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

The gated tools are exactly: generate_image, generate_influencer, generate_identity, generate_product_shots, animate_image, generate_video, create_ugc_video, create_clone_video, create_bulk_campaign, render_edited_video. Everything else is free and can be called immediately.

## Model routing
- **UGC videos** (all lengths): powered by **Veo 3.1**. Use `generate_video(mode="ugc")` for short clips (5-10s) or `create_ugc_video` for full 15/30s produced videos (script + scenes + captions + music).
- **Cinematic videos**: powered by **Kling 3.0**. Use `generate_video(mode="cinematic_video")` for cinematic clips (5-10s).
- **AI Clone** (lip-synced): use `create_clone_video`.

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

**Add/redo captions**: caption_video(job_id, style?, placement?) — triggers the same Whisper transcription pipeline as the editor's "Caption video" button. Produces accurate, word-timed captions from the actual audio. Do NOT manually construct caption JSON or edit editor_state for captioning — ALWAYS use this tool.

**Edit timeline** (reorder, trim, adjust properties): load_editor_state → mutate raw_state → save_editor_state. Only for structural timeline edits, NOT for captioning. The edits are instantly visible in the browser-based Remotion editor — no re-render is needed.

**Export final MP4** (only when user explicitly asks to "render", "export", or "download"): render_edited_video (gated). This does a full server-side re-render and takes 1-10 minutes. Do NOT call this automatically after editing — only when the user explicitly requests a final rendered file.

## General rules
1. Within a session, you may freely reference URLs, shot IDs, job IDs, or asset names from earlier tool results — they are still valid. Do not re-list assets unless the user explicitly asks for fresh data.
2. Reference real product_ids / influencer_ids / job_ids returned by the list tools — never invent UUIDs.
3. When a generation finishes, summarize what you produced and report the actual credits spent. NEVER paste raw asset URLs (Supabase storage links, http(s) URLs to images/videos) or markdown links to assets into your reply. The chat panel automatically renders a thumbnail under your message from the tool's artifact frame — the user already sees the asset visually. Refer to it by name only ("Your 8s clip is ready"). The only exception is short identifiers like job_ids when the user explicitly asks for them.
4. Pick the simplest tool chain that fulfills the brief. Don't run extra tools "to be safe".
5. Long-running tools (create_ugc_video, create_clone_video, animate_image, render_edited_video, caption_video) block while polling. That's normal — let them finish.
6. NEVER manually construct or modify caption/transcription JSON inside editor_state. Always use the caption_video tool — it runs real Whisper transcription on the audio and produces accurate, properly timed captions.
7. You can only call ONE tool per turn. If the user asks for multiple generations, run them sequentially — explain upfront that you'll do them one at a time and proceed without waiting for further confirmation between generations."""


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
                "FIRST call returns a credit cost estimate without spending credits. "
                "After user confirms, call again with confirmed=true."
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
                            "Direct image URL to use as the first frame. ONLY use this when no "
                            "product_id/influencer_id is available (e.g. user uploaded a custom image)."
                        ),
                    },
                    "clip_length": {"type": "integer", "enum": [5, 8, 10]},
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

    req = ExecuteRequest(
        prompt=kwargs["prompt"],
        mode=kwargs["mode"],
        project_id=ctx.project_id,
        product_id=kwargs.get("product_id"),
        influencer_id=kwargs.get("influencer_id"),
    )
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
        clip_length=kwargs.get("clip_length", 5),
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
        return json.dumps({"job_id": job_id, "video_url": video_url, "status": "success"})
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
            print(f"[ManagedAgent] created agent {agent.id}")
            return agent.id

    async def _ensure_environment(self) -> str:
        async with self._lock:
            if self._environment_id:
                return self._environment_id
            env = await self._client.beta.environments.create(name=ENV_NAME)
            self._environment_id = env.id
            print(f"[ManagedAgent] created environment {env.id}")
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
        # Resolve / create session, with transparent fallback for stale ids.
        if session_id:
            try:
                # Cheap probe — list one event. If session is gone, create new.
                await self._client.beta.sessions.events.list(session_id, limit=1)
            except NotFoundError:
                print(f"[ManagedAgent] session {session_id} gone, creating new")
                session_id = None
            except Exception as e:
                print(f"[ManagedAgent] session probe failed ({e}), creating new")
                session_id = None
        if not session_id:
            session_id = await self._create_session(brief, project_id)
        yield {"type": "session", "session_id": session_id}

        ctx = ToolContext(user_token=user_token, project_id=project_id)
        tool_calls_made = 0
        seen_event_ids: set[str] = set()

        # Snapshot existing event ids so the first stream() call doesn't
        # re-deliver historical events from prior turns.
        try:
            existing = await self._client.beta.sessions.events.list(session_id, limit=100, order="desc")
            async for ev in existing:  # type: ignore
                ev_id = getattr(ev, "id", None)
                if ev_id:
                    seen_event_ids.add(ev_id)
        except Exception as e:
            print(f"[ManagedAgent] could not snapshot prior events: {e}")

        # Send the user brief.
        # If the session has a pending tool call from a crashed/interrupted run,
        # the API rejects user.message. In that case, interrupt and start fresh.
        try:
            await self._client.beta.sessions.events.send(
                session_id,
                events=[{"type": "user.message", "content": [{"type": "text", "text": brief}]}],
            )
        except BadRequestError as e:
            if "waiting on responses" in str(e):
                print(f"[ManagedAgent] session {session_id} has pending tool calls, resetting")
                try:
                    await self.interrupt_session(session_id)
                except Exception:
                    pass
                session_id = await self._create_session(brief, project_id)
                yield {"type": "session", "session_id": session_id}
                seen_event_ids.clear()
                try:
                    existing = await self._client.beta.sessions.events.list(session_id, limit=100, order="desc")
                    async for ev in existing:
                        ev_id = getattr(ev, "id", None)
                        if ev_id:
                            seen_event_ids.add(ev_id)
                except Exception:
                    pass
                await self._client.beta.sessions.events.send(
                    session_id,
                    events=[{"type": "user.message", "content": [{"type": "text", "text": brief}]}],
                )
            else:
                raise

        try:
            while True:
                stream = await self._client.beta.sessions.events.stream(session_id)
                went_idle = False
                got_tool_call = False

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
                            if text:
                                yield {"type": "agent_message", "text": text}

                    elif ev_type == "agent.custom_tool_use":
                        tool_calls_made += 1
                        if tool_calls_made > max_tool_calls:
                            yield {"type": "error", "message": f"exceeded max_tool_calls={max_tool_calls}"}
                            return
                        name = ev.name
                        tool_input = ev.input or {}
                        tool_use_id = ev.id
                        yield {
                            "type": "tool_call",
                            "name": name,
                            "input_summary": _summarize_input(tool_input),
                            "tool_use_id": tool_use_id,
                        }
                        fn = TOOL_DISPATCH.get(name)
                        if fn is None:
                            result_text = json.dumps({"error": f"unknown tool: {name}"})
                            is_error = True
                        else:
                            try:
                                print(f"[ManagedAgent] tool {name}({_summarize_input(tool_input, 120)})")
                                # Run the tool in a task and emit keepalive pings every
                                # 15 s so the SSE stream doesn't go idle and get killed
                                # by Railway's reverse proxy or the browser.
                                tool_task = asyncio.create_task(fn(ctx, **tool_input))
                                elapsed = 0
                                while not tool_task.done():
                                    try:
                                        await asyncio.wait_for(asyncio.shield(tool_task), timeout=15.0)
                                    except asyncio.TimeoutError:
                                        elapsed += 15
                                        yield {
                                            "type": "keepalive",
                                            "tool_use_id": tool_use_id,
                                            "elapsed_seconds": elapsed,
                                        }
                                result_text = tool_task.result()
                                is_error = False
                            except Exception as e:
                                result_text = json.dumps({"error": str(e)})
                                is_error = True

                        # Emit a tool_result event for the UI activity log.
                        yield {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "summary": _summarize_result(result_text),
                            "is_error": is_error,
                        }
                        # Drain new artifacts that the tool just produced.
                        if ctx.new_artifacts:
                            for art in ctx.new_artifacts:
                                yield {"type": "artifact", "artifact": art}
                            ctx.new_artifacts.clear()

                        # Hand the tool result back to the agent.
                        await self._client.beta.sessions.events.send(
                            session_id,
                            events=[
                                {
                                    "type": "user.custom_tool_result",
                                    "custom_tool_use_id": tool_use_id,
                                    "content": [{"type": "text", "text": result_text}],
                                    "is_error": is_error,
                                }
                            ],
                        )
                        got_tool_call = True
                        # Re-open stream so we receive the next batch.
                        break

                    elif ev_type == "session.status_idle":
                        went_idle = True
                        break

                    elif ev_type == "session.error":
                        err = getattr(ev, "error", None)
                        msg = getattr(err, "message", None) or str(err) or "unknown session error"
                        yield {"type": "error", "message": msg}
                        return

                if went_idle:
                    break
                if not got_tool_call:
                    # Stream ended without idle and without dispatching a tool —
                    # nothing left to do for this turn.
                    break

            yield {"type": "done", "session_id": session_id}

        except asyncio.CancelledError:
            # Client disconnected (Stop button or page nav). Tell Anthropic to abort.
            print(f"[ManagedAgent] cancelled — interrupting session {session_id}")
            try:
                await self.interrupt_session(session_id)
            finally:
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
