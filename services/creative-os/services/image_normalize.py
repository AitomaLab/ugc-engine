"""Normalize any user-provided image to an opaque PNG on a white background.

Kept self-contained (no ugc_db import) so creative-os can import it without
needing the repo root on sys.path. The ugc_backend copy at
ugc_db/image_normalize.py is identical."""
from __future__ import annotations

import io
from PIL import Image, ImageOps


def normalize_image_bytes(raw: bytes) -> bytes:
    """Take any image bytes, return opaque PNG bytes on a white background.
    Honors EXIF orientation, drops EXIF, flattens alpha."""
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


__all__ = ["normalize_image_bytes"]
