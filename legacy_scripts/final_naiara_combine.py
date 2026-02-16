"""
Final assembly script for Naiara project:
1. Generate music (retry)
2. Trim 5s clips to specific scene durations
3. Combine and add music
"""
import sys
import os
import subprocess
from pathlib import Path
sys.path.append('tools')
from generate_music import generate_music
from dotenv import load_dotenv
import requests

# Load environment
load_dotenv('.agent/.env')

PROJECT_NAME = "Naiara UGC Clone"
OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)
INPUT_VIDEO_DIR = Path("inputs/project3 - naiara/videos")
TEMP_DIR = Path("temp_clips")
TEMP_DIR.mkdir(exist_ok=True)

print("🎬 Final Naiara Assembly: Trimming & Combining")
print("=" * 60)

# 1. Generate Music (Wait up to 2 mins)
print("🎼 Generating background music...")
music_prompt = "Upbeat, modern, travel vlog background music with acoustic guitar and energetic rhythm, happy vibes, instrumental only"
music_path = OUTPUT_DIR / "naiara_bg_music.mp3"
try:
    # Proceed even if music fails
    music_url = generate_music(music_prompt, instrumental=True)
    print(f"   ✅ Music generated: {music_url[:50]}...")
    response = requests.get(music_url)
    with open(music_path, 'wb') as f:
        f.write(response.content)
except Exception as e:
    print(f"   ⚠️ Music generation skipped/failed: {e}")
    music_path = None

# 2. Trim Clips
# Durations from analysis: 3, 1, 1, 1, 2, 2, 3, 2 = 15s
durations = [3, 1, 1, 1, 2, 2, 3, 2]
trimmed_files = []

print("\n✂️ Trimming clips to target durations...")
for i, duration in enumerate(durations, 1):
    input_file = INPUT_VIDEO_DIR / f"scene_{i}.mp4"
    output_temp = TEMP_DIR / f"scene_{i}_trimmed.mp4"
    
    if not input_file.exists():
        print(f"   ❌ Missing scene_{i}.mp4")
        continue

    print(f"   Trimming Scene {i} to {duration}s...")
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_file),
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac",
        str(output_temp)
    ]
    subprocess.run(cmd, capture_output=True)
    trimmed_files.append(str(output_temp))

# 3. Create file list for concatenation
list_file = TEMP_DIR / "videos.txt"
with open(list_file, "w") as f:
    for video in trimmed_files:
        abs_path = str(Path(video).absolute()).replace("\\", "/")
        f.write(f"file '{abs_path}'\n")

# 4. Final Match & Merge
final_video = OUTPUT_DIR / "naiara_ugc_clone_final.mp4"
print(f"\n🎥 Combining {len(trimmed_files)} clips...")

if music_path and music_path.exists():
    print("   Adding music overlay...")
    # Map video from concat and audio from music
    # Shorts/TikTok often have a quick fade out
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-i", str(music_path),
        "-filter_complex", "[0:v]copy[v];[1:a]afade=t=out:st=13:d=2[a]",
        "-map", "[v]",
        "-map", "[a]",
        "-shortest",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac",
        str(final_video)
    ]
else:
    print("   No music found, just concatenating...")
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-c:a", "aac",
        str(final_video)
    ]

result = subprocess.run(cmd, capture_output=True, text=True)
if result.returncode == 0:
    print(f"\n✨ SUCCESS! Final video: {final_video}")
    # Cleanup
    # for f in trimmed_files: Path(f).unlink()
    # list_file.unlink()
else:
    print(f"\n❌ Error combining: {result.stderr[:200]}")

print("=" * 60)
