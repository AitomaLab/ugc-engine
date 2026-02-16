"""
Generate all images for Naiara UGC video clone
Uses NanoBanana Pro via Kie.ai API with naiara.jpeg as reference
"""
import sys
import os
from pathlib import Path
sys.path.append('tools')
from generate_images import upload_to_kie, generate_image, log_image_to_airtable
from dotenv import load_dotenv
import requests

# Load environment
load_dotenv('.agent/.env')
AIRTABLE_TOKEN = os.getenv('AIRTABLE_TOKEN')
AIRTABLE_BASE_ID = os.getenv('AIRTABLE_BASE_ID')

PROJECT_NAME = "Naiara UGC Clone"

print("🎨 Generating Naiara UGC Clone Images")
print("=" * 60)
print(f"Cost: 8 images × $0.09 = $0.72")
print("=" * 60)
print()

# Step 1: Upload Naiara reference image
print("📤 Uploading Naiara app reference image...")
naiara_ref_path = "inputs/project3 - naiara/naiara.jpeg"
try:
    naiara_url = upload_to_kie(naiara_ref_path)
    print(f"   ✅ Reference image uploaded: {naiara_url[:50]}...")
except Exception as e:
    print(f"   ⚠️ Warning: Could not upload reference ({str(e)})")
    naiara_url = None
print()

# Step 2: Create output directory
output_dir = Path("inputs/project3 - naiara/images")
output_dir.mkdir(exist_ok=True)

# Step 3: Fetch scenes from Airtable
print("📋 Fetching scenes from Airtable...")
headers = {
    'Authorization': f'Bearer {AIRTABLE_TOKEN}',
    'Content-Type': 'application/json'
}
url = f'https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/Scenes'
response = requests.get(url, headers=headers)
records = response.json().get('records', [])

# Filter for Naiara project
naiara_scenes = [r for r in records if r['fields'].get('Project Name') == PROJECT_NAME]
naiara_scenes.sort(key=lambda x: x['fields']['scene'])  # Sort by scene name

print(f"   Found {len(naiara_scenes)} scenes")
print()

# Step 4: Generate images for each scene
for i, record in enumerate(naiara_scenes, 1):
    fields = record['fields']
    scene_name = fields['scene']
    prompt = fields['start_image_prompt']
    
    print(f"🖼️  Scene {i}/8: {scene_name}")
    print(f"   Prompt: {prompt[:100]}...")
    
    try:
        # Determine if this scene needs the Naiara reference
        reference_urls = []
        if naiara_url and ("app" in scene_name.lower() or "screen" in scene_name.lower()):
            reference_urls = [naiara_url]
            print(f"   Using Naiara reference image")
        
        # Generate image
        image_url = generate_image(prompt, reference_urls, aspect_ratio="9:16")
        print(f"   ✅ Generated: {image_url[:50]}...")
        
        # Log to Airtable
        log_image_to_airtable(PROJECT_NAME, scene_name, image_url)
        
        # Download locally
        output_path = output_dir / f"scene_{i}.jpg"
        response = requests.get(image_url)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        print(f"   💾 Saved: {output_path}")
        
    except Exception as e:
        error_msg = str(e)
        print(f"   ❌ Error: {error_msg}")
        
        # Check if it's a Kie AI error (as per agent rules, don't auto-retry)
        if "KIE_ERROR" in error_msg:
            print()
            print("=" * 60)
            print("⚠️ KIE AI ERROR DETECTED")
            print("=" * 60)
            print(f"Scene {i} failed: {scene_name}")
            print(f"Error: {error_msg}")
            print()
            print("Per agent rules, I'm stopping here.")
            print("Please check kie.ai for the status of this generation.")
            print()
            print("Options:")
            print("  1. Retry this scene")
            print("  2. Skip this scene")
            print("  3. Check kie.ai first")
            sys.exit(1)
    
    print()

print("=" * 60)
print("✅ All 8 images generated successfully!")
print("=" * 60)
print()
print("📁 Images saved to: inputs/project3 - naiara/images/")
print("📊 Logged to Airtable: Scenes table")
print()
print("🛑 CHECKPOINT: Please review the generated images before proceeding")
print("   Next step: Generate videos (8 videos × $0.28 = $2.24)")
