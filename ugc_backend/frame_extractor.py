"""
UGC Engine — Frame Extractor

Extracts the first frame from a video URL using FFmpeg and uploads it
to Supabase Storage. Used to generate first_frame_url for app clips.
"""
import os
import uuid
import subprocess
import tempfile
import requests
from pathlib import Path
from typing import Optional


def extract_first_frame(video_url: str) -> Optional[str]:
    """
    Downloads a video from a URL, extracts its first frame using FFmpeg,
    uploads the frame to Supabase Storage, and returns the public URL.

    Args:
        video_url: Public URL of the video to extract the frame from.

    Returns:
        Public URL of the uploaded frame image, or None on failure.
    """
    if not video_url:
        return None

    work_id = uuid.uuid4().hex[:8]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        video_file = tmp_path / f"clip_{work_id}.mp4"
        frame_file = tmp_path / f"frame_{work_id}.jpg"

        # Step 1: Download the video
        try:
            print(f"      [FRAME] Downloading clip for frame extraction: {video_url[:60]}...")
            response = requests.get(video_url, timeout=30, stream=True)
            response.raise_for_status()
            with open(video_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"      [FAIL] Frame extractor: Failed to download video: {e}")
            return None

        # Step 2: Extract the first frame with FFmpeg
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_file),
                "-vframes", "1",        # Extract exactly 1 frame
                "-q:v", "2",            # High quality JPEG
                str(frame_file),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode != 0:
                print(f"      [FAIL] Frame extractor: FFmpeg failed: {result.stderr.decode()[-500:]}")
                return None
        except Exception as e:
            print(f"      [FAIL] Frame extractor: FFmpeg error: {e}")
            return None

        # Step 3: Upload to Supabase Storage
        try:
            from ugc_db.db_manager import get_supabase
            sb = get_supabase()
            bucket = "app-clips"
            filename = f"frames/frame_{work_id}.jpg"

            with open(frame_file, "rb") as f:
                sb.storage.from_(bucket).upload(
                    filename, f,
                    file_options={"content-type": "image/jpeg"}
                )

            public_url = sb.storage.from_(bucket).get_public_url(filename)
            print(f"      [OK] First frame extracted and uploaded: {public_url}")
            return public_url

        except Exception as e:
            print(f"      [FAIL] Frame extractor: Supabase upload failed: {e}")
            return None
