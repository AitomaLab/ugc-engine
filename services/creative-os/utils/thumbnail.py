"""
Video Thumbnail Generator

Extracts the first frame from a video URL using FFmpeg, uploads it to
Supabase Storage, and returns the public URL. Used by the schedule modal
to show instant video previews instead of loading full video files.
"""
import os
import asyncio
import tempfile
import subprocess
from pathlib import Path


def _get_ffmpeg_path() -> str:
    """Resolve the ffmpeg binary path. Tries system ffmpeg first, then imageio-ffmpeg."""
    import shutil
    system_ffmpeg = shutil.which("ffmpeg")
    if system_ffmpeg:
        return system_ffmpeg
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return "ffmpeg"


async def generate_thumbnail(video_url: str, job_id: str) -> str | None:
    """Extract the first frame of a video and upload as a JPEG thumbnail.

    Uses FFmpeg's native HTTP support to read directly from the URL,
    avoiding the need to download the entire file.

    Returns the public URL of the thumbnail, or None on failure.
    """
    from env_loader import load_env
    load_env(Path(__file__).parent)

    supabase_url = os.getenv("SUPABASE_URL")

    if not supabase_url or not video_url:
        return None

    # Check if thumbnail already exists in storage (deterministic filename)
    storage_filename = f"thumb_{job_id[:8]}.jpg"
    try:
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        import httpx
        thumb_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
        async with httpx.AsyncClient(timeout=5.0) as http:
            head = await http.head(thumb_url)
            if head.status_code == 200:
                print(f"[Thumbnail] Cache hit for {job_id}: {thumb_url[:80]}...")
                return thumb_url
    except Exception:
        pass

    ffmpeg = _get_ffmpeg_path()
    thumb_path = None

    try:
        # Extract first frame directly from URL — FFmpeg handles HTTP natively.
        # This only downloads the bytes needed for a single frame (typically <500KB)
        # instead of the full video file.
        thumb_path = tempfile.mktemp(suffix=".jpg")
        result = await asyncio.to_thread(
            subprocess.run,
            [
                ffmpeg, "-y",
                "-i", video_url,
                "-vframes", "1",
                "-q:v", "3",  # Good quality JPEG
                "-vf", "scale='min(720,iw)':-2",  # Cap width at 720px
                thumb_path,
            ],
            capture_output=True,
            timeout=30,
        )
        if result.returncode != 0 or not os.path.exists(thumb_path):
            stderr = result.stderr.decode("utf-8", errors="replace")[-300:] if result.stderr else "unknown"
            print(f"[Thumbnail] FFmpeg failed for {job_id}: {stderr}")
            return None

        if os.path.getsize(thumb_path) == 0:
            print(f"[Thumbnail] FFmpeg produced empty file for {job_id}")
            return None

        # Upload to Supabase Storage
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        with open(thumb_path, "rb") as f:
            try:
                sb.storage.from_("generated-videos").upload(
                    storage_filename, f,
                    file_options={"content-type": "image/jpeg"},
                )
            except Exception as e:
                # File might already exist — try update
                if "Duplicate" in str(e) or "already exists" in str(e):
                    with open(thumb_path, "rb") as f2:
                        sb.storage.from_("generated-videos").update(
                            storage_filename, f2,
                            file_options={"content-type": "image/jpeg"},
                        )
                else:
                    raise
        thumb_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
        print(f"[Thumbnail] Generated for {job_id}: {thumb_url[:80]}...")
        return thumb_url

    except Exception as e:
        print(f"[Thumbnail] Failed for {job_id}: {e}")
        import traceback; traceback.print_exc()
        return None
    finally:
        if thumb_path:
            try:
                os.unlink(thumb_path)
            except Exception:
                pass
