"""Competitor intelligence (Slice 3) — existing BrightData, zero new vendors.

Scrapes each named competitor's account through the same
`scraper_service.scrape` path used for the user's own accounts (no job_id →
no persistence side-effects there) and stores the top posts as OBSERVATIONS
in brand_research with full provenance. Competitor posts must NEVER enter
analytics_posts — that table is the user's own analytics.

Ranking honesty (measured platform reality): IG account scrapes never
return views → IG competitors rank by engagement; TikTok returns plays →
ranks by plays. The benchmark against the user's own posts is computed in
code at read time from the same deduped rows the dashboard uses — no stored
number can go stale or be invented.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
import threading
from datetime import datetime, timezone

from ugc_backend.research import records

logger = logging.getLogger("research.competitors")

MAX_COMPETITORS = 5   # per workspace (plan cost cap)
POSTS_PER_COMPETITOR = 8


def _sb():
    from supabase import create_client
    import os

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("missing SUPABASE_URL or service key")
    return create_client(url, key)


# ── manage ──────────────────────────────────────────────────────────────────

def list_competitors(user_id: str) -> list[dict]:
    return (
        _sb().table("brand_competitors").select("*").eq("user_id", user_id)
        .order("created_at").execute()
    ).data or []


def add_competitor(user_id: str, platform: str, handle: str) -> dict:
    handle = handle.strip().lstrip("@")
    if not handle:
        raise ValueError("empty handle")
    if platform not in ("instagram", "tiktok", "youtube", "facebook"):
        raise ValueError(f"unsupported platform: {platform}")
    if len(list_competitors(user_id)) >= MAX_COMPETITORS:
        raise ValueError(f"competitor limit reached ({MAX_COMPETITORS})")
    resp = (
        _sb().table("brand_competitors")
        .upsert(
            {"user_id": user_id, "platform": platform, "handle": handle},
            on_conflict="user_id,platform,handle",
        )
        .execute()
    )
    return (resp.data or [{}])[0]


def remove_competitor(user_id: str, competitor_id: str) -> None:
    sb = _sb()
    rows = (
        sb.table("brand_competitors").select("platform,handle").eq("id", competitor_id)
        .eq("user_id", user_id).limit(1).execute()
    ).data or []
    sb.table("brand_competitors").delete().eq("id", competitor_id).eq("user_id", user_id).execute()
    # drop that competitor's stored observations too
    if rows:
        handle = rows[0]["handle"]
        sb.table("brand_research").delete().eq("user_id", user_id).eq(
            "insight_type", "competitor_post"
        ).eq("source", f"brightdata:{rows[0]['platform']}:{handle.lower()}").execute()


# ── scrape ──────────────────────────────────────────────────────────────────

def _rank_key(platform: str):
    if platform == "tiktok":
        return lambda p: int(p.get("views") or 0)
    return lambda p: int(p.get("total_engagement") or 0)


async def _scrape_one(user_id: str, platform: str, handle: str) -> list[dict]:
    from ugc_backend.analytics import scraper_service

    profile_url = scraper_service._profile_url_for(platform, handle, "account")
    if not profile_url:
        return []
    result = await scraper_service.scrape(
        input_value=profile_url,
        user_id=user_id,
        kind_override="account",
        top_n=POSTS_PER_COMPETITOR,
    )
    if result.status == "failed":
        logger.warning("[competitors] scrape failed %s/%s: %s", platform, handle, result.error_message)
        return []
    posts = sorted(result.posts or [], key=_rank_key(platform), reverse=True)
    return posts[:POSTS_PER_COMPETITOR]


def run_competitor_research(user_id: str) -> dict:
    comps = list_competitors(user_id)
    if not comps:
        return {"competitors": 0, "posts": 0, "reason": "no competitors configured"}

    now = datetime.now(timezone.utc).isoformat()
    total = 0
    for c in comps:
        platform, handle = c["platform"], c["handle"]
        source_tag = f"brightdata:{platform}:{handle.lower()}"
        try:
            posts = asyncio.run(_scrape_one(user_id, platform, handle))
        except Exception:
            logger.exception("[competitors] scrape errored %s/%s", platform, handle)
            continue
        if not posts:
            continue
        # replace-on-refresh for this competitor only
        records.delete_records(user_id, insight_type="competitor_post", source=source_tag)
        obs = []
        for p in posts:
            url = p.get("post_url")
            caption = (p.get("caption") or "").strip()
            if not url:
                continue
            obs.append(
                {
                    "insight_type": "competitor_post",
                    "subject_text": caption[:100] or url,
                    "language": None,
                    "source": source_tag,
                    "source_url": url,
                    "scraped_at": now,
                    "payload": {
                        "handle": handle,
                        "platform": platform,
                        "caption": caption[:280],
                        "views": p.get("views"),
                        "likes": p.get("likes"),
                        "comments": p.get("comments"),
                        "total_engagement": p.get("total_engagement"),
                        "posted_at": p.get("posted_at"),
                        "thumbnail": p.get("thumbnail_url") or p.get("display_url"),
                    },
                }
            )
        records.insert_observations(user_id, obs)
        total += len(obs)
    return {"competitors": len(comps), "posts": total}


# ── benchmark (computed at read time, never stored) ─────────────────────────

def benchmark_vs_you(user_id: str) -> dict | None:
    from ugc_backend.analytics import db as analytics_db

    own = analytics_db.dedupe_physical_posts(
        analytics_db.list_posts(user_id, period_days=90, sort="recent", limit=100)
    )
    own_eng = [int(p.get("total_engagement") or 0) for p in own if (p.get("total_engagement") or 0) > 0]
    comp_rows = records.list_records(user_id, kind="observation", insight_type="competitor_post", limit=100)
    comp_eng = [
        int((r.get("payload") or {}).get("total_engagement") or 0)
        for r in comp_rows
        if ((r.get("payload") or {}).get("total_engagement") or 0) > 0
    ]
    if not own_eng or not comp_eng:
        return None
    return {
        "your_median_engagement": int(statistics.median(own_eng)),
        "your_posts": len(own_eng),
        "competitor_median_engagement": int(statistics.median(comp_eng)),
        "competitor_posts": len(comp_eng),
    }


# ── background refresh with per-user lock ───────────────────────────────────

_inflight: set[str] = set()
_lock = threading.Lock()


def enqueue_competitor_research(user_id: str) -> bool:
    with _lock:
        if user_id in _inflight:
            return False
        _inflight.add(user_id)

    def _run():
        try:
            out = run_competitor_research(user_id)
            logger.info("[competitors] research complete for %s: %s", user_id, out)
        except Exception:
            logger.exception("[competitors] research failed for %s", user_id)
        finally:
            with _lock:
                _inflight.discard(user_id)

    threading.Thread(target=_run, name=f"competitor-research-{user_id[:8]}", daemon=True).start()
    return True
