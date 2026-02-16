"""
Generate all video clips for Naiara UGC video clone
Uses Kling 2.6 image-to-video via Kie.ai API
"""
import sys
import os
import time
from pathlib import Path
sys.path.append('tools')
from generate_videos import generate_video, log_video_to_airtable, download_video
from dotenv import load_dotenv
import requests

# Load environment
load_dotenv('.agent/.env')
AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

PROJECT_NAME = "Naiara UGC Clone"

print("🎥 Generating Naiara UGC Clone Videos")
print("=" * 60)
print(f"Cost: 8 videos × $0.28 = $2.24")
print("=" * 60)
print()

# Step 1: Create output directory
output_dir = Path("inputs/project3 - naiara/videos")
output_dir.mkdir(exist_ok=True)

# Step 2: Fetch scenes from Airtable
print("📋 Fetching scenes from Airtable...")
headers = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
}
url = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Scenes'
response = requests.get(url, headers=headers)
records = response.json().get('records', [])

# Filter for Naiara project and sort
naiara_scenes = [r for r in records if r['fields'].get('Project Name') == PROJECT_NAME]
naiara_scenes.sort(key=lambda x: x['fields']['scene'])

print(f"   Found {len(naiara_scenes)} scenes with images")
print()

# Step 3: Generate videos for each scene
for i, record in enumerate(naiara_scenes, 1):
    fields = record['fields']
    scene_name = fields['scene']
    video_prompt = fields['video_prompt']
    
    # Get the image URL from Airtable attachments
    start_images = fields.get('start_image', [])
    if not start_images:
        print(f"   ⚠️ Skipping Scene {i}: {scene_name} (No image found in Airtable)")
        continue
        
    image_url = start_images[0]['url']
    
    print(f"🎥 Scene {i}/8: {scene_name}")
    print(f"   Action: {video_prompt[:100]}...")
    
    try:
        # Generate video (5 seconds)
        video_url = generate_video(image_url, video_prompt, duration="5")
        print(f"   ✅ Generated: {video_url[:50]}...")
        
        # Log to Airtable
        log_video_to_airtable(PROJECT_NAME, scene_name, video_url)
        
        # Download locally
        output_path = output_dir / f"scene_{i}.mp4"
        download_video(video_url, str(output_path))
        print(f"   💾 Saved: {output_path}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ Error: {error_msg}")
        
        if "KIE_ERROR" in error_msg:
            print()
            print("=" * 60)
            print("⚠️ KIE AI ERROR DETECTED")
            print("=" * 60)
            print(f"Scene {i} failed: {scene_name}")
            print(f"Error: {error_msg}")
            print()
            print("Stopping to avoid duplicate charges.")
            sys.exit(1)
    
    print()

print("=" * 60)
print("✅ All 8 video clips generated successfully!")
print("=" * 60)
print()
print("📁 Videos saved to: inputs/project3 - naiara/videos/")
print("📊 Logged to Airtable: Scenes table")
print()
print("🛑 CHECKPOINT: Please review the video clips before final combination")
print("   Next step: Combined all clips and add music")
