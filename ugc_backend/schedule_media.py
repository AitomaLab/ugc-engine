"""Prepare media URLs for Ayrshare / Instagram scheduling.

Ayrshare enforces platform media limits (Instagram images ≤ 8 MB). Studio
images are often high-res PNGs from generation pipelines — we downscale and
JPEG-compress when needed, upload to public Supabase Storage, and hand
Ayrshare a URL it can fetch.
"""

from __future__ import annotations

import io
import uuid
from typing import Optional

import httpx
from PIL import Image, ImageOps

from ugc_db.db_manager import get_supabase

# Instagram via Ayrshare — https://www.ayrshare.com/docs/media-guidelines
AYRSHARE_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_SCHEDULE_BUCKET = "product-images"


def _compress_image_bytes(raw: bytes, *, max_bytes: int = AYRSHARE_MAX_IMAGE_BYTES) -> bytes:
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
) -> str:
    """Download ``media_url``; if over ``max_bytes``, compress + re-host publicly."""
    if not media_url:
        raise ValueError("Missing image URL for scheduling.")

    async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
        head = await client.head(media_url)
        length: Optional[int] = None
        if head.status_code < 400:
            try:
                length = int(head.headers.get("content-length") or 0) or None
            except ValueError:
                length = None
        if length is not None and length <= max_bytes:
            return media_url

        resp = await client.get(media_url)
        resp.raise_for_status()
        raw = resp.content

    if len(raw) <= max_bytes:
        return media_url

    jpeg = _compress_image_bytes(raw, max_bytes=max_bytes)
    public_url = _upload_public_jpeg(user_id, jpeg)
    print(
        f"[schedule_media] Compressed {len(raw) / (1024 * 1024):.2f} MB → "
        f"{len(jpeg) / (1024 * 1024):.2f} MB for Ayrshare"
    )
    return public_url
