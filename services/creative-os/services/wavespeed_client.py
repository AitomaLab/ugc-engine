"""WaveSpeed API client — primary marketplace for image/video generation.

Single source of truth for every WaveSpeed call. Per-model wrappers map our
internal request shape to the WaveSpeed payload, validate against the documented
schema, and return either a prediction_id (async path with webhook) or a
completed result dict (sync polling path).

Auth: Authorization: Bearer ${WAVESPEED_API_KEY}
Base URL: https://api.wavespeed.ai/api/v3
Async lifecycle: POST -> {data:{id, urls:{get}}} -> GET urls.get OR webhook POST
Response envelope: {code, message, data: {...}} (we unwrap to data)
"""
from __future__ import annotations

import os
import time
from typing import Any, Iterable, Sequence
from urllib.parse import urlencode

import requests

WAVESPEED_BASE_URL = os.getenv("WAVESPEED_BASE_URL", "https://api.wavespeed.ai/api/v3")
DEFAULT_POLL_INTERVAL = 5
DEFAULT_MAX_POLL_SECONDS = 1200  # 20 min — matches WaveSpeed webhook ack window


class WaveSpeedError(RuntimeError):
    """Any WaveSpeed call failure. .transient signals safe-to-fall-back."""

    def __init__(self, message: str, *, transient: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.transient = transient
        self.status_code = status_code


def _api_key() -> str:
    key = os.getenv("WAVESPEED_API_KEY", "")
    if not key:
        raise WaveSpeedError("WAVESPEED_API_KEY not set", transient=False)
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }


def _classify_status(code: int) -> bool:
    """True if a status code is transient (worth falling back / retrying)."""
    return code == 429 or code >= 500


def _unwrap(api_result: Any) -> dict:
    """WaveSpeed wraps responses as {code, message, data}. Some endpoints return
    the raw data inline. Handle both."""
    if isinstance(api_result, dict) and "data" in api_result and isinstance(api_result["data"], dict):
        return api_result["data"]
    return api_result if isinstance(api_result, dict) else {}


def default_webhook_url() -> str | None:
    """Compose the public webhook URL from WAVESPEED_WEBHOOK_BASE if set."""
    base = os.getenv("WAVESPEED_WEBHOOK_BASE", "").strip()
    if not base:
        return None
    return f"{base.rstrip('/')}/creative-os/wavespeed/webhook"


def _build_url(endpoint_path: str, *, webhook: str | None = None) -> str:
    """Compose the full POST URL, appending ?webhook=... when provided.

    If `webhook` is None, falls back to WAVESPEED_WEBHOOK_BASE if set so the
    handler in routers/wavespeed_webhook.py can short-circuit pollers.
    """
    if endpoint_path.startswith("http"):
        url = endpoint_path
    else:
        url = f"{WAVESPEED_BASE_URL}/{endpoint_path.lstrip('/')}"
    effective = webhook if webhook is not None else default_webhook_url()
    if effective:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}{urlencode({'webhook': effective})}"
    return url


def submit(endpoint_path: str, payload: dict, *, webhook: str | None = None, label: str = "") -> dict:
    """POST a payload to WaveSpeed, return the unwrapped data dict.

    Caller decides whether to poll (.poll_until_done) or wait for webhook callback.
    """
    url = _build_url(endpoint_path, webhook=webhook)
    tag = f"[WaveSpeed {label or endpoint_path}]"
    print(f"      {tag} POST {url}")
    try:
        resp = requests.post(url, headers=_headers(), json=payload, timeout=60)
    except requests.RequestException as exc:
        raise WaveSpeedError(f"{tag} network error: {exc}", transient=True) from exc
    if resp.status_code != 200:
        raise WaveSpeedError(
            f"{tag} API error ({resp.status_code}): {resp.text[:300]}",
            transient=_classify_status(resp.status_code),
            status_code=resp.status_code,
        )
    data = _unwrap(resp.json())
    if not data.get("id"):
        raise WaveSpeedError(f"{tag} response missing prediction id: {str(resp.json())[:300]}", transient=True)
    print(f"      {tag} prediction_id={data['id']}")
    return data


def poll_until_done(prediction_id_or_url: str, *, label: str = "", max_poll_seconds: int = DEFAULT_MAX_POLL_SECONDS) -> dict:
    """Poll a prediction's result endpoint until status is completed/failed.

    Accepts either a bare prediction id or the full urls.get URL.
    Returns the inner data dict on success. Raises WaveSpeedError on failure/timeout.
    """
    if prediction_id_or_url.startswith("http"):
        status_url = prediction_id_or_url
    else:
        status_url = f"{WAVESPEED_BASE_URL}/predictions/{prediction_id_or_url}/result"
    tag = f"[WaveSpeed {label or 'poll'}]"
    end_at = time.time() + max_poll_seconds
    while time.time() < end_at:
        time.sleep(DEFAULT_POLL_INTERVAL)
        try:
            resp = requests.get(status_url, headers=_headers(), timeout=30)
        except requests.RequestException as exc:
            print(f"      {tag} poll warn: {exc}")
            continue
        if resp.status_code != 200:
            print(f"      {tag} poll status {resp.status_code}: {resp.text[:200]}")
            continue
        inner = _unwrap(resp.json())
        status = (inner.get("status") or "processing").lower()
        if status == "completed":
            print(f"      {tag} completed")
            return inner
        if status == "failed":
            err = inner.get("error") or "unknown"
            # Backend hiccup: prediction marked failed before inference started
            # (executionTime=0 + generic "try again later"). Caller can retry the
            # whole submission once. Distinct from a real model failure where
            # executionTime > 0 and the error is specific.
            exec_time = int(inner.get("executionTime") or 0)
            err_lc = err.lower()
            is_transient = exec_time == 0 and (
                "something went wrong" in err_lc or "try again later" in err_lc
            )
            raise WaveSpeedError(f"{tag} failed: {err}", transient=is_transient)
    raise WaveSpeedError(f"{tag} timed out after {max_poll_seconds}s", transient=True)


def first_output_url(result: dict) -> str:
    """Extract the first output URL from a completed prediction.

    WaveSpeed outputs are sometimes [str, str, ...] (most models) and sometimes
    [{"url": "..."}, ...] (Seedance fast). Handle both shapes.
    """
    outputs = result.get("outputs") or []
    if not outputs:
        raise WaveSpeedError("Completed prediction has no outputs", transient=False)
    first = outputs[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        url = first.get("url") or first.get("output")
        if url:
            return url
    raise WaveSpeedError(f"Unrecognised output shape: {first!r}", transient=False)


# ---------------------------------------------------------------------------
# Aspect-ratio + duration helpers
# ---------------------------------------------------------------------------

VEO_DURATIONS = (4, 6, 8)
KLING_DURATIONS = tuple(range(3, 16))  # 3..15
SEEDANCE_DURATIONS = tuple(range(4, 16))  # 4..15
NANOBANANA_RESOLUTIONS = ("1k", "2k", "4k")
VEO_RESOLUTIONS = ("720p", "1080p", "4k")
VEO_ASPECTS = ("16:9", "9:16")
KLING_ASPECTS = ("16:9", "9:16", "1:1")
SEEDANCE_ASPECTS = ("16:9", "9:16", "4:3", "3:4", "1:1", "21:9")
NANOBANANA_ASPECTS = ("1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9")


def _clamp_to(value: int, options: Sequence[int]) -> int:
    return min(options, key=lambda x: abs(x - int(value)))


def _coerce_aspect(value: str | None, allowed: Sequence[str], default: str) -> str:
    if not value:
        return default
    return value if value in allowed else default


# ---------------------------------------------------------------------------
# Kling 3.0 Standard
# ---------------------------------------------------------------------------

def kling_v3_std_i2v(
    *,
    image: str,
    prompt: str | None = None,
    duration: int = 5,
    element_ids: Iterable[str] | None = None,
    multi_prompt: list[dict] | None = None,
    end_image: str | None = None,
    sound: bool = True,
    cfg_scale: float = 0.5,
    negative_prompt: str | None = None,
    shot_type: str = "customize",
    webhook: str | None = None,
) -> dict:
    """Submit a Kling 3.0 Std image-to-video job.

    Either prompt or multi_prompt must be provided (not both).
    element_list[].element_id values must come from kling_register_element.
    """
    if not image:
        raise WaveSpeedError("kling_v3_std_i2v: image is required", transient=False)
    if not prompt and not multi_prompt:
        raise WaveSpeedError("kling_v3_std_i2v: prompt or multi_prompt required", transient=False)
    if prompt and multi_prompt:
        raise WaveSpeedError("kling_v3_std_i2v: prompt and multi_prompt are mutually exclusive", transient=False)
    payload: dict = {
        "image": image,
        "duration": _clamp_to(duration, KLING_DURATIONS),
        "sound": bool(sound),
        "cfg_scale": float(cfg_scale),
        "shot_type": shot_type if shot_type in ("customize", "intelligent") else "customize",
    }
    if prompt:
        payload["prompt"] = prompt
    if multi_prompt:
        payload["multi_prompt"] = multi_prompt
    if end_image:
        payload["end_image"] = end_image
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    ids = [eid for eid in (element_ids or []) if eid]
    if ids:
        payload["element_list"] = [{"element_id": eid} for eid in ids[:3]]  # WaveSpeed maxItems=3
    return submit("kwaivgi/kling-v3.0-std/image-to-video", payload, webhook=webhook, label="Kling i2v")


def kling_v3_std_t2v(
    *,
    prompt: str | None = None,
    multi_prompt: list[dict] | None = None,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    element_ids: Iterable[str] | None = None,
    sound: bool = True,
    cfg_scale: float = 0.5,
    negative_prompt: str | None = None,
    shot_type: str = "customize",
    webhook: str | None = None,
) -> dict:
    if not prompt and not multi_prompt:
        raise WaveSpeedError("kling_v3_std_t2v: prompt or multi_prompt required", transient=False)
    if prompt and multi_prompt:
        raise WaveSpeedError("kling_v3_std_t2v: prompt and multi_prompt are mutually exclusive", transient=False)
    payload: dict = {
        "duration": _clamp_to(duration, KLING_DURATIONS),
        "aspect_ratio": _coerce_aspect(aspect_ratio, KLING_ASPECTS, "9:16"),
        "sound": bool(sound),
        "cfg_scale": float(cfg_scale),
        "shot_type": shot_type if shot_type in ("customize", "intelligent") else "customize",
    }
    if prompt:
        payload["prompt"] = prompt
    if multi_prompt:
        payload["multi_prompt"] = multi_prompt
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    ids = [eid for eid in (element_ids or []) if eid]
    if ids:
        payload["element_list"] = [{"element_id": eid} for eid in ids[:3]]
    return submit("kwaivgi/kling-v3.0-std/text-to-video", payload, webhook=webhook, label="Kling t2v")


def kling_register_element(
    *,
    name: str,
    description: str,
    image: str,
    refer_list: Sequence[str],
    voice_id: str | None = None,
) -> dict:
    """Register a Kling element. Synchronous: poll the result for element_id.

    Cost: $0.01 per element. Cache element_id by image content hash to avoid
    re-registering — see services/kling_elements.py.
    """
    if not name or len(name) > 20:
        raise WaveSpeedError("kling_register_element: name required, max 20 chars", transient=False)
    if not description or len(description) > 100:
        raise WaveSpeedError("kling_register_element: description required, max 100 chars", transient=False)
    if not image:
        raise WaveSpeedError("kling_register_element: image required", transient=False)
    refers = [u for u in refer_list if u][:3]
    if not refers:
        # WaveSpeed requires minItems=1 for element_refer_list; fall back to the primary image.
        refers = [image]
    payload: dict = {
        "name": name[:20],
        "description": description[:100],
        "image": image,
        "element_refer_list": refers,
    }
    if voice_id:
        payload["voice_id"] = voice_id
    submitted = submit("kwaivgi/kling-elements", payload, label="Kling element register")
    # Element registration completes quickly; poll synchronously.
    result = poll_until_done(submitted["id"], label="Kling element register", max_poll_seconds=300)
    return result  # caller pulls element_id (see kling_elements.py)


# ---------------------------------------------------------------------------
# Veo 3.1 Fast
# ---------------------------------------------------------------------------

def veo31_fast_i2v(
    *,
    image: str,
    prompt: str,
    duration: int = 8,
    aspect_ratio: str = "9:16",
    resolution: str = "1080p",
    last_image: str | None = None,
    generate_audio: bool = True,
    negative_prompt: str | None = None,
    seed: int | None = None,
    webhook: str | None = None,
) -> dict:
    if not image:
        raise WaveSpeedError("veo31_fast_i2v: image is required", transient=False)
    if not prompt:
        raise WaveSpeedError("veo31_fast_i2v: prompt is required", transient=False)
    payload: dict = {
        "image": image,
        "prompt": prompt,
        "aspect_ratio": _coerce_aspect(aspect_ratio, VEO_ASPECTS, "9:16"),
        "duration": _clamp_to(duration, VEO_DURATIONS),
        "resolution": resolution if resolution in VEO_RESOLUTIONS else "1080p",
        "generate_audio": bool(generate_audio),
    }
    if last_image:
        payload["last_image"] = last_image
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = int(seed)
    return submit("google/veo3.1-fast/image-to-video", payload, webhook=webhook, label="Veo i2v")


def veo31_fast_extend(
    *,
    video: str,
    prompt: str | None = None,
    resolution: str = "1080p",
    negative_prompt: str | None = None,
    seed: int | None = None,
    webhook: str | None = None,
) -> dict:
    if not video:
        raise WaveSpeedError("veo31_fast_extend: video is required", transient=False)
    payload: dict = {
        "video": video,
        "resolution": resolution if resolution in ("720p", "1080p") else "1080p",
    }
    if prompt:
        payload["prompt"] = prompt
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if seed is not None:
        payload["seed"] = int(seed)
    return submit("google/veo3.1-fast/video-extend", payload, webhook=webhook, label="Veo extend")


# ---------------------------------------------------------------------------
# Seedance 2.0 Fast
# ---------------------------------------------------------------------------

def seedance2_fast_i2v(
    *,
    image: str,
    prompt: str,
    duration: int = 5,
    aspect_ratio: str | None = None,
    resolution: str = "720p",
    last_image: str | None = None,
    enable_web_search: bool = False,
    webhook: str | None = None,
) -> dict:
    if not image:
        raise WaveSpeedError("seedance2_fast_i2v: image is required", transient=False)
    if not prompt:
        raise WaveSpeedError("seedance2_fast_i2v: prompt is required", transient=False)
    dur = _clamp_to(duration, SEEDANCE_DURATIONS)
    payload: dict = {
        "image": image,
        "prompt": prompt,
        "duration": dur,
        "resolution": resolution if resolution in ("480p", "720p", "1080p") else "720p",
    }
    if aspect_ratio:
        payload["aspect_ratio"] = _coerce_aspect(aspect_ratio, SEEDANCE_ASPECTS, "9:16")
    if last_image:
        payload["last_image"] = last_image
    if enable_web_search:
        payload["enable_web_search"] = True
    return submit("bytedance/seedance-2.0-fast/image-to-video", payload, webhook=webhook, label="Seedance i2v")


def seedance2_fast_t2v(
    *,
    prompt: str,
    reference_images: Sequence[str] | None = None,
    reference_videos: Sequence[str] | None = None,
    reference_audios: Sequence[str] | None = None,
    duration: int = 5,
    aspect_ratio: str = "9:16",
    resolution: str = "720p",
    enable_web_search: bool = False,
    webhook: str | None = None,
) -> dict:
    if not prompt:
        raise WaveSpeedError("seedance2_fast_t2v: prompt is required", transient=False)
    payload: dict = {
        "prompt": prompt,
        "duration": _clamp_to(duration, SEEDANCE_DURATIONS),
        "aspect_ratio": _coerce_aspect(aspect_ratio, SEEDANCE_ASPECTS, "9:16"),
        "resolution": resolution if resolution in ("480p", "720p", "1080p") else "720p",
    }
    if reference_images:
        payload["reference_images"] = list(reference_images)[:9]
    if reference_videos:
        payload["reference_videos"] = list(reference_videos)[:3]
    if reference_audios:
        payload["reference_audios"] = list(reference_audios)[:3]
    if enable_web_search:
        payload["enable_web_search"] = True
    return submit("bytedance/seedance-2.0-fast/text-to-video", payload, webhook=webhook, label="Seedance t2v")


# ---------------------------------------------------------------------------
# NanoBanana Pro (Gemini 3.0 Pro Image)
# ---------------------------------------------------------------------------

def nanobanana_edit(
    *,
    images: Sequence[str],
    prompt: str,
    aspect_ratio: str | None = None,
    resolution: str = "2k",
    output_format: str = "png",
    webhook: str | None = None,
) -> dict:
    image_list = [u for u in (images or []) if u][:14]
    if not image_list:
        raise WaveSpeedError("nanobanana_edit: at least one image is required", transient=False)
    if not prompt:
        raise WaveSpeedError("nanobanana_edit: prompt is required", transient=False)
    payload: dict = {
        "images": image_list,
        "prompt": prompt,
        "resolution": resolution if resolution in NANOBANANA_RESOLUTIONS else "2k",
        "output_format": output_format if output_format in ("png", "jpeg") else "png",
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio if aspect_ratio in NANOBANANA_ASPECTS else "1:1"
    return submit("google/nano-banana-pro/edit", payload, webhook=webhook, label="NanoBanana edit")


def nanobanana_edit_multi(
    *,
    images: Sequence[str],
    prompt: str,
    aspect_ratio: str | None = None,
    output_format: str = "png",
    webhook: str | None = None,
) -> dict:
    """Edit-multi variant: returns 2 alternative outputs from one prompt."""
    image_list = [u for u in (images or []) if u][:14]
    if not image_list:
        raise WaveSpeedError("nanobanana_edit_multi: at least one image is required", transient=False)
    if not prompt:
        raise WaveSpeedError("nanobanana_edit_multi: prompt is required", transient=False)
    payload: dict = {
        "images": image_list,
        "prompt": prompt,
        "num_images": 2,
        "output_format": output_format if output_format in ("png", "jpeg") else "png",
    }
    if aspect_ratio:
        # edit-multi only allows 3:2/2:3/3:4/4:3
        ratio = aspect_ratio if aspect_ratio in ("3:2", "2:3", "3:4", "4:3") else "3:2"
        payload["aspect_ratio"] = ratio
    return submit("google/nano-banana-pro/edit-multi", payload, webhook=webhook, label="NanoBanana edit-multi")


def nanobanana_t2i(
    *,
    prompt: str,
    aspect_ratio: str | None = None,
    resolution: str = "2k",
    output_format: str = "png",
    webhook: str | None = None,
) -> dict:
    if not prompt:
        raise WaveSpeedError("nanobanana_t2i: prompt is required", transient=False)
    payload: dict = {
        "prompt": prompt,
        "resolution": resolution if resolution in NANOBANANA_RESOLUTIONS else "2k",
        "output_format": output_format if output_format in ("png", "jpeg") else "png",
    }
    if aspect_ratio:
        payload["aspect_ratio"] = aspect_ratio if aspect_ratio in NANOBANANA_ASPECTS else "1:1"
    return submit("google/nano-banana-pro/text-to-image", payload, webhook=webhook, label="NanoBanana t2i")


# ---------------------------------------------------------------------------
# Convenience: submit-and-wait for synchronous callers
# ---------------------------------------------------------------------------

def submit_and_wait(submit_fn, *, label: str, max_poll_seconds: int = DEFAULT_MAX_POLL_SECONDS, **kwargs) -> dict:
    """Helper for callers that don't use webhooks: submit then poll to completion.

    Usage:
        result = submit_and_wait(veo31_fast_i2v, label="Veo i2v",
                                 image=url, prompt=p, duration=8)
        video_url = first_output_url(result)
    """
    submitted = submit_fn(**kwargs)
    return poll_until_done(submitted["id"], label=label, max_poll_seconds=max_poll_seconds)
