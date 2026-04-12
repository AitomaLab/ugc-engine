"""
Creative OS — Video Generation Router

Handles video generation with mode-aware routing:
- UGC mode → Veo 3.1
- Cinematic mode → Kling 3.0
- AI Clone mode → InfiniTalk + ElevenLabs (via core API clone-jobs)
"""
import os
import re
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from core_api_client import CoreAPIClient
from services.model_router import get_video_mode, get_clip_lengths


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

        job = await client.create_job({
            "influencer_id": influencer_id,
            "product_id": data.product_id,
            "product_type": "physical",
            "model_api": model_api,
            "length": duration,
            "campaign_name": "Creative OS",
            "video_language": data.language,
            "subtitles_enabled": data.captions,
            "music_enabled": data.background_music,
            "hook": prompt[:500],
        })
        job_id = job.get("id") or job.get("job", {}).get("id")
        print(f"[Creative OS] Created video job record: {job_id}")
        return {"id": job_id, "kie_task_id": task_id}
    except Exception as e:
        print(f"[Creative OS] WARNING: Failed to create job record: {e}")
        import traceback; traceback.print_exc()
        return {"id": None, "kie_task_id": task_id}


async def _update_video_job_via_api(token: str, project_id: str, job_id: str, updates: dict):
    """Update a video_jobs record via Supabase REST API."""
    import httpx
    from pathlib import Path
    from dotenv import load_dotenv
    _root = Path(__file__).parent.parent.parent.parent
    load_dotenv(_root / ".env.saas", override=False)

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    if not supabase_url or not anon_key or not job_id:
        print(f"[Creative OS] Cannot update job — missing config or job_id")
        return

    headers = {
        "apikey": anon_key,
        "Authorization": f"Bearer {token}",
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

    if data.product_id:
        try:
            product = await client.get_product(data.product_id)
            product_image_url = product.get("image_url") if product else None
        except Exception:
            pass

    if data.influencer_id:
        try:
            influencers = await client.list_influencers()
            inf = next((i for i in influencers if i["id"] == data.influencer_id), None)
            influencer_image_url = inf.get("image_url") if inf else None
        except Exception:
            pass

    # Build the best reference image: prefer explicit selection > product > influencer.
    # Exception: in UGC mode with both product + influencer, leave reference_image_url
    # empty so the pipeline generates a NanoBanana Pro composite instead of skipping it.
    if not data.reference_image_url:
        if data.mode == "ugc" and product_image_url and influencer_image_url:
            pass  # Let _run_ugc_clip_pipeline handle the composite
        else:
            data.reference_image_url = product_image_url or influencer_image_url

    if data.mode == "ai_clone":
        return await _generate_clone_video(data, client)
    elif data.mode == "cinematic_video":
        return await _generate_kling_video(data, client, user, background_tasks)
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

    # 1. Create job record immediately so frontend can poll
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
            "campaign_name": "Creative OS",
            "video_language": data.language,
            "subtitles_enabled": False,
            "music_enabled": False,
            "hook": data.prompt[:500] if data.prompt else "",
        })
        job_id = job.get("id") or job.get("job", {}).get("id")
        print(f"[Creative OS] Cinematic job created: {job_id}")
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
        except Exception:
            pass
    if data.influencer_id:
        try:
            influencers_list = await client.list_influencers()
            inf = next((i for i in influencers_list if i["id"] == data.influencer_id), None)
            influencer_image_url = inf.get("image_url") if inf else None
        except Exception:
            pass

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
    )

    duration = max(3, min(15, data.clip_length))
    return {
        "status": "generating",
        "job_id": job_id,
        "mode": "cinematic_video",
        "clip_length": duration,
    }


async def _run_cinematic_clip_pipeline(
    job_id: str,
    data: VideoGenerateRequest,
    token: str,
    project_id: str,
    influencer_id: str,
    product_image_url: str | None,
    influencer_image_url: str | None,
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

    project_root = str(Path(__file__).parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import asyncio
    import httpx
    import generate_scenes
    from services.prompt_enhancer import enhance_prompt

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

        # Merge @mention-based element_refs from frontend (override generic elements)
        if data.element_refs:
            existing_names = {e["name"] for e in kling_elements}
            for ref in data.element_refs:
                if ref.name not in existing_names and ref.image_url:
                    kling_elements.append({
                        "name": ref.name,
                        "description": f"{ref.type}: {ref.name.replace('element_', '')}",
                        "element_input_urls": [ref.image_url, ref.image_url],
                    })
                    element_tags += f" @{ref.name}"
                    element_context.append({"name": ref.name, "description": ref.name.replace("element_", "")})
                    print(f"[Cinematic] Added @mention element: {ref.name} ({ref.type})")

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
        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Building cinematic prompt...",
            "progress": 35,
        })

        prompt = data.prompt
        try:
            enhance_context = {}
            if first_frame_url:
                enhance_context["image_url"] = first_frame_url
            if element_context:
                enhance_context["elements"] = element_context

            if first_frame_url:
                print(f"[Cinematic] Enhancing with VISION image + {len(element_context)} element(s)...")
                enhanced = await enhance_prompt(
                    user_prompt=data.prompt,
                    mode="kling_director",
                    language=data.language,
                    context=enhance_context,
                )
            else:
                enhanced = await enhance_prompt(
                    user_prompt=data.prompt,
                    mode="cinematic",
                    language=data.language,
                )
            prompt = enhanced[0]["prompt"] if enhanced else data.prompt
            print(f"[Cinematic] Enhanced prompt ({len(prompt)} chars): {prompt[:100]}...")
        except Exception as e:
            print(f"[Cinematic] Prompt enhance failed (using raw): {e}")
            prompt = data.prompt

        # Append element tags to prompt if not already present
        if kling_elements:
            for tag in element_tags.strip().split():
                if tag not in prompt:
                    prompt += f" {tag}"
        else:
            # Strip any @element_ tags the prompt enhancer may have hallucinated
            import re
            prompt = re.sub(r'\s*@element_\w+', '', prompt).strip()

        # ── Step 3: Submit to Kling 3.0 with element refs ──
        duration = max(3, min(15, data.clip_length))

        await _update_video_job_via_api(token, project_id, job_id, {
            "status_message": "Generating cinematic video with Kling 3.0...",
            "progress": 50,
        })

        try:
            result = await asyncio.to_thread(
                generate_scenes.generate_video_with_retry,
                prompt=prompt,
                reference_image_url=first_frame_url,
                model_api="kling-3.0/video",
                duration=duration,
                kling_elements=kling_elements if kling_elements else None,
            )
            video_url = result["videoUrl"]
            print(f"[Cinematic] Kling animation complete: {video_url[:80]}...")
        except Exception as e:
            print(f"[Cinematic] Kling animation FAILED: {e}")
            await _update_video_job_via_api(token, project_id, job_id, {
                "status": "failed",
                "error_message": f"Cinematic video generation failed: {str(e)[:400]}",
            })
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

        # ── Step 5: Mark job as success ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "success",
            "progress": 100,
            "final_video_url": final_url,
            "preview_url": None,
            "preview_type": None,
            "status_message": None,
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
        "campaign_name": "Creative OS",
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
            "campaign_name": "Creative OS",
            "video_language": data.language,
            "subtitles_enabled": False,
            "music_enabled": False,
            "hook": data.prompt[:500] if data.prompt else "",
        })
        job_id = job.get("id") or job.get("job", {}).get("id")
        print(f"[Creative OS] UGC clip job created: {job_id}")
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
    project_root = str(Path(__file__).parent.parent.parent.parent)
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    import asyncio
    import generate_scenes
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

            print(f"[UGC Clip] Generating NanoBanana composite...")
            try:
                import random
                global_seed = random.randint(0, 2**32 - 1)
                composite_url = await asyncio.to_thread(
                    generate_scenes.generate_composite_image_with_retry,
                    scene=scene,
                    influencer=influencer,
                    product=product,
                    seed=global_seed,
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
                )
            else:
                # Text-to-video (no reference image)
                result = await asyncio.to_thread(
                    generate_scenes.generate_video_with_retry,
                    prompt=veo_prompt,
                    reference_image_url=data.reference_image_url,
                    model_api="veo-3.1-fast",
                    duration=data.clip_length,
                )
            video_url = result["videoUrl"]
            print(f"[UGC Clip] Veo animation complete: {video_url[:80]}...")
        except Exception as e:
            print(f"[UGC Clip] Veo animation FAILED: {e}")
            await _update_video_job_via_api(token, project_id, job_id, {
                "status": "failed",
                "error_message": f"Video animation failed: {str(e)[:400]}",
            })
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

        # ── Step 8: Mark job as success ──
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "success",
            "progress": 100,
            "final_video_url": final_url,
            "preview_url": None,
            "preview_type": None,
            "status_message": None,
        })
        print(f"[UGC Clip] Job {job_id} complete! Video: {final_url[:80]}...")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"[UGC Clip] Pipeline FAILED for job {job_id}: {e}")
        await _update_video_job_via_api(token, project_id, job_id, {
            "status": "failed",
            "error_message": f"UGC clip generation failed: {str(e)[:400]}",
        })

