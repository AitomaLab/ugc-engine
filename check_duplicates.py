from dotenv import load_dotenv
load_dotenv(".env.saas")
from ugc_db.db_manager import get_supabase

sb = get_supabase()

print("🔎 Checking for Duplicate 'Meg'...")
res = sb.table("influencers").select("*").eq("name", "Meg").execute()

if res.data:
    print(f"Found {len(res.data)} records:")
    for i, inf in enumerate(res.data):
        print(f"--- Record {i+1} ---")
        print(f"ID: {inf['id']}")
        print(f"Has Image URL? {bool(inf.get('image_url'))}")
        print(f"Image URL: {inf.get('image_url')}")
else:
    print("No Meg found.")
