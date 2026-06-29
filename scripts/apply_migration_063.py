#!/usr/bin/env python3
"""Apply migration 063 (analytics locale columns) to Supabase."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "ugc_db" / "migrations" / "063_analytics_locale_variants.sql"


def main() -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env.saas")
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
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'analytics_video_breakdowns'
          AND column_name IN ('output_locale', 'locale_variants')
        ORDER BY column_name
        """
    )
    cols = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    print("Migration 063 applied. analytics_video_breakdowns columns:", cols)
    return 0 if len(cols) == 2 else 1


if __name__ == "__main__":
    raise SystemExit(main())
