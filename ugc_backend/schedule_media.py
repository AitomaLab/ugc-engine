"""Prepare media URLs for Ayrshare / Instagram scheduling.

Ayrshare enforces platform media limits (Instagram images ≤ 8 MB). Studio
images are often high-res PNGs from generation pipelines — we downscale and
JPEG-compress when needed, upload to public Supabase Storage, and hand
Ayrshare a URL it can fetch.
"""

from __future__ import annotations

import io
import uuid
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from ugc_db.db_manager import get_supabase

# Instagram via Ayrshare — https://www.ayrshare.com/docs/media-guidelines
AYRSHARE_MAX_IMAGE_BYTES = 8 * 1024 * 1024
AYRSHARE_TARGET_IMAGE_BYTES = int(7.5 * 1024 * 1024)
_SCHEDULE_BUCKET = "product-images"

_LOSSLESS_EXTENSIONS = (".png", ".webp", ".gif", ".bmp", ".tiff", ".tif")
_LOSSLESS_CONTENT_TYPES = (
    "image/png",
    "image/webp",
    "image/gif",
    "image/bmp",
    "image/tiff",
)
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff", ".tif")

IMAGE_CAMPAIGN_ASSET_TYPES = frozenset({"product_shot", "generated_image"})


def is_image_asset_url(url: str) -> bool:
    """True when ``url`` looks like a static image (not video)."""
    path = urlparse((url or "").split("?")[0]).path.lower()
    return any(path.endswith(ext) for ext in _IMAGE_EXTENSIONS)


def _is_lossless_image(*, raw: bytes, content_type: str = "", media_url: str = "") -> bool:
    ct = (content_type or "").split(";")[0].strip().lower()
    if ct in _LOSSLESS_CONTENT_TYPES:
        return True
    path = urlparse(media_url).path.lower()
    if any(path.endswith(ext) for ext in _LOSSLESS_EXTENSIONS):
        return True
    try:
        with Image.open(io.BytesIO(raw)) as im:
            fmt = (im.format or "").upper()
            if fmt in ("PNG", "WEBP", "GIF", "BMP", "TIFF"):
                return True
    except Exception:
        pass
    return False


def _needs_schedule_reencode(
    raw: bytes,
    *,
    content_type: str = "",
    media_url: str = "",
    target_bytes: int = AYRSHARE_TARGET_IMAGE_BYTES,
) -> bool:
    if len(raw) > target_bytes:
        return True
    return _is_lossless_image(raw=raw, content_type=content_type, media_url=media_url)


def _compress_image_bytes(raw: bytes, *, max_bytes: int = AYRSHARE_TARGET_IMAGE_BYTES) -> bytes:
    """Return JPEG bytes under ``max_bytes`` (best effort)."""
    im = Image.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGB":
        im = im.convert("RGB")

    max_side = 2048
    quality_steps = (88, 82, 76, 70, 64, 58, 52, 46, 40)

    best = raw
    for _attempt in range(12):
        trial = im.copy()
        w, h = trial.size
        if max(w, h) > max_side:
            scale = max_side / float(max(w, h))
            trial = trial.resize((max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS)
        for q in quality_steps:
            buf = io.BytesIO()
            trial.save(buf, format="JPEG", quality=q, optimize=True)
            data = buf.getvalue()
            if len(data) <= max_bytes:
                return data
            if len(data) < len(best):
                best = data
        max_side = int(max_side * 0.82)
        if max_side < 720:
            break

    if len(best) <= max_bytes:
        return best
    raise ValueError(
        f"Could not compress image below {max_bytes // (1024 * 1024)} MB for social scheduling."
    )


def _upload_public_jpeg(user_id: str, jpeg_bytes: bytes) -> str:
    sb = get_supabase()
    key = f"scheduled/{user_id}/{uuid.uuid4()}.jpg"
    sb.storage.from_(_SCHEDULE_BUCKET).upload(
        key,
        jpeg_bytes,
        file_options={"content-type": "image/jpeg", "upsert": "true"},
    )
    return sb.storage.from_(_SCHEDULE_BUCKET).get_public_url(key)


async def prepare_image_url_for_ayrshare(
    media_url: str,
    *,
    user_id: str,
    max_bytes: int = AYRSHARE_MAX_IMAGE_BYTES,
    target_bytes: int = AYRSHARE_TARGET_IMAGE_BYTES,
) -> str:
    """Download ``media_url``; re-encode/compress when needed; re-host publicly."""
    if not media_url:
        raise ValueError("Missing image URL for scheduling.")

    effective_target = min(target_bytes, max_bytes)

    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        resp = await client.get(media_url)
        resp.raise_for_status()
        raw = resp.content
        content_type = resp.headers.get("content-type", "")

    if not _needs_schedule_reencode(
        raw,
        content_type=content_type,
        media_url=media_url,
        target_bytes=effective_target,
    ):
        return media_url

    jpeg = _compress_image_bytes(raw, max_bytes=effective_target)
    public_url = _upload_public_jpeg(user_id, jpeg)
    print(
        f"[schedule_media] Prepared image for Ayrshare: "
        f"{len(raw) / (1024 * 1024):.2f} MB ({content_type or 'unknown'}) → "
        f"{len(jpeg) / (1024 * 1024):.2f} MB JPEG"
    )
    return public_url
