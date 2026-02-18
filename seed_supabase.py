"""
Seed Supabase with CORRECT data from Airtable.
Fixed field mapping based on actual Airtable field names.
"""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.saas")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID", "appVAUSKsSNnZNqnt")
HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}
BASE_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"

# Voice IDs from config.py
VOICE_MAP = {
    "Meg": "hpp4J3VqNfWAUOO0d1Us",
    "Max": "pNInz6obpgDQGcFmaJgB",
}

from ugc_db.db_manager import get_supabase

sb = get_supabase()

# ---------------------------------------------------------------------------
# Step 0: Check what columns exist in the influencers table
# ---------------------------------------------------------------------------
print("🔍 Checking Supabase table schema...")
try:
    test = sb.table("influencers").select("*").limit(1).execute()
    if test.data:
        print(f"   influencers columns: {list(test.data[0].keys())}")
    else:
        print("   influencers table empty, inserting test row to check columns...")
except Exception as e:
    print(f"   Error: {e}")

try:
    test2 = sb.table("app_clips").select("*").limit(1).execute()
    if test2.data:
        print(f"   app_clips columns: {list(test2.data[0].keys())}")
except Exception as e:
    print(f"   Error: {e}")

# ---------------------------------------------------------------------------
# Step 1: Fetch from Airtable
# ---------------------------------------------------------------------------
print("\n👤 Fetching Influencers from Airtable...")
resp = requests.get(f"{BASE_URL}/Influencers", headers=HEADERS)
influencers_raw = resp.json().get("records", []) if resp.status_code == 200 else []
print(f"   Found {len(influencers_raw)} influencers")

print("\n📱 Fetching App Clips from Airtable...")
resp2 = requests.get(f"{BASE_URL}/App Clips", headers=HEADERS)
clips_raw = resp2.json().get("records", []) if resp2.status_code == 200 else []
print(f"   Found {len(clips_raw)} app clips")

# ---------------------------------------------------------------------------
# Step 2: Clear existing data
# ---------------------------------------------------------------------------
print("\n🧹 Clearing existing Supabase data...")
for table in ["influencers", "app_clips"]:
    existing = sb.table(table).select("id").execute().data
    for e in existing:
        sb.table(table).delete().eq("id", e["id"]).execute()
    print(f"   Deleted {len(existing)} from {table}")

# ---------------------------------------------------------------------------
# Step 3: Seed Influencers with CORRECT field mapping
# ---------------------------------------------------------------------------
print("\n👤 Seeding influencers...")
for rec in influencers_raw:
    f = rec["fields"]
    
    # Extract image from attachment array (field = "Reference Image")
    image_url = None
    ref_images = f.get("Reference Image", [])
    if isinstance(ref_images, list) and len(ref_images) > 0:
        image_url = ref_images[0].get("url")
    
    name = f.get("Name", "Unknown")
    
    inf_data = {
        "name": name,
        "description": f.get("Description", ""),
        "personality": f.get("Personality", ""),
        "style": f.get("Category", ""),          # Category = Travel/Shop etc
        "speaking_style": f.get("Accent", ""),    # Accent info
        "target_audience": f.get("Tone", ""),     # Tone
        "image_url": image_url,
        "elevenlabs_voice_id": VOICE_MAP.get(name, ""),
    }
    
    # Remove None values (Supabase doesn't like None for non-nullable columns)
    inf_data = {k: v for k, v in inf_data.items() if v is not None}
    
    try:
        result = sb.table("influencers").insert(inf_data).execute()
        row = result.data[0] if result.data else {}
        print(f"   ✅ {name} → {row.get('id', 'no-id')}")
        print(f"      description: {inf_data.get('description', '')[:60]}...")
        print(f"      personality: {inf_data.get('personality', '')[:60]}...")
        print(f"      image: {'yes' if image_url else 'no'}")
        print(f"      voice: {inf_data.get('elevenlabs_voice_id', 'none')}")
    except Exception as e:
        print(f"   ⚠️ {name}: {e}")
        # Try without optional fields in case schema doesn't have them
        minimal = {"name": name, "description": inf_data.get("description", "")}
        if image_url:
            minimal["image_url"] = image_url
        if VOICE_MAP.get(name):
            minimal["elevenlabs_voice_id"] = VOICE_MAP[name]
        try:
            result = sb.table("influencers").insert(minimal).execute()
            row = result.data[0] if result.data else {}
            print(f"   ✅ (minimal) {name} → {row.get('id', 'no-id')}")
        except Exception as e2:
            print(f"   ❌ (minimal also failed) {name}: {e2}")

# ---------------------------------------------------------------------------
# Step 4: Seed App Clips with CORRECT field mapping
# ---------------------------------------------------------------------------
print("\n📱 Seeding app clips...")
for rec in clips_raw:
    f = rec["fields"]
    
    # Extract video from attachment array (field = "Video")
    video_url = ""
    videos = f.get("Video", [])
    if isinstance(videos, list) and len(videos) > 0:
        video_url = videos[0].get("url", "")
    
    clip_data = {
        "name": f.get("Clip Name", f.get("Name", "Unnamed")),  # Field is "Clip Name"!
        "description": f.get("AI Assistant", ""),   # AI Assistant = Travel/Shop
        "video_url": video_url,
        "duration_seconds": int(f.get("Duration", 4)),
    }
    
    try:
        result = sb.table("app_clips").insert(clip_data).execute()
        row = result.data[0] if result.data else {}
        print(f"   ✅ {clip_data['name']} → {row.get('id', 'no-id')}")
        print(f"      type: {clip_data['description']}")
        print(f"      duration: {clip_data['duration_seconds']}s")
        print(f"      video: {'yes' if video_url else 'no'}")
    except Exception as e:
        print(f"   ⚠️ {clip_data['name']}: {e}")

# ---------------------------------------------------------------------------
# Step 5: Final summary
# ---------------------------------------------------------------------------
print("\n📊 Final Supabase counts:")
for table in ["influencers", "scripts", "app_clips", "video_jobs"]:
    count = len(sb.table(table).select("id").execute().data)
    print(f"   {table}: {count}")

# Show full influencer data for verification
print("\n📋 Influencer details:")
infs = sb.table("influencers").select("*").execute().data
for i in infs:
    print(f"   {i['name']}:")
    print(f"     id: {i['id']}")
    print(f"     image: {str(i.get('image_url','none'))[:80]}")
    print(f"     voice: {i.get('elevenlabs_voice_id','none')}")

print("\n📋 App Clip details:")
clips = sb.table("app_clips").select("*").execute().data
for c in clips:
    print(f"   {c['name']}:")
    print(f"     id: {c['id']}")
    print(f"     video: {str(c.get('video_url','none'))[:80]}")

print("\n🎉 Done!")
