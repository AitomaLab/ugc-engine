from dotenv import load_dotenv
load_dotenv(".env.saas")
from ugc_db.db_manager import get_supabase

sb = get_supabase()
data = sb.table("app_clips").select("*").execute().data
print(f"App Clips found: {len(data)}")
for clip in data:
    print(f"- {clip['id']}: {clip['name']}")
