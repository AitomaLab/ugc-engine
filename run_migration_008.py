"""Run migration 008: Add gender column to influencers table."""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv(".env.saas")

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL not set in .env.saas")

print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

print("Adding 'gender' column to influencers table...")
cur.execute("ALTER TABLE public.influencers ADD COLUMN IF NOT EXISTS gender TEXT DEFAULT 'Female'")
conn.commit()

print("✅ Migration 008 complete — 'gender' column added to influencers table!")
cur.close()
conn.close()
