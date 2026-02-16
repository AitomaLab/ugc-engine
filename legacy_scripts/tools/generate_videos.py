"""
Generate videos using Kling 2.6 via Kie.ai API
Includes Airtable logging for generated videos
"""
import os
import sys
import time
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / ".agent" / ".env")

KIE_API_KEY = os.getenv("KIE_API_KEY")
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
KIE_URL = "https://api.kie.ai/api/v1/jobs"
headers = {"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"}


def generate_video(image_url, prompt, duration="5"):
    """Generate a video from an image using Kling 2.6"""
    payload = {
        "model": "kling-2.6/image-to-video",
        "input": {
            "prompt": prompt,
            "image_urls": [image_url],
            "sound": False,
            "duration": duration
        }
    }
    
    r = requests.post(f"{KIE_URL}/createTask", headers=headers, json=payload)
    result = r.json()
    
    if result.get("code") != 200:
        error_msg = result.get('message', str(result))
        raise Exception(f"KIE_ERROR_API: Could not create video task. API response: {error_msg}")
    
    task_id = result["data"]["taskId"]
    print(f"   Task: {task_id[:20]}...")
    
    # Wait for completion
    for i in range(60):  # 10 minutes max
        time.sleep(10)
        r = requests.get(f"{KIE_URL}/recordInfo", headers=headers, params={"taskId": task_id})
        result = r.json()
        state = result["data"]["state"]
        
        if state == "success":
            return json.loads(result["data"]["resultJson"])["resultUrls"][0]
        elif state == "fail":
            fail_msg = result['data'].get('failMsg', 'Unknown reason')
            raise Exception(f"KIE_ERROR_FAILED: Video generation failed. Reason: {fail_msg}")
        elif state == "unknown":
            print(f"   ⚠️ Status unknown... ({i*10}s)")
        else:
            print(f"   Waiting... ({i*10}s)")
    
    raise Exception("KIE_ERROR_TIMEOUT: Video generation timed out after 10 minutes. The task might still be running on Kie AI's servers.")


def log_video_to_airtable(project_name, scene_name, video_url):
    """
    Log a generated video to the Scenes table in Airtable.
    Updates the scene_video field for the matching scene.
    """
    airtable_headers = {
        "Authorization": f"Bearer {AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Find the scene record
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Scenes"
    r = requests.get(url, headers=airtable_headers)
    records = r.json().get("records", [])
    
    record_id = None
    for rec in records:
        fields = rec.get("fields", {})
        if fields.get("Project Name") == project_name and fields.get("scene") == scene_name:
            record_id = rec["id"]
            break
    
    if not record_id:
        print(f"   ⚠️ Scene not found in Airtable: {project_name} / {scene_name}")
        return False
    
    # Update the record with the video
    update_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Scenes/{record_id}"
    update_data = {
        "fields": {
            "scene_video": [{"url": video_url}]
        }
    }
    
    r = requests.patch(update_url, headers=airtable_headers, json=update_data)
    if r.status_code == 200:
        print(f"   ✅ Logged video to Airtable")
        return True
    else:
        print(f"   ⚠️ Failed to log to Airtable: {r.text}")
        return False


def download_video(url, output_path):
    """Download a video from URL"""
    r = requests.get(url)
    with open(output_path, "wb") as f:
        f.write(r.content)
    print(f"   💾 Saved: {output_path}")


if __name__ == "__main__":
    print("This script is meant to be imported and used by other scripts.")
    print("Functions available:")
    print("  - generate_video(image_url, prompt, duration) -> Returns generated video URL")
    print("  - log_video_to_airtable(project_name, scene_name, video_url)")
    print("  - download_video(url, output_path)")
