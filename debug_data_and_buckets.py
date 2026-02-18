from dotenv import load_dotenv
load_dotenv(".env.saas")
from ugc_db.db_manager import get_supabase

sb = get_supabase()

# 1. Check Buckets
print("🪣 Checking Storage Buckets...")
try:
    buckets = sb.storage.list_buckets()
    print(f"Found {len(buckets)} buckets:")
    for b in buckets:
        print(f"- {b.name}")
except Exception as e:
    print(f"❌ Failed to list buckets: {e}")

# 2. Check Meg
print("\n👤 Checking Influencer 'Meg'...")
res = sb.table("influencers").select("*").eq("name", "Meg").execute()
if res.data:
    meg = res.data[0]
    print(f"ID: {meg.get('id')}")
    print(f"Name: {meg.get('name')}")
    print(f"Image URL: {meg.get('image_url')}")
    print(f"Ref Image URL: {meg.get('reference_image_url')}")
else:
    print("❌ Meg not found!")
