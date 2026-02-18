"""
Naiara Content Distribution Engine — Scene Generator

Orchestrates AI video generation via Kie.ai API.
Model is configurable via VIDEO_MODEL in .env:
  - seedance-1.5-pro (default): native lip-sync + Spanish, $0.28/clip
  - seedance-2.0: upgraded version (Feb 24), 2K res
  - veo-3.1-fast: fallback, no language control
For each AI scene, sends reference image + prompt → gets back video with speech.
For 'clip' scenes, downloads the pre-recorded app footage.
"""
import os
import time
import json
import requests
from pathlib import Path
import config


# ---------------------------------------------------------------------------
# Model-specific API configs (Kie.ai endpoints differ per model family)
# ---------------------------------------------------------------------------
MODEL_ENDPOINTS = {
    "seedance": {
        "generate": f"{config.KIE_API_URL}/api/v1/jobs/createTask",
        "poll": f"{config.KIE_API_URL}/api/v1/jobs/recordInfo",
    },
    "kling": {
        "generate": f"{config.KIE_API_URL}/api/v1/jobs/createTask",
        "poll": f"{config.KIE_API_URL}/api/v1/jobs/recordInfo",
    },
    "veo": {
        "generate": f"{config.KIE_API_URL}/api/v1/veo/generate",
        "poll": f"{config.KIE_API_URL}/api/v1/veo/record-info",
    },
    "lipsync": {
        "generate": f"{config.KIE_API_URL}/api/v1/jobs/createTask",
        "poll": f"{config.KIE_API_URL}/api/v1/jobs/recordInfo",
    }
}

def _get_model_family(model_name=None):
    """Determine API family from provided model name or config."""
    model = model_name or config.VIDEO_MODEL
    if "seedance" in model:
        return "seedance"
    if "kling" in model:
        return "kling"
    return "veo"


def generate_video(prompt, reference_image_url=None, model_api=None):
    """
    Generate video using specified AI model API (Seedance/Kie.ai).

    Supports Seedance 1.5 Pro (default) and Veo 3.1 as fallback.
    Seedance provides native lip-sync and Spanish speech.
    """
    print(f"   🎬 generate_video called!")
    print(f"      Arg reference_image_url: '{reference_image_url}'")
    print(f"      Arg model_api (raw): '{model_api}'")

    if model_api is None:
        model_api = config.VIDEO_MODEL_API
        model_display = config.VIDEO_MODEL
    else:
        # Map friendly name (e.g. seedance-1.5-pro) to API ID (bytedance/seedance-1.5-pro)
        model_display = model_api  # Keep the original name for error messages
        model_api = config.MODEL_REGISTRY.get(model_api, model_api)
        
    print(f"      Resolved model_api: '{model_api}'")
    family = _get_model_family(model_api)
    endpoints = MODEL_ENDPOINTS[family]

    if family == "seedance":
        # --- Seedance payload (as per official documentation) ---
        payload = {
            "model": model_api,
            "input": {
                "prompt": prompt,
                "input_urls": [reference_image_url] if reference_image_url else [],
                "aspect_ratio": config.VIDEO_ASPECT_RATIO,
                "resolution": config.SEEDANCE_QUALITY,
                "duration": str(config.AI_CLIP_DURATION),
                "generate_audio": config.SEEDANCE_AUDIO,
                "fixed_lens": False
            },
            "callBackUrl": "https://example.com/callback",
        }
    elif family == "kling":
        # --- Kling payload (uses image_urls, no audio) ---
        # Kling only accepts duration "5" or "10"
        kling_duration = "5" if config.AI_CLIP_DURATION <= 5 else "10"
        payload = {
            "model": model_api,
            "input": {
                "prompt": prompt,
                "image_urls": [reference_image_url] if reference_image_url else [],
                "sound": False,
                "duration": kling_duration,
            }
        }
    else:
        # --- Veo 3.1 payload (flat format, dedicated /veo/generate endpoint) ---
        payload = {
            "prompt": prompt,
            "model": model_api,
            "aspect_ratio": config.VIDEO_ASPECT_RATIO,
        }
        if reference_image_url:
            payload["imageUrls"] = [reference_image_url]
            payload["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"

    resp = requests.post(endpoints["generate"], headers=config.KIE_HEADERS, json=payload)
    
    if resp.status_code != 200:
        try:
            err_data = resp.json()
            err_msg = err_data.get("message", err_data.get("msg", str(err_data)))
        except:
            err_msg = resp.text[:200]
        raise RuntimeError(f"{model_display} API error ({resp.status_code}): {err_msg}")

    result = resp.json()
    if result.get("code") != 200:
        error_msg = result.get("message", result.get("msg", str(result)))
        raise RuntimeError(f"{model_display} API error: {error_msg}")

    task_id = result["data"]["taskId"]
    print(f"      Task: {task_id[:30]}...")

    # Poll for completion — typically 1-3 minutes, up to 15-20min for complex scenes
    for i in range(120):  # 20 minutes max
        time.sleep(10)

        resp = requests.get(
            endpoints["poll"],
            headers=config.KIE_HEADERS,
            params={"taskId": task_id},
        )
        result = resp.json()

        if result.get("code") != 200:
            print(f"      ⚠️ Poll error: {result.get('msg', '')} ({i * 10}s)")
            continue

        data = result.get("data", {})

        if family == "veo":
            # Veo uses successFlag: 0=generating, 1=success, 2=failed, 3=gen failed
            flag = data.get("successFlag", 0)
            if flag == 1:
                # Veo nests URLs under data.response.resultUrls
                response_obj = data.get("response") or {}
                if isinstance(response_obj, str):
                    try:
                        response_obj = json.loads(response_obj)
                    except:
                        response_obj = {}
                result_urls = response_obj.get("resultUrls") or data.get("resultUrls") or []
                if isinstance(result_urls, str):
                    result_urls = json.loads(result_urls)
                if result_urls:
                    print(f"      ✨ Generation complete! ({i * 10}s)")
                    return result_urls[0]
                print(f"      ⚠️ Success but no resultUrls ({i * 10}s)")
                print(f"      DEBUG data keys: {list(data.keys())}")
                continue
            elif flag in (2, 3):
                error_msg = data.get("failMsg", data.get("statusDescription", "Unknown generation error"))
                raise RuntimeError(f"Generation failed: {error_msg}")
            else:
                status_desc = data.get("statusDescription", "generating")
                print(f"      ⏳ {status_desc}... ({i * 10}s)")
        else:
            # Seedance / Kling use state: success/fail/processing
            state = data.get("state", "processing").lower()

            if state == "success":
                result_json_str = data.get("resultJson", "{}")
                try:
                    result_data = json.loads(result_json_str)
                    video_url = result_data.get("resultUrls", [None])[0]
                    if video_url:
                        print(f"      ✨ Generation complete! ({i * 10}s)")
                        return video_url
                except Exception as e:
                    print(f"      ⚠️ Error parsing resultJson: {e}")
                    continue

            elif state == "fail":
                error_msg = data.get("failMsg", "Unknown generation error")
                raise RuntimeError(f"Generation failed: {error_msg}")
            elif state == "waiting" or state == "processing":
                print(f"      ⏳ Generating... ({i * 10}s)")
            else:
                print(f"      ⚠️ Unknown state: {state} ({i * 10}s)")

    raise RuntimeError(f"{model_display} generation timed out after 20 minutes")


def generate_lipsync_video(image_url, audio_url, prompt="Lip-syncing video"):
    """
    Generate a lip-synced video using Kie.ai InfiniteTalk.
    image_url: Public URL to the influencer reference image.
    audio_url: Public URL to the ElevenLabs generated audio.
    prompt: Optional prompt (now required by some Kie.ai models).
    """
    endpoints = MODEL_ENDPOINTS["lipsync"]
    model_api = config.LIPSYNC_MODEL
    
    payload = {
        "model": model_api,
        "input": {
            "image_url": image_url,
            "audio_url": audio_url,
            "prompt": prompt or "Lip-syncing video",
            "resolution": config.LIPSYNC_QUALITY
        },
        "callBackUrl": "https://example.com/callback",
    }

    print(f"   👄 Submitting Lip-Sync task (InfiniteTalk)...")
    print(f"      Payload: {json.dumps(payload, indent=2)}")
    
    resp = requests.post(endpoints["generate"], headers=config.KIE_HEADERS, json=payload)
    
    if resp.status_code != 200:
        raise RuntimeError(f"Lip-Sync API error ({resp.status_code}): {resp.text[:500]}")

    result = resp.json()
    print(f"      Dbg: Kie.ai Raw Resp: {result}")
    if result.get("code") != 200:
        raise RuntimeError(f"Lip-Sync API error: {result.get('msg', str(result))}")

    task_id = result["data"]["taskId"]
    print(f"      Task: {task_id}")

    # Poll for completion with adaptive backoff
    for i in range(120): # 20 minutes max (InfiniteTalk can be slow)
        # Adaptive sleep: start frequent, then back off to prevent socket timeouts
        wait_time = 10 if i < 30 else 20
        time.sleep(wait_time)
        
        try:
            resp = requests.get(endpoints["poll"], headers=config.KIE_HEADERS, params={"taskId": task_id}, timeout=30)
            result = resp.json()
        except Exception as poll_err:
            print(f"      ⚠️ Poll network warning: {poll_err}")
            continue
        
        if result.get("code") != 200:
            print(f"      ⚠️ API warning: {result.get('msg', 'Unknown error')}")
            continue
            
        data = result.get("data", {})
        state = data.get("state", "processing").lower()

        if state == "success":
            video_url = _extract_video_url(data)
            if video_url:
                print(f"      ✨ Lip-Sync complete! ({i * 10}s)")
                return video_url
        elif state == "fail":
            fail_msg = data.get("failMsg", "Unknown error")
            # Specific hint for common audio issue
            if "audio file is unavailable" in fail_msg.lower():
                fail_msg += " (Try verifying the direct download link format)"
            raise RuntimeError(f"Lip-Sync failed: {fail_msg}")
        
        print(f"      ⏳ Syncing... ({i * wait_time}s)")

    raise RuntimeError("Lip-Sync generation timed out after 20 minutes")


def _extract_video_url(data):
    """Pull the video URL from Kie.ai's response data (works for all models)."""
    response_obj = data.get("response", {})

    # 1. response.resultUrls
    if response_obj.get("resultUrls"):
        return response_obj["resultUrls"][0]
    # 2. response.videoUrl
    if response_obj.get("videoUrl"):
        return response_obj["videoUrl"]
    # 3. Fallback: resultJson (older Veo responses)
    result_json = data.get("resultJson", "{}")
    if isinstance(result_json, str):
        try:
            result_data = json.loads(result_json)
        except (json.JSONDecodeError, TypeError):
            result_data = {}
    else:
        result_data = result_json

    if result_data.get("resultUrls"):
        return result_data["resultUrls"][0]
    return result_data.get("videoUrl")


def download_video(url, output_path):
    """Download a video from URL to local file."""
    print(f"   📥 Downloading video...")
    resp = requests.get(url, stream=True)
    resp.raise_for_status()

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"      💾 Saved: {output_path} ({size_mb:.1f} MB)")
    return str(output_path)


def generate_all_scenes(scenes, project_name="video", record_id=None, status_callback=None):
    """
    Generate/download all scene videos with real-time progress tracking.

    Args:
        scenes: List of scene dicts from scene_builder.build_scenes()
        project_name: Used for output filenames and asset tracking
        record_id: Content Calendar record ID for status updates
        status_callback: Function to call with status updates (e.g., airtable_client.update_status)

    Returns:
        List of local file paths (in scene order)
    """
    output_dir = config.TEMP_DIR / project_name
    output_dir.mkdir(parents=True, exist_ok=True)

    video_paths = []
    total_cost = 0

    for i, scene in enumerate(scenes, 1):
        # Update status before starting scene
        if status_callback and record_id:
            scene_status = f"Gen: {scene['name'].title()} ({i}/{len(scenes)})"
            status_callback(record_id, scene_status)

        print(f"\n{'='*50}")
        print(f"Scene {i}/{len(scenes)}: {scene['name'].upper()}")
        print(f"{'='*50}")

        output_path = output_dir / f"scene_{i}_{scene['name']}.mp4"

        try:
            if scene["type"] == "veo":
                # Generate with AI model (Seedance / Veo / etc.)
                video_url = generate_video(
                    prompt=scene["prompt"],
                    reference_image_url=scene.get("reference_image_url"),
                )
                download_video(video_url, output_path)
                clip_cost = 0.28 if _get_model_family() == "seedance" else 0.30
                total_cost += clip_cost
                
                # Log the generated video asset
                import airtable_client
                airtable_client.log_asset(
                    content_title=project_name,
                    scene_name=scene["name"],
                    asset_type="AI Video",
                    source_url=video_url,
                    duration=8.0,
                    model=config.VIDEO_MODEL_API,
                    cost=clip_cost,
                    status="Ready"
                )

            elif scene["type"] == "clip":
                # Download pre-recorded footage
                print(f"   📱 Using pre-recorded app clip")
                download_video(scene["video_url"], output_path)
                
                # Log the app clip
                import airtable_client
                airtable_client.log_asset(
                    content_title=project_name,
                    scene_name=scene["name"],
                    asset_type="App Clip",
                    source_url=scene["video_url"],
                    duration=scene.get("target_duration", 8),
                    status="Ready"
                )

            scene["path"] = str(output_path)
            video_paths.append(scene)

        except Exception as e:
            print(f"   ❌ Error in scene {i} ({scene['name']}): {e}")
            
            # Log failure to Generated Assets
            import airtable_client
            airtable_client.log_asset(
                content_title=project_name,
                scene_name=scene["name"],
                asset_type="AI Video" if scene["type"] == "veo" else "App Clip",
                source_url="",
                status="Failed",
                error_msg=str(e)
            )
            
            # Fail fast — an incomplete video is not helpful
            raise RuntimeError(f"Scene {i} ({scene['name']}) generation failed: {e}")

    print(f"\n✅ All {len(scenes)} scenes ready! Cost: ~${total_cost:.2f}")
    return video_paths


# ---------------------------------------------------------------------------
# Music generation (reuses existing Suno V4 logic)
# ---------------------------------------------------------------------------

def generate_music(prompt="upbeat, trendy, short-form social media background music, "
                          "energetic and positive vibe, modern pop instrumental",
                   instrumental=True):
    """
    Generate background music using Suno V4 via Kie.ai.
    Returns URL to the generated audio file, or None if failed.
    """
    print("🎵 Generating background music...")
    print(f"   Prompt: {prompt[:80]}...")

    payload = {
        "prompt": prompt[:500],
        "customMode": False,
        "instrumental": instrumental,
        "model": "V4",
        "callBackUrl": "https://example.com/callback",
    }

    resp = requests.post(
        "https://api.kie.ai/api/v1/generate",
        headers=config.KIE_HEADERS,
        json=payload,
    )
    result = resp.json()

    if result.get("code") != 200:
        print(f"   ⚠️ Music generation failed: {result}")
        return None

    task_id = result["data"]["taskId"]
    print(f"   Task: {task_id[:20]}...")

    for i in range(48):  # 8 minutes max
        time.sleep(10)
        resp = requests.get(
            "https://api.kie.ai/api/v1/generate/record-info",
            headers=config.KIE_HEADERS,
            params={"taskId": task_id},
        )
        result = resp.json()

        if result.get("code") != 200:
            print(f"   Waiting... ({i * 10}s)")
            continue

        status = result["data"]["status"]

        if status in ["SUCCESS", "FIRST_SUCCESS"]:
            suno_data = result["data"]["response"]["sunoData"]
            if suno_data:
                audio_url = suno_data[0]["audioUrl"]
                print(f"   ✅ Music ready!")
                return audio_url
        elif status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED"]:
            print("   ⚠️ Music generation failed")
            return None

        print(f"   ⏳ Generating... ({i * 10}s)")

    print("   ⚠️ Music generation timed out")
    return None


if __name__ == "__main__":
    print("This module is imported by pipeline.py")
    print("Functions: generate_veo_video(), generate_all_scenes(), generate_music()")
