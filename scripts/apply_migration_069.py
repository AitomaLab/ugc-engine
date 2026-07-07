#!/usr/bin/env python3
"""Apply migration 069 (social_posts external media_urls) to Supabase."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "ugc_db" / "migrations" / "069_social_posts_external_media.sql"


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env.saas")
        load_dotenv(ROOT / "env.saas")
        load_dotenv(ROOT / "env")
    except ImportError:
        pass

    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set — run the SQL in Supabase SQL Editor:", file=sys.stderr)
        print(MIGRATION.read_text(encoding="utf-8"), file=sys.stderr)
        return 1

    import psycopg2

    sql = MIGRATION.read_text(encoding="utf-8")
    conn = psycopg2.connect(url)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(sql)
    cur.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'social_posts' AND column_name = 'media_urls'
        """
    )
    col = cur.fetchone()
    cur.execute(
        """
        SELECT pg_get_constraintdef(oid)
        FROM pg_constraint
        WHERE conname = 'chk_social_posts_media_source'
        """
    )
    constraint = cur.fetchone()
    cur.execute("NOTIFY pgrst, 'reload schema'")
    cur.close()
    conn.close()

    print("Migration 069 applied.")
    print("media_urls column:", col)
    if constraint:
        print("constraint:", constraint[0][:240])
    print("PostgREST schema reload notified.")
    return 0 if col and constraint and "media_urls" in constraint[0] else 1


if __name__ == "__main__":
    raise SystemExit(main())
