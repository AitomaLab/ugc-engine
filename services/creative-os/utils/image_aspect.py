"""Cover-crop remote images to a target aspect ratio for Veo i2v first frames."""

from __future__ import annotations

import io
import uuid
from typing import Tuple

import requests
from PIL import Image, ImageOps

ASPECT_TOLERANCE = 0.02
DEFAULT_LONG_EDGE = 1280
CROP_BUCKET = "influencer-images"


def _parse_aspect(aspect_ratio: str) -> Tuple[int, int]:
    if aspect_ratio == "16:9":
        return 16, 9
    if aspect_ratio == "1:1":
        return 1, 1
    return 9, 16


def _target_dimensions(aspect_ratio: str, long_edge: int = DEFAULT_LONG_EDGE) -> Tuple[int, int]:
    aw, ah = _parse_aspect(aspect_ratio)
    if aw >= ah:
        w = long_edge
        h = max(2, int(round(long_edge * ah / aw)))
    else:
        h = long_edge
        w = max(2, int(round(long_edge * aw / ah)))
    return w - (w % 2), h - (h % 2)


def _aspect_matches(size: Tuple[int, int], aspect_ratio: str) -> bool:
    w, h = size
    if w <= 0 or h <= 0:
        return False
    aw, ah = _parse_aspect(aspect_ratio)
    target = aw / ah
    current = w / h
    return abs(current - target) / target <= ASPECT_TOLERANCE


def _cover_crop_to_size(im: Image.Image, target_w: int, target_h: int) -> Image.Image:
    src_w, src_h = im.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h
    if src_ratio > target_ratio:
        new_w = int(round(src_h * target_ratio))
        left = (src_w - new_w) // 2
        im = im.crop((left, 0, left + new_w, src_h))
    elif src_ratio < target_ratio:
        new_h = int(round(src_w / target_ratio))
        top = (src_h - new_h) // 2
        im = im.crop((0, top, src_w, top + new_h))
    return im.resize((target_w, target_h), Image.LANCZOS)


def _crop_bytes(raw: bytes, aspect_ratio: str, long_edge: int = DEFAULT_LONG_EDGE) -> bytes:
    im = Image.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGB":
        im = im.convert("RGB")
    target_w, target_h = _target_dimensions(aspect_ratio, long_edge)
    if _aspect_matches(im.size, aspect_ratio):
        if im.size != (target_w, target_h):
            im = im.resize((target_w, target_h), Image.LANCZOS)
    else:
        im = _cover_crop_to_size(im, target_w, target_h)
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


def _upload_jpeg(body: bytes, *, prefix: str = "aspect_crop") -> str:
    import os
    from supabase import create_client

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not service_key:
        raise RuntimeError("Supabase credentials missing for aspect crop upload")
    sb = create_client(supabase_url, service_key)
    filename = f"{prefix}/{uuid.uuid4().hex}.jpg"
    sb.storage.from_(CROP_BUCKET).upload(
        filename,
        body,
        file_options={"content-type": "image/jpeg", "upsert": "true"},
    )
    return sb.storage.from_(CROP_BUCKET).get_public_url(filename)


def crop_image_url_to_aspect(
    image_url: str,
    aspect_ratio: str = "9:16",
    *,
    long_edge: int = DEFAULT_LONG_EDGE,
) -> str:
    """Download, center cover-crop to aspect, rehost on Supabase. Returns original URL on failure."""
    if not image_url or not image_url.startswith("http"):
        return image_url
    try:
        resp = requests.get(image_url, timeout=120)
        resp.raise_for_status()
        raw = resp.content
        if not raw:
            return image_url
        im_probe = Image.open(io.BytesIO(raw))
        im_probe = ImageOps.exif_transpose(im_probe)
        if _aspect_matches(im_probe.size, aspect_ratio):
            tw, th = _target_dimensions(aspect_ratio, long_edge)
            if abs(im_probe.size[0] - tw) <= 4 and abs(im_probe.size[1] - th) <= 4:
                print(f"[image_aspect] skip crop — already {aspect_ratio} ({im_probe.size[0]}x{im_probe.size[1]})")
                return image_url
        cropped = _crop_bytes(raw, aspect_ratio, long_edge)
        url = _upload_jpeg(cropped)
        print(f"[image_aspect] cover-cropped to {aspect_ratio} → {url[:80]}...")
        return url
    except Exception as e:
        print(f"[image_aspect] crop failed (using original): {e}")
        return image_url


async def crop_and_rehost_for_aspect(
    image_url: str,
    aspect_ratio: str = "9:16",
    *,
    long_edge: int = DEFAULT_LONG_EDGE,
) -> str:
    """Async wrapper for crop_image_url_to_aspect (runs PIL/requests in a thread)."""
    import asyncio

    return await asyncio.to_thread(
        crop_image_url_to_aspect,
        image_url,
        aspect_ratio,
        long_edge=long_edge,
    )
