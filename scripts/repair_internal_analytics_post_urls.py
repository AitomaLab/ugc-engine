"""Repair internal analytics_posts rows with corrupted numeric IG post_url values.

Earlier video-prep bugs overwrote ``studio://social-post/{id}`` keys with invalid
``instagram.com/p/{numeric_pk}`` URLs. This script restores the stable studio key.

Usage:
    python scripts/repair_internal_analytics_post_urls.py
    python scripts/repair_internal_analytics_post_urls.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from dotenv import load_dotenv

load_dotenv(root / ".env.saas")
load_dotenv(root / "env.saas")
load_dotenv(root / ".env")
load_dotenv(root / "env")

from ugc_db.db_manager import get_supabase

_NUMERIC_IG_POST_URL = re.compile(
    r"instagram\.com/(?:p|reel|reels|tv)/(\d+)",
    re.IGNORECASE,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("id,user_id,post_url,social_post_id,source")
        .eq("source", "internal")
        .execute()
    )
    repaired = 0
    for row in res.data or []:
        post_url = (row.get("post_url") or "").strip()
        if not post_url or post_url.startswith("studio://"):
            continue
        if not _NUMERIC_IG_POST_URL.search(post_url):
            continue
        sp_id = row.get("social_post_id")
        if not sp_id:
            print(f"skip {row['id'][:8]} — no social_post_id")
            continue
        fixed = f"studio://social-post/{sp_id}"
        print(f"{'[dry-run] ' if args.dry_run else ''}repair {row['id'][:8]}: {post_url} -> {fixed}")
        if args.dry_run:
            repaired += 1
            continue
        try:
            sb.table("analytics_posts").update({"post_url": fixed}).eq(
                "id", row["id"],
            ).execute()
            repaired += 1
        except Exception as exc:
            err = str(exc).lower()
            if "unique" in err or "23505" in err:
                canonical = (
                    sb.table("analytics_posts")
                    .select("id")
                    .eq("user_id", row["user_id"])
                    .eq("post_url", fixed)
                    .limit(1)
                    .execute()
                )
                if canonical.data:
                    print(f"  duplicate — deleting corrupt row {row['id'][:8]}")
                    sb.table("analytics_posts").delete().eq("id", row["id"]).execute()
                    repaired += 1
                else:
                    print(f"  failed {row['id'][:8]}: {exc}")
            else:
                print(f"  failed {row['id'][:8]}: {exc}")

    print(f"Done — {'would repair' if args.dry_run else 'repaired'} {repaired} row(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
