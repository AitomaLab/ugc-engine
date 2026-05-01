"""
Creative OS — Video Generation Router

Handles video generation with mode-aware routing:
- UGC mode → Veo 3.1
- Cinematic mode → Kling 3.0
- AI Clone mode → InfiniTalk + ElevenLabs (via core API clone-jobs)
"""
import os
import re
import sys
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from core_api_client import CoreAPIClient
from services.model_router import get_video_mode, get_clip_lengths


def _load_creative_os_generate_scenes():
    """Load the creative-os local generate_scenes.py by absolute file path.

    There are two `generate_scenes.py` files on disk with diverging APIs:
    - repo-root version owns `generate_music` (legacy music pipeline)
    - creative-os local version owns `generate_video_with_retry(element_ids=...)`
      and `_wavespeed_primary_enabled()` (new element-aware Kling path).

    A bare `import generate_scenes` returns whichever one wins the sys.path
    race — and `managed_agent_client.py` prepends the repo root at import
    time, so the wrong one wins for video pipelines. This helper bypasses
    sys.path entirely by loading the creative-os file under a distinct
    sys.modules key.
    """
    import importlib.util
    from pathlib import Path
    cached = sys.modules.get("creative_os_generate_scenes")
    if cached is not None:
        return cached
    path = Path(__file__).resolve().parent.parent / "generate_scenes.py"
    spec = importlib.util.spec_from_file_location("creative_os_generate_scenes", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["creative_os_generate_scenes"] = mod
    spec.loader.exec_module(mod)
    return mod


def _refund_on_failure(user_id: Optional[str], credit_cost: Optional[int], job_id: str, reason: str) -> None:
    """Best-effort refund for a failed generation. Swallows all errors."""
    if not user_id or not credit_cost or credit_cost <= 0:
        return
    try:
        from ugc_db.db_manager import refund_credits
        refund_credits(user_id, credit_cost, {"reason": reason, "job_id": job_id})
        print(f"[Refund] {credit_cost} credits refunded to {user_id} for job {job_id} ({reason})")
    except Exception as e:
        print(f"[Refund] FAILED to refund {credit_cost} credits for job {job_id}: {e}")


def _sanitize_influencer_description(description: str, actual_name: str) -> str:
    """Replace any wrong name embedded in the AI-generated identity description.

    AI identity generation sometimes bakes a fictional first name into the
    description text (e.g. "Meg is a grounded...") that may differ from the
    influencer's actual stored name.  This helper detects the pattern
    '<Name> is a ...' at the start and replaces <Name> with actual_name.
    """
    if not description or not actual_name:
        return description

    # Pattern: "SomeName is a ..." at the very start
    match = re.match(r'^([A-Z][a-z]+)\s+is\s+', description)
    if match:
        embedded_name = match.group(1)
        if embedded_name.lower() != actual_name.lower():
            description = re.sub(
                r'\b' + re.escape(embedded_name) + r'\b',
                actual_name,
                description,
            )

    # Also catch "SomeName, a 25-year-old" pattern
    match2 = re.match(r'^([A-Z][a-z]+),?\s', description)
    if match2:
        embedded_name = match2.group(1)
        if embedded_name.lower() != actual_name.lower():
            description = re.sub(
                r'\b' + re.escape(embedded_name) + r'\b',
                actual_name,
                description,
            )

    return description


def _derive_asset_name(prompt: str, fallback: str = "Video") -> str:
    """Derive a short, human-readable asset name from the generation prompt.

    Used as `campaign_name` in job records, which surfaces in notifications
    and the asset library. Keeps at most 4 words.
    """
    if not prompt or not prompt.strip():
        return fallback
    # Strip markdown-style formatting, system tags, and excessive whitespace
    clean = re.sub(r'\[.*?\]', '', prompt).strip()
    clean = re.sub(r'\s+', ' ', clean)
    if not clean:
        return fallback
    words = clean.split()
    if len(words) <= 4:
        return clean
    return ' '.join(words[:4]) + '…'


router = APIRouter(prefix="/generate/video", tags=["video-generation"])



class ElementRef(BaseModel):
    name: str  # e.g. "element_lipstick"
    type: str  # "product" or "influencer"
    image_url: Optional[str] = None



class VideoGenerateRequest(BaseModel):
    prompt: str
    mode: str  # "ugc", "cinematic_video", "ai_clone"
    project_id: str
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None
    reference_image_url: Optional[str] = None  # Generated image to use as first frame
    language: str = "en"
    clip_length: int = 5  # seconds
    full_video_mode: bool = False
    video_length: int = 15  # 15 or 30 (only when full_video_mode=True)
    background_music: bool = True
    captions: bool = True
    element_refs: Optional[list[ElementRef]] = None  # @mention-based element refs from frontend
    multi_shot_mode: bool = False  # Kling 3.0 multi-shot (backend auto-splits prompt into shots)
    reference_image_urls: Optional[list[str]] = None  # Seedance 2.0 — multi-image reference
    reference_video_urls: Optional[list[str]] = None  # Seedance 2.0 — video reference
    aspect_ratio: Optional[str] = None  # "9:16" (vertical) or "16:9" (horizontal). None = pipeline default (vertical).
    product_type: Optional[str] = None  # "physical" | "digital" — resolved from product row when omitted.
    app_clip_id: Optional[str] = None  # Picked app clip UUID — drives composite + B-roll concat.


# ── Job record helpers (via core API — handles auth + RLS) ───────────

async def _create_video_job_record(
    client: CoreAPIClient,
    data: VideoGenerateRequest,
    task_id: str,
    prompt: str,
    model_api: str,
    duration: int,
) -> dict:
    """Create a video_jobs record via the core API /jobs endpoint."""
    try:
        # Resolve influencer_id — FK constraint requires a valid ID
        influencer_id = data.influencer_id
        if not influencer_id:
            try:
                influencers = await client.list_influencers()
                influencer_id = influencers[0]["id"] if influencers else None
            except Exception:
                pass

        if not influencer_id:
            print("[Creative OS] WARNING: No valid influencer_id — job record may fail")
            influencer_id = "00000000-0000-0000-0000-000000000000"

        product_type = data.product_type
        if not product_type and data.app_clip_id:
            product_type = "digital"
        if not product_type and data.product_id:
            try:
                p = await client.get_product(data.product_id)
                if p:
                    if p.get("type") in ("physical", "digital"):
                        product_type = p["type"]
                    elif p.get("website_url"):
                        product_type = "digital"
            except Exception:
                pass
        if product_type not in ("physical", "digital"):
            product_type = "physical"

        job_payload: dict = {
            "influencer_id": influencer_id,
            "product_id": data.product_id,
            "product_type": product_type,
            "model_api": model_api,
            "length": duration,
            "campaign_name": _derive_asset_name(prompt),
            "video_language": data.language,
            "subtitles_enabled": data.captions,
            "music_enabled": data.background_music,
            "hook": prompt[:500],
        }
        if data.app_clip_id:
            job_payload["app_clip_id"] = data.app_clip_id
        job = await client.create_job(job_payload)
        job_id = job.get("id") or job.get("job", {}).get("id")
        print(f"[Creative OS] Created video job record: {job_id}")
        return {"id": job_id, "kie_task_id": task_id}
    except Exception as e:
        print(f"[Creative OS] WARNING: Failed to create job record: {e}")
        import traceback; traceback.print_exc()
        return {"id": None, "kie_task_id": task_id}


async def _update_video_job_via_api(token: str, project_id: str, job_id: str, updates: dict):
    """Update a video_jobs record via Supabase REST API.

    Uses the service key for auth when available so that background
    pipeline tasks (which can run for several minutes) are immune to
    the user JWT expiring mid-generation.
    """
    import httpx
    from pathlib import Path
    from dotenv import load_dotenv
    from env_loader import load_env
    load_env(Path(__file__))

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not supabase_url or not anon_key or not job_id:
        print(f"[Creative OS] Cannot update job — missing config or job_id")
        return

    # Prefer the service_role JWT (never expires, bypasses RLS) over the
    # user JWT which can expire during long-running background pipelines.
    # SUPABASE_SERVICE_ROLE_KEY = the service_role JWT from Supabase dashboard.
    # SUPABASE_SERVICE_KEY = legacy name (may be JWT secret, not a JWT).
    service_role_jwt = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    auth_token = service_role_jwt if service_role_jwt else token

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.patch(
                f"{supabase_url}/rest/v1/video_jobs?id=eq.{job_id}",
                headers=headers,
                json=updates,
            )
            if resp.status_code < 300:
                print(f"[Creative OS] Updated job {job_id}: {list(updates.keys())}")
            else:
                print(f"[Creative OS] Update failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as e:
        print(f"[Creative OS] WARNING: Failed to update job {job_id}: {e}")


# ── Kie.ai task polling ──────────────────────────────────────────────

async def _poll_kie_task(
    task_id: str,
    job_id: str,
    model_type: str,
    token: str,
    project_id: str,
):
    """Background task: poll kie.ai until the video is ready, then update DB."""
    import httpx
    import asyncio

    if not job_id:
        print(f"[Creative OS] Skipping poll — no job_id for task {task_id}")
        return

    kie_url = os.getenv("KIE_API_URL", "https://api.kie.ai")
    kie_key = os.getenv("KIE_API_KEY", "")
    headers = {"Authorization": f"Bearer {kie_key}"}

    # Different status endpoints for Kling vs Veo
    if model_type == "veo":
        status_url = f"{kie_url}/api/v1/veo/status/{task_id}"
    else:
        status_url = f"{kie_url}/api/v1/jobs/status/{task_id}"

    max_attempts = 300  # 25 minutes (5s intervals)
    for attempt in range(max_attempts):
        await asyncio.sleep(5)
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(status_url, headers=headers)
                if resp.status_code != 200:
                    continue
                result = resp.json()
                status_data = result.get("data", {})
                task_status = status_data.get("status", "").lower()

                if task_status in ("completed", "succeed", "success"):
                    video_url = (
                        status_data.get("outputUrl")
                        or status_data.get("output", {}).get("videoUrl")
                        or status_data.get("videoUrl")
                        or status_data.get("resultUrl")
                    )
                    if video_url:
                        await _update_video_job_via_api(token, project_id, job_id, {
                            "status": "success",
                            "final_video_url": video_url,
                            "preview_url": video_url,
                        })
                        print(f"[Creative OS] Video job {job_id} completed: {video_url}")
                        return
                elif task_status in ("failed", "error"):
                    error_msg = status_data.get("error", "Generation failed on kie.ai")
                    await _update_video_job_via_api(token, project_id, job_id, {
                        "status": "failed",
                        "error_message": str(error_msg)[:500],
                    })
                    print(f"[Creative OS] Video job {job_id} failed: {error_msg}")
                    return
        except Exception as e:
            print(f"[Creative OS] Poll attempt {attempt} error: {e}")
            continue

    # Timeout
    await _update_video_job_via_api(token, project_id, job_id, {
        "status": "failed",
        "error_message": "Generation timed out after 10 minutes",
    })


# ── AI Script Generation ─────────────────────────────────────────────

class AIScriptRequest(BaseModel):
    project_id: str
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None
    reference_image_url: Optional[str] = None
    language: str = "en"
    clip_length: int = 8
    full_video_mode: bool = False  # True = multi-scene 15s/30s script
    context: Optional[str] = None  # User's existing prompt text as creative direction


@router.post("/ai-script")
async def generate_ai_script(data: AIScriptRequest, user: dict = Depends(get_current_user)):
    """Generate an AI script adapted to clip length, product, and influencer context.

    Two paths:
    - Product present → core engine generate_script() (3-call prompt chain)
    - No product → GPT-4o with veo_ugc_director system prompt

    full_video_mode changes behavior:
    - True: generates a complete multi-scene script for 15/30s videos
    - False: generates a short, punchy single-clip script
    """
    client = CoreAPIClient(token=user["token"], project_id=data.project_id)
    lang_name = "English" if data.language.lower() in ("en", "english") else "Spanish"

    print(f"[AI Script] Request: lang={data.language} clip={data.clip_length}s "
          f"full_video={data.full_video_mode} product={data.product_id} influencer={data.influencer_id}")

    script_text = ""

    # ── Path A: Product available → core engine script generation ──
    if data.product_id:
        try:
            # Resolve influencer_id for the core API
            influencer_id = data.influencer_id
            if not influencer_id:
                try:
                    influencers = await client.list_influencers()
                    influencer_id = influencers[0]["id"] if influencers else None
                except Exception:
                    pass

            product_type = "physical"
            if data.product_id:
                try:
                    product = await client.get_product(data.product_id)
                    if product and product.get("website_url"):
                        product_type = "digital"
                except Exception:
                    pass

            if data.full_video_mode:
                # Full video → structured JSON format for multi-scene script
                result = await client.generate_scripts(
                    product_id=data.product_id,
                    duration=data.clip_length,
                    influencer_id=influencer_id,
                    product_type=product_type,
                    video_language=data.language,
                    context=data.context if data.context else None,
                )
                script_json = result.get("script_json", {})
                if script_json:
                    # Flatten scenes into a readable script
                    scenes = script_json.get("scenes", [])
                    if scenes:
                        parts = []
                        for scene in scenes:
                            dialogue = scene.get("dialogue", "").strip()
                            if dialogue:
                                parts.append(dialogue)
                        script_text = "\n\n".join(parts)
                        print(f"[AI Script] Structured script: {len(scenes)} scenes, {len(script_text)} chars")
                    else:
                        # Fallback: check for legacy format in the response
                        script_text = result.get("script", "")
            else:
                # Clip mode → legacy format
                result = await client.generate_script(
                    product_id=data.product_id,
                    duration=data.clip_length,
                    influencer_id=influencer_id,
                    product_type=product_type,
                    output_format="legacy",
                    video_language=data.language,
                    context=data.context if data.context else None,
                )
                generated = result.get("script", "")
                if generated:
                    # For clips, use the full script (all segments joined)
                    if "|||" in generated:
                        script_text = " ".join(seg.strip() for seg in generated.split("|||") if seg.strip())
                    else:
                        script_text = generated.strip()

            if script_text:
                print(f"[AI Script] Core engine script ({len(script_text)} chars): {script_text[:120]}...")
        except Exception as e:
            print(f"[AI Script] Core engine failed: {e}")
            import traceback; traceback.print_exc()

    # ── Path B: No product or core failed → GPT-4o with UGC director ──
    if not script_text:
        try:
            from services.prompt_enhancer import enhance_prompt

            # Build context for the prompt enhancer
            enhance_ctx = {}
            if data.reference_image_url:
                enhance_ctx["image_url"] = data.reference_image_url

            # Fetch product/influencer names for context
            if data.product_id:
                try:
                    product = await client.get_product(data.product_id)
                    if product:
                        enhance_ctx["product_name"] = product.get("name")
                        desc = product.get("visual_description") or {}
                        enhance_ctx["product_description"] = (
                            desc if isinstance(desc, str)
                            else desc.get("visual_description", "")
                        )
                except Exception:
                    pass

            if data.influencer_id:
                try:
                    influencer = await client.get_influencer(data.influencer_id)
                    if influencer:
                        enhance_ctx["influencer_name"] = influencer.get("name")
                except Exception:
                    pass

            # Build a user prompt that asks for the right type of script
            user_prompt = data.context or "Create a natural UGC video script"

            if data.full_video_mode:
                # Full video: multi-scene script with proper word count
                words_target = 40 if data.clip_length <= 15 else 80
                clip_prompt = (
                    f"Generate a complete UGC video script for a {data.clip_length}-second video. "
                    f"The script should have 3-4 natural-sounding scenes/segments, "
                    f"totaling approximately {words_target} words of spoken dialogue. "
                    f"Include a strong hook, middle content, and clear CTA. "
                    f"The dialogue must be in {lang_name}. "
                    f"User's creative direction: {user_prompt}"
                )
            else:
                clip_prompt = (
                    f"Generate exactly ONE UGC script option for a {data.clip_length}-second clip. "
                    f"The dialogue must be in {lang_name}. "
                    f"User's creative direction: {user_prompt}"
                )

            enhanced = await enhance_prompt(
                user_prompt=clip_prompt,
                mode="ugc",
                language=data.language,
                context=enhance_ctx,
            )

            if enhanced:
                raw = enhanced[0]["prompt"]
                # Parse dialogue from the enhanced output
                for line in raw.split("\n"):
                    if line.lower().startswith("dialogue:"):
                        script_text = line[len("dialogue:"):].strip()
                        break
                if not script_text:
                    script_text = raw.strip()
                print(f"[AI Script] GPT-4o script ({len(script_text)} chars): {script_text[:120]}...")
        except Exception as e:
            print(f"[AI Script] GPT-4o fallback failed: {e}")
            import traceback; traceback.print_exc()

    if not script_text:
        raise HTTPException(status_code=500, detail="Failed to generate script")

    # Clean up — remove system prompt artifacts and surrounding quotes
    import re
    script_text = re.sub(
        r'^They say this in (?:English|Spanish|[A-Za-z]+) in a natural tone:\s*',
        '', script_text, flags=re.IGNORECASE
    ).strip().strip('"').strip("'")

    return {"script": script_text, "language": lang_name, "clip_length": data.clip_length}


# ── Routes ───────────────────────────────────────────────────────────

@router.post("/")
async def generate_video(
    data: VideoGenerateRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Generate a video using the appropriate model based on mode."""
    print(f"[Video Gen] ── Incoming request ──")
    print(f"  mode={data.mode} full_video={data.full_video_mode} clip_length={data.clip_length}")
    print(f"  product_id={data.product_id} influencer_id={data.influencer_id}")
    print(f"  reference_image_url={data.reference_image_url}")
    print(f"  element_refs={[r.name for r in data.element_refs] if data.element_refs else 'None'}")
    print(f"  prompt={data.prompt[:100]}...")

    mode_config = get_video_mode(data.mode)
    client = CoreAPIClient(token=user["token"], project_id=data.project_id)

    # Validate clip length
    valid_lengths = mode_config["clip_lengths"]
    if valid_lengths and data.clip_length not in valid_lengths:
        data.clip_length = valid_lengths[0]

    # Resolve product/influencer IDs to actual image URLs
    product_image_url = None
    influencer_image_url = None

    # Digital-product app-clip override: when the user picked a specific app clip,
    # use its first frame as the "product image" for the composite step.
    if data.app_clip_id:
        try:
            clip = await client.get_app_clip(data.app_clip_id)
            if clip and clip.get("first_frame_url"):
                product_image_url = clip["first_frame_url"]
                # Force digital routing downstream
                if not data.product_type:
                    data.product_type = "digital"
                print(f"[Video Gen] Using app clip {data.app_clip_id} first frame as product image")
        except Exception as e:
            print(f"[Video Gen] WARNING: Failed to fetch app clip {data.app_clip_id}: {e}")

    if data.product_id and not product_image_url:
        try:
            product = await client.get_product(data.product_id)
            product_image_url = product.get("image_url") if product else None
        except Exception as e:
            print(f"[Video Gen] WARNING: Failed to fetch product {data.product_id}: {e}")

    if data.influencer_id:
        try:
            inf = await client.get_influencer(data.influencer_id)
            influencer_image_url = inf.get("image_url") if inf else None
        except Exception as e:
            print(f"[Video Gen] WARNING: Failed to fetch influencer {data.influencer_id}: {e}")

    # Build the best reference image: prefer explicit selection > product > influencer.
    # Exception: in UGC mode with both product + influencer, leave reference_image_url
    # empty so the pipeline generates a NanoBanana Pro composite instead of skipping it.
    if not data.reference_image_url:
        if data.mode == "ugc" and product_image_url and influencer_image_url:
            pass  # Let _run_ugc_clip_pipeline handle the composite
        else:
            data.reference_image_url = product_image_url or influencer_image_url

    print(f"[Video Gen] Resolved images: product={product_image_url is not None} "
          f"influencer={influencer_image_url is not None} "
          f"reference={data.reference_image_url is not None}")

    if data.mode == "ai_clone":
        return await _generate_clone_video(data, client)
    elif data.mode == "cinematic_video":
        return await _generate_kling_video(data, client, user, background_tasks)
    elif data.mode in ("seedance_2_ugc", "seedance_2_cinematic", "seedance_2_product"):
        return await _generate_seedance_video(data, client, user, background_tasks)
    else:
        return await _generate_veo_video(data, client, user, background_tasks)


# ── AI Clone ─────────────────────────────────────────────────────────

async def _generate_clone_video(data: VideoGenerateRequest, client: CoreAPIClient) -> dict:
    """Generate AI Clone video via InfiniTalk + ElevenLabs (proxied through core API)."""
    payload = {
        "prompt": data.prompt,
        "language": data.language,
        "influencer_id": data.influencer_id,
        "clip_length": data.clip_length,
    }
    return await client._request("POST", "/clone-jobs", json=payload)


# ── Seedance 2.0 Fast ─────────────────────────────────────────────────

async def _generate_seedance_video(
    data: VideoGenerateRequest,
    client: CoreAPIClient,
    user: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate video via Seedance 2.0 Fast (KIE bytedance/seedance-2-fast).

    The `prompt` field is passed verbatim — it is expected to be the full
    4-section structured Seedance output (Style & Mood / Dynamic /
    Static / Audio). No NanoBanana composite is built: Seedance accepts
    multiple image + video reference URLs directly.
    """
    # The video_jobs table has a FK on influencer_id, so the core API's /jobs
    # endpoint rejects the nil UUID. Fall back to the first influencer purely
    # to satisfy the FK — the downstream pipeline below gates image injection
    # on the ORIGINAL data.influencer_id, so no persona image / product leaks
    # into a prompt that didn't ask for one.
    influencer_id = data.influencer_id
    if not influencer_id:
        try:
            influencers = await client.list_influencers()
            influencer_id = influencers[0]["id"] if influencers else None
        except Exception:
            pass
    if not influencer_id:
        influencer_id = "00000000-0000-0000-0000-000000000000"

    product_type = "physical" if data.product_id else "digital"

    try:
        job = await client.create_job({
            "influencer_id": influencer_id,
            "product_id": data.product_id,
            "product_type": product_type,
            "model_api": "seedance-2.0-fast",
            "length": data.clip_length,
            "campaign_name": _derive_asset_name(data.prompt),
            "video_language": data.language,
            "subtitles_enabled": False,
            "music_enabled": False,
            "hook": (data.prompt or "")[:500],
        })
        job_id = job.get("id") or job.get("job", {}).get("id")
        credit_cost = int(job.get("credits_deducted") or 0)
        print(f"[Seedance] Job created: {job_id} (cost={credit_cost})")
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)[:200]}")

    # ── Onboarding free video: refund credits for the user's first video ──
    # Check if this is the first-ever job in this project. If so, it's the
    # onboarding welcome video and should be free.
    if credit_cost > 0 and data.project_id and user.get("id"):
        try:
            existing_jobs = await client.list_jobs()
            # Only the job we just created should exist
            if len(existing_jobs or []) <= 1:
                from ugc_db.db_manager import refund_credits
                refund_credits(user["id"], credit_cost, {"reason": "onboarding_free_video", "job_id": job_id})
                print(f"[Seedance] Onboarding free video — refunded {credit_cost} credits to {user['id']}")
                credit_cost = 0
        except Exception as e:
            print(f"[Seedance] WARNING: onboarding refund check failed: {e}")

    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create job record")

    # Resolve references.
    #
    # For digital products (app_clip_id set): feed Seedance the full app clip
    # as a VIDEO reference — it anchors on real motion + UI pixels, which is
    # dramatically more faithful than a static first-frame screenshot. The
    # influencer face (if @-mentioned) stays as an image reference so the
    # persona is locked in.
    #
    # For physical products (no app_clip): fall back to product + influencer
    # images as before.
    ref_images: list[str] = []
    ref_videos: list[str] = []
    app_clip = None
    app_clip_first_frame = None
    if data.app_clip_id:
        try:
            app_clip = await client.get_app_clip(data.app_clip_id)
            if app_clip:
                if app_clip.get("video_url"):
                    ref_videos.append(app_clip["video_url"])
                app_clip_first_frame = app_clip.get("first_frame_url")
        except Exception as e:
            print(f"[Seedance] WARNING: app clip fetch failed: {e}")

    if data.influencer_id:
        try:
            inf = await client.get_influencer(data.influencer_id)
            if inf and inf.get("image_url"):
                ref_images.append(inf["image_url"])
        except Exception as e:
            print(f"[Seedance] WARNING: influencer fetch failed: {e}")

    # Only fall back to product / bare ref image when NO app clip is set.
    if not app_clip:
        if data.product_id:
            try:
                product = await client.get_product(data.product_id)
                if product and product.get("image_url"):
                    ref_images.append(product["image_url"])
            except Exception as e:
                print(f"[Seedance] WARNING: product fetch failed: {e}")
        if not ref_images and data.reference_image_url:
            ref_images.append(data.reference_image_url)

    # Merge explicit URLs from the agent, deduped. Drop the app clip's
    # first_frame_url if the agent passed it — the video reference covers it.
    if data.reference_image_urls:
        for u in data.reference_image_urls:
            if not u or u in ref_images or u == app_clip_first_frame:
                continue
            ref_images.append(u)
    if data.reference_video_urls:
        for u in data.reference_video_urls:
            if u and u not in ref_videos:
                ref_videos.append(u)

    # Cap at Seedance's 4-image ceiling.
    seen: set[str] = set()
    ref_images = [u for u in ref_images if not (u in seen or seen.add(u))][:4]

    background_tasks.add_task(
        _run_seedance_clip_pipeline,
        job_id=job_id,
        data=data,
        token=user["token"],
        project_id=data.project_id,
        reference_image_urls=ref_images,
        reference_video_urls=ref_videos,
        user_id=user.get("id"),
        credit_cost=credit_cost,
    )

    return {
        "status": "generating",
        "job_id": job_id,
        "mode": data.mode,
        "clip_length": data.clip_length,
    }


async def _run_seedance_clip_pipeline(
    job_id: str,
    data: VideoGenerateRequest,
    token: str,
    project_id: str,
    reference_image_urls: list[str],
    reference_video_urls: list[str],
    user_id: Optional[str] = None,
    credit_cost: int = 0,
):
    """Background: call KIE Seedance 2.0 Fast and finalize the job."""
    import asyncio
    import tempfile
    from datetime import datetime as _dt
    generate_scenes = _load_creative_os_generate_scenes()

    client_sync = CoreAPIClient(token=token, project_id=project_id)

    # ── Digital-product app-clip context ──
    # Reference resolution (video ref for the app clip, image ref for the
    # influencer) is owned by _generate_seedance_video upstream. Here we only
    # refetch the app clip so the post-generation B-roll concat step below has
    # access to the walkthrough video_url.
    app_clip = None
    if data.app_clip_id:
        try:
            app_clip = await client_sync.get_app_clip(data.app_clip_id)
        except Exception as e:
            print(f"[Seedance] WARNING: Failed to fetch app clip {data.app_clip_id}: {e}")

    try:
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Enhancing prompt...",
            "progress": 5,
        })

        # Expand the freeform brief into the 4-section Seedance Director
        # structure (Style & Mood / Dynamic / Static / Audio). Mirror the
        # Kling pattern — fall back to the raw prompt if enhancement fails.
        structured_prompt = data.prompt
        try:
            from services.prompt_enhancer import enhance_prompt
            enhance_context = {"duration": data.clip_length, "has_reference": bool(reference_image_urls or reference_video_urls)}
            if reference_image_urls:
                enhance_context["image_url"] = reference_image_urls[0]
            enhanced = await enhance_prompt(
                user_prompt=data.prompt,
                mode=data.mode,
                language=data.language,
                context=enhance_context,
            )
            if enhanced:
                structured_prompt = enhanced[0].get("prompt") or data.prompt
            print(f"[Seedance] Enhanced prompt ({len(structured_prompt)} chars)")
        except Exception as e:
            print(f"[Seedance] Prompt enhance failed (using raw): {e}")

        # Safety net: ensure reference bindings are present. Without them,
        # Seedance treats the references as loose style guides and
        # hallucinates on-screen content.
        if reference_video_urls and "@Video1" not in structured_prompt:
            structured_prompt += (
                "\n\nIMPORTANT: The app interface shown in @Video1 must be rendered with exact "
                "visual fidelity — preserve its layout, typography, colors, and any visible UI "
                "text from @Video1. Do not invent screen content."
            )
            print("[Seedance] Injected @Video1 binding (not found in enhanced prompt)")
        if reference_image_urls and "@Image1" not in structured_prompt:
            subject = "person" if reference_video_urls else "product"
            if subject == "person":
                structured_prompt += (
                    "\n\nIMPORTANT: The person shown in @Image1 must be rendered with exact "
                    "facial likeness — preserve their features, skin tone, and hair from @Image1. "
                    "Do not invent a different face."
                )
            else:
                structured_prompt += (
                    "\n\nIMPORTANT: The product shown in @Image1 must be rendered with exact visual "
                    "fidelity — preserve all text, logos, typography, and spelling from @Image1. "
                    "Do not hallucinate or alter any text on the product."
                )
            print(f"[Seedance] Injected @Image1 binding (subject={subject})")

        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Generating Seedance video...",
            "progress": 10,
        })

        print(
            f"[Seedance] ref_images={reference_image_urls or []} "
            f"ref_videos={reference_video_urls or []} duration={data.clip_length}s "
            f"aspect={data.aspect_ratio or '9:16'} prompt_len={len(structured_prompt)}",
            flush=True,
        )

        def _submit():
            return generate_scenes.generate_video_with_retry(
                prompt=structured_prompt,
                model_api="seedance-2.0-fast",
                duration=data.clip_length,
                reference_image_urls=reference_image_urls or None,
                reference_video_urls=reference_video_urls or None,
                aspect_ratio=data.aspect_ratio or "9:16",
            )

        result = await asyncio.to_thread(_submit)
        video_url = result.get("videoUrl")
        if not video_url:
            raise RuntimeError(f"Seedance returned no videoUrl: {result}")

        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Uploading video...",
            "progress": 90,
        })

        final_url = video_url
        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name
            await asyncio.to_thread(generate_scenes.download_video, video_url, tmp_path)
            storage_filename = f"seedance_clip_{job_id[:8]}_{timestamp}.mp4"
            try:
                from ugc_db.db_manager import get_supabase
                sb = get_supabase()
                with open(tmp_path, "rb") as f:
                    sb.storage.from_("generated-videos").upload(
                        storage_filename, f,
                        file_options={"content-type": "video/mp4"},
                    )
                final_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
            except Exception as upload_err:
                print(f"[Seedance] Supabase upload failed: {upload_err}, using raw URL")
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        except Exception as e:
            print(f"[Seedance] Upload failed, using raw URL: {e}")

        # App-clip B-roll concat (digital products) is now a separate agent
        # step — the agent chains `splice_app_clip(job_id)` after this tool
        # returns so the user sees two discrete activity cards (cinematic
        # done → splicing B-roll) instead of a single 3-min wait. We stash
        # app_clip_id in metadata so splice_app_clip can find it.
        meta = {"mode": data.mode, "engine": "seedance-2.0-fast"}
        if app_clip and app_clip.get("video_url"):
            meta["app_clip_id"] = data.app_clip_id
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "success",
            "progress": 100,
            "final_video_url": final_url,
            "preview_url": None,
            "preview_type": None,
            "status_message": None,
            "metadata": meta,
        })
        print(f"[Seedance] Job {job_id} complete: {final_url[:80]}...")
    except Exception as e:
        import traceback; traceback.print_exc()
        summary = (
            f"refs={len(reference_image_urls or [])}i/{len(reference_video_urls or [])}v "
            f"dur={data.clip_length}s aspect={data.aspect_ratio or '9:16'}"
        )
        print(f"[Seedance] FAILED {summary} err={str(e)[:600]}", flush=True)
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "failed",
            "error_message": f"Seedance generation failed [{summary}]: {str(e)[:400]}",
        })
        _refund_on_failure(user_id, credit_cost, job_id, "seedance_generation_failed")


# ── Kling 3.0 ────────────────────────────────────────────────────────

async def _generate_kling_video(
    data: VideoGenerateRequest,
    client: CoreAPIClient,
    user: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate cinematic video via Kling 3.0.

    When both product + influencer are present, generates a NanoBanana Pro
    composite image first, then animates with Kling 3.0 using the
    kling_director system prompt. Otherwise uses a single reference image.
    """

    # 1. Create job record immediately so frontend can poll.
    # The video_jobs FK requires a real influencer_id, so fall back to the
    # first available one purely to satisfy the constraint. The downstream
    # pipeline gates influencer_image_url on the ORIGINAL data.influencer_id
    # below, so a random persona's image never leaks into the rendered scene.
    influencer_id = data.influencer_id
    if not influencer_id:
        try:
            influencers = await client.list_influencers()
            influencer_id = influencers[0]["id"] if influencers else None
        except Exception:
            pass
    if not influencer_id:
        influencer_id = "00000000-0000-0000-0000-000000000000"

    product_type = "physical" if data.product_id else "digital"

    try:
        job = await client.create_job({
            "influencer_id": influencer_id,
            "product_id": data.product_id,
            "product_type": product_type,
            "model_api": "kling-3.0/video",
            "length": data.clip_length,
            "campaign_name": _derive_asset_name(data.prompt),
            "video_language": data.language,
            "subtitles_enabled": False,
            "music_enabled": False,
            "hook": data.prompt[:500] if data.prompt else "",
        })
        job_id = job.get("id") or job.get("job", {}).get("id")
        credit_cost = int(job.get("credits_deducted") or 0)
        print(f"[Creative OS] Cinematic job created: {job_id} (cost={credit_cost})")
    except Exception as e:
        print(f"[Creative OS] Job creation failed: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)[:200]}")

    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create job record")

    # Resolve product/influencer image URLs for the background task
    product_image_url = None
    influencer_image_url = None
    if data.product_id:
        try:
            product = await client.get_product(data.product_id)
            product_image_url = product.get("image_url") if product else None
        except Exception as e:
            print(f"[Cinematic] WARNING: Failed to fetch product image: {e}")
    if data.influencer_id:
        try:
            inf = await client.get_influencer(data.influencer_id)
            influencer_image_url = inf.get("image_url") if inf else None
        except Exception as e:
            print(f"[Cinematic] WARNING: Failed to fetch influencer image: {e}")

    # 2. Launch background pipeline
    background_tasks.add_task(
        _run_cinematic_clip_pipeline,
        job_id=job_id,
        data=data,
        token=user["token"],
        project_id=data.project_id,
        influencer_id=influencer_id,
        product_image_url=product_image_url,
        influencer_image_url=influencer_image_url,
        user_id=user.get("id"),
        credit_cost=credit_cost,
    )

    duration = max(3, min(15, data.clip_length))
    return {
        "status": "generating",
        "job_id": job_id,
        "mode": "cinematic_video",
        "clip_length": duration,
    }


async def _split_prompt_into_shots(
    user_prompt: str,
    enhanced_prompt: str,
    target_duration: int = 10,
    element_tags: str = "",
    element_context: list[dict] | None = None,
) -> list[dict] | None:
    """Use GPT-4o to split a user prompt into Kling 3.0 multi-shot format.

    Uses the user's ORIGINAL prompt as the narrative source, enriched by the
    enhanced prompt's visual style. Returns [{"prompt": ..., "duration": ...}] or None.
    """
    import json
    from openai import AsyncOpenAI
    import os

    try:
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Build element info string
        element_info = ""
        if element_context:
            for e in element_context:
                element_info += f"  - @{e['name']}: {e.get('description', 'N/A')}\n"

        system = (
            "You are a cinematic multi-shot director for Kling 3.0 AI video generation.\n"
            "Your job is to convert the user's narrative into a multi-shot video sequence.\n\n"
            "CRITICAL RULES:\n"
            "1. The user's original prompt describes WHAT HAPPENS. You MUST follow their narrative exactly.\n"
            "   - If they say a character picks up a product, one shot MUST show that action.\n"
            "   - If they describe a sequence of events, your shots must follow that sequence.\n"
            "2. The enhanced prompt provides VISUAL STYLE guidance (lighting, camera work, mood).\n"
            "   Use it for visual direction, NOT for overriding the user's narrative.\n"
            "3. Each shot MUST have:\n"
            "   - A different camera distance (wide/medium/close-up/detail)\n"
            "   - Clear physical ACTION (movement, gesture, interaction - NOT static poses)\n"
            "   - Duration: 1-12 seconds (integer only)\n"
            "4. The SUM of all shot durations MUST equal the target total duration exactly.\n"
            "5. Each shot prompt: max 500 characters, written in English.\n"
            "6. Do NOT write static product-only shots unless the user specifically asks for them.\n"
            "   Characters must MOVE, INTERACT, and PERFORM actions.\n"
            "7. Do NOT include dialogue or speech in any language.\n"
            "8. If element tags are provided, append ALL of them at the END of EACH shot prompt.\n\n"
            "Respond with a JSON object:\n"
            '{"shots": [{"prompt": "shot description...", "duration": 3}, ...]}'
        )

        user_msg = f"Target total duration: {target_duration}s\n\n"
        user_msg += f"USER'S ORIGINAL PROMPT (this is the narrative you MUST follow):\n{user_prompt}\n\n"
        user_msg += f"ENHANCED VISUAL STYLE (use for visual direction only):\n{enhanced_prompt}\n"
        if element_info:
            user_msg += f"\nELEMENT REFERENCES:\n{element_info}"
        if element_tags.strip():
            user_msg += f"\nElement tags to append to each shot: {element_tags.strip()}\n"

        print(f"[MultiShot] Calling GPT-4o to split into shots (target {target_duration}s)...")
        print(f"[MultiShot] User prompt: {user_prompt[:150]}...")
        print(f"[MultiShot] Enhanced prompt ({len(enhanced_prompt)} chars): {enhanced_prompt[:150]}...")

        resp = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
            max_tokens=2000,
            response_format={"type": "json_object"},
        )

        raw = resp.choices[0].message.content.strip()
        print(f"[MultiShot] GPT split response ({len(raw)} chars): {raw[:500]}")

        parsed = json.loads(raw)

        # Extract the shots array from the JSON object
        shots = None
        if isinstance(parsed, dict):
            for key in ("shots", "multi_prompt", "prompts", "sequence"):
                if key in parsed and isinstance(parsed[key], list):
                    shots = parsed[key]
                    break
            if shots is None:
                for v in parsed.values():
                    if isinstance(v, list) and len(v) >= 2:
                        shots = v
                        break
        elif isinstance(parsed, list):
            shots = parsed

        if not shots:
            print(f"[MultiShot] Could not find shots array in response: {list(parsed.keys()) if isinstance(parsed, dict) else type(parsed)}")
            return None

        # Validate and clamp
        valid_shots = []
        for s in shots:
            if isinstance(s, dict) and "prompt" in s and "duration" in s:
                valid_shots.append({
                    "prompt": str(s["prompt"])[:500],
                    "duration": max(1, min(12, int(s["duration"]))),
                })

        if len(valid_shots) < 2:
            print(f"[MultiShot] Only {len(valid_shots)} valid shots parsed - need at least 2")
            return None

        valid_shots = valid_shots[:5]  # Kling max 5 shots
        total = sum(s["duration"] for s in valid_shots)
        print(f"[MultiShot] Success: {len(valid_shots)} shots, total {total}s")
        for i, s in enumerate(valid_shots):
            print(f"  Shot {i+1} ({s['duration']}s): {s['prompt'][:100]}...")
        return valid_shots

    except Exception as e:
        import traceback
        print(f"[MultiShot] Shot splitting failed: {e}")
        traceback.print_exc()
        return None


async def _run_cinematic_clip_pipeline(
    job_id: str,
    data: VideoGenerateRequest,
    token: str,
    project_id: str,
    influencer_id: str,
    product_image_url: str | None,
    influencer_image_url: str | None,
    user_id: Optional[str] = None,
    credit_cost: int = 0,
):
    """Background task: Cinematic clip pipeline with Kling 3.0 element references.

    Steps:
    1. Build kling_elements from product/influencer images (skip NanoBanana)
    2. Enhance prompt with kling_director system prompt + element tags
    3. Submit to Kling 3.0 API with element refs
    4. Poll for completion
    5. Upload to Supabase Storage
    6. Update job record
    """
    import sys
    from pathlib import Path

    # Add repo root to sys.path for core engine imports (local dev only).
    # On Railway standalone, these imports won't resolve — but the full
    # video pipeline runs on Modal/Celery, not on Creative OS directly.
    from env_loader import load_env
    _root = load_env(Path(__file__))
    if _root and str(_root) not in sys.path:
        # Append (not insert) so creative-os local modules (e.g. generate_scenes.py)
        # always shadow any same-named files at the repo root.
        sys.path.append(str(_root))

    import asyncio
    import httpx
    generate_scenes = _load_creative_os_generate_scenes()
    from services.prompt_enhancer import enhance_prompt
    from services.kling_image import ensure_kling_compatible

    try:
        # ── Step 0: Update status ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "processing",
            "progress": 5,
            "status_message": "Preparing cinematic clip...",
        })

        # ── Step 1: Build element references (skip NanoBanana) ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Building element references...",
            "progress": 10,
        })

        # Kling 3.0 only accepts jpeg/jpg/png — convert anything else (webp,
        # etc.) once and cache the result. No-op for already-compatible URLs.
        product_image_url = await ensure_kling_compatible(product_image_url)
        influencer_image_url = await ensure_kling_compatible(influencer_image_url)
        data.reference_image_url = await ensure_kling_compatible(data.reference_image_url)
        for ref in (data.element_refs or []):
            ref.image_url = await ensure_kling_compatible(ref.image_url)

        # Determine the first-frame image (image_urls[0] for Kling)
        first_frame_url = data.reference_image_url or influencer_image_url or product_image_url

        # Build kling_elements from available images
        kling_elements = []
        element_tags = ""
        element_context = []  # For prompt enhancer

        # Fetch data for element descriptions
        client = CoreAPIClient(token=token, project_id=project_id)
        product = None
        influencer = None

        if data.product_id:
            try:
                product = await client.get_product(data.product_id)
            except Exception as e:
                print(f"[Cinematic] Product fetch warning: {e}")

        if influencer_id and influencer_id != "00000000-0000-0000-0000-000000000000":
            try:
                influencer = await client.get_influencer(influencer_id)
            except Exception as e:
                print(f"[Cinematic] Influencer fetch warning: {e}")

        # ── App-clip context (digital products) ──
        # When a clip is picked, use its first frame as the lead reference
        # (Kling first_frame_url + product element image) so the animation
        # visually leads into the real app UI. Full clip is spliced as
        # B-roll after Kling finishes.
        app_clip = None
        if data.app_clip_id:
            try:
                app_clip = await client.get_app_clip(data.app_clip_id)
                if app_clip and app_clip.get("first_frame_url"):
                    product_image_url = app_clip["first_frame_url"]
                    first_frame_url = data.reference_image_url or app_clip["first_frame_url"]
                    print(f"[Cinematic] Using app clip {data.app_clip_id} first frame as lead reference")
            except Exception as e:
                print(f"[Cinematic] WARNING: Failed to fetch app clip {data.app_clip_id}: {e}")

        # Product element
        if product_image_url:
            visual_desc = product.get("visual_description") or {} if product else {}
            if isinstance(visual_desc, str):
                desc_str = visual_desc[:100]
            else:
                desc_str = visual_desc.get("visual_description", product.get("name", "the product") if product else "the product")[:100]

            kling_elements.append({
                "name": "element_product",
                "description": desc_str,
                "element_input_urls": [product_image_url, product_image_url],
            })
            element_tags += " @element_product"
            element_context.append({"name": "element_product", "description": desc_str})

        # Influencer/character element
        if influencer_image_url:
            inf_desc = "the person/character"
            if influencer:
                inf_name = influencer.get("name", "character")
                raw_detail = influencer.get("description", "")[:100]
                inf_detail = _sanitize_influencer_description(raw_detail, inf_name)
                inf_desc = f"{inf_name} — {inf_detail}" if inf_detail else inf_name

            kling_elements.append({
                "name": "element_character",
                "description": inf_desc,
                "element_input_urls": [influencer_image_url, influencer_image_url],
            })
            element_tags += " @element_character"
            element_context.append({"name": "element_character", "description": inf_desc})

        # Merge @mention-based element_refs from frontend (skip duplicates for same image)
        if data.element_refs:
            existing_names = {e["name"] for e in kling_elements}
            existing_urls = {e["element_input_urls"][0] for e in kling_elements if e.get("element_input_urls")}
            for ref in data.element_refs:
                if ref.name in existing_names:
                    continue  # Skip - already have this element
                if ref.image_url in existing_urls:
                    print(f"[Cinematic] Skipping @mention element {ref.name} - image already used by another element")
                    continue  # Skip - same image already covered
                if len(kling_elements) >= 3:
                    print(f"[Cinematic] Skipping @mention element {ref.name} - Kling max 3 elements reached")
                    break
                kling_elements.append({
                    "name": ref.name,
                    "description": f"{ref.type}: {ref.name.replace('element_', '')}",
                    "element_input_urls": [ref.image_url, ref.image_url],
                })
                element_tags += f" @{ref.name}"
                element_context.append({"name": ref.name, "description": ref.name.replace("element_", "")})
                print(f"[Cinematic] Added @mention element: {ref.name} ({ref.type})")

        # Final cap at 3 elements (Kling max)
        if len(kling_elements) > 3:
            print(f"[Cinematic] Capping elements from {len(kling_elements)} to 3")
            kling_elements = kling_elements[:3]
            # Rebuild element_tags from the kept elements
            element_tags = " ".join(f"@{e['name']}" for e in kling_elements)

        if kling_elements:
            print(f"[Cinematic] Built {len(kling_elements)} element(s): {[e['name'] for e in kling_elements]}")
            # Show first-frame preview
            if first_frame_url:
                await _update_video_job_via_api(token, project_id, job_id, {
                    "status_message": "References ready, building prompt...",
                    "progress": 25,
                    "preview_url": first_frame_url,
                    "preview_type": "image",
                })
        elif first_frame_url:
            print(f"[Cinematic] No elements, using first-frame only: {first_frame_url[:80]}...")
            await _update_video_job_via_api(token, project_id, job_id, {
                "status_message": "Reference image ready, building prompt...",
                "progress": 25,
                "preview_url": first_frame_url,
                "preview_type": "image",
            })
        else:
            print("[Cinematic] No reference images — text-to-video mode")

        # ── Step 2: Enhance prompt with kling_director ──
        is_multi = data.multi_shot_mode
        print(f"[Cinematic] clip_length={data.clip_length}, multi_shot_mode={is_multi}")
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": f"Building cinematic {'multi-shot ' if is_multi else ''}prompt...",
            "progress": 35,
        })

        # If multi-shot, append an instruction so the director produces multi-shot format
        user_prompt_for_enhance = data.prompt
        if is_multi:
            user_prompt_for_enhance += (
                f"\n\n[MULTI-SHOT MODE] Create a multi-shot cinematic sequence for a {data.clip_length}s total video. "
                "Use the multi-shot format with Shot 1, Shot 2, etc. "
                f"Target total duration: {data.clip_length}s. "
                "Each shot should have a different camera angle, distance, and action. "
                "Write all prompts in English. Do NOT include any dialogue or speech."
            )
            print(f"[Cinematic] Multi-shot mode active, target {data.clip_length}s")

        prompt = data.prompt
        raw_enhanced_text = ""
        try:
            enhance_context = {}
            if first_frame_url:
                enhance_context["image_url"] = first_frame_url
            if element_context:
                enhance_context["elements"] = element_context

            if first_frame_url:
                print(f"[Cinematic] Enhancing with VISION image + {len(element_context)} element(s){' (multi-shot)' if is_multi else ''}...")
                enhanced = await enhance_prompt(
                    user_prompt=user_prompt_for_enhance,
                    mode="kling_director",
                    language=data.language,
                    context=enhance_context,
                )
            else:
                enhanced = await enhance_prompt(
                    user_prompt=user_prompt_for_enhance,
                    mode="cinematic",
                    language=data.language,
                )
            prompt = enhanced[0]["prompt"] if enhanced else data.prompt
            # For multi-shot, we also need the raw GPT response text (before parsing)
            raw_enhanced_text = prompt
            print(f"[Cinematic] Enhanced prompt ({len(prompt)} chars): {prompt[:100]}...")
        except Exception as e:
            print(f"[Cinematic] Prompt enhance failed (using raw): {e}")
            prompt = data.prompt
            raw_enhanced_text = prompt

        # Sanitize @tags in prompt — replace user @mentions with plain text, keep only valid element tags
        if kling_elements:
            import re
            valid_element_names = {e["name"] for e in kling_elements}
            # Replace any @tags that aren't valid element names with plain text
            all_at_tags = re.findall(r'@(\w+)', prompt)
            for tag in all_at_tags:
                if tag not in valid_element_names:
                    prompt = prompt.replace(f"@{tag}", tag.replace("_", " "))
            # Ensure all valid element tags are appended
            for tag in element_tags.strip().split():
                if tag not in prompt:
                    prompt += f" {tag}"
        else:
            # Strip any @element_ tags the prompt enhancer may have hallucinated
            import re
            prompt = re.sub(r'\s*@element_\w+', '', prompt).strip()

        # ── Step 3: Submit to Kling 3.0 with element refs ──
        multi_prompt_payload = None
        if is_multi:
            # Auto-split enhanced prompt into shots using GPT
            await _update_video_job_via_api(token, project_id, job_id, {
                "status_message": "Splitting into cinematic shots...",
                "progress": 42,
            })
            multi_prompt_payload = await _split_prompt_into_shots(
                user_prompt=data.prompt,
                enhanced_prompt=raw_enhanced_text,
                target_duration=data.clip_length,
                element_tags=element_tags if kling_elements else "",
                element_context=element_context if kling_elements else None,
            )
            if multi_prompt_payload:
                # Sanitize @tags in shot prompts — only keep tags matching actual kling_elements
                import re
                valid_element_names = {e["name"] for e in kling_elements} if kling_elements else set()
                for shot in multi_prompt_payload:
                    # Find all @tags in the prompt
                    all_tags = re.findall(r'@(\w+)', shot["prompt"])
                    for tag in all_tags:
                        if tag not in valid_element_names:
                            # Remove invalid @tag (user @mention that doesn't match an element)
                            shot["prompt"] = shot["prompt"].replace(f"@{tag}", tag.replace("_", " "))
                            print(f"[MultiShot] Replaced invalid @{tag} with plain text in shot prompt")
                    # Ensure all valid element tags are present at the end
                    for ename in valid_element_names:
                        if f"@{ename}" not in shot["prompt"]:
                            shot["prompt"] += f" @{ename}"
                duration = max(3, min(15, sum(s["duration"] for s in multi_prompt_payload)))
                print(f"[Cinematic] Auto-split into {len(multi_prompt_payload)} shots, total {duration}s")
            else:
                # Fallback: single-shot mode if splitting failed
                print("[Cinematic] Shot splitting failed — falling back to single-shot")
                is_multi = False
                duration = max(3, min(15, data.clip_length))
        else:
            duration = max(3, min(15, data.clip_length))

        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": f"Generating cinematic video with Kling 3.0{' (multi-shot)' if multi_prompt_payload else ''}...",
            "progress": 50,
        })

        # ── WaveSpeed-primary element-id resolution (best-effort) ──
        # If WS-primary is on and we have kling_elements, mint element_ids first
        # so generate_video_with_retry can try the WaveSpeed Kling path. Any
        # failure here just leaves element_ids empty → falls through to legacy
        # KIE chain unchanged. No clip generation depends on this path.
        resolved_element_ids: list[str] = []
        if generate_scenes._wavespeed_primary_enabled() and kling_elements:
            try:
                from services.kling_elements import ensure_element_id
                for el in kling_elements:
                    refer_urls = el.get("element_input_urls") or []
                    primary = refer_urls[0] if refer_urls else None
                    if not primary:
                        continue
                    owner_kwargs: dict = {}
                    if el["name"] == "element_product" and data.product_id:
                        owner_kwargs["product_id"] = data.product_id
                    elif el["name"] == "element_character" and influencer_id and influencer_id != "00000000-0000-0000-0000-000000000000":
                        owner_kwargs["influencer_id"] = influencer_id
                    eid = await ensure_element_id(
                        name=el["name"],
                        description=el.get("description") or el["name"],
                        image_url=primary,
                        refer_urls=refer_urls,
                        **owner_kwargs,
                    )
                    resolved_element_ids.append(eid)
                if len(resolved_element_ids) != len(kling_elements):
                    print(f"[Cinematic] element_id resolution incomplete ({len(resolved_element_ids)}/{len(kling_elements)}) — skipping WS-primary")
                    resolved_element_ids = []
            except Exception as ws_el_err:
                print(f"[Cinematic] element_id resolution failed: {ws_el_err} — falling through to KIE chain")
                resolved_element_ids = []

        try:
            result = await asyncio.to_thread(
                generate_scenes.generate_video_with_retry,
                prompt=prompt,
                reference_image_url=first_frame_url,
                model_api="kling-3.0/video",
                duration=duration,
                kling_elements=kling_elements if kling_elements else None,
                multi_prompt=multi_prompt_payload,
                aspect_ratio=data.aspect_ratio or "9:16",
                element_ids=resolved_element_ids or None,
            )
            video_url = result["videoUrl"]
            print(f"[Cinematic] Kling animation complete: {video_url[:80]}...")
        except Exception as e:
            print(f"[Cinematic] Kling animation FAILED: {e}")
            await _update_video_job_via_api(token, project_id, job_id, {
                "status": "failed",
                "error_message": f"Cinematic video generation failed: {str(e)[:400]}",
            })
            _refund_on_failure(user_id, credit_cost, job_id, "cinematic_generation_failed")
            return

        # ── Step 4: Upload to Supabase Storage & finalize ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Uploading video...",
            "progress": 90,
        })

        try:
            import tempfile
            from datetime import datetime as _dt

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name

            await asyncio.to_thread(generate_scenes.download_video, video_url, tmp_path)

            timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
            storage_filename = f"cinematic_clip_{job_id[:8]}_{timestamp}.mp4"
            try:
                from ugc_db.db_manager import get_supabase
                sb = get_supabase()
                with open(tmp_path, "rb") as f:
                    sb.storage.from_("generated-videos").upload(
                        storage_filename, f,
                        file_options={"content-type": "video/mp4"},
                    )
                final_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
            except Exception as upload_err:
                print(f"[Cinematic] Supabase upload failed: {upload_err}, using raw URL")
                final_url = video_url

            try:
                import os as _os
                _os.unlink(tmp_path)
            except Exception:
                pass

            print(f"[Cinematic] Uploaded: {final_url[:80]}...")
        except Exception as e:
            print(f"[Cinematic] Upload failed, using raw URL: {e}")
            final_url = video_url

        # App-clip B-roll concat is now a separate agent step — see Seedance
        # pipeline for rationale. Stash app_clip_id in metadata so the agent's
        # splice_app_clip tool can find it.
        meta = {"mode": "cinematic_video", "multi_shot": bool(multi_prompt_payload)}
        if app_clip and app_clip.get("video_url"):
            meta["app_clip_id"] = data.app_clip_id

        # ── Step 5: Mark job as success ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "success",
            "progress": 100,
            "final_video_url": final_url,
            "preview_url": None,
            "preview_type": None,
            "status_message": None,
            "metadata": meta,
        })
        print(f"[Cinematic] Job {job_id} complete! Video: {final_url[:80]}...")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[Cinematic] Pipeline FAILED for job {job_id}: {e}")
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "failed",
            "error_message": f"Cinematic clip generation failed: {str(e)[:400]}",
        })
        _refund_on_failure(user_id, credit_cost, job_id, "cinematic_generation_failed")


# ── Veo 3.1 / UGC Pipeline ───────────────────────────────────────────

async def _generate_veo_video(
    data: VideoGenerateRequest,
    client: CoreAPIClient,
    user: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """Generate UGC video — two paths:

    Path A (full_video_mode=False): Single UGC clip
      Product analysis → Script gen → NanoBanana Pro composite → Veo 3.1 animation
      No music, no captions, no multi-scene assembly. Just 1 Veo 3.1 scene.

    Path B (full_video_mode=True): Full multi-scene video
      Dispatches to the existing /create pipeline via POST /jobs.
      Worker handles music, captions, multi-scene assembly.
    """

    # ── Full Video Mode → dispatch to worker pipeline ────────────────
    if data.full_video_mode:
        return await _generate_full_video(data, client, user)

    # ── UGC Clip Mode → in-process pipeline ──────────────────────────
    return await _generate_ugc_clip(data, client, user, background_tasks)


async def _generate_full_video(
    data: VideoGenerateRequest,
    client: CoreAPIClient,
    user: dict,
) -> dict:
    """Full Video mode: dispatch to the existing /create pipeline via POST /jobs.
    The Celery worker runs core_engine.run_generation_pipeline() — handles
    multi-scene assembly, music, captions, and everything else.

    Key design decisions:
    - User prompt is ALWAYS passed as `context` to generate_script(), not as
      the literal script. The AI script chain uses it as creative direction.
    - Custom reference image (uploaded or selected) is stored in job metadata
      so the worker can prioritize it over the influencer's default image.
    - When no influencer is selected, we still satisfy the FK constraint with
      a fallback but log it clearly.
    """

    # Resolve influencer_id (FK constraint requires a valid value)
    influencer_id = data.influencer_id
    user_selected_influencer = bool(data.influencer_id)
    if not influencer_id:
        try:
            influencers = await client.list_influencers()
            influencer_id = influencers[0]["id"] if influencers else None
            if influencer_id:
                print(f"[Full Video] No influencer selected — using fallback: {influencer_id}")
        except Exception:
            pass
    if not influencer_id:
        raise HTTPException(status_code=400, detail="An influencer/model must be selected for full video mode")

    # Auto-detect product_type (physical requires product_id in core API)
    product_type = "digital"
    if data.product_id:
        product_type = "physical"  # Default for products with an ID
        try:
            product = await client.get_product(data.product_id)
            if product and product.get("website_url"):
                product_type = "digital"
        except Exception:
            pass

    # ── Build the hook/script ────────────────────────────────────────
    # Always try AI script generation with user prompt as CONTEXT.
    # The user's prompt provides creative direction (e.g. "woman drinking
    # matcha tea talking about benefits") — it should NOT be the literal
    # dialogue sent to Veo.
    user_prompt = data.prompt.strip()
    hook = None

    if data.product_id:
        # Product exists → generate a proper AI script using product data,
        # influencer personality, and user prompt as context/direction
        try:
            print(f"[Full Video] Generating AI script with user prompt as context...")
            print(f"[Full Video]   context: {user_prompt[:100]}...")
            script_result = await client.generate_script(
                product_id=data.product_id,
                duration=data.video_length,
                influencer_id=influencer_id,
                product_type=product_type,
                output_format="legacy",
                video_language=data.language,
                context=user_prompt if user_prompt else None,
            )
            hook = script_result.get("script", "")
            if hook:
                print(f"[Full Video] AI script generated ({len(hook)} chars): {hook[:120]}...")
            else:
                print(f"[Full Video] AI script returned empty — falling back to user prompt")
                hook = user_prompt or "Check this out!"
        except Exception as e:
            print(f"[Full Video] Script generation failed: {e}")
            hook = user_prompt or "Check this out!"
    else:
        # No product — use user prompt directly as the hook.
        # The worker's scene builder will use it as the script text.
        hook = user_prompt or "Check this out!"
        print(f"[Full Video] No product selected — using user prompt as hook")

    # ── Build job metadata ───────────────────────────────────────────
    # Store the custom reference image URL in metadata so the worker can
    # prioritize it over the influencer's default stored image.
    job_metadata = {}
    custom_ref_image = data.reference_image_url
    if custom_ref_image:
        job_metadata["reference_image_url"] = custom_ref_image
        print(f"[Full Video] Custom reference image stored in metadata: {custom_ref_image[:80]}...")
    if not user_selected_influencer:
        job_metadata["influencer_is_fallback"] = True

    # ── Create job via core API — worker picks it up automatically ───
    job_payload = {
        "influencer_id": influencer_id,
        "product_id": data.product_id,
        "product_type": product_type,
        "model_api": "veo-3.1-fast",
        "length": data.video_length,
        "campaign_name": _derive_asset_name(hook or data.prompt),
        "video_language": data.language,
        "subtitles_enabled": data.captions,
        "music_enabled": data.background_music,
        "hook": (hook or "")[:500],
    }
    print(f"[Full Video] Job payload hook: {job_payload['hook'][:120]}...")

    job = await client.create_job(job_payload, skip_dispatch=False)
    job_id = job.get("id") or job.get("job", {}).get("id")
    print(f"[Full Video] Job dispatched: {job_id}")

    # Store metadata on the job record (separate update since create_job
    # may strip unknown fields)
    if job_metadata and job_id:
        try:
            await _update_video_job_via_api(user["token"], data.project_id, job_id, {
                "metadata": job_metadata,
            })
            print(f"[Full Video] Metadata saved to job: {list(job_metadata.keys())}")
        except Exception as e:
            print(f"[Full Video] WARNING: Failed to save metadata: {e}")

    return {
        "status": "generating",
        "job_id": job_id,
        "mode": "ugc_full_video",
        "video_length": data.video_length,
        "product_type": product_type,
    }


async def _generate_ugc_clip(
    data: VideoGenerateRequest,
    client: CoreAPIClient,
    user: dict,
    background_tasks: BackgroundTasks,
) -> dict:
    """UGC Clip mode: Product analysis → Script → NanoBanana Pro → single Veo 3.1 scene.
    No music, no captions, no multi-scene assembly.

    If user selected a pre-generated reference image, skip NanoBanana and go
    straight to Veo 3.1 animation with that image.
    """

    # 1. Create job record immediately so frontend can poll
    influencer_id = data.influencer_id
    user_selected_influencer = bool(data.influencer_id)  # Did the user explicitly pick one?
    if not influencer_id:
        try:
            influencers = await client.list_influencers()
            influencer_id = influencers[0]["id"] if influencers else None
        except Exception:
            pass
    if not influencer_id:
        influencer_id = "00000000-0000-0000-0000-000000000000"

    # Determine product_type — 'physical' requires a product_id in the core API
    product_type = "physical" if data.product_id else "digital"

    try:
        job = await client.create_job({
            "influencer_id": influencer_id,
            "product_id": data.product_id,
            "product_type": product_type,
            "model_api": "veo-3.1-fast",
            "length": data.clip_length,
            "campaign_name": _derive_asset_name(data.prompt),
            "video_language": data.language,
            "subtitles_enabled": False,
            "music_enabled": False,
            "hook": data.prompt[:500] if data.prompt else "",
        })
        job_id = job.get("id") or job.get("job", {}).get("id")
        credit_cost = int(job.get("credits_deducted") or 0)
        print(f"[Creative OS] UGC clip job created: {job_id} (cost={credit_cost})")
    except Exception as e:
        print(f"[Creative OS] Job creation failed: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create job: {str(e)[:200]}")

    if not job_id:
        raise HTTPException(status_code=500, detail="Failed to create job record")

    # 2. Launch background pipeline
    background_tasks.add_task(
        _run_ugc_clip_pipeline,
        job_id=job_id,
        data=data,
        token=user["token"],
        project_id=data.project_id,
        influencer_id=influencer_id,
        user_selected_influencer=user_selected_influencer,
        user_id=user.get("id"),
        credit_cost=credit_cost,
    )

    return {
        "status": "generating",
        "job_id": job_id,
        "mode": "ugc",
        "clip_length": data.clip_length,
    }


async def _run_ugc_clip_pipeline(
    job_id: str,
    data: VideoGenerateRequest,
    token: str,
    project_id: str,
    influencer_id: str,
    user_selected_influencer: bool = True,
    user_id: Optional[str] = None,
    credit_cost: int = 0,
):
    """Background task: runs the UGC clip pipeline end-to-end.

    Steps:
    1. Fetch & analyze product (if needed)
    2. Fetch influencer data
    3. Generate script (if no user prompt)
    4. Generate NanoBanana Pro composite image (or use reference image)
    5. Animate with Veo 3.1
    6. Upload to Supabase Storage
    7. Update job record
    """
    import sys
    from pathlib import Path

    # Add project root to path for core engine imports
    # Add repo root to sys.path for core engine imports (local dev only).
    # On Railway standalone, these imports won't resolve — but the full
    # video pipeline runs on Modal/Celery, not on Creative OS directly.
    from env_loader import load_env
    _root = load_env(Path(__file__))
    if _root and str(_root) not in sys.path:
        # Append (not insert) so creative-os local modules (e.g. generate_scenes.py)
        # always shadow any same-named files at the repo root.
        sys.path.append(str(_root))

    import asyncio
    generate_scenes = _load_creative_os_generate_scenes()
    from prompts import sanitize_dialogue

    client_sync = CoreAPIClient(token=token, project_id=project_id)

    try:
        # ── Step 0: Update status to processing ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "processing",
            "progress": 5,
            "status_message": "Preparing UGC clip...",
        })

        # ── Step 1: Fetch & analyze product ──
        product = None
        product_type = "physical"
        if data.product_id:
            try:
                product = await client_sync.get_product(data.product_id)
                if product and product.get("website_url"):
                    product_type = "digital"

                # Auto-analyze if no visual_description
                if product and not product.get("visual_description"):
                    await _update_video_job_via_api(token, project_id, job_id, {
                        "status_message": "Analyzing product...",
                        "progress": 8,
                    })
                    try:
                        analysis = await client_sync.analyze_product(data.product_id)
                        if analysis:
                            product["visual_description"] = analysis
                            print(f"[UGC Clip] Product analyzed: {analysis.get('brand_name', 'N/A')}")
                    except Exception as e:
                        print(f"[UGC Clip] Product analysis failed (non-fatal): {e}")
            except Exception as e:
                print(f"[UGC Clip] Product fetch failed: {e}")

        # ── Step 1b: App-clip context (digital products) ──
        app_clip = None
        clip_orientation = None  # 'phone' | 'laptop'
        if data.app_clip_id:
            try:
                app_clip = await client_sync.get_app_clip(data.app_clip_id)
                if app_clip:
                    product_type = "digital"
                    # Override product.image_url with clip's first_frame_url so
                    # the composite prompt uses the app UI as the "product".
                    if product is not None and app_clip.get("first_frame_url"):
                        product["image_url"] = app_clip["first_frame_url"]
                    # Detect clip native orientation via ffprobe
                    from utils.video_concat import probe_orientation
                    probe_src = app_clip.get("video_url") or app_clip.get("first_frame_url")
                    if probe_src:
                        clip_orientation = await asyncio.to_thread(probe_orientation, probe_src)
                        print(f"[UGC Clip] App clip orientation: {clip_orientation}")
            except Exception as e:
                print(f"[UGC Clip] App clip fetch/probe failed: {e}")

        # ── Step 2: Fetch influencer (only if user explicitly selected one) ──
        influencer = None
        if user_selected_influencer and influencer_id and influencer_id != "00000000-0000-0000-0000-000000000000":
            try:
                influencer = await client_sync.get_influencer(influencer_id)
                print(f"[UGC Clip] Influencer (user-selected): {influencer.get('name', 'Unknown')}")
            except Exception as e:
                print(f"[UGC Clip] Influencer fetch failed: {e}")
        elif not user_selected_influencer:
            print(f"[UGC Clip] No influencer selected — using reference image + prompt only")

        # ── Step 3: Generate script/dialogue ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Generating script/dialogue...",
            "progress": 12,
        })

        user_prompt = data.prompt.strip()
        script_text = ""
        action_direction = ""

        # Build context for enhancement
        enhance_ctx = {"image_url": data.reference_image_url}
        if product:
            enhance_ctx["product_name"] = product.get("name")
            desc = product.get("visual_description") or {}
            enhance_ctx["product_description"] = desc if isinstance(desc, str) else desc.get("visual_description", "")
        if influencer:
            enhance_ctx["influencer_name"] = influencer.get("name")

        # CASE A: User provided a prompt → Enhance it into a UGC script
        if user_prompt:
            try:
                from services.prompt_enhancer import enhance_prompt
                enhanced_options = await enhance_prompt(
                    user_prompt=user_prompt,
                    mode="ugc",
                    language=data.language,
                    context=enhance_ctx,
                )
                if enhanced_options:
                    # Pick the first professional option
                    professional_prompt = enhanced_options[0]["prompt"]
                    print(f"[UGC Clip] Enhanced user prompt: {professional_prompt[:100]}...")
                    
                    # Parse 'dialogue:' and 'action:' from the enhanced text
                    lines = professional_prompt.split("\n")
                    for line in lines:
                        if line.lower().startswith("dialogue:"):
                            script_text = line[len("dialogue:"):].strip()
                        elif line.lower().startswith("action:"):
                            action_direction = line[len("action:"):].strip()
                    
                    # Fallback if parsing failed but we have text
                    if not script_text and not action_direction:
                        script_text = professional_prompt
            except Exception as e:
                print(f"[UGC Clip] Prompt enhancement failed: {e}")
                script_text = user_prompt

        # CASE B: No user prompt → Auto-generate from product/influencer data
        if not script_text and data.product_id:
            try:
                script_result = await client_sync.generate_script(
                    product_id=data.product_id,
                    duration=data.clip_length,
                    influencer_id=influencer_id if influencer else None,
                    product_type=product_type,
                    output_format="legacy",
                    video_language=data.language,
                )
                generated_script = script_result.get("script", "")
                if generated_script:
                    # For single clip, use only the first part of the ||| script
                    if "|||" in generated_script:
                        script_text = generated_script.split("|||")[0].strip()
                    else:
                        script_text = generated_script.strip()
                    print(f"[UGC Clip] Auto-generated script: {script_text[:80]}...")
            except Exception as e:
                print(f"[UGC Clip] Script generation failed: {e}")

        # Final Fallback
        if not script_text:
            script_text = "Check this out, it's actually amazing."

        script_text = sanitize_dialogue(script_text)
        print(f"[UGC Clip] Final script: {script_text[:100]}...")
        if action_direction:
            print(f"[UGC Clip] Extracted action: {action_direction[:100]}...")

        # ── Step 4: Generate composite image or use reference ──
        has_reference_image = bool(data.reference_image_url)

        if has_reference_image:
            # User selected a pre-generated image → skip NanoBanana
            composite_url = data.reference_image_url
            print(f"[UGC Clip] Using pre-generated reference image: {composite_url[:80]}...")
            await _update_video_job_via_api(token, project_id, job_id, {
                "status_message": "Animating reference image...",
                "progress": 40,
                "preview_url": composite_url,
                "preview_type": "image",
            })
        elif product and influencer:
            # Generate NanoBanana Pro composite
            await _update_video_job_via_api(token, project_id, job_id, {
                "status_message": "Creating composite image...",
                "progress": 20,
            })

            # Build context for prompt generation
            visual_desc = product.get("visual_description") or {}
            if isinstance(visual_desc, str):
                visual_desc_str = visual_desc
            else:
                visual_desc_str = visual_desc.get("visual_description", product.get("name", "the product"))

            poss = "his" if influencer.get("gender", "Female") == "Male" else "her"
            ctx = {
                "age": influencer.get("age", "25-year-old"),
                "gender": influencer.get("gender", "Female"),
                "visuals": influencer.get("description", "casual style")[:200],
                "setting": influencer.get("setting", "") or "natural environment matching the background visible in the reference image",
                "product": product,
            }

            # The composite device framing follows the APP CLIP's native
            # orientation — a phone-native recording gets a phone prop; a
            # laptop-native recording gets a laptop prop. The COMPOSITE CANVAS
            # aspect is independent: it follows the user-selected final video
            # aspect ratio (passed as `composite_aspect` to NanoBanana below).
            # B-roll letterboxing in concat_videos_matched handles any aspect
            # mismatch between the UGC clip and the B-roll at render time.
            digital_device = clip_orientation if clip_orientation in ("phone", "laptop") else "phone"

            if product_type == "digital" and digital_device == "phone":
                nano_prompt = (
                    f"action: character holding a smartphone facing the camera in portrait orientation "
                    f"with an excited expression, casually showing the app on screen\n"
                    f"device: modern smartphone held vertically, phone screen fills the frame from the "
                    f"phone's perspective; the phone screen displays the provided app interface EXACTLY as "
                    f"shown in the reference image — pixel-perfect, do NOT redraw or reinterpret UI, keep "
                    f"all text, icons, layout, colors identical\n"
                    f"anatomy: exactly one person with exactly two arms and two hands, "
                    f"one hand explicitly holds the phone, other arm rests naturally TO THE PERSON'S SIDE\n"
                    f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
                    f"detailed realistic complexion with fine natural imperfections, unretouched raw look\n"
                    f"setting: {ctx['setting']}, natural lighting\n"
                    f"camera: amateur iPhone selfie, slightly uneven framing\n"
                    f"style: candid UGC look, no filters, photorealistic, high detail, raw unedited photo quality\n"
                    f"negative: no artificial smoothing, no plastic CGI appearance, no third arm, no third hand, "
                    f"no extra limbs, no extra fingers, no studio backdrop, no geometric distortion, "
                    f"no mutated hands, no floating limbs, disconnected limbs, mutation, "
                    f"no arm crossing screen, no unnatural arm position, no altered UI, no made-up UI elements"
                )
            elif product_type == "digital" and digital_device == "laptop":
                nano_prompt = (
                    f"action: character seated at a desk in front of a laptop or desktop monitor with an "
                    f"engaged expression, casually presenting the app on-screen\n"
                    f"device: laptop or desktop monitor in landscape orientation facing the camera at a "
                    f"natural angle; the screen displays the provided app interface EXACTLY as shown in "
                    f"the reference image — pixel-perfect, do NOT redraw or reinterpret UI, keep all text, "
                    f"icons, layout, colors identical\n"
                    f"anatomy: exactly one person with exactly two arms and two hands, hands resting near "
                    f"the keyboard or gesturing naturally toward the screen\n"
                    f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
                    f"detailed realistic complexion with fine natural imperfections, unretouched raw look\n"
                    f"setting: {ctx['setting']}, natural lighting\n"
                    f"camera: amateur iPhone capture, slightly uneven framing\n"
                    f"style: candid UGC look, no filters, photorealistic, high detail, raw unedited photo quality\n"
                    f"negative: no artificial smoothing, no plastic CGI appearance, no extra limbs, no extra fingers, "
                    f"no studio backdrop, no geometric distortion, no altered UI, no made-up UI elements"
                )
            else:
                nano_prompt = (
                    f"action: character holding the product up close to the camera with an excited expression, "
                    f"casually presenting the product\n"
                    f"anatomy: exactly one person with exactly two arms and two hands, "
                    f"one hand explicitly holds the product, other arm rests naturally TO THE PERSON'S SIDE\n"
                    f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
                    f"detailed realistic complexion with fine natural imperfections, unretouched raw look\n"
                    f"product: the {visual_desc_str} is clearly visible, "
                    f"preserve all visible text and logos exactly as in reference image\n"
                    f"setting: {ctx['setting']}, natural lighting\n"
                    f"camera: amateur iPhone selfie, slightly uneven framing\n"
                    f"style: candid UGC look, no filters, photorealistic, high detail, "
                    f"raw unedited photo quality\n"
                    f"negative: no artificial smoothing, no plastic CGI appearance, "
                    f"no third arm, no third hand, no extra limbs, no extra fingers, "
                    f"no studio backdrop, no geometric distortion, "
                    f"no mutated hands, no floating limbs, disconnected limbs, mutation, "
                    f"no arm crossing screen, no unnatural arm position"
                )

            scene = {
                "nano_banana_prompt": nano_prompt,
                "reference_image_url": influencer.get("image_url", ""),
                "product_image_url": product.get("image_url", ""),
            }

            # Composite aspect MUST match the downstream video aspect —
            # otherwise Veo/Kling crop or stretch the first frame and the
            # output looks zoomed-in (9:16 composite feeding a 16:9 render
            # was the bug that prompted this plumbing).
            composite_aspect = data.aspect_ratio or "9:16"
            print(f"[UGC Clip] Generating NanoBanana composite (aspect={composite_aspect})...")
            try:
                import random
                global_seed = random.randint(0, 2**32 - 1)
                composite_url = await asyncio.to_thread(
                    generate_scenes.generate_composite_image_with_retry,
                    scene=scene,
                    influencer=influencer,
                    product=product,
                    seed=global_seed,
                    aspect_ratio=composite_aspect,
                )
                print(f"[UGC Clip] Composite ready: {composite_url[:80]}...")

                await _update_video_job_via_api(token, project_id, job_id, {
                    "status_message": "Composite image ready, animating...",
                    "progress": 40,
                    "preview_url": composite_url,
                    "preview_type": "image",
                })
            except Exception as e:
                print(f"[UGC Clip] NanoBanana composite FAILED: {e}")
                raise RuntimeError(f"Composite image generation failed: {e}")
        else:
            # No product+influencer combo — use reference_image_url if available
            composite_url = data.reference_image_url or None
            if composite_url:
                print(f"[UGC Clip] Using uploaded reference image: {composite_url[:80]}...")
                await _update_video_job_via_api(token, project_id, job_id, {
                    "status_message": "Animating reference image...",
                    "progress": 40,
                    "preview_url": composite_url,
                    "preview_type": "image",
                })
            else:
                print("[UGC Clip] No reference image — using direct Veo text-to-video")
                await _update_video_job_via_api(token, project_id, job_id, {
                    "status_message": "Generating video...",
                    "progress": 30,
                })

        # ── Step 5: Build Veo animation prompt ──
        if influencer:
            inf_name = influencer.get("name", "character")
            age_str = influencer.get("age", "25-year-old")
            gender_str = influencer.get("gender", "Female").lower()
            raw_desc = influencer.get("description", "casual style")[:200]
            # Sanitize: the AI-generated description may embed a different name.
            # Replace any embedded first name with the actual influencer name.
            visuals_str = _sanitize_influencer_description(raw_desc, inf_name)
            accent_str = influencer.get("accent", "neutral English")
            tone_str = influencer.get("tone", "Enthusiastic").lower()
            energy_str = influencer.get("energy_level", "High").lower()
            setting_str = influencer.get("setting", "") or "natural environment matching the background visible in the reference image"

            if data.language == "es":
                accent_str = "native Spanish accent, speaking entirely in Spanish"

            # Use enhanced action if available, else fallback to template
            final_action = action_direction if action_direction else "person holds product at chest level showing it to camera, excited expression, eye contact"

            veo_prompt = (
                f"dialogue: {script_text}\n"
                f"action: {final_action}\n"
                f"character: {age_str} {gender_str} named {inf_name}, {visuals_str}, detailed realistic complexion with fine natural imperfections, unretouched raw look\n"
                f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
                f"setting: {setting_str}, natural lighting\n"
                f"emotion: {energy_str}, genuine excitement\n"
                f"voice_type: clear confident pronunciation, casual, {tone_str}, conversational {accent_str}, consistent medium-fast pacing\n"
                f"style: raw UGC, candid, not polished\n"
                f"speech_constraint: speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, "
                f"absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, "
                f"speaking pace is consistent, MUST finish speaking all words entirely 1 second before the end of the video, "
                f"character remains completely silent and just smiles warmly during the final 1-2 seconds\n"
                f"negative: no auditory hallucinations, no filler words, no repeated words, no stuttering, no repeated syllables, "
                f"no artificial smoothing, no plastic CGI appearance, no extra limbs, no extra fingers, no mutated hands"
            )
        else:
            # No influencer selected — build prompt from user's input + reference image context
            accent_line = "native Spanish accent, speaking entirely in Spanish" if data.language == "es" else "neutral English accent"
            final_action = action_direction if action_direction else "person speaking directly to camera, casual and excited, holding product if visible in reference"

            if composite_url:
                # Reference image uploaded: instruct Veo to match the person in it
                veo_prompt = (
                    f"dialogue: {script_text}\n"
                    f"action: {final_action}\n"
                    f"reference_image: MUST match the exact person, face, hair, clothing, and product shown in the reference image — "
                    f"do NOT change the person's appearance, do NOT substitute a different person\n"
                    f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
                    f"style: raw UGC, candid, not polished, photorealistic\n"
                    f"voice_type: clear confident pronunciation, casual, conversational {accent_line}, consistent medium-fast pacing\n"
                    f"speech_constraint: speak ONLY the exact dialogue words provided, crystal-clear pronunciation, "
                    f"no stuttering, no auditory hallucinations, MUST finish speaking 1 second before video ends\n"
                    f"negative: no auditory hallucinations, no filler words, no stuttering, no extra limbs, "
                    f"do NOT use a different person than the reference image"
                )
            else:
                veo_prompt = (
                    f"dialogue: {script_text}\n"
                    f"action: {final_action}\n"
                    f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
                    f"style: raw UGC, candid, not polished\n"
                    f"voice_type: clear confident pronunciation, casual, conversational {accent_line}, consistent medium-fast pacing\n"
                    f"speech_constraint: speak ONLY the exact dialogue words provided, crystal-clear pronunciation, "
                    f"no stuttering, no auditory hallucinations\n"
                    f"negative: no auditory hallucinations, no filler words, no stuttering, no extra limbs"
                )

        print(f"[UGC Clip] Veo prompt ({len(veo_prompt)} chars): {veo_prompt[:120]}...")

        # ── Step 6: Animate with Veo 3.1 ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Animating with Veo 3.1...",
            "progress": 50,
        })

        try:
            if composite_url:
                # Image-to-video animation
                result = await asyncio.to_thread(
                    generate_scenes.generate_video_with_retry,
                    prompt=veo_prompt,
                    reference_image_url=composite_url,
                    model_api="veo-3.1-fast",
                    duration=data.clip_length,
                    aspect_ratio=data.aspect_ratio or "9:16",
                )
            else:
                # Text-to-video (no reference image)
                result = await asyncio.to_thread(
                    generate_scenes.generate_video_with_retry,
                    prompt=veo_prompt,
                    reference_image_url=data.reference_image_url,
                    model_api="veo-3.1-fast",
                    duration=data.clip_length,
                    aspect_ratio=data.aspect_ratio or "9:16",
                )
            video_url = result["videoUrl"]
            print(f"[UGC Clip] Veo animation complete: {video_url[:80]}...")
        except Exception as e:
            print(f"[UGC Clip] Veo animation FAILED: {e}")
            await _update_video_job_via_api(token, project_id, job_id, {
                "status": "failed",
                "error_message": f"Video animation failed: {str(e)[:400]}",
            })
            _refund_on_failure(user_id, credit_cost, job_id, "ugc_generation_failed")
            return

        # ── Step 7: Upload to Supabase Storage & finalize ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Uploading video...",
            "progress": 90,
        })

        try:
            # Download the video to a temp file and re-upload to Supabase
            import tempfile
            from datetime import datetime as _dt

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                tmp_path = tmp.name

            await asyncio.to_thread(generate_scenes.download_video, video_url, tmp_path)

            # Upload to Supabase Storage (inline to avoid Celery dependency)
            timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
            storage_filename = f"ugc_clip_{job_id[:8]}_{timestamp}.mp4"
            try:
                from ugc_db.db_manager import get_supabase
                sb = get_supabase()
                with open(tmp_path, "rb") as f:
                    sb.storage.from_("generated-videos").upload(
                        storage_filename, f,
                        file_options={"content-type": "video/mp4"},
                    )
                final_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
            except Exception as upload_err:
                print(f"[UGC Clip] Supabase upload failed: {upload_err}, using raw URL")
                final_url = video_url

            # Clean up temp file
            try:
                import os as _os
                _os.unlink(tmp_path)
            except Exception:
                pass

            print(f"[UGC Clip] Uploaded: {final_url[:80]}...")
        except Exception as e:
            print(f"[UGC Clip] Upload failed, using raw URL: {e}")
            final_url = video_url

        # App-clip B-roll concat is now a separate agent step — see Seedance
        # pipeline for rationale. Stash app_clip_id in metadata so the agent's
        # splice_app_clip tool can find it.
        meta: dict = {}
        if app_clip and app_clip.get("video_url"):
            meta["app_clip_id"] = data.app_clip_id

        # ── Step 8: Mark job as success ──
        success_update: dict = {
            "status": "success",
            "progress": 100,
            "final_video_url": final_url,
            "preview_url": None,
            "preview_type": None,
            "status_message": None,
        }
        if meta:
            success_update["metadata"] = meta
        await _update_video_job_via_api(token, project_id, job_id, success_update)
        print(f"[UGC Clip] Job {job_id} complete! Video: {final_url[:80]}...")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[UGC Clip] Pipeline FAILED for job {job_id}: {e}")
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "failed",
            "error_message": f"UGC clip generation failed: {str(e)[:400]}",
        })
        _refund_on_failure(user_id, credit_cost, job_id, "ugc_generation_failed")


# ── WaveSpeed-only additions: video extend ─────────────────────────────

class ExtendVideoRequest(BaseModel):
    video_url: str
    prompt: Optional[str] = None
    resolution: str = "1080p"  # 720p | 1080p
    project_id: Optional[str] = None


async def _lookup_source_context(video_url: str, token: str) -> dict:
    """Recover the source clip's context for an extend job.

    Lookup strategy: match by `final_video_url`, OR by the WaveSpeed CloudFront
    URL we stash in `metadata.wavespeed_cloudfront_url` on prior extensions
    (so re-extending an already-extended clip still finds the chain).

    Returns a dict of:
      row, influencer, product, language, original_hook, project_id

    Empty dict if nothing was found or any lookup failed.
    """
    row: Optional[dict] = None
    try:
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        rows = (
            sb.table("video_jobs")
            .select("metadata,video_language,influencer_id,product_id,project_id,app_clip_id")
            .eq("final_video_url", video_url)
            .limit(1)
            .execute()
        )
        if rows.data:
            row = rows.data[0]
        else:
            # Fall back to matching by the CloudFront URL we stash on extension rows.
            rows = (
                sb.table("video_jobs")
                .select("metadata,video_language,influencer_id,product_id,project_id,app_clip_id")
                .filter("metadata->>wavespeed_cloudfront_url", "eq", video_url)
                .limit(1)
                .execute()
            )
            if rows.data:
                row = rows.data[0]
    except Exception as e:
        print(f"[Extend] source-job lookup failed ({e})")
        return {}

    if not row:
        return {}

    language = (row.get("video_language") or "en").lower()
    metadata = row.get("metadata") or {}
    original_hook = metadata.get("hook", "") if isinstance(metadata, dict) else ""
    project_id = row.get("project_id")

    influencer = None
    product = None
    try:
        client = CoreAPIClient(token=token, project_id=project_id)
        if row.get("influencer_id"):
            influencer = await client.get_influencer(row["influencer_id"])
        if row.get("product_id"):
            product = await client.get_product(row["product_id"])
    except Exception as e:
        print(f"[Extend] influencer/product lookup failed ({e})")

    return {
        "row": row,
        "influencer": influencer,
        "product": product,
        "language": language,
        "original_hook": original_hook,
        "project_id": project_id,
    }


def _build_extend_prompt(ctx: dict, user_continuation: Optional[str]) -> str:
    """Build the structured Veo-extend prompt from a recovered source context.

    Always returns a non-empty prompt — even when ctx is empty (no DB match),
    we still emit a "continue the scene" skeleton so WaveSpeed/Veo never
    receives a bare video with no instruction (which causes hallucinated
    speech and minutes-long generations).
    """
    from prompts import sanitize_dialogue

    influencer = ctx.get("influencer") or {}
    product = ctx.get("product") or {}
    language = ctx.get("language") or "en"
    original_hook = ctx.get("original_hook") or ""

    inf_name = influencer.get("name", "the character")
    inf_visuals = _sanitize_influencer_description(
        (influencer.get("description", "") or "")[:200], inf_name
    ) if influencer else ""

    product_name = product.get("name", "") if product else ""
    product_desc = ""
    if product:
        vd = product.get("visual_description") or {}
        if isinstance(vd, dict):
            product_desc = vd.get("visual_description", "")
        elif isinstance(vd, str):
            product_desc = vd
    product_str = f"{product_name} ({product_desc[:120]})" if product_desc else product_name

    dialogue = sanitize_dialogue(user_continuation) if user_continuation else ""

    accent_line = (
        "native Spanish accent, speaking entirely in Spanish"
        if language == "es" else "neutral English accent, speaking entirely in English"
    )

    parts: list[str] = []
    if dialogue:
        parts.append(f"dialogue: {dialogue}")
    parts.append(
        "action: continue the previous scene seamlessly. "
        f"{inf_name} stays in the SAME setting, wardrobe, and lighting"
        + (f", still holding the {product_str}" if product_str else "")
        + ". Natural continuation of the original handheld UGC selfie shot."
    )
    if inf_visuals:
        parts.append(f"character: {inf_name}, {inf_visuals}. Same person as the previous scene, do NOT change identity, face, hair, or clothing.")
    if product_str:
        parts.append(f"product: {product_str}. Do NOT swap the product. The same item must remain visible and unchanged.")
    if original_hook:
        parts.append(f"original_scene_context: {original_hook[:400]}")
    parts.append("camera: amateur iPhone selfie video, slightly uneven framing, handheld")
    parts.append("style: raw UGC, candid, photorealistic, identical look to the original scene")
    parts.append(f"voice_type: clear confident pronunciation, casual, conversational, {accent_line}, consistent medium-fast pacing")
    if dialogue:
        parts.append(
            "speech_constraint: speak ONLY the exact dialogue words above, "
            "crystal-clear pronunciation, no stuttering, zero auditory hallucinations, "
            "MUST finish speaking 1 second before the end of the video"
        )
    parts.append(
        "negative: no auditory hallucinations, no filler words, no stuttering, "
        "do NOT change the character, do NOT swap the product, do NOT change the language"
    )

    prompt = "\n".join(parts)
    print(f"[Extend] built prompt ({len(prompt)} chars) for {inf_name} + {product_name or 'no-product'}, lang={language}")
    return prompt


async def _persist_extended_clip(
    *,
    cloudfront_url: str,
    source_url: str,
    structured_prompt: str,
    source_ctx: dict,
    token: str,
) -> str:
    """Download the extension from CloudFront, upload to Supabase storage,
    and create a video_jobs row mirroring the source clip's context.

    Returns the Supabase public URL on success, or the original CloudFront URL
    on any failure (best-effort — never blocks the user response).
    """
    import asyncio
    import tempfile
    from datetime import datetime as _dt

    final_url = cloudfront_url
    row = source_ctx.get("row") or {}
    project_id = source_ctx.get("project_id") or row.get("project_id")

    # 1. Download CloudFront → upload to Supabase storage
    try:
        generate_scenes = _load_creative_os_generate_scenes()
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = tmp.name
        await asyncio.to_thread(generate_scenes.download_video, cloudfront_url, tmp_path)
        try:
            from ugc_db.db_manager import get_supabase
            sb = get_supabase()
            timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
            storage_filename = f"veo_extend_{timestamp}.mp4"
            with open(tmp_path, "rb") as f:
                sb.storage.from_("generated-videos").upload(
                    storage_filename, f,
                    file_options={"content-type": "video/mp4"},
                )
            final_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
            print(f"[Extend] uploaded to Supabase: {final_url[:80]}...")
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
    except Exception as e:
        print(f"[Extend] Supabase upload failed ({e}), keeping CloudFront URL")

    # 2. Create a video_jobs row so the next re-extend can recover context
    if not row:
        return final_url
    try:
        client = CoreAPIClient(token=token, project_id=project_id)
        product_type = "physical"
        if row.get("app_clip_id"):
            product_type = "digital"
        elif row.get("product_id"):
            try:
                p = await client.get_product(row["product_id"])
                if p and p.get("type") in ("physical", "digital"):
                    product_type = p["type"]
            except Exception:
                pass

        job_payload: dict = {
            "influencer_id": row.get("influencer_id") or "00000000-0000-0000-0000-000000000000",
            "product_id": row.get("product_id"),
            "product_type": product_type,
            "model_api": "veo3.1-fast-extend",
            "length": 8,
            "campaign_name": _derive_asset_name(structured_prompt),
            "video_language": row.get("video_language") or "en",
            "subtitles_enabled": False,
            "music_enabled": False,
            "hook": (structured_prompt or "")[:500],
        }
        if row.get("app_clip_id"):
            job_payload["app_clip_id"] = row["app_clip_id"]

        job = await client.create_job(job_payload)
        job_id = job.get("id") or job.get("job", {}).get("id")
        if job_id:
            await _update_video_job_via_api(token, project_id, job_id, {
                "status": "success",
                "progress": 100,
                "final_video_url": final_url,
                "metadata": {
                    "engine": "veo3.1-fast-extend",
                    "hook": (structured_prompt or "")[:1000],
                    "parent_video_url": source_url,
                    "wavespeed_cloudfront_url": cloudfront_url,
                },
            })
            print(f"[Extend] persisted video_jobs row {job_id}")
    except Exception as e:
        print(f"[Extend] failed to persist video_jobs row: {e}")

    return final_url


@router.post("/extend")
async def extend_video(data: ExtendVideoRequest, user: dict = Depends(get_current_user)):
    """Extend a Veo-generated clip by ~8 seconds using Veo 3.1 Fast video-extend.

    WaveSpeed-only capability — KIE does not expose video extend. Returns the
    final extended video URL after polling to completion. Caller-side credit
    debit happens via existing pipelines; this endpoint is a thin proxy.
    """
    import asyncio
    from services import wavespeed_client as ws

    if not os.getenv("WAVESPEED_API_KEY"):
        raise HTTPException(status_code=503, detail="WaveSpeed not configured")

    if not data.video_url:
        raise HTTPException(status_code=400, detail="video_url is required")

    source_ctx = await _lookup_source_context(data.video_url, user["token"])
    structured_prompt = _build_extend_prompt(source_ctx, data.prompt)
    if not source_ctx:
        print("[Extend] no source-job match — using fallback structured prompt (no character/product context)")

    async def _submit_and_poll() -> str:
        submitted = await asyncio.to_thread(
            ws.veo31_fast_extend,
            video=data.video_url,
            prompt=structured_prompt,
            resolution=data.resolution if data.resolution in ("720p", "1080p") else "1080p",
        )
        result = await asyncio.to_thread(
            ws.poll_until_done, submitted["id"], label="Veo extend", max_poll_seconds=900
        )
        return ws.first_output_url(result)

    try:
        cloudfront_url = await _submit_and_poll()
    except ws.WaveSpeedError as e:
        if getattr(e, "transient", False):
            print(f"[Extend] transient WaveSpeed failure, retrying once: {e}")
            await asyncio.sleep(10)
            try:
                cloudfront_url = await _submit_and_poll()
            except Exception as e2:
                raise HTTPException(status_code=502, detail=f"video extend failed (after retry): {str(e2)[:300]}")
        else:
            raise HTTPException(status_code=502, detail=f"video extend failed: {str(e)[:300]}")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"video extend failed: {str(e)[:300]}")

    final_url = await _persist_extended_clip(
        cloudfront_url=cloudfront_url,
        source_url=data.video_url,
        structured_prompt=structured_prompt,
        source_ctx=source_ctx,
        token=user["token"],
    )

    return {
        "status": "success",
        "video_url": final_url,
        "source_video_url": data.video_url,
        "provider_model": "wavespeed/veo3.1-fast/extend",
    }

