"""
Generate background music using Suno V4 via Kie.ai API
"""
import os
import sys
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".agent" / ".env")

KIE_API_KEY = os.getenv("KIE_API_KEY")
headers = {"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"}


def generate_music(prompt, instrumental=True):
    """
    Generate music using Suno V4 via Kie.ai
    
    Args:
        prompt: Description of the music style/mood
        instrumental: If True, generates instrumental only (no vocals)
    
    Returns:
        URL to the generated audio file, or None if failed
    """
    print("🎵 Generating music...")
    print(f"   Prompt: {prompt[:100]}...")
    
    payload = {
        "prompt": prompt[:500],  # Suno has a prompt limit
        "customMode": False,
        "instrumental": instrumental,
        "model": "V4",
        "callBackUrl": "https://example.com/callback"
    }
    
    r = requests.post("https://api.kie.ai/api/v1/generate", headers=headers, json=payload)
    result = r.json()
    
    if result.get("code") != 200:
        print(f"   ⚠️ Music generation failed: {result}")
        return None
    
    task_id = result["data"]["taskId"]
    print(f"   Task: {task_id[:20]}...")
    
    # Wait for completion (music takes longer than images)
    for i in range(48):  # 8 minutes max
        time.sleep(10)
        r = requests.get("https://api.kie.ai/api/v1/generate/record-info", headers=headers, params={"taskId": task_id})
        result = r.json()
        
        if result.get("code") != 200:
            print(f"   Waiting... ({i*10}s)")
            continue
        
        status = result["data"]["status"]
        print(f"   Status: {status} ({i*10}s)")
        
        if status in ["SUCCESS", "FIRST_SUCCESS"]:
            suno_data = result["data"]["response"]["sunoData"]
            if suno_data:
                audio_url = suno_data[0]["audioUrl"]
                print(f"   ✅ Music ready: {audio_url[:50]}...")
                return audio_url
        elif status in ["CREATE_TASK_FAILED", "GENERATE_AUDIO_FAILED"]:
            print("   ⚠️ Music generation failed")
            return None
    
    print("   ⚠️ Music generation timed out")
    return None


def download_music(url, output_path):
    """Download music from URL to local file"""
    print(f"   Downloading music...")
    r = requests.get(url)
    with open(output_path, "wb") as f:
        f.write(r.content)
    print(f"   💾 Saved: {output_path}")
    return output_path


if __name__ == "__main__":
    print("This script is meant to be imported and used by other scripts.")
    print("Functions available:")
    print("  - generate_music(prompt, instrumental=True) -> Returns audio URL")
    print("  - download_music(url, output_path) -> Downloads to local file")
