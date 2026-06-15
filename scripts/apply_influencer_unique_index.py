"""Apply migration 054 unique index via direct Postgres if DATABASE_URL is set."""
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from dotenv import load_dotenv

load_dotenv(root / ".env.saas")
load_dotenv(root / "env.saas")

MIGRATION_SQL = """
ALTER TABLE public.influencers
    DROP CONSTRAINT IF EXISTS influencers_project_name_key;

ALTER TABLE public.influencers
    DROP CONSTRAINT IF EXISTS influencers_name_project_key;

DROP INDEX IF EXISTS idx_influencers_project_name_unique;

CREATE UNIQUE INDEX IF NOT EXISTS idx_influencers_project_name_unique
    ON public.influencers (project_id, lower(btrim(name)))
    WHERE project_id IS NOT NULL AND btrim(name) <> '';
"""


def main():
    db_url = os.getenv("DATABASE_URL") or os.getenv("SUPABASE_DB_URL")
    if not db_url:
        print("DATABASE_URL not set — run ugc_db/migrations/054_dedupe_influencers_and_unique_name.sql in Supabase SQL Editor.")
        return 1
    try:
        import psycopg2
    except ImportError:
        print("Install psycopg2 to apply migration from CLI, or run the SQL file in Supabase SQL Editor.")
        return 1
    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(MIGRATION_SQL)
    conn.close()
    print("Applied idx_influencers_project_name_unique.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
