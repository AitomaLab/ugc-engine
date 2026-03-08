"""Run migrations 009 + add metadata column to video_jobs."""
import os
from dotenv import load_dotenv
load_dotenv(".env.saas")

from ugc_db.db_manager import get_supabase

sql_statements = [
    # Migration 009: Rename pedestal → elevated
    "UPDATE public.product_shots SET shot_type = 'elevated', updated_at = NOW() WHERE shot_type = 'pedestal'",
    
    # Migration 009: Add transition shot columns for Workflow B
    # (these use ALTER TABLE IF NOT EXISTS, safe to re-run)
    
    # Migration 009: Add auto_transition_type to video_jobs
    # (handled via Supabase REST below)
    
    # New: Add metadata JSONB column to video_jobs
    # (handled via Supabase REST below)
]

def main():
    sb = get_supabase()
    
    # 1. Rename pedestal -> elevated in product_shots (via Supabase update)
    print("1. Renaming pedestal → elevated in product_shots...")
    try:
        sb.table("product_shots").update({"shot_type": "elevated"}).eq("shot_type", "pedestal").execute()
        print("   ✅ Done (or no pedestal rows to rename)")
    except Exception as e:
        print(f"   ⚠️ Skipped: {e}")
    
    # 2. Check what columns need to be added via SQL Editor
    print("\n2. Checking video_jobs columns...")
    r = sb.table("video_jobs").select("*").limit(1).execute()
    existing_cols = set(r.data[0].keys()) if r.data else set()
    print(f"   Existing columns: {sorted(existing_cols)}")
    
    needed = {
        "auto_transition_type": "TEXT",
        "metadata": "JSONB",
    }
    
    missing = {k: v for k, v in needed.items() if k not in existing_cols}
    
    if not missing:
        print("   ✅ All needed columns already exist!")
    else:
        print(f"\n   ❌ Missing columns: {list(missing.keys())}")
        print("\n   👉 Please run the following SQL in your Supabase SQL Editor:\n")
        for col, typ in missing.items():
            print(f"   ALTER TABLE public.video_jobs ADD COLUMN IF NOT EXISTS {col} {typ};")
        print()
    
    # 3. Check product_shots columns
    print("3. Checking product_shots columns...")
    r2 = sb.table("product_shots").select("*").limit(1).execute()
    ps_cols = set(r2.data[0].keys()) if r2.data else set()
    
    ps_needed = {
        "transition_type": "TEXT",
        "preceding_video_url": "TEXT",
        "analysis_json": "JSONB",
    }
    
    ps_missing = {k: v for k, v in ps_needed.items() if k not in ps_cols}
    
    if not ps_missing:
        print("   ✅ All product_shots columns exist!")
    else:
        print(f"\n   ❌ Missing product_shots columns: {list(ps_missing.keys())}")
        print("\n   👉 Also run in Supabase SQL Editor:\n")
        for col, typ in ps_missing.items():
            print(f"   ALTER TABLE public.product_shots ADD COLUMN IF NOT EXISTS {col} {typ};")
        print()

    print("\n✅ Migration check complete!")

if __name__ == "__main__":
    main()
