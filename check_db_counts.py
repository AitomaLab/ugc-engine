import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env.saas")
DATABASE_URL = os.getenv("DATABASE_URL")

print(f"Checking DB: {DATABASE_URL.split('@')[-1] if DATABASE_URL else 'NONE'}")

if DATABASE_URL:
    engine = create_engine(DATABASE_URL)
    with engine.connect() as conn:
        inf_count = conn.execute(text("SELECT COUNT(*) FROM influencers")).scalar()
        clip_count = conn.execute(text("SELECT COUNT(*) FROM app_clips")).scalar()
        print(f"📊 Influencers: {inf_count}")
        print(f"📊 App Clips: {clip_count}")
else:
    print("❌ No DATABASE_URL found in .env.saas")
