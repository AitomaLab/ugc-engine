"""
Creative OS — generate_scenes shim

Standalone implementations of the 3 functions from the repo-root
generate_scenes.py that the video generation pipelines need.
On Railway, the repo root isn't available, so this module provides
self-contained versions using direct KIE API calls.

Functions:
  - generate_video_with_retry(prompt, reference_image_url, model_api, ...)
  - download_video(url, output_path)
  - generate_composite_image_with_retry(scene, influencer, product, ...)
"""
import json
import os
import time
import requests
from pathlib import Path

from env_loader import load_env
load_env(Path(__file__))

KIE_API_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
KIE_API_KEY = os.getenv("KIE_API_KEY", "")
KIE_HEADERS = {
    "Authorization": f"Bearer {KIE_API_KEY}",
    "Content-Type": "application/json",
}


def _get_model_family(model_api: str) -> str:
    lower = model_api.lower()
    if "kling" in lower or "kie" in lower:
        return "kling"
    if "seedance" in lower:
        return "seedance"
    return "veo"


# Internal model name → KIE API model identifier.
# Mirrors MODEL_REGISTRY in repo-root config.py (not importable on Railway).
KIE_MODEL_NAMES = {
    "veo-3.1-fast": "veo3_fast",
    "veo-3.1": "veo3",
    "seedance-1.5-pro": "bytedance/seedance-1.5-pro",
    "seedance-2.0": "bytedance/seedance-2",
    "kling-2.6": "kling-2.6/image-to-video",
}


def _to_kie_model_name(model_api: str) -> str:
    """Translate internal model name to KIE's accepted identifier.
    Pass-through for already-translated names (e.g. 'kling-3.0/video')."""
    return KIE_MODEL_NAMES.get(model_api, model_api)


MODEL_ENDPOINTS = {
    "seedance": {
        "generate": f"{KIE_API_URL}/api/v1/jobs/createTask",
        "poll": f"{KIE_API_URL}/api/v1/jobs/recordInfo",
    },
    "kling": {
        "generate": f"{KIE_API_URL}/api/v1/jobs/createTask",
        "poll": f"{KIE_API_URL}/api/v1/jobs/recordInfo",
    },
    "veo": {
        "generate": f"{KIE_API_URL}/api/v1/veo/generate",
        "poll": f"{KIE_API_URL}/api/v1/veo/record-info",
    },
}


# ---------------------------------------------------------------------------
# generate_video  (synchronous — called via asyncio.to_thread)
# ---------------------------------------------------------------------------
def generate_video(
    prompt,
    reference_image_url=None,
    model_api=None,
    first_frame_url=None,
    return_last_frame=False,
    duration=12,
    kling_elements=None,
    max_poll_seconds=None,
    multi_prompt=None,
):
    """Submit a video generation job to KIE and poll until completion.

    Returns dict: {"taskId": str, "videoUrl": str, "lastFrameUrl": str|None}
    """
    if model_api is None:
        model_api = "kling-3.0/video"

    family = _get_model_family(model_api)
    endpoints = MODEL_ENDPOINTS[family]
    # Translate internal name (e.g. "veo-3.1-fast") to KIE's identifier ("veo3_fast").
    # Family detection above relies on the readable name, so do this AFTER family.
    model_api_kie = _to_kie_model_name(model_api)

    # Build payload per model family
    if family == "kling":
        kling_duration = str(max(3, min(15, duration)))
        is_multi = bool(multi_prompt and len(multi_prompt) > 0)
        kling_input = {
            "prompt": prompt if not is_multi else "",
            "image_urls": [reference_image_url] if reference_image_url else [],
            "sound": True,
            "duration": kling_duration,
            "aspect_ratio": "9:16",
            "mode": "pro",
            "multi_shots": is_multi,
            "multi_prompt": multi_prompt if is_multi else [],
        }
        if is_multi:
            print(f"      [Kling] Multi-shot mode: {len(multi_prompt)} shot(s), total {sum(s.get('duration', 3) for s in multi_prompt)}s")
        if kling_elements:
            kling_input["kling_elements"] = kling_elements
            print(f"      [Kling] Payload includes {len(kling_elements)} element(s)")
        payload = {"model": model_api_kie, "input": kling_input}
    elif family == "veo":
        payload = {
            "prompt": prompt,
            "model": model_api_kie,
            "aspect_ratio": "9:16",
            "enableFallback": False,
            "enableTranslation": False,
            "watermark": "",
        }
        if reference_image_url:
            payload["imageUrls"] = [reference_image_url, reference_image_url]
            payload["generationType"] = "IMAGE_2_VIDEO"
    else:
        # Seedance
        payload = {
            "model": model_api_kie,
            "input": {
                "prompt": prompt,
                "aspect_ratio": "9:16",
                "resolution": "2K",
                "duration": duration,
                "generate_audio": True,
                "web_search": False,
            },
        }
        if reference_image_url:
            payload["input"]["reference_image_urls"] = [reference_image_url]
        if first_frame_url:
            payload["input"]["first_frame_url"] = first_frame_url
        if return_last_frame:
            payload["input"]["return_last_frame"] = True

    # Submit
    try:
        resp = requests.post(endpoints["generate"], headers=KIE_HEADERS, json=payload, timeout=60)
    except Exception as e:
        raise RuntimeError(f"KIE API network error: {e}")

    if resp.status_code != 200:
        try:
            err_data = resp.json()
            err_msg = err_data.get("message", err_data.get("msg", str(err_data)))
        except Exception:
            err_msg = resp.text[:200]
        raise RuntimeError(f"KIE API error ({resp.status_code}): {err_msg}")

    result = resp.json()
    if result.get("code") != 200:
        raise RuntimeError(f"KIE API error: {result.get('message', result.get('msg', str(result)))}")

    task_id = result["data"]["taskId"]
    print(f"      Task: {task_id[:30]}...")

    # Poll for completion
    poll_limit = (max_poll_seconds // 10) if max_poll_seconds else 120  # default 20 min
    for i in range(poll_limit):
        time.sleep(10)
        try:
            resp = requests.get(
                endpoints["poll"],
                headers=KIE_HEADERS,
                params={"taskId": task_id},
                timeout=30,
            )
            result = resp.json()
        except Exception as poll_err:
            print(f"      Poll warning: {poll_err} (continuing...)")
            continue

        if result.get("code") != 200:
            continue

        data = result.get("data", {})

        if family == "veo":
            flag = data.get("successFlag", 0)
            if flag == 1:
                response_obj = data.get("response") or {}
                if isinstance(response_obj, str):
                    try:
                        response_obj = json.loads(response_obj)
                    except Exception:
                        response_obj = {}
                result_urls = response_obj.get("resultUrls") or data.get("resultUrls") or []
                if isinstance(result_urls, str):
                    result_urls = json.loads(result_urls)
                if result_urls:
                    print(f"      [OK] Generation complete! ({i * 10}s)")
                    return {"taskId": task_id, "videoUrl": result_urls[0]}
                continue
            elif flag in (2, 3):
                error_msg = data.get("failMsg", data.get("statusDescription", "Unknown generation error"))
                raise RuntimeError(f"Generation failed: {error_msg}")
        else:
            # Kling / Seedance
            state = data.get("state", "processing").lower()
            if state == "success":
                result_json_str = data.get("resultJson", "{}")
                try:
                    if isinstance(result_json_str, str):
                        result_data = json.loads(result_json_str)
                    else:
                        result_data = result_json_str or {}
                    video_url = result_data.get("resultUrls", [None])[0]
                    last_frame_url = result_data.get("lastFrameUrl")
                    if video_url:
                        print(f"      [OK] Generation complete! ({i * 10}s)")
                        return {
                            "taskId": task_id,
                            "videoUrl": video_url,
                            "lastFrameUrl": last_frame_url,
                        }
                except Exception as e:
                    print(f"      Error parsing resultJson: {e}")
                    continue
            elif state == "fail":
                error_msg = data.get("failMsg", "Unknown generation error")
                raise RuntimeError(f"Generation failed: {error_msg}")

    timeout_mins = (max_poll_seconds // 60) if max_poll_seconds else 20
    raise RuntimeError(f"Video generation timed out after {timeout_mins} minutes")


def generate_video_with_retry(
    prompt,
    reference_image_url=None,
    model_api=None,
    first_frame_url=None,
    return_last_frame=False,
    duration=12,
    max_retries=3,
    kling_elements=None,
    multi_prompt=None,
):
    """Generate video with retry on transient errors."""
    RETRIABLE_PATTERNS = ("500", "internal error", "unknown generation error", "timed out", "timeout", "generation failed")

    for attempt in range(max_retries):
        try:
            return generate_video(
                prompt, reference_image_url, model_api,
                first_frame_url, return_last_frame, duration,
                kling_elements=kling_elements,
                multi_prompt=multi_prompt,
            )
        except RuntimeError as e:
            error_str = str(e).lower()
            is_retriable = any(p in error_str for p in RETRIABLE_PATTERNS)
            if is_retriable and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"      [RETRY] '{e}' - retrying in {wait_time}s (attempt {attempt + 2}/{max_retries})")
                time.sleep(wait_time)
                continue
            raise


# ---------------------------------------------------------------------------
# download_video  (synchronous — called via asyncio.to_thread)
# ---------------------------------------------------------------------------
def download_video(url, output_path, max_retries=5):
    """Download a video from URL to local file with retries."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"      Saved: {output_path} ({size_mb:.1f} MB)")
            return str(output_path)
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"      Download failed ({str(e)[:150]}). Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Failed to download video after {max_retries} attempts: {e}")


# ---------------------------------------------------------------------------
# generate_composite_image_with_retry  (NanoBanana Pro)
# ---------------------------------------------------------------------------
def generate_composite_image(scene: dict, influencer: dict, product: dict, seed: int = None) -> str:
    """Generate a composite image using NanoBanana Pro API."""
    endpoint = f"{KIE_API_URL}/api/v1/jobs/createTask"

    final_prompt = scene.get("nano_banana_prompt") or scene.get("prompt")
    negative_prompt = (
        "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, "
        "(extra limb:1.5), (third arm:1.5), (third hand:1.5), (extra arm:1.5), (extra hand:1.5), "
        "missing limb, floating limbs, (mutated hands and fingers:1.4), disconnected limbs, "
        "mutation, mutated, ugly, disgusting, blurry, amputation, (3rd hand:1.5), multiple people, "
        "different person, airbrushed skin, studio backdrop, geometric distortion, text overlays, watermarks, extra fingers"
    )
    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": final_prompt,
            "negative_prompt": negative_prompt,
            "image_input": [
                scene["reference_image_url"],
                scene["product_image_url"],
            ],
            "aspect_ratio": "9:16",
            "resolution": "2K",
        },
    }

    resp = requests.post(endpoint, headers=KIE_HEADERS, json=payload, timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"NanoBanana API error ({resp.status_code}): {resp.text[:500]}")

    result = resp.json()
    if result.get("code") != 200:
        raise RuntimeError(f"NanoBanana API error: {result.get('msg', str(result))}")

    task_id = result["data"]["taskId"]
    poll_endpoint = f"{KIE_API_URL}/api/v1/jobs/recordInfo"

    for i in range(60):  # 10 minutes max
        time.sleep(10)
        try:
            resp = requests.get(poll_endpoint, headers=KIE_HEADERS, params={"taskId": task_id}, timeout=30)
            result = resp.json()
        except Exception as e:
            print(f"      Poll error: {e}")
            continue

        if result.get("code") != 200:
            continue

        data = result.get("data", {})
        state = data.get("state", "processing").lower()

        if state == "success":
            result_json = data.get("resultJson", "{}")
            if isinstance(result_json, str):
                result_json = json.loads(result_json)
            urls = result_json.get("resultUrls", [])
            if urls:
                print(f"      Composite image ready! ({i * 10}s)")
                return urls[0]
        elif state == "fail":
            raise RuntimeError(f"NanoBanana generation failed: {data.get('failMsg', 'Unknown error')}")

    raise RuntimeError("NanoBanana generation timed out")


def generate_composite_image_with_retry(
    scene: dict, influencer: dict, product: dict, seed: int = None, max_retries: int = 5
) -> str:
    """Generate composite image with retry on rate limit errors."""
    for attempt in range(max_retries):
        try:
            return generate_composite_image(scene, influencer, product, seed)
        except RuntimeError as e:
            if ("concurrent requests limit" in str(e).lower() or "429" in str(e)) and attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"      NanoBanana rate limited. Retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            raise
