"""Ensure an image URL is in a Kling-compatible format (jpeg/jpg/png).

Kling 3.0 rejects webp/heic/avif/etc. This helper converts anything non-JPG/PNG
to a cached PNG in Supabase Storage and returns the new URL. No-ops for URLs
that are already compatible.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
from urllib.parse import urlparse

import httpx
from PIL import Image

from ugc_db.db_manager import get_supabase

_KLING_OK_EXTS = {".jpg", ".jpeg", ".png"}
_KLING_OK_CT = {"image/jpeg", "image/jpg", "image/png"}
_CACHE_BUCKET = "user-uploads"
_CACHE_PREFIX = "kling_cache/v2"


def _url_ext(url: str) -> str:
    path = urlparse(url).path.lower()
    dot = path.rfind(".")
    return path[dot:] if dot >= 0 else ""


async def ensure_kling_compatible(url: str | None) -> str | None:
    """Return a URL pointing at a jpeg/png image. If `url` already qualifies
    by extension, return as-is. Otherwise download, convert to PNG, upload to
    the cache bucket, and return the cached URL. Safe to call with None."""
    if not url:
        return url
    ext = _url_ext(url)
    if ext in _KLING_OK_EXTS:
        return url

    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:32]
    cached_path = f"{_CACHE_PREFIX}/{digest}.png"
    sb = get_supabase()

    public = sb.storage.from_(_CACHE_BUCKET).get_public_url(cached_path)
    try:
        async with httpx.AsyncClient(timeout=5.0) as http:
            head = await http.head(public)
            if head.status_code == 200 and head.headers.get("content-type", "").startswith("image/"):
                return public
    except Exception:
        pass

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
        resp = await http.get(url)
        resp.raise_for_status()
        img_bytes = resp.content
        ct = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()

    if ct in _KLING_OK_CT and ext in _KLING_OK_EXTS:
        return url

    def _convert(raw: bytes) -> bytes:
        im = Image.open(io.BytesIO(raw))
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            rgba = im.convert("RGBA")
            bg.paste(rgba, mask=rgba.split()[-1])
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        out = io.BytesIO()
        im.save(out, format="PNG", optimize=True)
        return out.getvalue()

    png_bytes = await asyncio.to_thread(_convert, img_bytes)

    sb.storage.from_(_CACHE_BUCKET).upload(
        cached_path, png_bytes,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    new_url = sb.storage.from_(_CACHE_BUCKET).get_public_url(cached_path)
    print(f"[Kling Convert] {url[:60]}... -> {new_url[:60]}...")
    return new_url
