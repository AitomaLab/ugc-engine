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
import re
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
    "seedance-2.0-fast": "bytedance/seedance-2-fast",
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
    reference_image_urls=None,
    reference_video_urls=None,
    aspect_ratio="9:16",
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
            "sound": True,
            "duration": kling_duration,
            "aspectRatio": aspect_ratio,
            "aspect_ratio": aspect_ratio,
            "mode": "pro",
            "multi_shots": is_multi,
            "multi_prompt": multi_prompt if is_multi else [],
        }
        if kling_elements:
            kling_input["kling_elements"] = kling_elements
            # KIE requires image_urls alongside kling_elements when prompt uses @role refs.
            element_image_urls: list[str] = []
            for el in kling_elements:
                urls = el.get("element_input_urls") or []
                if urls:
                    element_image_urls.append(urls[0])
            if reference_image_url and reference_image_url not in element_image_urls:
                element_image_urls.insert(0, reference_image_url)
            if element_image_urls:
                kling_input["image_urls"] = element_image_urls
            print(f"      [Kling] Payload includes {len(kling_elements)} element(s), image_urls={len(element_image_urls)}")
        elif reference_image_url:
            kling_input["image_urls"] = [reference_image_url]
        if is_multi:
            print(f"      [Kling] Multi-shot mode: {len(multi_prompt)} shot(s), total {sum(s.get('duration', 3) for s in multi_prompt)}s")
        payload = {"model": model_api_kie, "input": kling_input}
    elif family == "veo":
        payload = {
            "prompt": prompt,
            "model": model_api_kie,
            "aspect_ratio": aspect_ratio,
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
                "aspect_ratio": aspect_ratio,
                "resolution": "720p",
                "duration": duration,
                "generate_audio": True,
                "web_search": False,
            },
        }
        ref_list: list[str] = []
        if reference_image_urls:
            ref_list.extend([u for u in reference_image_urls if u])
        elif reference_image_url:
            ref_list.append(reference_image_url)
        if ref_list:
            payload["input"]["reference_image_urls"] = ref_list
        if reference_video_urls:
            payload["input"]["reference_video_urls"] = [u for u in reference_video_urls if u]
        if first_frame_url:
            payload["input"]["first_frame_url"] = first_frame_url
        if return_last_frame:
            payload["input"]["return_last_frame"] = True

    # Submit
    try:
        print(f"[KIE submit] family={family} model={model_api_kie} payload={json.dumps(payload)[:2000]}", flush=True)
    except Exception:
        pass
    try:
        resp = requests.post(endpoints["generate"], headers=KIE_HEADERS, json=payload, timeout=60)
    except Exception as e:
        raise RuntimeError(f"KIE API network error: {e}")

    if resp.status_code != 200:
        body = resp.text[:2000]
        print(f"[KIE submit] HTTP {resp.status_code} body={body}", flush=True)
        try:
            err_data = resp.json()
            err_msg = err_data.get("message", err_data.get("msg", str(err_data)))
        except Exception:
            err_msg = resp.text[:200]
        raise RuntimeError(f"KIE API error ({resp.status_code}): {err_msg}")

    result = resp.json()
    if result.get("code") != 200:
        print(f"[KIE submit] non-200 code result={str(result)[:2000]}", flush=True)
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
                print(f"[KIE poll] fail data={str(data)[:2000]}", flush=True)
                error_msg = data.get("failMsg", "Unknown generation error")
                raise RuntimeError(f"Generation failed: {error_msg}")

    timeout_mins = (max_poll_seconds // 60) if max_poll_seconds else 20
    raise RuntimeError(f"Video generation timed out after {timeout_mins} minutes")


# ---------------------------------------------------------------------------
# WaveSpeed fallback providers
# ---------------------------------------------------------------------------
WAVESPEED_API_URL = "https://api.wavespeed.ai/api/v3"
WAVESPEED_VEO_I2V_ENDPOINT = os.getenv(
    "WAVESPEED_VEO_I2V_ENDPOINT", f"{WAVESPEED_API_URL}/google/veo3.1/reference-to-video"
)
WAVESPEED_VEO_T2V_ENDPOINT = os.getenv(
    "WAVESPEED_VEO_T2V_ENDPOINT", f"{WAVESPEED_API_URL}/google/veo3.1-fast/text-to-video"
)
WAVESPEED_KLING_I2V_ENDPOINT = os.getenv(
    "WAVESPEED_KLING_I2V_ENDPOINT", f"{WAVESPEED_API_URL}/kwaivgi/kling-v3.0-std/image-to-video"
)
WAVESPEED_SEEDANCE_ENDPOINT = os.getenv(
    "WAVESPEED_SEEDANCE_ENDPOINT", f"{WAVESPEED_API_URL}/bytedance/seedance-2.0/image-to-video"
)
WAVESPEED_NANOBANANA_ENDPOINT = os.getenv(
    "WAVESPEED_NANOBANANA_ENDPOINT", f"{WAVESPEED_API_URL}/google/nano-banana-pro/edit"
)

# KIE overloaded — skip remaining retries and go straight to WaveSpeed.
SKIP_KIE_RETRY_PATTERNS = (
    "internal error", "high demand", "too many requests", "rate limit",
    "429", "503", "service is currently unavailable", "e003",
)
# Transient KIE errors — retry KIE a few times, then fall back to WaveSpeed.
RETRIABLE_PATTERNS = (
    "500", "unknown generation error", "timed out", "timeout", "generation failed",
)


def _wavespeed_primary_enabled() -> bool:
    """True iff WaveSpeed should be tried before the legacy KIE chain.

    Off by default (USE_WAVESPEED_PRIMARY=false) — preserves byte-for-byte
    today's behaviour at deploy time. Operator flips to true after smoke-test.
    Also requires WAVESPEED_API_KEY; if missing, control routes to KIE on
    the very first try (no wasted try/except round-trip).
    """
    flag = os.getenv("USE_WAVESPEED_PRIMARY", "false").strip().lower() == "true"
    return flag and bool(os.getenv("WAVESPEED_API_KEY"))


def _wavespeed_headers() -> dict:
    return {
        "Authorization": f"Bearer {os.getenv('WAVESPEED_API_KEY', '')}",
        "Content-Type": "application/json",
    }


def _wavespeed_submit_and_poll(endpoint: str, payload: dict, label: str, max_poll_seconds: int = 1200) -> dict:
    """Submit job to a WaveSpeed endpoint and poll for completion.

    Returns {"taskId": prediction_id, "videoUrl": first_output_url}.
    """
    headers = _wavespeed_headers()
    print(f"      [WaveSpeed {label}] Submitting to {endpoint}")
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    except Exception as e:
        raise RuntimeError(f"WaveSpeed {label} network error: {e}")
    if resp.status_code != 200:
        raise RuntimeError(f"WaveSpeed {label} API error ({resp.status_code}): {resp.text[:300]}")

    api_result = resp.json()
    result_data = api_result.get("data", api_result)
    prediction_id = result_data.get("id")
    if not prediction_id:
        raise RuntimeError(f"WaveSpeed {label} — no prediction ID: {str(api_result)[:300]}")
    status_url = (result_data.get("urls") or {}).get("get") or f"{WAVESPEED_API_URL}/predictions/{prediction_id}/result"
    print(f"      [WaveSpeed {label}] Task: {prediction_id}")

    poll_interval = 10
    for i in range(max_poll_seconds // poll_interval):
        time.sleep(poll_interval)
        try:
            poll_resp = requests.get(status_url, headers=headers, timeout=30)
            poll_data = poll_resp.json()
        except Exception as poll_err:
            print(f"      [WaveSpeed {label}] Poll warning: {poll_err}")
            continue
        inner = poll_data.get("data", poll_data)
        status = (inner.get("status") or "processing").lower()
        if status == "completed":
            outputs = inner.get("outputs") or []
            if outputs:
                first = outputs[0]
                url = first if isinstance(first, str) else (first.get("url") or first.get("output"))
                if url:
                    print(f"      [WaveSpeed {label}] Complete ({(i + 1) * poll_interval}s)")
                    return {"taskId": prediction_id, "videoUrl": url}
        elif status == "failed":
            raise RuntimeError(f"WaveSpeed {label} failed: {inner.get('error', 'unknown')}")

    raise RuntimeError(f"WaveSpeed {label} timed out after {max_poll_seconds}s")


def generate_video_wavespeed(prompt, reference_image_url=None, duration=8, family="veo"):
    """Generate a video via WaveSpeed for Veo / Kling / Seedance families.

    Returns {"taskId": ..., "videoUrl": ...} on success.
    Raises RuntimeError on failure or missing config.
    """
    if not os.getenv("WAVESPEED_API_KEY"):
        raise RuntimeError("WAVESPEED_API_KEY not set")

    if family == "kling":
        if not reference_image_url:
            raise RuntimeError("Kling WaveSpeed requires reference_image_url")
        if not WAVESPEED_KLING_I2V_ENDPOINT:
            raise RuntimeError("WAVESPEED_KLING_I2V_ENDPOINT not configured")
        kling_dur = max(3, min(15, int(duration)))
        payload = {
            "image": reference_image_url,
            "prompt": prompt or "",
            "duration": kling_dur,
            "sound": True,
            "negative_prompt": "no extra limbs, no mutated hands, no extra fingers, no blurry, no distortion",
        }
        return _wavespeed_submit_and_poll(WAVESPEED_KLING_I2V_ENDPOINT, payload, "Kling")

    if family == "seedance":
        if not reference_image_url:
            raise RuntimeError("Seedance WaveSpeed requires reference_image_url")
        if not WAVESPEED_SEEDANCE_ENDPOINT:
            raise RuntimeError("WAVESPEED_SEEDANCE_ENDPOINT not configured")
        # Seedance supports only 5, 10, or 15 seconds — snap to nearest.
        sd_dur = min([5, 10, 15], key=lambda d: abs(d - int(duration)))
        payload = {
            "image": reference_image_url,
            "prompt": prompt or "",
            "duration": sd_dur,
            "aspect_ratio": "9:16",
            "resolution": "720p",
        }
        return _wavespeed_submit_and_poll(WAVESPEED_SEEDANCE_ENDPOINT, payload, "Seedance")

    # Default: Veo (supports text-to-video and image-to-video)
    negative = (
        "no auditory hallucinations, no filler words, no stuttering, "
        "no extra limbs, no mutated hands, no extra fingers"
    )
    if reference_image_url:
        if not WAVESPEED_VEO_I2V_ENDPOINT:
            raise RuntimeError("WAVESPEED_VEO_I2V_ENDPOINT not configured")
        payload = {
            "images": [reference_image_url],
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "generate_audio": True,
            "negative_prompt": negative,
        }
        return _wavespeed_submit_and_poll(WAVESPEED_VEO_I2V_ENDPOINT, payload, "Veo i2v")

    if not WAVESPEED_VEO_T2V_ENDPOINT:
        raise RuntimeError("WAVESPEED_VEO_T2V_ENDPOINT not configured")
    ws_duration = min(8, max(4, int(duration)))
    if ws_duration not in (4, 6, 8):
        ws_duration = 8
    payload = {
        "prompt": prompt,
        "aspect_ratio": "9:16",
        "duration": ws_duration,
        "resolution": "720p",
        "generate_audio": True,
        "negative_prompt": negative,
    }
    return _wavespeed_submit_and_poll(WAVESPEED_VEO_T2V_ENDPOINT, payload, "Veo t2v")


def _wavespeed_primary_video_attempt(
    *, prompt, reference_image_url, family, duration, aspect_ratio, multi_prompt,
    element_ids=None, reference_image_urls=None, reference_video_urls=None,
    model_api=None,
):
    """Try video generation via WaveSpeed first using the new wavespeed_client.

    Returns the same dict shape as `generate_video` ({taskId, videoUrl, lastFrameUrl?})
    on success, or raises so the caller can fall through to the KIE chain.

    Skips kling_elements cases — those need element_id resolution which only
    the router has the context for. Routers that need element_ids will run
    their own WS-primary attempt before calling this function.
    """
    from services import wavespeed_client as ws

    if family == "veo":
        if not reference_image_url:
            # WaveSpeed has no Veo t2v — let the legacy KIE path handle text-only Veo.
            raise ws.WaveSpeedError("WS Veo t2v not supported — falling through to KIE", transient=True)
        ws_dur = min((4, 6, 8), key=lambda d: abs(d - int(duration)))
        data = ws.veo31_fast_i2v(
            image=reference_image_url,
            prompt=prompt or "",
            duration=ws_dur,
            aspect_ratio=aspect_ratio,
        )
    elif family == "seedance":
        sd_dur = max(4, min(15, int(duration)))
        ref_imgs = [u for u in (reference_image_urls or []) if u]
        ref_vids = [u for u in (reference_video_urls or []) if u]
        # Replace KIE-specific @ImageN / @VideoN placeholders with descriptive
        # noun phrases. WaveSpeed Seedance has no concept of named refs; if we
        # leave the literal tokens the model can render them as on-screen text,
        # but if we delete them outright the surrounding sentence becomes a
        # fragment ("@Image1 captures Alexa" → " captures Alexa"). The noun
        # phrase keeps the prompt grammatical without leaking a token.
        ws_prompt = re.sub(r"@Image\d+", "the reference image", prompt or "")
        ws_prompt = re.sub(r"@Video\d+", "the reference video", ws_prompt).strip()
        # Choose between seedance-2.0 (full quality) and seedance-2.0-fast
        use_fast = "fast" in (model_api or "").lower()
        # Multi-image or video-ref → t2v. WaveSpeed i2v is single-image only;
        # routing >1 image through i2v silently drops everything past the first,
        # which loses product/secondary-ref fidelity. KIE's unified Seedance
        # endpoint accepts a reference_image_urls array, so to match KIE quality
        # on WaveSpeed we use t2v for any multi-ref case.
        if ref_vids or len(ref_imgs) > 1:
            t2v_fn = ws.seedance2_fast_t2v if use_fast else ws.seedance2_t2v
            data = t2v_fn(
                prompt=ws_prompt,
                reference_images=ref_imgs or None,
                reference_videos=ref_vids or None,
                duration=sd_dur,
                aspect_ratio=aspect_ratio or "9:16",
            )
        else:
            primary_img = reference_image_url or (ref_imgs[0] if ref_imgs else None)
            if not primary_img:
                raise ws.WaveSpeedError("WS Seedance i2v requires reference image", transient=True)
            i2v_fn = ws.seedance2_fast_i2v if use_fast else ws.seedance2_i2v
            data = i2v_fn(
                image=primary_img,
                prompt=ws_prompt,
                duration=sd_dur,
                aspect_ratio=aspect_ratio,
            )
    else:  # kling
        if not reference_image_url:
            raise ws.WaveSpeedError("WS Kling i2v requires reference image", transient=True)
        kling_dur = max(3, min(15, int(duration)))
        data = ws.kling_v3_std_i2v(
            image=reference_image_url,
            prompt=prompt or "",
            duration=kling_dur,
            multi_prompt=multi_prompt,
            element_ids=list(element_ids) if element_ids else None,
        )

    pred_id = data["id"]
    result = ws.poll_until_done(pred_id, label=f"WS {family}", max_poll_seconds=1200)
    video_url = ws.first_output_url(result)
    return {"taskId": pred_id, "videoUrl": video_url, "lastFrameUrl": None}


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
    aspect_ratio="9:16",
    element_ids=None,
    reference_image_urls=None,
    reference_video_urls=None,
):
    """Try KIE (with short retries) then fall back to WaveSpeed for the same family.

    When USE_WAVESPEED_PRIMARY=true, attempt WaveSpeed first for non-element
    cases. Any exception falls through to the legacy KIE chain unchanged.
    """
    family = _get_model_family(model_api or "")

    # ── WaveSpeed-primary outer layer (additive; no behaviour change when flag off) ──
    # Skip WS-primary when kling_elements are present without pre-resolved element_ids
    # (the router has the context to resolve element_ids and will pass them in).
    # Also skip for the seedance family: KIE (kie.ai) is the canonical provider
    # for Seedance 2.0 / 2.0 Fast. WaveSpeed remains the tail-end fallback.
    can_attempt_ws = (
        _wavespeed_primary_enabled()
        and family != "seedance"
        and (not kling_elements or element_ids)
    )
    if can_attempt_ws:
        try:
            print(f"      [WaveSpeed primary] Attempt for family={family} element_ids={element_ids or '-'}")
            return _wavespeed_primary_video_attempt(
                prompt=prompt,
                reference_image_url=reference_image_url,
                family=family,
                duration=duration,
                aspect_ratio=aspect_ratio,
                multi_prompt=multi_prompt,
                element_ids=element_ids,
                reference_image_urls=reference_image_urls,
                reference_video_urls=reference_video_urls,
                model_api=model_api,
            )
        except Exception as ws_primary_err:
            print(f"      [WaveSpeed primary failed: {ws_primary_err}] — falling through to KIE chain")
            # Fall through to the unchanged legacy chain below.

    # ── Legacy KIE-then-WS-secondary chain (unchanged) ─────────────────
    # Veo: 5-min fast-fail. Kling/Seedance: 10 min (they're inherently slower).
    kie_max_poll = 300 if family == "veo" else 600
    last_error: Exception | None = None

    for attempt in range(max_retries):
        try:
            return generate_video(
                prompt, reference_image_url, model_api,
                first_frame_url, return_last_frame, duration,
                kling_elements=kling_elements,
                multi_prompt=multi_prompt,
                max_poll_seconds=kie_max_poll,
                aspect_ratio=aspect_ratio,
                reference_image_urls=reference_image_urls,
                reference_video_urls=reference_video_urls,
            )
        except RuntimeError as e:
            last_error = e
            err = str(e).lower()
            if any(p in err for p in SKIP_KIE_RETRY_PATTERNS):
                print(f"      [Router] KIE overloaded ({e}) — skipping retries, going to WaveSpeed")
                break
            if not any(p in err for p in RETRIABLE_PATTERNS):
                raise
            if attempt == max_retries - 1:
                break
            wait = (2 ** attempt) * 5
            print(f"      [RETRY] '{e}' - retrying KIE in {wait}s (attempt {attempt + 2}/{max_retries})")
            time.sleep(wait)

    # KIE exhausted — try WaveSpeed once if we have an API key.
    if os.getenv("WAVESPEED_API_KEY"):
        try:
            print(f"      [Router] Falling back to WaveSpeed for family={family}")
            return generate_video_wavespeed(prompt, reference_image_url, duration, family)
        except RuntimeError as ws_err:
            print(f"      [Router] WaveSpeed also failed: {ws_err}")
    if last_error:
        raise last_error
    raise RuntimeError("Video generation failed and no WaveSpeed fallback available")


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
def generate_composite_image(
    scene: dict, influencer: dict, product: dict, seed: int = None,
    aspect_ratio: str = "9:16",
) -> str:
    """Generate a composite image using NanoBanana Pro API.

    `aspect_ratio` must match the downstream video aspect ("9:16" or "16:9")
    so Veo/Kling don't crop or stretch the first frame.
    """
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
            "aspect_ratio": aspect_ratio,
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


def generate_composite_image_wavespeed(scene: dict) -> str:
    """Generate composite image via WaveSpeed NanoBanana Pro."""
    if not os.getenv("WAVESPEED_API_KEY"):
        raise RuntimeError("WAVESPEED_API_KEY not set")
    if not WAVESPEED_NANOBANANA_ENDPOINT:
        raise RuntimeError("WAVESPEED_NANOBANANA_ENDPOINT not configured")

    headers = _wavespeed_headers()
    payload = {
        "prompt": scene.get("nano_banana_prompt") or scene.get("prompt") or "",
        "seed": int(time.time()) % 999999,
    }
    # WaveSpeed NanoBanana edit takes a single "image" field — prefer the reference portrait.
    img = scene.get("reference_image_url") or scene.get("product_image_url")
    if img:
        payload["image"] = img

    print("      [WaveSpeed NanoBanana] Submitting")
    try:
        resp = requests.post(WAVESPEED_NANOBANANA_ENDPOINT, headers=headers, json=payload, timeout=60)
    except Exception as e:
        raise RuntimeError(f"WaveSpeed NanoBanana network error: {e}")
    if resp.status_code != 200:
        raise RuntimeError(f"WaveSpeed NanoBanana API error ({resp.status_code}): {resp.text[:300]}")

    data = (resp.json() or {}).get("data", {})
    prediction_id = data.get("id")
    if not prediction_id:
        raise RuntimeError("WaveSpeed NanoBanana: no prediction ID returned")
    status_url = (data.get("urls") or {}).get("get") or f"{WAVESPEED_API_URL}/predictions/{prediction_id}/result"

    for i in range(60):  # 10 min max
        time.sleep(10)
        try:
            r = requests.get(status_url, headers=headers, timeout=30)
            raw = r.json() or {}
        except Exception as e:
            print(f"      [WaveSpeed NanoBanana] poll err: {e}")
            continue
        inner = raw.get("data", raw)
        status = (inner.get("status") or "processing").lower()
        if status == "completed":
            outputs = inner.get("outputs") or []
            if outputs:
                first = outputs[0]
                url = first if isinstance(first, str) else first.get("url")
                if url:
                    print(f"      [WaveSpeed NanoBanana] Complete ({(i + 1) * 10}s)")
                    return url
        elif status == "failed":
            raise RuntimeError(f"WaveSpeed NanoBanana failed: {inner.get('error', 'unknown')}")
    raise RuntimeError("WaveSpeed NanoBanana timed out")


def _wavespeed_primary_composite_attempt(scene: dict, *, aspect_ratio: str = "9:16") -> str:
    """Composite-image attempt via WaveSpeed nanobanana_edit with full images[] array.

    Sends ALL reference URLs (up to 14) per the WaveSpeed schema, fixing the
    legacy single-`image` hack used in `generate_composite_image_wavespeed`.
    Falls back to nanobanana_t2i when no inputs are present.
    """
    from services import wavespeed_client as ws

    images: list[str] = []
    for key in ("reference_image_url", "product_image_url"):
        val = scene.get(key)
        if val and val not in images:
            images.append(val)
    for url in scene.get("image_input") or []:
        if url and url not in images:
            images.append(url)

    prompt = scene.get("nano_banana_prompt") or scene.get("prompt") or ""

    if images:
        data = ws.nanobanana_edit(
            images=images[:14],
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution="2k",
        )
    else:
        data = ws.nanobanana_t2i(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            resolution="2k",
        )
    pred_id = data["id"]
    result = ws.poll_until_done(pred_id, label="WS NanoBanana", max_poll_seconds=600)
    return ws.first_output_url(result)


def generate_composite_image_with_retry(
    scene: dict, influencer: dict, product: dict, seed: int = None, max_retries: int = 5,
    aspect_ratio: str = "9:16",
) -> str:
    """Try KIE NanoBanana with retry; fall back to WaveSpeed on exhaustion / overload.

    `aspect_ratio` forwards to the NanoBanana input so the composite matches
    the downstream video orientation ("9:16" or "16:9").

    When USE_WAVESPEED_PRIMARY=true, attempt WaveSpeed first with the full
    `images[]` array; any error falls through to the legacy KIE chain.
    """
    # ── WaveSpeed-primary outer layer (additive) ─────────────────────────
    if _wavespeed_primary_enabled():
        try:
            print("      [WaveSpeed primary] NanoBanana composite attempt")
            return _wavespeed_primary_composite_attempt(scene, aspect_ratio=aspect_ratio)
        except Exception as ws_primary_err:
            print(f"      [WaveSpeed primary failed: {ws_primary_err}] — falling through to KIE chain")

    # ── Legacy KIE-then-WS-secondary chain (unchanged) ───────────────────
    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            return generate_composite_image(scene, influencer, product, seed, aspect_ratio=aspect_ratio)
        except RuntimeError as e:
            last_error = e
            err = str(e).lower()
            if any(p in err for p in SKIP_KIE_RETRY_PATTERNS):
                print(f"      [Router] NanoBanana KIE overloaded ({e}) — going to WaveSpeed")
                break
            if "concurrent requests limit" in err or "429" in err:
                if attempt < max_retries - 1:
                    wait = (2 ** attempt) * 5
                    print(f"      NanoBanana rate limited. Retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                break
            if not any(p in err for p in RETRIABLE_PATTERNS):
                raise
            if attempt == max_retries - 1:
                break
            wait = (2 ** attempt) * 5
            time.sleep(wait)

    if os.getenv("WAVESPEED_API_KEY"):
        try:
            print("      [Router] Falling back to WaveSpeed NanoBanana")
            return generate_composite_image_wavespeed(scene)
        except RuntimeError as ws_err:
            print(f"      [Router] WaveSpeed NanoBanana also failed: {ws_err}")
    if last_error:
        raise last_error
    raise RuntimeError("Composite image generation failed")
