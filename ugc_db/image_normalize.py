"""Normalize any user-provided image to an opaque PNG on a white background.

Fixes transparency (kills the 'checkerboard' artifact Kling paints into
alpha), strips EXIF (including the orientation tag so phone photos don't
render rotated), and coerces the format to PNG so every downstream
consumer can trust what it gets from Supabase Storage.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps


def normalize_image_bytes(raw: bytes) -> bytes:
    """Take any image bytes, return opaque PNG bytes."""
    im = Image.open(io.BytesIO(raw))
    im = ImageOps.exif_transpose(im)
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
