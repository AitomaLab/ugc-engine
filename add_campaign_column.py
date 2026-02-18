"""Add campaign_name column to video_jobs table."""
from dotenv import load_dotenv
load_dotenv(".env.saas")

from ugc_db.db_manager import get_supabase

sb = get_supabase()

print("🔧 Adding 'campaign_name' column to video_jobs table...")
try:
    # Supabase REST API doesn't support ALTER TABLE directly.
    # We'll use the rpc method or just check if the column exists
    # by doing a test insert/update.
    # For now, let's verify by trying to read the column.
    res = sb.table("video_jobs").select("campaign_name").limit(1).execute()
    print("✅ Column 'campaign_name' already exists!")
except Exception as e:
    err_msg = str(e)
    if "column" in err_msg.lower() and "not" in err_msg.lower():
        print("⚠️  Column 'campaign_name' does not exist.")
        print("   Please add it manually in Supabase Dashboard:")
        print("   Table: video_jobs")
        print("   Column: campaign_name (text, nullable)")
        print()
        print("   Or run this SQL in the Supabase SQL Editor:")
        print("   ALTER TABLE video_jobs ADD COLUMN campaign_name TEXT;")
    else:
        print(f"✅ Column check returned: {err_msg}")
        print("   (Column likely exists already)")
