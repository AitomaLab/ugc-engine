"""One-time repair: restore external posts' engagement columns from raw_payload.

Before the propagate fix, stale internal (Ayrshare) metrics were copied onto
freshly scraped external rows on every account-modal open, so the columns hold
the frozen values while raw_payload (written verbatim at scrape time) holds
the real ones BrightData returned. This restores likes/comments/shares/saves
from the latest raw_payload for source='external' rows.

Views are NOT touched (IG account scrapes never return views; the column's
value came from the internal twin and is the best available signal).

Idempotent. Pass --dry-run to preview.
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

# Key priority mirrors scraper_service._normalize_instagram etc.
_METRIC_KEYS = {
    "likes": ("like_count", "digg_count", "likes"),
    "comments": ("comment_count", "comments"),
    "shares": ("share_count", "shares"),
    "saves": ("save_count", "saves", "collect_count"),
}


def _coerce(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _raw_metrics(raw) -> dict:
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    for col, keys in _METRIC_KEYS.items():
        for k in keys:
            val = _coerce(raw.get(k))
            if val is not None:
                out[col] = val
                break
    return out


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    sb = get_supabase()
    rows = []
    start, page = 0, 1000
    while True:
        batch = (
            sb.table("analytics_posts")
            .select("id,likes,comments,shares,saves,raw_payload")
            .eq("source", "external")
            .range(start, start + page - 1)
            .execute()
        ).data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page

    print(f"external posts: {len(rows)}")
    to_fix = []
    for r in rows:
        raw_m = _raw_metrics(r.get("raw_payload"))
        patch = {
            col: val for col, val in raw_m.items()
            if val is not None and val != r.get(col)
        }
        if patch:
            to_fix.append((r["id"], patch, {c: r.get(c) for c in patch}))

    print(f"rows needing repair: {len(to_fix)}")
    for pid, patch, old in to_fix[:20]:
        print(f"  {str(pid)[:8]}...  {old} -> {patch}")
    if len(to_fix) > 20:
        print(f"  ... and {len(to_fix) - 20} more")

    if dry_run:
        print("\nDry run — no changes written.")
        return 0

    for pid, patch, _ in to_fix:
        sb.table("analytics_posts").update(patch).eq("id", pid).execute()
    print(f"\nRepaired {len(to_fix)} rows from raw_payload.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
