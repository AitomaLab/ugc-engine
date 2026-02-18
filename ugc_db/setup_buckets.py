from dotenv import load_dotenv
load_dotenv(".env.saas")
from ugc_db.db_manager import get_supabase

sb = get_supabase()

BUCKET_NAME = "generated-videos"

print(f"🪣 Setting up bucket: {BUCKET_NAME}")

# 1. Check if exists
try:
    buckets = sb.storage.list_buckets()
    names = [b.name for b in buckets]
    if BUCKET_NAME in names:
        print("✅ Bucket already exists.")
    else:
        print("🆕 Creating bucket...")
        sb.storage.create_bucket(BUCKET_NAME, options={"public": True})
        print("✅ Bucket created (public).")

    # 2. Verify Output
    buckets = sb.storage.list_buckets()
    for b in buckets:
        if b.name == BUCKET_NAME:
            print(f"🔎 Status: Public={b.public}")

except Exception as e:
    print(f"❌ Error: {e}")
