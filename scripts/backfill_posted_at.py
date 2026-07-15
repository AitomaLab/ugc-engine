"""One-time backfill: populate analytics_posts.posted_at from raw_payload.

Fixes the BrightData date-mapping bug: external/scraped posts were ingested
with posted_at=NULL because the Instagram mappers never read BrightData's
`datetime` key (see scraper_service._pick_posted_at). The dashboard period
filter then fell back to added_at (the ingest date), mis-windowing every
organic post. This sets posted_at from the raw_payload date the scrape
already stored, so the windows become correct without a re-scrape.

Idempotent: only touches rows where posted_at IS NULL and a usable date is
present in raw_payload. Pass --dry-run to preview.
"""
import json
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

# Same key priority as scraper_service._pick_posted_at.
_DATE_KEYS = (
    "datetime", "date_posted", "posted_at", "taken_at",
    "create_time", "create_date", "created_time", "published_at", "timestamp",
)


def _pick(raw: dict) -> str | None:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return None
    if not isinstance(raw, dict):
        return None
    for k in _DATE_KEYS:
        v = raw.get(k)
        if v:
            return str(v)
    return None


def _fetch_all(sb) -> list[dict]:
    rows: list[dict] = []
    start, page = 0, 1000
    while True:
        batch = (
            sb.table("analytics_posts")
            .select("id,posted_at,raw_payload")
            .is_("posted_at", "null")
            .range(start, start + page - 1)
            .execute()
        ).data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    sb = get_supabase()

    rows = _fetch_all(sb)
    print(f"Posts with posted_at IS NULL: {len(rows)}")

    to_fix = []
    for r in rows:
        dt = _pick(r.get("raw_payload") or {})
        if dt:
            to_fix.append((r["id"], dt))

    print(f"Of those, resolvable from raw_payload: {len(to_fix)}")
    for pid, dt in to_fix[:20]:
        print(f"  - {str(pid)[:8]}...  ->  {dt}")
    if len(to_fix) > 20:
        print(f"  ... and {len(to_fix) - 20} more")

    if dry_run:
        print("\nDry run — no changes written.")
        return 0

    updated = 0
    for pid, dt in to_fix:
        try:
            sb.table("analytics_posts").update({"posted_at": dt}).eq("id", pid).execute()
            updated += 1
        except Exception as exc:
            print(f"  ! failed {str(pid)[:8]}: {exc}")
    print(f"\nUpdated {updated} rows with posted_at from raw_payload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
