"""
Fal AI async client — cinematic-ads workflow.

Wraps the official `fal-client` Python SDK so we don't reinvent the routing
quirks (raw `queue.fal.run` requests returned 404 for Seedance because the
internal Fal router needs SDK-driven path construction).

Public API:

    upload_to_fal_storage(data, *, content_type, file_name) -> str
    upload_url_to_fal_storage(url, *, content_type, file_name=None) -> str
        Upload bytes / re-upload a remote URL to Fal storage. Returns a public
        Fal CDN URL safe to pass to any Fal model.

    generate_storyboard(prompt, image_urls, width=2560, height=1792) -> dict
        GPT Image 2 storyboard sheet. Returns {"url": str, "raw": dict}.

    animate_storyboard_seedance(prompt, image_urls, duration="15",
                                resolution="720p", aspect_ratio="16:9",
                                generate_audio=True) -> dict
        Seedance 2.0 Pro reference-to-video. Returns {"url": str, "seed": int|None, "raw": dict}.

All paid calls raise FalError with the exact `msg` field on rejection so the
agent tool surfaces it verbatim (skill Gate 2: never silently retry).
"""
from __future__ import annotations

import os
from typing import Optional

import fal_client
import httpx


# Model IDs — official `fal-ai/...` namespacing for the SDK. The SDK builds
# the queue URLs internally so we don't have to wonder if it's `/openai/...`
# vs `/fal-ai/openai/...`.
# Fal moved gpt-image-2 — `fal-ai/openai/gpt-image-2/edit` now 404s with
# "Application 'openai' not found". The flat path mirrors `fal-ai/gpt-image-1/edit`.
STORYBOARD_MODEL = "fal-ai/gpt-image-2/edit"
# Canonical model id per the official Fal docs
# (https://fal.ai/models/bytedance/seedance-2.0/reference-to-video).
# Fal canonicalizes this to `fal-ai/seedance-2/...` for the dashboard / billing
# display but the docs-canonical path is the source of truth and is what the
# fal-client SDK examples use.
SEEDANCE_MODEL = "bytedance/seedance-2.0/reference-to-video"


class FalError(Exception):
    """Raised on a Fal failure. `msg` carries the exact response field."""

    def __init__(self, message: str, *, raw: Optional[dict] = None):
        super().__init__(message)
        self.raw = raw or {}


def _api_key() -> str:
    key = os.getenv("FAL_KEY")
    if not key:
        raise FalError("FAL_KEY not set in environment")
    return key


def _ensure_fal_env() -> None:
    """fal_client picks up FAL_KEY from env automatically; just verify it's set."""
    _api_key()


# ── Storage upload ────────────────────────────────────────────────────
async def upload_to_fal_storage(
    data: bytes,
    *,
    content_type: str,
    file_name: str,
) -> str:
    """Upload raw bytes to Fal storage. Returns the public file_url."""
    _ensure_fal_env()
    try:
        # fal_client.upload_async takes (data, content_type, file_name)
        return await fal_client.upload_async(data, content_type, file_name)
    except Exception as e:
        raise FalError(f"Fal storage upload failed: {e}")


async def upload_url_to_fal_storage(url: str, *, content_type: str, file_name: Optional[str] = None) -> str:
    """Fetch a remote URL and re-upload to Fal storage. Returns the file_url."""
    _ensure_fal_env()
    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.get(url)
        if resp.status_code != 200:
            raise FalError(f"failed to fetch {url} for re-upload ({resp.status_code})")
        data = resp.content
    name = file_name or url.rsplit("/", 1)[-1].split("?")[0] or "asset.bin"
    return await upload_to_fal_storage(data, content_type=content_type, file_name=name)


# ── Storyboard (GPT Image 2) ──────────────────────────────────────────
_STORYBOARD_SHEET_SIZE = {
    "16:9": (2560, 1792),
    "4:3":  (2048, 1536),
    "9:16": (1792, 2560),
}


async def generate_storyboard(
    *,
    prompt: str,
    image_urls: list[str],
    width: Optional[int] = None,
    height: Optional[int] = None,
    aspect_ratio: str = "16:9",
) -> dict:
    """Generate a single storyboard sheet via GPT Image 2 /edit.

    Returns {"url": <png url>, "raw": <full Fal response>}.
    """
    _ensure_fal_env()
    if not image_urls:
        raise FalError("generate_storyboard requires at least one reference image_url")
    # Resolve sheet dimensions from aspect_ratio unless caller passed explicit
    # width/height. This keeps the storyboard PNG matched to the final ad's
    # aspect so panels render at the right proportion.
    if width is None or height is None:
        w, h = _STORYBOARD_SHEET_SIZE.get(aspect_ratio, _STORYBOARD_SHEET_SIZE["16:9"])
        width = width or w
        height = height or h
    arguments = {
        "prompt": prompt,
        "image_urls": image_urls,
        "image_size": {"width": width, "height": height},
        "quality": "high",
        "num_images": 1,
        "output_format": "png",
    }
    print(f"[fal] storyboard subscribe model={STORYBOARD_MODEL} ar={aspect_ratio} size={width}x{height} image_count={len(image_urls)}")
    try:
        result = await fal_client.subscribe_async(
            STORYBOARD_MODEL,
            arguments=arguments,
            with_logs=False,
        )
    except Exception as e:
        raise FalError(f"Fal storyboard call failed: {e}", raw={"exception": str(e)})

    images = (result or {}).get("images") or []
    if not images:
        raise FalError(f"Fal storyboard returned no images: {result}", raw=result or {})
    url = images[0].get("url")
    if not url:
        raise FalError(f"Fal storyboard image missing url: {images[0]}", raw=result or {})
    print(f"[fal] storyboard OK url={url[:80]}...")
    return {"url": url, "raw": result}


# ── Seedance 2.0 Pro animation ────────────────────────────────────────
async def animate_storyboard_seedance(
    *,
    prompt: str,
    image_urls: list[str],
    duration: str = "15",
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
) -> dict:
    """Animate with Seedance 2.0 Pro ref-to-video.

    `image_urls` must follow the skill's two-reference rule:
      [storyboard_url (@Image1), product_url (@Image2)]  — for storyboard-driven ads
      [product_url (@Image1)]                           — for product-macro-only
    Returns {"url": <mp4 url>, "seed": int|None, "raw": <full Fal response>}.
    """
    _ensure_fal_env()
    if not image_urls:
        raise FalError("animate_storyboard_seedance requires at least one image_url")
    arguments = {
        "prompt": prompt,
        "image_urls": image_urls,
        "resolution": resolution,
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
        "generate_audio": generate_audio,
    }
    print(f"[fal] seedance subscribe model={SEEDANCE_MODEL} duration={duration} res={resolution} image_count={len(image_urls)}")
    try:
        result = await fal_client.subscribe_async(
            SEEDANCE_MODEL,
            arguments=arguments,
            with_logs=False,
        )
    except Exception as e:
        _err_str = str(e)
        # Detect Fal's downstream-service-unavailable response — translate to a
        # user-friendly message instead of dumping the raw stacktrace into chat.
        if "downstream_service_unavailable" in _err_str or "Downstream service unavailable" in _err_str:
            print(f"[fal] seedance FAILED: downstream service unavailable (Fal-side Seedance outage)")
            raise FalError(
                "Seedance is temporarily unavailable on Fal (downstream service outage on their side, not ours). "
                "Check https://status.fal.ai and retry in 15-60 min.",
                raw={"exception": _err_str, "kind": "fal_downstream_unavailable"},
            )
        print(f"[fal] seedance FAILED: {type(e).__name__}: {_err_str[:300]}")
        raise FalError(f"Fal seedance call failed: {e}", raw={"exception": _err_str})

    video = (result or {}).get("video") or {}
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise FalError(f"Fal seedance returned no video url: {result}", raw=result or {})
    seed = (result or {}).get("seed")
    print(f"[fal] seedance OK url={url[:80]}... seed={seed}")
    return {"url": url, "seed": seed, "raw": result}
