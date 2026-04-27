"""
Creative OS — Animation Router

All animation styles (Director + UGC) route to Kling 3.0.
Kling 3.0 is used for all image-to-video animations since they
don't require speech/dialogue — just camera movement presets.
"""
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from services.model_router import DIRECTOR_STYLES, UGC_STYLES
from services.prompt_enhancer import enhance_prompt
from core_api_client import CoreAPIClient
from dotenv import load_dotenv
from pathlib import Path

from env_loader import load_env
load_env(Path(__file__))

KIE_API_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
KIE_API_KEY = os.getenv("KIE_API_KEY", "")

router = APIRouter(prefix="/animate", tags=["animation"])


class AnimateRequest(BaseModel):
    image_url: str
    style: str
    user_context: Optional[str] = None
    duration: int = 5
    mode: str = "pro"  # pro or std for Kling 3.0
    project_id: Optional[str] = None
    product_image_url: Optional[str] = None      # Product image for element ref
    influencer_image_url: Optional[str] = None    # Influencer image for element ref


@router.get("/styles")
async def list_animation_styles():
    """Return all available animation styles — all use Kling 3.0."""
    all_styles = sorted(DIRECTOR_STYLES | UGC_STYLES)
    return {
        "styles": [
            {
                "id": s,
                "label": s.replace("_", " ").title(),
                "model": "kling-3.0",
                "durations": [5, 10],
            }
            for s in all_styles
        ],
    }


@router.post("/")
async def animate_image(
    data: AnimateRequest,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user)
):
    """Animate a still image into a video clip. All styles use Kling 3.0."""
    all_styles = DIRECTOR_STYLES | UGC_STYLES
    if data.style not in all_styles:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown style: {data.style}. Available: {sorted(all_styles)}",
        )

    client = CoreAPIClient(token=user["token"], project_id=data.project_id)

    # 1. Get a real influencer_id (core API validates it!)
    try:
        influencers = await client.list_influencers()
        influencer_id = influencers[0]["id"] if influencers else None
    except Exception:
        influencer_id = None

    if not influencer_id:
        raise HTTPException(status_code=400, detail="No influencers found — cannot create animation job")

    # 2. Create a job record so the "Generating..." card appears in the gallery
    try:
        job_payload = {
            "influencer_id": influencer_id,
            "product_type": "digital",
            "model_api": "kling-3.0/video",
            "length": data.duration,
            "campaign_name": f"Animation: {data.style.replace('_', ' ').title()}",
            "video_language": "en",
            "preview_url": data.image_url,
            "preview_type": "image",
            "hook": f"Animate: {data.style}",
        }
        job = await client.create_job(job_payload)
        job_id = job.get("id") or job.get("job", {}).get("id")
        print(f"[Animate] Job created: {job_id}")
    except Exception as e:
        print(f"[Animate] Failed to create job record: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to create animation job: {str(e)[:200]}")

    # 3. Fire background task
    background_tasks.add_task(
        _run_animation_pipeline,
        job_id=job_id,
        data=data,
        token=user["token"]
    )

    return {
        "status": "generating",
        "job_id": job_id,
        "style": data.style,
        "model": "kling-3.0",
    }


async def _run_animation_pipeline(job_id: str, data: AnimateRequest, token: str):
    """Background task to prompt-enhance, call Kling, and update job status."""
    import asyncio
    import json as json_mod
    import httpx
    from pathlib import Path as _Path
    from dotenv import load_dotenv as _load_dotenv

    from env_loader import load_env as _load_env
    _load_env(_Path(__file__))

    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")

    async def update_job(updates: dict):
        """Update job status directly via Supabase REST API."""
        if not supabase_url or not anon_key or not job_id:
            print(f"[Animate] Cannot update job — missing config")
            return
        try:
            headers = {
                "apikey": anon_key,
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }
            async with httpx.AsyncClient(timeout=10.0) as http:
                resp = await http.patch(
                    f"{supabase_url}/rest/v1/video_jobs?id=eq.{job_id}",
                    headers=headers,
                    json=updates,
                )
                if resp.status_code < 300:
                    print(f"[Animate] Updated job {job_id}: {list(updates.keys())}")
                else:
                    print(f"[Animate] Job update failed ({resp.status_code}): {resp.text[:200]}")
        except Exception as e:
            print(f"[Animate] Job update failed: {e}")

    try:
        # Step 1: Enhance prompt
        await update_job({"status_message": "Building animation prompt...", "progress": 10})
        style_label = data.style.replace('_', ' ')
        motion_description = f"Create a professional animation for this image with a '{style_label}' camera movement."
        if data.user_context:
            motion_description += f" User instructions: {data.user_context}"

        try:
            enhanced = await enhance_prompt(
                user_prompt=motion_description,
                mode="kling_director",
                language="en",
                context={"image_url": data.image_url}
            )
            prompt = enhanced[0]["prompt"] if enhanced else motion_description
            print(f"[Animate] Enhanced prompt: {prompt[:120]}...")
        except Exception as e:
            print(f"[Animate] Enhancement failed, using fallback: {e}")
            prompt = motion_description

        # Step 2: Call Kling API
        await update_job({"status_message": "Animating image (Kling 3.0)...", "progress": 30})
        duration = max(3, min(15, data.duration))

        # Kling 3.0 only accepts jpeg/jpg/png — convert anything else once + cache.
        from services.kling_image import ensure_kling_compatible
        data.image_url = await ensure_kling_compatible(data.image_url)
        data.product_image_url = await ensure_kling_compatible(data.product_image_url)
        data.influencer_image_url = await ensure_kling_compatible(data.influencer_image_url)

        # Build element references from available images
        kling_elements = []
        element_tags = ""

        if data.product_image_url:
            kling_elements.append({
                "name": "element_product",
                "description": "the product being showcased",
                "element_input_urls": [data.product_image_url, data.product_image_url],
            })
            element_tags += " @element_product"

        if data.influencer_image_url:
            kling_elements.append({
                "name": "element_character",
                "description": "the person/character in the scene",
                "element_input_urls": [data.influencer_image_url, data.influencer_image_url],
            })
            element_tags += " @element_character"

        # Strip hallucinated @element_ tags if no elements are provided
        if not kling_elements:
            import re
            prompt = re.sub(r'\s*@element_\w+', '', prompt).strip()

        kling_payload = {
            "model": "kling-3.0/video",
            "input": {
                "prompt": prompt + (element_tags if kling_elements else ""),
                "image_urls": [data.image_url],
                "sound": True,
                "duration": str(duration),
                "aspectRatio": "9:16",
                "aspect_ratio": "9:16",
                "mode": data.mode,
                "multi_shots": False,
                "multi_prompt": [],
                **({
                    "kling_elements": kling_elements
                } if kling_elements else {}),
            },
        }

        kie_url = os.getenv("KIE_API_URL", "https://api.kie.ai")
        kie_headers = {
            "Authorization": f"Bearer {os.getenv('KIE_API_KEY')}",
            "Content-Type": "application/json",
        }

        # Keep httpx client open for BOTH creating and polling
        async with httpx.AsyncClient(timeout=30.0) as http:
            async def _kie_animate() -> str:
                resp = await http.post(
                    f"{kie_url}/api/v1/jobs/createTask",
                    headers=kie_headers,
                    json=kling_payload,
                )
                resp.raise_for_status()
                result = resp.json()
                if result.get("code") != 200:
                    raise RuntimeError(f"Kling API error: {result.get('msg')}")
                task_id = result["data"]["taskId"]
                print(f"[Animate] Kling task created: {task_id}")

                await update_job({"status_message": "Processing video...", "progress": 50})
                for _ in range(90):  # ~15 minutes max (10s * 90)
                    await asyncio.sleep(10)
                    try:
                        poll_resp = await http.get(
                            f"{kie_url}/api/v1/jobs/recordInfo",
                            headers=kie_headers,
                            params={"taskId": task_id},
                        )
                        poll_resp.raise_for_status()
                        poll_data = poll_resp.json()
                    except Exception as poll_err:
                        print(f"[Animate] Poll error (continuing): {poll_err}")
                        continue

                    if poll_data.get("code") != 200:
                        continue
                    state = poll_data.get("data", {}).get("state", "processing")
                    if state == "success":
                        res_json = poll_data["data"].get("resultJson")
                        if isinstance(res_json, str):
                            res_json = json_mod.loads(res_json)
                        else:
                            res_json = res_json or {}
                        urls = res_json.get("resultUrls") or res_json.get("videos") or []
                        if urls:
                            return urls[0]
                    elif state == "fail":
                        fail_msg = poll_data.get("data", {}).get("failMsg", "Unknown")
                        raise RuntimeError(f"Kling generation failed: {fail_msg}")
                raise RuntimeError("Kling generation timed out after 15 minutes")

            async def _wavespeed_animate() -> str:
                ws_endpoint = os.getenv(
                    "WAVESPEED_KLING_I2V_ENDPOINT",
                    "https://api.wavespeed.ai/api/v3/kwaivgi/kling-v3.0-std/image-to-video",
                )
                ws_key = os.getenv("WAVESPEED_API_KEY", "")
                if not ws_key or not ws_endpoint:
                    raise RuntimeError("WaveSpeed Kling not configured")
                ws_headers = {
                    "Authorization": f"Bearer {ws_key}",
                    "Content-Type": "application/json",
                }
                ws_payload = {
                    "image": data.image_url,
                    "prompt": prompt,
                    "duration": max(3, min(15, duration)),
                    "sound": True,
                    "negative_prompt": "no extra limbs, no mutated hands, no extra fingers, no blurry, no distortion",
                }
                print(f"[Animate] [WaveSpeed] Submitting to {ws_endpoint}")
                sub_resp = await http.post(ws_endpoint, headers=ws_headers, json=ws_payload)
                if sub_resp.status_code != 200:
                    raise RuntimeError(f"WaveSpeed Kling submit error ({sub_resp.status_code}): {sub_resp.text[:300]}")
                api_result = sub_resp.json()
                inner = api_result.get("data", api_result)
                prediction_id = inner.get("id")
                if not prediction_id:
                    raise RuntimeError(f"WaveSpeed Kling: no prediction id: {str(api_result)[:200]}")
                status_url = (inner.get("urls") or {}).get("get") or (
                    f"https://api.wavespeed.ai/api/v3/predictions/{prediction_id}/result"
                )
                print(f"[Animate] [WaveSpeed] Task: {prediction_id}")

                for _ in range(120):  # 20 min max
                    await asyncio.sleep(10)
                    try:
                        r = await http.get(status_url, headers=ws_headers)
                        poll = r.json()
                    except Exception as e:
                        print(f"[Animate] [WaveSpeed] Poll warn: {e}")
                        continue
                    pinner = poll.get("data", poll)
                    status = (pinner.get("status") or "processing").lower()
                    if status == "completed":
                        outputs = pinner.get("outputs") or []
                        if outputs:
                            first = outputs[0]
                            url = first if isinstance(first, str) else (first.get("url") or first.get("output"))
                            if url:
                                return url
                    elif status == "failed":
                        raise RuntimeError(f"WaveSpeed Kling failed: {pinner.get('error', 'unknown')}")
                raise RuntimeError("WaveSpeed Kling timed out after 20 minutes")

            async def _ws_primary_animate() -> str:
                """WaveSpeed-primary attempt using the new wavespeed_client.

                Resolves element_ids for kling_elements (best-effort) and
                calls Kling v3 std i2v. Any failure here is caught by the
                outer try and falls through to the legacy KIE chain.
                """
                from services import wavespeed_client as ws
                element_ids: list[str] = []
                if kling_elements:
                    try:
                        from services.kling_elements import ensure_element_id
                        for el in kling_elements:
                            urls = el.get("element_input_urls") or []
                            primary = urls[0] if urls else None
                            if not primary:
                                continue
                            owner_kwargs: dict = {}
                            if el["name"] == "element_product" and getattr(data, "product_id", None):
                                owner_kwargs["product_id"] = data.product_id
                            elif el["name"] == "element_character" and getattr(data, "influencer_id", None):
                                owner_kwargs["influencer_id"] = data.influencer_id
                            eid = await ensure_element_id(
                                name=el["name"],
                                description=el.get("description") or el["name"],
                                image_url=primary,
                                refer_urls=urls,
                                **owner_kwargs,
                            )
                            element_ids.append(eid)
                        if len(element_ids) != len(kling_elements):
                            raise RuntimeError(f"element_id resolution incomplete ({len(element_ids)}/{len(kling_elements)})")
                    except Exception as el_err:
                        raise RuntimeError(f"element_id resolution failed: {el_err}")

                submit_data = await asyncio.to_thread(
                    ws.kling_v3_std_i2v,
                    image=data.image_url,
                    prompt=prompt,
                    duration=max(3, min(15, duration)),
                    element_ids=element_ids or None,
                )
                pred_id = submit_data["id"]
                result = await asyncio.to_thread(
                    ws.poll_until_done, pred_id, label="WS animate Kling", max_poll_seconds=1200,
                )
                return ws.first_output_url(result)

            SKIP_PATTERNS = ("internal error", "high demand", "429", "503", "rate limit", "service is currently unavailable", "e003")
            RETRY_PATTERNS = ("500", "unknown generation error", "timed out", "timeout", "generation failed")

            video_url: Optional[str] = None

            # ── WaveSpeed-primary outer layer (additive) ─────────────
            ws_primary_on = (
                os.getenv("USE_WAVESPEED_PRIMARY", "false").strip().lower() == "true"
                and bool(os.getenv("WAVESPEED_API_KEY"))
            )
            if ws_primary_on:
                try:
                    print("[Animate] [WaveSpeed primary] attempt")
                    video_url = await _ws_primary_animate()
                    print(f"[Animate] [WaveSpeed primary] complete: {video_url[:80]}...")
                except Exception as ws_primary_err:
                    print(f"[Animate] [WaveSpeed primary failed: {ws_primary_err}] — falling through to KIE chain")
                    video_url = None

            if video_url:
                # WaveSpeed primary succeeded — skip the legacy KIE chain entirely.
                pass
            else:
                try:
                    video_url = await _kie_animate()
                except Exception as kie_err:
                    err = str(kie_err).lower()
                    should_fallback = (
                        any(p in err for p in SKIP_PATTERNS)
                        or any(p in err for p in RETRY_PATTERNS)
                    )
                    if should_fallback and os.getenv("WAVESPEED_API_KEY"):
                        print(f"[Animate] KIE failed ({kie_err}) — falling back to WaveSpeed Kling")
                        await update_job({"status_message": "KIE failed — retrying on WaveSpeed...", "progress": 55})
                        video_url = await _wavespeed_animate()
                    else:
                        raise

            if not video_url:
                raise RuntimeError("Animation produced no video URL")

            print(f"[Animate] Complete! Video URL: {video_url[:80]}...")
            await update_job({
                "status": "success",
                "final_video_url": video_url,
                "progress": 100,
                "status_message": "Complete!",
            })
            return

    except Exception as e:
        print(f"[Animate] Pipeline failed for job {job_id}: {e}")
        await update_job({"status": "failed", "error_message": str(e)[:500]})




@router.get("/status/{task_id}")
async def get_animation_status(task_id: str, user: dict = Depends(get_current_user)):
    """Poll the status of an animation task."""
    headers = {
        "Authorization": f"Bearer {KIE_API_KEY}",
        "Content-Type": "application/json",
    }

    # Try Kling endpoint first (recordInfo), then Veo (record-info)
    async with httpx.AsyncClient(timeout=15.0) as client:
        # Check if it's a Kling task
        if "kling" in task_id.lower():
            resp = await client.get(
                f"{KIE_API_URL}/api/v1/jobs/recordInfo",
                headers=headers,
                params={"taskId": task_id},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200:
                return {"status": "processing", "task_id": task_id}

            state = data.get("data", {}).get("state", "processing")
            if state == "success":
                import json
                result_json = data["data"].get("resultJson")
                if isinstance(result_json, str):
                    result_data = json.loads(result_json)
                else:
                    result_data = result_json or {}

                urls = result_data.get("resultUrls") or result_data.get("videos") or []
                return {
                    "status": "complete",
                    "task_id": task_id,
                    "video_url": urls[0] if urls else None,
                }
            elif state == "fail":
                return {
                    "status": "failed",
                    "task_id": task_id,
                    "error": data["data"].get("failMsg", "Unknown error"),
                }
            return {"status": "processing", "task_id": task_id}

        else:
            # Veo endpoint
            resp = await client.get(
                f"{KIE_API_URL}/api/v1/veo/record-info",
                headers=headers,
                params={"taskId": task_id},
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") != 200:
                return {"status": "processing", "task_id": task_id}

            flag = data.get("data", {}).get("successFlag", 0)
            if flag == 1:
                import json
                response_obj = data["data"].get("response") or {}
                if isinstance(response_obj, str):
                    try:
                        response_obj = json.loads(response_obj)
                    except Exception:
                        response_obj = {}
                urls = response_obj.get("resultUrls") or data["data"].get("resultUrls") or []
                return {
                    "status": "complete",
                    "task_id": task_id,
                    "video_url": urls[0] if urls else None,
                }
            elif flag in (2, 3):
                return {
                    "status": "failed",
                    "task_id": task_id,
                    "error": data["data"].get("failMsg", "Unknown error"),
                }
            return {"status": "processing", "task_id": task_id}
