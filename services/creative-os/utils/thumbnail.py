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
    """Download the first frame of a video and upload as a JPEG thumbnail.

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
        # Try to get the public URL — if the file exists, return it immediately
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
    video_path = None

    try:
        # 1. Download the video (only first few seconds needed)
        import httpx
        video_path = tempfile.mktemp(suffix=".mp4")
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as http:
            async with http.stream("GET", video_url) as resp:
                resp.raise_for_status()
                with open(video_path, "wb") as f:
                    bytes_read = 0
                    async for chunk in resp.aiter_bytes(chunk_size=65536):
                        f.write(chunk)
                        bytes_read += len(chunk)
                        # Only need first ~2MB to get a frame
                        if bytes_read > 2 * 1024 * 1024:
                            break

        # 2. Extract first frame with FFmpeg
        thumb_path = tempfile.mktemp(suffix=".jpg")
        result = await asyncio.to_thread(
            subprocess.run,
            [
                ffmpeg, "-y",
                "-i", video_path,
                "-vframes", "1",
                "-q:v", "3",  # Good quality JPEG
                "-vf", "scale='min(720,iw)':-2",  # Cap width at 720px
                thumb_path,
            ],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0 or not os.path.exists(thumb_path):
            print(f"[Thumbnail] FFmpeg failed for {job_id}: {result.stderr[-200:]}")
            return None

        # 3. Upload to Supabase Storage
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
        return None
    finally:
        # Cleanup temp files
        for p in (video_path, thumb_path):
            if p:
                try:
                    os.unlink(p)
                except Exception:
                    pass
