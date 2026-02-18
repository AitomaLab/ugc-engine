"""Check video_jobs schema in Supabase."""
from dotenv import load_dotenv
load_dotenv(".env.saas")
from ugc_db.db_manager import get_supabase

sb = get_supabase()

# Get columns by looking at existing data or inserting a test
existing = sb.table("video_jobs").select("*").limit(1).execute().data
if existing:
    print("video_jobs columns:", sorted(existing[0].keys()))
else:
    print("No jobs yet. Checking via a minimal insert + delete...")
    try:
        test = sb.table("video_jobs").insert({
            "influencer_id": "00000000-0000-0000-0000-000000000000",
            "status": "test",
        }).execute()
        if test.data:
            print("video_jobs columns:", sorted(test.data[0].keys()))
            sb.table("video_jobs").delete().eq("id", test.data[0]["id"]).execute()
            print("(test row cleaned up)")
    except Exception as e:
        print(f"Error: {e}")
