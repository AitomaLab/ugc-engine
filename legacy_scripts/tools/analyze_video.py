"""
Analyze a reference video using Gemini AI
Uses the SEALCaM framework to break down each scene
"""
import os
import sys
import time
from pathlib import Path
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".agent" / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

ANALYSIS_PROMPT = """Analyze this video for recreation purposes. For each distinct scene, provide:

1. **Scene Description**: What's happening visually
2. **Subject**: Main focus (animal, product, person)
3. **Environment**: Setting, background, atmosphere
4. **Action**: What motion occurs
5. **Lighting**: Light quality, direction, mood
6. **Camera**: Angle, movement, framing
7. **Duration**: Approximate seconds

Focus on 3-5 key scenes that could be recreated.

Output in YAML format like:
music_analysis: "Description of music/sound"
scenes:
  - scene_number: 1
    description: "..."
    subject: "..."
    environment: "..."
    action: "..."
    lighting: "..."
    camera: "..."
    duration: "..."
"""


def wait_for_file(file, max_wait=120):
    """Wait for file to be processed by Gemini"""
    start = time.time()
    while time.time() - start < max_wait:
        status = client.files.get(name=file.name)
        if status.state.name == "ACTIVE":
            return status
        print(f"   Processing... ({int(time.time() - start)}s)")
        time.sleep(5)
    raise Exception("File processing timeout")


def analyze_video(video_path, output_path=None):
    """Analyze a video and return the scene breakdown"""
    print("🎬 Analyzing video...")
    print("=" * 50)
    
    # Upload video
    print("\n📤 Uploading video to Gemini...")
    video_file = client.files.upload(file=video_path)
    print(f"   File: {video_file.name}")
    
    # Wait for processing
    print("\n⏳ Waiting for processing...")
    video_file = wait_for_file(video_file)
    print("   ✅ Ready!")
    
    # Analyze
    print("\n🔍 Analyzing video...")
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=[video_file, ANALYSIS_PROMPT]
    )
    
    print("\n" + "=" * 50)
    print("📋 ANALYSIS RESULT:")
    print("=" * 50)
    print(response.text)
    
    # Save analysis if output path provided
    if output_path:
        with open(output_path, "w") as f:
            f.write(response.text)
        print(f"\n💾 Saved to {output_path}")
    
    return response.text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python analyze_video.py <video_path> [output_path]")
        print("Example: python analyze_video.py ../inputs/my-project/video.mp4")
        sys.exit(1)
    
    video_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    analyze_video(video_path, output_path)
