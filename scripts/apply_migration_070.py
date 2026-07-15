#!/usr/bin/env python3
"""Apply migration 070 (analytics_post_metric_snapshots) to Supabase."""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "ugc_db" / "migrations" / "070_analytics_post_metric_snapshots.sql"


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
        WHERE table_schema = 'public'
          AND table_name = 'analytics_post_metric_snapshots'
        ORDER BY ordinal_position
        """
    )
    cols = cur.fetchall()
    print("analytics_post_metric_snapshots columns:")
    for name, dtype in cols:
        print(f"  {name}: {dtype}")
    cur.close()
    conn.close()
    return 0 if cols else 1


if __name__ == "__main__":
    raise SystemExit(main())
