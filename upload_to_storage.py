"""
Download assets from Airtable temporary URLs and upload to Supabase Storage.
This gives us permanent, public URLs that won't expire.

Buckets used:
  - influencer-images  (for influencer reference images)
  - app-clips          (for app clip videos)
"""
import requests
import os
import tempfile
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.saas")

from ugc_db.db_manager import get_supabase

sb = get_supabase()
SUPABASE_URL = os.getenv("SUPABASE_URL")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ensure_bucket(name: str):
    """Create a storage bucket if it doesn't exist."""
    try:
        sb.storage.get_bucket(name)
        print(f"   Bucket '{name}' exists ✅")
    except Exception:
        try:
            sb.storage.create_bucket(name, options={"public": True})
            print(f"   Bucket '{name}' created ✅")
        except Exception as e:
            if "already exists" in str(e).lower() or "Duplicate" in str(e):
                print(f"   Bucket '{name}' already exists ✅")
            else:
                print(f"   ⚠️ Bucket '{name}': {e}")


def download_file(url: str) -> bytes | None:
    """Download a file from a URL and return the bytes."""
    try:
        resp = requests.get(url, timeout=60)
        if resp.status_code == 200:
            return resp.content
        print(f"   ⚠️ Download failed: HTTP {resp.status_code}")
        return None
    except Exception as e:
        print(f"   ⚠️ Download error: {e}")
        return None


def upload_to_storage(bucket: str, path: str, data: bytes, content_type: str) -> str | None:
    """Upload bytes to Supabase Storage and return the public URL."""
    try:
        # Remove existing file if it exists (upsert)
        try:
            sb.storage.from_(bucket).remove([path])
        except Exception:
            pass
        
        sb.storage.from_(bucket).upload(
            path,
            data,
            file_options={"content-type": content_type, "upsert": "true"}
        )
        
        # Build public URL
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{path}"
        return public_url
    except Exception as e:
        print(f"   ⚠️ Upload error: {e}")
        return None


def guess_content_type(url: str, default: str = "application/octet-stream") -> str:
    """Guess content type from URL."""
    url_lower = url.lower().split("?")[0]
    if url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
        return "image/jpeg"
    elif url_lower.endswith(".png"):
        return "image/png"
    elif url_lower.endswith(".webp"):
        return "image/webp"
    elif url_lower.endswith(".mp4"):
        return "video/mp4"
    elif url_lower.endswith(".mov"):
        return "video/quicktime"
    # For Airtable URLs, try to detect from response
    return default


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
print("🪣 Ensuring storage buckets exist...")
ensure_bucket("influencer-images")
ensure_bucket("app-clips")

# ---------------------------------------------------------------------------
# Upload Influencer Images
# ---------------------------------------------------------------------------
print("\n👤 Uploading influencer images...")
influencers = sb.table("influencers").select("*").execute().data

for inf in influencers:
    name = inf["name"]
    image_url = inf.get("image_url")
    
    if not image_url:
        print(f"   ⏭️ {name}: no image URL, skipping")
        continue
    
    # Skip if already a Supabase URL
    if SUPABASE_URL and SUPABASE_URL in str(image_url):
        print(f"   ⏭️ {name}: already on Supabase Storage")
        continue
    
    print(f"   📥 Downloading {name}'s image...")
    data = download_file(image_url)
    if not data:
        continue
    
    # Determine file extension from content
    content_type = "image/png"  # Default for AI-generated images
    if data[:3] == b'\xff\xd8\xff':
        content_type = "image/jpeg"
        ext = "jpg"
    elif data[:8] == b'\x89PNG\r\n\x1a\n':
        content_type = "image/png"
        ext = "png"
    elif data[:4] == b'RIFF':
        content_type = "image/webp"
        ext = "webp"
    else:
        ext = "png"
    
    filename = f"{name.lower().replace(' ', '_')}_reference.{ext}"
    print(f"   📤 Uploading as {filename} ({content_type}, {len(data)//1024}KB)...")
    
    public_url = upload_to_storage("influencer-images", filename, data, content_type)
    if public_url:
        # Update the database record with the permanent URL
        sb.table("influencers").update({"image_url": public_url}).eq("id", inf["id"]).execute()
        print(f"   ✅ {name} → {public_url}")
    else:
        print(f"   ❌ {name}: upload failed")

# ---------------------------------------------------------------------------
# Upload App Clip Videos
# ---------------------------------------------------------------------------
print("\n📱 Uploading app clip videos...")
clips = sb.table("app_clips").select("*").execute().data

for clip in clips:
    name = clip["name"]
    video_url = clip.get("video_url")
    
    if not video_url:
        print(f"   ⏭️ {name}: no video URL, skipping")
        continue
    
    # Skip if already a Supabase URL
    if SUPABASE_URL and SUPABASE_URL in str(video_url):
        print(f"   ⏭️ {name}: already on Supabase Storage")
        continue
    
    print(f"   📥 Downloading {name} video...")
    data = download_file(video_url)
    if not data:
        continue
    
    # Determine format
    content_type = "video/mp4"
    ext = "mp4"
    if data[:4] == b'\x1aE\xdf\xa3':
        content_type = "video/webm"
        ext = "webm"
    
    filename = f"{name.lower().replace(' ', '_').replace('/', '_')}.{ext}"
    size_mb = len(data) / (1024 * 1024)
    print(f"   📤 Uploading as {filename} ({content_type}, {size_mb:.1f}MB)...")
    
    public_url = upload_to_storage("app-clips", filename, data, content_type)
    if public_url:
        sb.table("app_clips").update({"video_url": public_url}).eq("id", clip["id"]).execute()
        print(f"   ✅ {name} → {public_url}")
    else:
        print(f"   ❌ {name}: upload failed")

# ---------------------------------------------------------------------------
# Final verification
# ---------------------------------------------------------------------------
print("\n📊 Verification:")
print("\nInfluencers:")
for inf in sb.table("influencers").select("name, image_url").execute().data:
    url = inf.get("image_url", "none")
    is_permanent = "✅ Supabase" if SUPABASE_URL and SUPABASE_URL in str(url) else "⚠️ External"
    print(f"   {inf['name']}: {is_permanent} → {str(url)[:80]}")

print("\nApp Clips:")
for clip in sb.table("app_clips").select("name, video_url").execute().data:
    url = clip.get("video_url", "none")
    is_permanent = "✅ Supabase" if SUPABASE_URL and SUPABASE_URL in str(url) else "⚠️ External"
    print(f"   {clip['name']}: {is_permanent} → {str(url)[:80]}")

print("\n🎉 Asset upload complete!")
