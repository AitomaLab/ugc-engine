"""
Generate images using NanoBanana Pro via Kie.ai API
Includes Kie.ai file upload for reference images and Airtable logging
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
KIE_UPLOAD_URL = "https://kieai.redpandaai.co/api/file-stream-upload"
headers = {"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"}


def upload_to_kie(filepath):
    """
    Upload a local file to Kie.ai and return the public URL.
    Uses the same KIE_API_KEY - no extra keys needed!
    Files are temporary (3 days) but that's fine since we use them immediately.
    """
    print(f"   Uploading {os.path.basename(filepath)} to Kie.ai...")
    
    upload_headers = {"Authorization": f"Bearer {KIE_API_KEY}"}
    
    with open(filepath, "rb") as f:
        files = {"file": (os.path.basename(filepath), f)}
        response = requests.post(KIE_UPLOAD_URL, headers=upload_headers, files=files)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            file_url = result["data"]["fileUrl"]
            print(f"   ✅ Uploaded: {file_url}")
            return file_url
    
    raise Exception(f"Kie.ai upload failed: {response.text}")


def upload_image(filepath):
    """Upload an image and return a public URL"""
    if str(filepath).startswith("http"):
        return str(filepath)
    return upload_to_kie(filepath)


def generate_image(prompt, reference_urls, aspect_ratio="9:16"):
    """Generate an image using NanoBanana Pro"""
    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": prompt,
            "image_input": reference_urls,
            "aspect_ratio": aspect_ratio,
            "resolution": "2K"
        }
    }
    
    r = requests.post(f"{KIE_URL}/createTask", headers=headers, json=payload)
    result = r.json()
    
    if result.get("code") != 200:
        error_msg = result.get('message', str(result))
        raise Exception(f"KIE_ERROR_API: Could not create task. API response: {error_msg}")
    
    task_id = result["data"]["taskId"]
    print(f"   Task: {task_id[:20]}...")
    
    # Wait for completion
    for i in range(36):  # 3 minutes max
        time.sleep(5)
        r = requests.get(f"{KIE_URL}/recordInfo", headers=headers, params={"taskId": task_id})
        result = r.json()
        state = result["data"]["state"]
        
        if state == "success":
            return json.loads(result["data"]["resultJson"])["resultUrls"][0]
        elif state == "fail":
            fail_msg = result['data'].get('failMsg', 'Unknown reason')
            raise Exception(f"KIE_ERROR_FAILED: Image generation failed. Reason: {fail_msg}")
        elif state == "unknown":
            print(f"   ⚠️ Status unknown... ({i*5}s)")
        else:
            print(f"   Waiting... ({i*5}s)")
    
    raise Exception("KIE_ERROR_TIMEOUT: Image generation timed out after 3 minutes. The task might still be running on Kie AI's servers.")


def log_image_to_airtable(project_name, scene_name, image_url):
    """
    Log a generated image to the Scenes table in Airtable.
    Updates the start_image field for the matching scene.
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
    
    # Update the record with the image
    update_url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Scenes/{record_id}"
    update_data = {
        "fields": {
            "start_image": [{"url": image_url}]
        }
    }
    
    r = requests.patch(update_url, headers=airtable_headers, json=update_data)
    if r.status_code == 200:
        print(f"   ✅ Logged image to Airtable")
        return True
    else:
        print(f"   ⚠️ Failed to log to Airtable: {r.text}")
        return False


def download_image(url, output_path):
    """Download an image from URL"""
    r = requests.get(url)
    with open(output_path, "wb") as f:
        f.write(r.content)
    print(f"   💾 Saved: {output_path}")


if __name__ == "__main__":
    print("This script is meant to be imported and used by other scripts.")
    print("Functions available:")
    print("  - upload_to_kie(filepath) -> Returns public URL")
    print("  - generate_image(prompt, reference_urls) -> Returns generated image URL")
    print("  - log_image_to_airtable(project_name, scene_name, image_url)")
    print("  - download_image(url, output_path)")
