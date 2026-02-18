"""Add missing columns to video_jobs table for production fields."""
from dotenv import load_dotenv
load_dotenv(".env.saas")

import os
import requests

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")

# Use Supabase's SQL endpoint (via rpc) to add columns
# We'll use the REST API to alter the table
headers = {
    "apikey": SUPABASE_SERVICE_KEY,
    "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
    "Content-Type": "application/json",
}

# Add columns via Supabase SQL (using the pg_net extension or direct SQL)
sql = """
ALTER TABLE video_jobs 
ADD COLUMN IF NOT EXISTS hook text,
ADD COLUMN IF NOT EXISTS model_api text DEFAULT 'seedance-1.5-pro',
ADD COLUMN IF NOT EXISTS assistant_type text DEFAULT 'Travel',
ADD COLUMN IF NOT EXISTS length integer DEFAULT 15,
ADD COLUMN IF NOT EXISTS user_id uuid;
"""

print("Adding missing columns to video_jobs table...")
resp = requests.post(
    f"{SUPABASE_URL}/rest/v1/rpc/exec_sql",
    headers=headers,
    json={"query": sql}
)

if resp.status_code == 200:
    print("✅ Columns added successfully!")
elif resp.status_code == 404:
    # exec_sql function might not exist, try via SQL editor endpoint
    print("exec_sql not available, trying direct SQL...")
    
    # Use the management API instead
    resp2 = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/",
        headers=headers,
        json={"query": sql}
    )
    print(f"Response: {resp2.status_code} {resp2.text[:200]}")
else:
    print(f"Response: {resp.status_code} {resp.text[:300]}")

# Verify by checking the schema
from ugc_db.db_manager import get_supabase
sb = get_supabase()
try:
    test = sb.table("video_jobs").insert({
        "influencer_id": "00000000-0000-0000-0000-000000000000",
        "status": "schema_test",
        "hook": "test hook",
        "model_api": "seedance-1.5-pro",
        "assistant_type": "Travel",
        "length": 15,
    }).execute()
    if test.data:
        print(f"\n✅ Schema verified! Columns: {sorted(test.data[0].keys())}")
        sb.table("video_jobs").delete().eq("id", test.data[0]["id"]).execute()
        print("(test row cleaned up)")
    else:
        print("Insert returned no data")
except Exception as e:
    print(f"\n❌ Schema test failed: {e}")
    print("\nThe columns need to be added manually in Supabase Dashboard → SQL Editor")
    print("Run this SQL:")
    print(sql)
