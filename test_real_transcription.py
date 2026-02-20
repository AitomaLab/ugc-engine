
import os
import sys
import requests
import subprocess
from pathlib import Path
from dotenv import load_dotenv

import config
# Ensure env is loaded via config
if not os.getenv("OPENAI_API_KEY"):
    print("⚠️ OPENAI_API_KEY not found in env, trying to load manually...")
    load_dotenv(Path(__file__).parent / ".env")

try:
    from ugc_backend.transcription_client import TranscriptionClient
    print(f"✅ Imported TranscriptionClient (Key present: {bool(os.getenv('OPENAI_API_KEY'))})")
except ImportError as e:
    print(f"❌ Import failed (run from root): {e}")
    sys.exit(1)

VIDEO_URL = "https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/generated-videos/naiara_20260219_164931_a4ac2dc4.mp4"
TEMP_DIR = Path("temp/test_transcription")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

def test_pipeline():
    print(f"⬇️ Downloading video: {VIDEO_URL}")
    video_path = TEMP_DIR / "test_video.mp4"
    
    try:
        resp = requests.get(VIDEO_URL, stream=True)
        resp.raise_for_status()
        with open(video_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"✅ Downloaded: {video_path}")
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return

    print("🎙️ Extracting audio...")
    audio_path = TEMP_DIR / "test_audio.mp3"
    try:
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-i", str(video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            str(audio_path)
        ]
        subprocess.run(cmd, check=True)
        print(f"✅ Audio extracted: {audio_path}")
    except Exception as e:
        print(f"❌ Audio extraction failed (check ffmpeg): {e}")
        return

    print("🧠 Transcribing...")
    client = TranscriptionClient()
    if not client.api_key:
        print("❌ SKIPPING: No OpenAI Key")
        return

    result = client.transcribe_audio(str(audio_path))
    
    if result:
        words = result.get("words", [])
        print(f"✅ Success! Found {len(words)} words.")
        print("-" * 40)
        # Print first 10 words with timestamps
        for w in words[:10]:
            print(f"[{w['start']:.2f} - {w['end']:.2f}] {w['word']}")
        print("-" * 40)
        print(f"Full Text: {result.get('text', '')}")
    else:
        print("❌ Transcription returned None")

if __name__ == "__main__":
    test_pipeline()
