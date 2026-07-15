"""Thin Supabase REST wrappers for the Analytics module.

All functions accept a `user_id` and scope queries to that user. They use the
service-role key (via `ugc_db.db_manager.get_supabase`) because the backend
already authenticates the JWT in `auth.get_current_user`; we then enforce the
user scope explicitly via `.eq("user_id", user_id)` calls. RLS in Postgres is
the second line of defense.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

from ugc_db.db_manager import get_supabase

logger = logging.getLogger(__name__)

_LOCALE_BREAKDOWN_COLUMNS = frozenset({"output_locale", "locale_variants"})
_OPTIONAL_BREAKDOWN_COLUMNS = _LOCALE_BREAKDOWN_COLUMNS | frozenset({"updated_at"})

BREAKDOWN_STALE_SEC = 480  # 8 minutes — orphaned daemon threads / hung Gemini calls

_VIDEO_PREVIEW_RE = re.compile(r"\.(mp4|webm|mov|avi|mkv|m4v)(\?.*)?$", re.I)


def _is_video_preview_url(url: str) -> bool:
    return bool(_VIDEO_PREVIEW_RE.search(url))


# ── Scrape depth + engagement rate ──────────────────────────────────────────

DEFAULT_TOP_N = 50
LARGE_ACCOUNT_TOP_N = 100
LARGE_ACCOUNT_FOLLOWER_THRESHOLD = 100_000
MAX_TOP_N = 200


def resolve_scrape_top_n(
    user_id: str,
    override: Optional[int] = None,
    *,
    follower_count: Optional[int] = None,
) -> int:
    """Posts to retain per account scrape — explicit override > 100K tier > user default."""
    if override and override > 0:
        return min(int(override), MAX_TOP_N)
    fc = int(follower_count or 0)
    if fc >= LARGE_ACCOUNT_FOLLOWER_THRESHOLD:
        return LARGE_ACCOUNT_TOP_N
    settings = get_analytics_settings(user_id)
    return int(settings.get("default_top_n") or DEFAULT_TOP_N)


def post_engagement(post: dict) -> int:
    """Total engagement for a single post — likes + comments + shares + saves.

    Prefers the stored ``total_engagement`` column (already summed at scrape
    time) and falls back to summing the individual metric fields when it's
    absent, so the formula stays correct for partially-populated rows.
    """
    te = post.get("total_engagement")
    if te is not None:
        return int(te or 0)
    return sum(int(post.get(k) or 0) for k in ("likes", "comments", "shares", "saves"))


def compute_engagement_rate(
    posts: Iterable[dict],
    follower_count: Optional[int],
) -> float:
    """Engagement Rate for dashboard KPIs.

    Primary (industry standard when followers are known):

    ``(average_engagement_per_post / follower_count) × 100``

    Fallback when follower count is missing (common on freshly-added
    external accounts before the next profile scrape patches
    ``follower_count``):

    ``(total_engagement / total_views) × 100`` — the "engagement per view"
    rate IG/TikTok surface in native analytics when plays are available.
    """
    rows = list(posts)
    if not rows:
        return 0.0
    n = len(rows)
    total_eng = sum(post_engagement(p) for p in rows)
    fc = int(follower_count or 0)
    if fc > 0:
        return round((total_eng / n) / fc * 100.0, 2)
    total_views = sum(int(p.get("views") or 0) for p in rows)
    if total_views > 0:
        return round(total_eng / total_views * 100.0, 2)
    total_reach = sum(
        int(p.get("impressions") or p.get("reach") or 0) for p in rows
    )
    if total_reach > 0:
        return round(total_eng / total_reach * 100.0, 2)
    return 0.0


def period_engagement_rate(
    rows: list[dict],
    follower_count: Optional[int] = None,
) -> float:
    """Period-scoped engagement rate for dashboard KPIs.

    Primary: ``(total_engagement / total_views) × 100`` over the window.
    Falls back to follower-based ``compute_engagement_rate`` when views are
    unavailable.
    """
    if not rows:
        return 0.0
    total_eng = sum(post_engagement(r) for r in rows)
    total_views = sum(int(r.get("views") or 0) for r in rows)
    if total_views > 0:
        return round(total_eng / total_views * 100.0, 2)
    return compute_engagement_rate(rows, follower_count)


def _post_activity_date(post: dict):
    """Best-effort calendar date for period filtering / sparklines."""
    ts = post.get("posted_at") or post.get("added_at") or post.get("scraped_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date()
    except Exception:
        return None


def _filter_posts_by_period(
    posts: Iterable[dict],
    period_days: Optional[int],
) -> list[dict]:
    """Keep posts whose activity date falls inside the rolling window."""
    rows = list(posts)
    if not period_days or period_days <= 0:
        return rows
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=int(period_days) - 1)
    filtered = [p for p in rows if (_d := _post_activity_date(p)) and _d >= cutoff]
    # If timestamps are missing across the board, fall back to the full set
    # rather than reporting zero — the scrape still happened.
    if not filtered and rows and all(_post_activity_date(p) is None for p in rows):
        return rows
    return filtered


def _fetch_dashboard_posts(
    user_id: str,
    *,
    period_days: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
    limit: int = 500,
) -> tuple[list[dict], list[dict]]:
    """Return ``(period_rows, all_rows)`` for KPI / distribution helpers.

    Account-scoped queries pull the full scraped library (up to ``limit``)
    then slice by ``posted_at`` in Python so metrics aren't tied to
    ``added_at`` (which clusters to the scrape timestamp).
    """
    cap = min(max(int(limit or 500), 1), 500)
    tracked_slugs: set[tuple[str, str]] | None = None
    if username and platform and platform != "all":
        all_rows = list_account_posts(
            user_id,
            platform=platform,
            username=username,
            source=source if source and source != "all" else None,
            limit=cap,
        )
    else:
        tracked_slugs = active_tracked_slugs(user_id)
        all_rows = list_posts(
            user_id,
            platform=platform,
            source=source,
            username=username,
            limit=cap,
            tracked_only=True,
            tracked_slugs=tracked_slugs,
        )
    period_rows = _filter_posts_by_period(all_rows, period_days)
    return period_rows, all_rows


def mean_engagement_rate_for_accounts(
    user_id: str,
    accounts: Iterable[dict],
    *,
    source: Optional[str] = None,
) -> float:
    """Unweighted mean ER across tracked accounts (each uses its scrape sample)."""
    rates: list[float] = []
    for acct in accounts:
        plat = (acct.get("platform") or "").strip().lower()
        nick = (acct.get("username") or "").strip().lower().lstrip("@")
        if not plat or not nick:
            continue
        posts = list_account_posts(
            user_id, platform=plat, username=nick, source=source, limit=500,
        )
        fc = acct.get("follower_count") or acct.get("followers")
        er = compute_engagement_rate(posts, fc)
        if posts:
            rates.append(er)
    if not rates:
        return 0.0
    return round(sum(rates) / len(rates), 2)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _missing_column_from_error(err: Exception) -> Optional[str]:
    """Extract a column name from PostgREST / Postgres schema-mismatch errors."""
    msg = str(err).lower()
    if (
        "pgrst204" not in msg
        and "could not find" not in msg
        and "42703" not in msg
        and "does not exist" not in msg
    ):
        return None
    match = re.search(r"'([^']+)'\s+column", msg)
    if match:
        return match.group(1)
    match = re.search(r"column\s+(?:\w+\.)?(\w+)\s+does not exist", msg)
    if match:
        return match.group(1)
    return None


def _strip_missing_column(payload: dict, err: Exception) -> bool:
    """Drop one missing column from ``payload`` so the write can retry."""
    col = _missing_column_from_error(err)
    if col and col in payload:
        payload.pop(col, None)
        return True
    return False


def _is_unique_violation(err: Exception) -> bool:
    """True when an update would collide on a unique index (e.g. post_url)."""
    msg = str(err).lower()
    return "23505" in msg or "duplicate key" in msg


def _supabase_update(table: str, payload: dict, **filters: Any) -> None:
    """Update a row, retrying without columns the live schema does not have yet."""
    data = dict(payload)
    sb = get_supabase()
    while data:
        try:
            q = sb.table(table).update(data)
            for key, val in filters.items():
                q = q.eq(key, val)
            q.execute()
            return
        except Exception as err:
            if _strip_missing_column(data, err):
                continue
            # Studio rows keep ``studio://`` URLs; patching in the public IG
            # permalink collides with BrightData-scraped duplicates.
            if _is_unique_violation(err) and "post_url" in data:
                data.pop("post_url", None)
                continue
            raise


def _supabase_upsert(table: str, payload: dict | list[dict], *, on_conflict: str) -> Any:
    """Upsert row(s), retrying without columns the live schema does not have yet."""
    rows = payload if isinstance(payload, list) else [payload]
    sb = get_supabase()
    while rows:
        try:
            return sb.table(table).upsert(rows, on_conflict=on_conflict).execute()
        except Exception as err:
            stripped = False
            for row in rows:
                if _strip_missing_column(row, err):
                    stripped = True
            if not stripped:
                raise
            rows = [r for r in rows if r]


def _normalize_account_slug(platform: str, username: str) -> tuple[str, str]:
    return (
        (platform or "").strip().lower(),
        (username or "").strip().lower().lstrip("@"),
    )


def active_tracked_slugs(user_id: str) -> set[tuple[str, str]]:
    """``(platform, username)`` pairs for rows the user still tracks."""
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .select("platform,username,is_active")
        .eq("user_id", user_id)
        .execute()
    )
    out: set[tuple[str, str]] = set()
    for row in res.data or []:
        if row.get("is_active") is False:
            continue
        plat, nick = _normalize_account_slug(
            str(row.get("platform") or ""),
            str(row.get("username") or ""),
        )
        if plat and nick:
            out.add((plat, nick))
    return out


def _scope_rows_to_tracked_accounts(
    user_id: str,
    rows: list[dict],
    *,
    slugs: set[tuple[str, str]] | None = None,
) -> list[dict]:
    tracked = slugs if slugs is not None else active_tracked_slugs(user_id)
    if not tracked:
        return []
    kept: list[dict] = []
    for row in rows:
        plat, nick = _normalize_account_slug(
            str(row.get("platform") or ""),
            str(row.get("username") or ""),
        )
        if (plat, nick) in tracked:
            kept.append(row)
    return kept


def purge_orphan_analytics_posts(user_id: str) -> int:
    """Remove scraped rows whose handle is no longer in ``analytics_tracked_accounts``."""
    slugs = active_tracked_slugs(user_id)
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("id,platform,username")
        .eq("user_id", user_id)
        .execute()
    )
    delete_ids: list[str] = []
    for row in res.data or []:
        plat, nick = _normalize_account_slug(
            str(row.get("platform") or ""),
            str(row.get("username") or ""),
        )
        if not plat or not nick or (plat, nick) not in slugs:
            if row.get("id"):
                delete_ids.append(row["id"])
    if not delete_ids:
        return 0
    sb.table("analytics_posts").delete().in_("id", delete_ids).execute()
    return len(delete_ids)


# ── analytics_posts ─────────────────────────────────────────────────────────

def upsert_posts(rows: Iterable[dict]) -> list[dict]:
    """Insert/update analytics_posts rows. Caller must include user_id on each row.

    Conflict on (user_id, platform, post_url) updates metric columns + scraped_at.

    `added_at` is deliberately stripped from the payload so the DB-side
    `DEFAULT NOW()` fires only on the first insert and existing rows keep their
    original "added-to-tracking" timestamp — that's what the period-filter
    pills in the Analytics tab rely on (see migration 034).
    """
    payload = []
    for r in rows:
        row = {k: v for k, v in r.items() if k != "added_at"}
        row["scraped_at"] = row.get("scraped_at") or _now()
        payload.append(row)
    if not payload:
        return []
    result = _supabase_upsert(
        "analytics_posts",
        payload,
        on_conflict="user_id,platform,post_url",
    )
    return result.data or []


def list_posts(
    user_id: str,
    *,
    period_days: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
    sort: str = "engagement",
    q: Optional[str] = None,
    limit: int = 50,
    cursor: Optional[str] = None,
    tracked_only: bool = True,
    tracked_slugs: set[tuple[str, str]] | None = None,
) -> list[dict]:
    sb = get_supabase()
    qry = sb.table("analytics_posts").select("*").eq("user_id", user_id)
    if platform and platform != "all":
        qry = qry.eq("platform", platform)
    if source and source != "all":
        qry = qry.eq("source", source)
    if username:
        qry = qry.eq("username", username.lower())
    if q:
        qry = qry.ilike("caption", f"%{q}%")

    # v2 — 5 sort keys (engagement / views / likes / comments / recent).
    # Falls through to `engagement` for any unrecognised key so a bad URL
    # never breaks the page.
    if sort == "recent":
        qry = qry.order("posted_at", desc=True)
    elif sort == "views":
        qry = qry.order("views", desc=True)
    elif sort == "likes":
        qry = qry.order("likes", desc=True)
    elif sort == "comments":
        qry = qry.order("comments", desc=True)
    elif sort == "hasBreakdown":
        qry = qry.order("scraped_at", desc=True)
    else:
        qry = qry.order("total_engagement", desc=True)

    if cursor:
        # Cursor is an ISO scraped_at timestamp; paginate by recency to keep
        # things simple and stateless.
        qry = qry.lt("scraped_at", cursor)
    qry = qry.limit(min(limit, 500))
    result = qry.execute()
    rows = result.data or []
    if period_days:
        rows = _filter_posts_by_period(rows, period_days)
    if tracked_only and not username:
        rows = _scope_rows_to_tracked_accounts(user_id, rows, slugs=tracked_slugs)
    return rows


def set_post_storage_video_url(post_id: str, storage_video_url: str) -> None:
    """Patch the mirrored Supabase Storage URL onto a single analytics_posts
    row. Called from the background mirror thread spawned by the scraper after
    a fresh BrightData scrape."""
    if not post_id or not storage_video_url:
        return
    sb = get_supabase()
    sb.table("analytics_posts").update(
        {"storage_video_url": storage_video_url}
    ).eq("id", post_id).execute()


def set_post_thumbnail_url(post_id: str, thumbnail_url: str) -> None:
    """Patch the (Supabase-hosted) thumbnail URL onto a single analytics_posts
    row. Called from the mirror pipeline after we extract a poster frame from
    the downloaded video — guarantees every card has a working thumbnail
    instead of the gray placeholder that shows when BrightData's CDN URL is
    CORS-blocked / expired."""
    if not post_id or not thumbnail_url:
        return
    sb = get_supabase()
    sb.table("analytics_posts").update(
        {"thumbnail_url": thumbnail_url}
    ).eq("id", post_id).execute()


def set_post_url(post_id: str, post_url: str) -> None:
    """Patch a canonical platform permalink onto a single analytics_posts row."""
    if not post_id or not post_url:
        return
    sb = get_supabase()
    existing = (
        sb.table("analytics_posts")
        .select("source,post_url")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )
    row = (existing.data or [None])[0]
    if row:
        if (row.get("source") or "") == "internal":
            return
        current = (row.get("post_url") or "").strip()
        if current.startswith("studio://"):
            return
    sb.table("analytics_posts").update(
        {"post_url": post_url[:8000]}
    ).eq("id", post_id).execute()


def set_post_duration(post_id: str, duration_seconds: float) -> None:
    """Persist a derived video duration onto a single analytics_posts row.
    Called from the modal once the `<video>` tag fires `loadedmetadata` —
    cheaper and more accurate than asking the AI breakdown to extract it,
    and means it surfaces immediately in the metrics grid and is available
    to future AI breakdowns as context."""
    if not post_id or duration_seconds is None or duration_seconds <= 0:
        return
    sb = get_supabase()
    sb.table("analytics_posts").update(
        {"duration_seconds": float(duration_seconds)}
    ).eq("id", post_id).execute()


def get_post(user_id: str, post_id: str) -> Optional[dict]:
    sb = get_supabase()
    result = (
        sb.table("analytics_posts")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", post_id)
        .limit(1)
        .execute()
    )
    return (result.data or [None])[0]


def list_posts_by_ids(user_id: str, post_ids: list[str]) -> list[dict]:
    """Fetch analytics posts by primary key, scoped to the user."""
    ids = [pid for pid in post_ids if pid]
    if not ids:
        return []
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("*")
        .eq("user_id", user_id)
        .in_("id", ids)
        .execute()
    )
    return res.data or []


def list_internal_posts(user_id: str) -> list[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("*")
        .eq("user_id", user_id)
        .eq("source", "internal")
        .execute()
    )
    return res.data or []


def list_posts_needing_metrics_refresh(
    user_id: str,
    *,
    source: Optional[str] = None,
    limit: int = 25,
) -> list[dict]:
    """Posts with null/zero views — candidates for a metrics backfill scrape."""
    sb = get_supabase()
    qry = (
        sb.table("analytics_posts")
        .select("*")
        .eq("user_id", user_id)
        .or_("views.is.null,views.eq.0")
        .order("scraped_at", desc=True)
        .limit(limit)
    )
    if source:
        qry = qry.eq("source", source)
    res = qry.execute()
    return res.data or []


def get_social_post(user_id: str, social_post_id: str) -> Optional[dict]:
    sb = get_supabase()
    res = (
        sb.table("social_posts")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", social_post_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def get_analytics_post_by_social_post_id(
    user_id: str,
    social_post_id: str,
) -> Optional[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("*")
        .eq("user_id", user_id)
        .eq("social_post_id", social_post_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def update_social_post(user_id: str, social_post_id: str, updates: dict) -> None:
    if not social_post_id or not updates:
        return
    sb = get_supabase()
    sb.table("social_posts").update(updates).eq("user_id", user_id).eq(
        "id", social_post_id,
    ).execute()


def merge_post_raw_payload(post_id: str, merge: dict) -> None:
    """Shallow-merge keys into analytics_posts.raw_payload (e.g. Ayrshare permalink)."""
    if not post_id or not merge:
        return
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("raw_payload")
        .eq("id", post_id)
        .limit(1)
        .execute()
    )
    row = (res.data or [None])[0]
    if not row:
        return
    existing = row.get("raw_payload")
    if not isinstance(existing, dict):
        existing = {}
    merged = {**existing, **merge}
    sb.table("analytics_posts").update({"raw_payload": merged}).eq("id", post_id).execute()


def patch_post_metrics(post_id: str, updates: dict) -> None:
    """Patch engagement (+ optional post_url + funnel metrics) on a single
    analytics_posts row.

    Funnel metrics (impressions, reach, clicks, ctr, media_type) are only
    populated when Ayrshare returns them for the platform's tier — see
    migration 039 for the column definitions.
    """
    allowed = {
        "views", "likes", "comments", "shares", "saves",
        "impressions", "reach", "clicks", "ctr",
        "media_type",
        "post_url", "external_post_id", "storage_video_url",
    }
    payload = {k: v for k, v in updates.items() if k in allowed and v is not None}
    if not payload:
        return
    payload["scraped_at"] = _now()
    _supabase_update("analytics_posts", payload, id=post_id)


def stats(
    user_id: str,
    *,
    period_days: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Aggregate KPIs for the strip. Done client-side over a capped fetch — the
    typical user will have <1k posts so this is plenty fast and avoids needing
    a dedicated SQL RPC.

    NOTE — kept intentionally minimal: this function is bound to the legacy
    KPI strip. New aggregations (sparklines, deltas, distributions, cumulative)
    live in dedicated helpers (`stats_extras`, `stats_distribution`,
    `stats_cumulative`) so this contract stays stable.
    """
    rows, all_rows = _fetch_dashboard_posts(
        user_id,
        period_days=period_days,
        platform=platform,
        source=source,
        username=username,
        limit=500,
    )
    return stats_from_rows(
        user_id,
        rows,
        all_rows,
        platform=platform,
        source=source,
        username=username,
    )


def stats_from_rows(
    user_id: str,
    period_rows: list[dict],
    all_rows: list[dict],
    *,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """KPI strip aggregates from a pre-fetched post set."""
    total_views = sum(int(r.get("views") or 0) for r in period_rows)
    total_eng = sum(int(r.get("total_engagement") or 0) for r in period_rows)
    posts_tracked = len(period_rows)
    posts_total = len(all_rows)

    if username and platform and platform != "all":
        acct = get_tracked_account_by_slug(user_id, platform=platform, username=username)
        fc = (acct or {}).get("follower_count") or (acct or {}).get("followers")
        avg_rate = period_engagement_rate(period_rows, fc)
    else:
        avg_rate = period_engagement_rate(period_rows)
    return {
        "total_views": total_views,
        "total_engagement": total_eng,
        "avg_engagement_rate": avg_rate,
        "posts_tracked": posts_tracked,
        "posts_total": posts_total,
    }


# ── Dashboard aggregations (added in v3, dashboard rewrite) ────────────────
#
# These helpers compute the data for the new dashboard widgets without
# mutating the legacy `stats()` contract. They share the same "fetch up to N
# rows then aggregate in Python" approach since:
#
#   • A typical Aitoma tenant tracks <1K analytics_posts rows
#   • Supabase REST doesn't expose efficient GROUP BY without RPCs, and we'd
#     rather not introduce SQL functions for v1 of the dashboard
#   • The same scan can power multiple panels (a single fetch fans out to
#     KPI sparklines, distributions, deltas) — composition lives in the router

def _bucket_key(post: dict) -> Optional[str]:
    """Pick the date a post should bucket into for time-series aggregation.

    Falls through `posted_at → added_at → scraped_at`; returns ``None`` when
    no usable timestamp is present so the post is dropped from the chart.
    """
    ts = post.get("posted_at") or post.get("added_at") or post.get("scraped_at")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        return None


def stats_extras(
    user_id: str,
    *,
    period_days: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Sparkline arrays + period-over-period deltas for KPI cards."""
    rows, all_rows = _fetch_dashboard_posts(
        user_id,
        period_days=period_days,
        platform=platform,
        source=source,
        username=username,
        limit=500,
    )
    return stats_extras_from_rows(rows, all_rows, period_days=period_days)


def stats_extras_from_rows(
    period_rows: list[dict],
    all_rows: list[dict],
    *,
    period_days: Optional[int] = None,
) -> dict:
    """Sparkline arrays + period-over-period deltas from a pre-fetched post set.

    Sparklines span **2× the active window**: first half = previous period,
    second half = current period (architecture-reference contract).
    """
    span = max(int(period_days or 30), 1)
    today = datetime.now(timezone.utc).date()
    spark_len = 2 * span
    spark_index = {
        (today - timedelta(days=spark_len - 1 - i)).isoformat(): i
        for i in range(spark_len)
    }
    daily_views = [0] * spark_len
    daily_eng = [0] * spark_len
    daily_posts = [0] * spark_len

    prev_start = today - timedelta(days=2 * span - 1)
    prev_end = today - timedelta(days=span)

    for r in all_rows:
        d = _post_activity_date(r)
        if not d or d < prev_start or d > today:
            continue
        bucket = _bucket_key(r)
        if not bucket or bucket not in spark_index:
            continue
        idx = spark_index[bucket]
        daily_views[idx] += int(r.get("views") or 0)
        daily_eng[idx] += post_engagement(r)
        daily_posts[idx] += 1

    daily_engagement_rate = [
        round(e / v * 100.0, 2) if v > 0 else 0.0
        for v, e in zip(daily_views, daily_eng)
    ]

    delta_views = 0.0
    delta_eng = 0.0
    delta_posts = 0.0
    if period_days:
        total_views = sum(int(r.get("views") or 0) for r in period_rows)
        posts_tracked = len(period_rows)
        prev_rows = [
            p for p in all_rows
            if (d := _post_activity_date(p)) and prev_start <= d <= prev_end
        ]
        prev_views = sum(int(p.get("views") or 0) for p in prev_rows)
        prev_posts = len(prev_rows)
        if prev_views:
            delta_views = round((total_views - prev_views) / prev_views * 100.0, 1)
        curr_rate = period_engagement_rate(period_rows)
        prev_rate = period_engagement_rate(prev_rows)
        if prev_rate:
            delta_eng = round((curr_rate - prev_rate) / prev_rate * 100.0, 1)
        if prev_posts:
            delta_posts = round((posts_tracked - prev_posts) / prev_posts * 100.0, 1)

    return {
        "daily_views": daily_views,
        "daily_engagement": daily_eng,
        "daily_engagement_rate": daily_engagement_rate,
        "daily_posts": daily_posts,
        "views_delta_pct": delta_views,
        "engagement_delta_pct": delta_eng,
        "posts_delta_pct": delta_posts,
    }


def stats_distribution(
    user_id: str,
    *,
    period_days: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Group analytics_posts rows by platform (summing views) and media_type
    (counting posts). Returns both the rich array form (with per-bucket views
    + post counts) used by the dashboard panels and the simple
    ``{platforms: {...}, media_types: {...}}`` shape promised by the
    architecture-reference doc — endpoint consumers can pick either.
    """
    rows, _all_rows = _fetch_dashboard_posts(
        user_id,
        period_days=period_days,
        platform=platform,
        source=source,
        username=username,
        limit=500,
    )
    return stats_distribution_from_rows(rows)


def stats_distribution_from_rows(period_rows: list[dict]) -> dict:
    """Platform + media-type buckets from a pre-fetched post set."""
    platform_buckets: dict[str, dict[str, int]] = {}
    media_buckets: dict[str, dict[str, int]] = {}
    for r in period_rows:
        plat = (r.get("platform") or "unknown").lower()
        pb = platform_buckets.setdefault(plat, {"value": 0, "posts": 0})
        pb["value"] += int(r.get("views") or 0)
        pb["posts"] += 1

        mt = (r.get("media_type") or "video").lower()
        # Collapse rare or unknown media types into "other" so the chart isn't
        # cluttered by long-tail buckets.
        if mt not in ("video", "image", "carousel"):
            mt = "other"
        mb = media_buckets.setdefault(mt, {"value": 0, "posts": 0})
        mb["value"] += int(r.get("total_engagement") or 0)
        mb["posts"] += 1

    platform_distribution = sorted(
        [{"key": k, **v} for k, v in platform_buckets.items()],
        key=lambda x: x["value"],
        reverse=True,
    )
    content_type_distribution = sorted(
        [{"key": k, **v} for k, v in media_buckets.items()],
        key=lambda x: x["posts"],
        reverse=True,
    )
    # Compact maps for the architecture-reference endpoint contract.
    platforms_map = {k: v["value"] for k, v in platform_buckets.items()}
    media_types_map = {k: v["posts"] for k, v in media_buckets.items()}

    return {
        "platform_distribution": platform_distribution,
        "content_type_distribution": content_type_distribution,
        "platforms": platforms_map,
        "media_types": media_types_map,
    }


def stats_cumulative(
    user_id: str,
    *,
    period_days: Optional[int] = None,
    platform: Optional[str] = None,
    source: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Daily cumulative totals over the active window — feeds the growth chart.

    The cumulative line includes posts older than the window so the curve
    reflects "lifetime accumulated" engagement at each day, not just what was
    added in-window. We seed the running totals from rows older than the
    cutoff so day 1 of the window is non-zero on accounts with prior history.

    Each point exposes ``cumulative_views`` / ``cumulative_engagement`` /
    ``cumulative_posts`` (per the architecture-reference contract) and also
    bare ``views`` / ``engagement`` / ``posts`` aliases so the existing FE
    chart doesn't need to know about the rename.
    """
    sb = get_supabase()
    span = max(int(period_days or 30), 1)
    today = datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=span - 1)

    qry = (
        sb.table("analytics_posts")
        .select(
            "views,total_engagement,posted_at,added_at,scraped_at,"
            "platform,source,username,media_type"
        )
        .eq("user_id", user_id)
    )
    if platform and platform != "all":
        qry = qry.eq("platform", platform)
    if source and source != "all":
        qry = qry.eq("source", source)
    if username:
        qry = qry.eq("username", username.lower())
    rows = (qry.limit(2000).execute()).data or []
    if not username:
        rows = _scope_rows_to_tracked_accounts(user_id, rows)

    daily: dict[str, dict[str, int]] = {}
    seed_views = 0
    seed_eng = 0
    seed_posts = 0
    for r in rows:
        bucket = _bucket_key(r)
        if not bucket:
            continue
        try:
            d = datetime.fromisoformat(bucket).date()
        except Exception:
            continue
        views = int(r.get("views") or 0)
        eng = int(r.get("total_engagement") or 0)
        if d < cutoff:
            seed_views += views
            seed_eng += eng
            seed_posts += 1
            continue
        b = daily.setdefault(bucket, {"views": 0, "engagement": 0, "posts": 0})
        b["views"] += views
        b["engagement"] += eng
        b["posts"] += 1

    points: list[dict] = []
    cum_v, cum_e, cum_p = seed_views, seed_eng, seed_posts
    for offset in range(span - 1, -1, -1):
        d = (today - timedelta(days=offset)).isoformat()
        slot = daily.get(d) or {"views": 0, "engagement": 0, "posts": 0}
        cum_v += slot["views"]
        cum_e += slot["engagement"]
        cum_p += slot["posts"]
        points.append({
            "date": d,
            # Architecture-reference contract names…
            "cumulative_views": cum_v,
            "cumulative_engagement": cum_e,
            "cumulative_posts": cum_p,
            # …with FE-friendly aliases so the chart can read either.
            "views": cum_v,
            "engagement": cum_e,
            "posts": cum_p,
        })

    return {
        "points": points,
        "total_views": cum_v,
        "total_engagement": cum_e,
        "total_posts": cum_p,
    }


# Backward-compat alias — the v3 dashboard hook previously imported
# ``cumulative_stats``; keep it pointing at the new function so we don't
# break in-flight code paths.
cumulative_stats = stats_cumulative


# ── analytics_scrape_jobs ───────────────────────────────────────────────────

def create_scrape_job(
    user_id: str,
    *,
    kind: str,
    input_value: str,
    platform: Optional[str] = None,
) -> dict:
    sb = get_supabase()
    result = (
        sb.table("analytics_scrape_jobs")
        .insert({
            "user_id": user_id,
            "kind": kind,
            "input": input_value,
            "platform": platform,
            "status": "pending",
        })
        .execute()
    )
    return result.data[0]


def update_scrape_job(job_id: str, updates: dict) -> None:
    sb = get_supabase()
    sb.table("analytics_scrape_jobs").update(updates).eq("id", job_id).execute()


def get_scrape_job(user_id: str, job_id: str) -> Optional[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_scrape_jobs")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", job_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


# ── analytics_tracked_accounts ──────────────────────────────────────────────

def list_tracked_accounts(user_id: str) -> list[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return res.data or []


def get_tracked_account(user_id: str, account_id: str) -> Optional[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", account_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def get_tracked_account_by_slug(
    user_id: str,
    *,
    platform: str,
    username: str,
) -> Optional[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", platform.strip().lower())
        .eq("username", username.strip().lower().lstrip("@"))
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def upsert_tracked_account(user_id: str, *, platform: str, username: str, extras: Optional[dict] = None) -> dict:
    sb = get_supabase()
    payload = {"user_id": user_id, "platform": platform, "username": username.lower()}
    if extras:
        payload.update({k: v for k, v in extras.items() if v is not None})
    res = (
        sb.table("analytics_tracked_accounts")
        .upsert(payload, on_conflict="user_id,platform,username")
        .execute()
    )
    return res.data[0]


def get_ayrshare_profile_key(user_id: str) -> Optional[str]:
    """Sub-profile UUID Ayrshare issued for JWT / posting (from `ayrshare_profiles`)."""
    sb = get_supabase()
    res = (
        sb.table("ayrshare_profiles")
        .select("ayrshare_profile_key")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    row = (res.data or [None])[0]
    return row["ayrshare_profile_key"] if row else None


def clear_studio_link_flags_missing(user_id: str, alive: set[tuple[str, str]]) -> None:
    """Reconcile the analytics_tracked_accounts table against the live set of
    Ayrshare-connected handles (``alive``) for ``user_id``.

    For every row currently flagged ``linked_via_connections=TRUE`` whose
    ``(platform, username)`` is **not** present in ``alive`` (i.e. the user
    just disconnected it on Ayrshare's portal):

      • If the row has any associated ``analytics_posts`` (Studio-published
        OR externally-scraped) — flip the flag to FALSE so it survives as
        an External tracked account, preserving the historical performance
        data the user might still want to read.
      • Otherwise — DELETE the row outright. These are the "I clicked
        Connect, then later clicked Disconnect, never scraped a post"
        cases, where leaving a stale row in the Accounts grid is the
        actual user complaint.

    `analytics_posts` rows are keyed by ``user_id + platform + username``
    (not by ``tracked_account_id``), so deleting the tracked-account row
    never orphans a post. Re-connecting later just re-creates the row.

    Tuple keys are lowercase (`platform`, `username_without_at`)."""
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .select("id,platform,username,linked_via_connections")
        .eq("user_id", user_id)
        .eq("linked_via_connections", True)
        .execute()
    )
    rows = res.data or []
    for row in rows:
        if not row.get("linked_via_connections"):
            continue
        platform = str(row.get("platform") or "").lower()
        username = str(row.get("username") or "").lower().lstrip("@")
        key = (platform, username)
        if key in alive:
            continue
        # Decide between flag-flip and hard-delete based on whether the
        # user has any historical analytics for this handle. Cheap COUNT
        # head-only query to keep the per-row cost minimal.
        post_check = (
            sb.table("analytics_posts")
            .select("id", count="exact", head=True)
            .eq("user_id", user_id)
            .eq("platform", platform)
            .eq("username", username)
            .execute()
        )
        post_count = post_check.count or 0
        if post_count > 0:
            sb.table("analytics_tracked_accounts").update(
                {"linked_via_connections": False}
            ).eq("id", row["id"]).execute()
        else:
            sb.table("analytics_tracked_accounts").delete().eq(
                "id", row["id"]
            ).execute()


def update_tracked_account_config(user_id: str, account_id: str, updates: dict) -> Optional[dict]:
    """Patch an existing tracked account row with v2 config fields (scrape
    frequency, top-N retention, active flag). Returns the updated row or None
    when the account doesn't belong to the user."""
    if not updates:
        return get_tracked_account(user_id, account_id)
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .update(updates)
        .eq("user_id", user_id)
        .eq("id", account_id)
        .execute()
    )
    return (res.data or [None])[0]


def save_account_strategy_report(
    user_id: str,
    account_id: str,
    report_markdown: str,
    *,
    locale: str = "en",
) -> None:
    """Persist the AI strategy report markdown onto the tracked-account row.

    Best-effort — swallows write errors so a failed save never bubbles into
    the fire-and-forget analyzer thread. Stored in the additive
    ``ai_strategy_report`` / ``ai_strategy_generated_at`` columns
    (migration 041).
    """
    try:
        from . import locale_content

        loc = locale_content.normalize_locale(locale)
        sb = get_supabase()
        (
            sb.table("analytics_tracked_accounts")
            .update({
                "ai_strategy_report": report_markdown,
                "ai_strategy_generated_at": _now(),
                "ai_strategy_report_locale": loc,
                "ai_strategy_report_i18n": {},
            })
            .eq("user_id", user_id)
            .eq("id", account_id)
            .execute()
        )
    except Exception:
        pass


def get_account_strategy_report(user_id: str, account_id: str) -> dict:
    """Return ``{report, generated_at}`` for one account (empty when unset).

    Defensive against the additive columns (migration 041) not yet being
    applied — returns an empty/pending payload rather than raising so the UI
    degrades to a "pending" state instead of erroring.
    """
    try:
        sb = get_supabase()
        res = (
            sb.table("analytics_tracked_accounts")
            .select(
                "ai_strategy_report,ai_strategy_generated_at,"
                "ai_strategy_report_locale,ai_strategy_report_i18n",
            )
            .eq("user_id", user_id)
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        return {
            "report": row.get("ai_strategy_report"),
            "generated_at": row.get("ai_strategy_generated_at"),
            "report_locale": row.get("ai_strategy_report_locale") or "en",
            "report_i18n": row.get("ai_strategy_report_i18n") or {},
        }
    except Exception:
        return {
            "report": None,
            "generated_at": None,
            "report_locale": "en",
            "report_i18n": {},
        }


def delete_tracked_account(user_id: str, account_id: str) -> bool:
    acct = get_tracked_account(user_id, account_id)
    if not acct:
        return False
    plat, nick = _normalize_account_slug(
        str(acct.get("platform") or ""),
        str(acct.get("username") or ""),
    )
    sb = get_supabase()
    if plat and nick:
        (
            sb.table("analytics_posts")
            .delete()
            .eq("user_id", user_id)
            .eq("platform", plat)
            .eq("username", nick)
            .execute()
        )
    res = (
        sb.table("analytics_tracked_accounts")
        .delete()
        .eq("user_id", user_id)
        .eq("id", account_id)
        .execute()
    )
    return bool(res.data)


def delete_post(user_id: str, post_id: str) -> bool:
    """Remove a single analytics post.

    `analytics_video_breakdowns` has `ON DELETE CASCADE` on its
    `analytics_post_id` FK (migration 033), so the breakdown row is
    cleaned up automatically — we don't have to touch it here.
    """
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .delete()
        .eq("user_id", user_id)
        .eq("id", post_id)
        .execute()
    )
    return bool(res.data)


def list_account_posts(
    user_id: str,
    *,
    platform: str,
    username: str,
    period_days: Optional[int] = None,
    limit: int = 500,
    source: Optional[str] = None,
    sort: str = "engagement",
) -> list[dict]:
    """All posts for one tracked account (used by aggregate + trend + top-N
    queries). Bounded at 500 — anything past that is well into the long tail
    and isn't worth the extra wire bytes for the dashboard."""
    sb = get_supabase()
    qry = (
        sb.table("analytics_posts")
        .select("*")
        .eq("user_id", user_id)
        .eq("platform", platform)
        .eq("username", username.lower())
    )
    if source:
        qry = qry.eq("source", source)
    # Period filtering is applied in Python via ``_filter_posts_by_period`` so
    # dashboard metrics use publish date (``posted_at``) rather than scrape
    # ingest time (``added_at``).
    if sort == "recent":
        qry = qry.order("posted_at", desc=True)
    else:
        qry = qry.order("total_engagement", desc=True)
    rows = qry.limit(min(limit, 500)).execute().data or []
    if period_days:
        rows = _filter_posts_by_period(rows, period_days)
    if sort == "recent":
        rows.sort(
            key=lambda r: str(r.get("posted_at") or r.get("added_at") or r.get("scraped_at") or ""),
            reverse=True,
        )
    return rows


def fetch_all_posts_for_account_aggregates(user_id: str, *, limit: int = 2000) -> list[dict]:
    """Single fetch for per-account dashboard aggregates."""
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select(
            "platform,username,views,total_engagement,posted_at,added_at,scraped_at",
        )
        .eq("user_id", user_id)
        .limit(min(max(int(limit or 2000), 1), 2000))
        .execute()
    )
    return res.data or []


def group_posts_by_account(posts: list[dict]) -> dict[tuple[str, str], list[dict]]:
    grouped: dict[tuple[str, str], list[dict]] = {}
    for post in posts:
        plat, nick = _normalize_account_slug(
            str(post.get("platform") or ""),
            str(post.get("username") or ""),
        )
        if plat and nick:
            grouped.setdefault((plat, nick), []).append(post)
    return grouped


def prune_account_posts_to_top_n(
    user_id: str, *, platform: str, username: str, top_n: int,
) -> int:
    """Keep only the top-N most-engaging posts for an account; delete the rest.
    Used after an account-scrape so we don't accumulate the long tail across
    refreshes (per migration 035 spec). Returns the number of deleted rows.

    Only deletes posts that came from BrightData scrapes (`source = 'external'`
    AND no `social_post_id`) — Studio-published posts and any post linked back
    to a `video_jobs` row are exempt so we never delete first-party data.
    """
    if top_n <= 0:
        return 0
    sb = get_supabase()
    # Fetch the full set ordered by engagement to figure out which IDs to keep.
    res = (
        sb.table("analytics_posts")
        .select("id,total_engagement,source,social_post_id")
        .eq("user_id", user_id)
        .eq("platform", platform)
        .eq("username", username.lower())
        .order("total_engagement", desc=True)
        .limit(1000)
        .execute()
    )
    rows = res.data or []
    if len(rows) <= top_n:
        return 0
    keep_ids = {r["id"] for r in rows[:top_n]}
    delete_ids = [
        r["id"] for r in rows[top_n:]
        if r.get("source") == "external" and not r.get("social_post_id")
        and r["id"] not in keep_ids
    ]
    if not delete_ids:
        return 0
    sb.table("analytics_posts").delete().in_("id", delete_ids).execute()
    return len(delete_ids)


# ── analytics_settings (per user) ──────────────────────────────────────────

def get_analytics_settings(user_id: str) -> dict:
    """Returns the user's settings row, falling back to system defaults if
    no row has been created yet (first-time visitors of the Settings modal)."""
    sb = get_supabase()
    res = (
        sb.table("analytics_settings")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    row = (res.data or [None])[0]
    if row:
        return row
    return {
        "user_id": user_id,
        "default_scrape_frequency": "daily",
        "default_top_n": DEFAULT_TOP_N,
        "monthly_budget_limit_usd": 10.00,
        "alert_threshold_usd": 0.05,
        "last_metrics_refreshed_at": None,
    }


def upsert_analytics_settings(user_id: str, updates: dict) -> dict:
    """Insert-or-update the user's settings row with the provided fields.
    Only keys explicitly present in `updates` are touched (lets the UI PATCH
    a single field without clobbering the others)."""
    payload = {"user_id": user_id, **{k: v for k, v in updates.items() if v is not None}}
    payload["updated_at"] = _now()
    res = _supabase_upsert("analytics_settings", payload, on_conflict="user_id")
    return res.data[0] if res.data else get_analytics_settings(user_id)


# ── analytics_video_breakdowns ──────────────────────────────────────────────

def get_breakdown_by_target(
    user_id: str,
    *,
    analytics_post_id: Optional[str] = None,
    video_job_id: Optional[str] = None,
) -> Optional[dict]:
    sb = get_supabase()
    qry = sb.table("analytics_video_breakdowns").select("*").eq("user_id", user_id)
    if analytics_post_id:
        qry = qry.eq("analytics_post_id", analytics_post_id)
    if video_job_id:
        qry = qry.eq("video_job_id", video_job_id)
    res = qry.limit(1).execute()
    return (res.data or [None])[0]


def get_breakdown_for_post(user_id: str, post: dict) -> Optional[dict]:
    """Resolve a breakdown row by analytics post id, then video_job_id fallback."""
    post_id = post.get("id")
    if post_id:
        row = get_breakdown_by_target(user_id, analytics_post_id=str(post_id))
        if row:
            return row
    video_job_id = post.get("video_job_id")
    if video_job_id:
        return get_breakdown_by_target(user_id, video_job_id=str(video_job_id))
    return None


def get_breakdown(user_id: str, breakdown_id: str) -> Optional[dict]:
    sb = get_supabase()
    res = (
        sb.table("analytics_video_breakdowns")
        .select("*")
        .eq("user_id", user_id)
        .eq("id", breakdown_id)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def create_breakdown(
    user_id: str,
    *,
    analytics_post_id: Optional[str] = None,
    video_job_id: Optional[str] = None,
) -> dict:
    sb = get_supabase()
    res = (
        sb.table("analytics_video_breakdowns")
        .insert({
            "user_id": user_id,
            "analytics_post_id": analytics_post_id,
            "video_job_id": video_job_id,
            "status": "pending",
        })
        .execute()
    )
    return res.data[0]


def _is_missing_optional_column_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "pgrst204" in text
        or "could not find" in text and "column" in text
    ) and any(col in text for col in _OPTIONAL_BREAKDOWN_COLUMNS)


def _parse_breakdown_timestamp(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        return None


def breakdown_is_stale(row: dict, *, max_age_sec: int = BREAKDOWN_STALE_SEC) -> bool:
    """True when a pending/running breakdown exceeded max_age without completing."""
    status = row.get("status")
    if status not in ("pending", "running"):
        return False
    ts = row.get("updated_at") or row.get("created_at")
    dt = _parse_breakdown_timestamp(ts)
    if not dt:
        return False
    age = datetime.now(timezone.utc) - dt
    return age.total_seconds() > max_age_sec


def fail_stale_breakdown_if_needed(breakdown_id: str, row: dict) -> Optional[dict]:
    """Mark orphaned pending/running rows failed so the UI can retry."""
    if not breakdown_is_stale(row):
        return None
    stale_at = _parse_breakdown_timestamp(row.get("updated_at") or row.get("created_at"))
    age_sec = (datetime.now(timezone.utc) - stale_at).total_seconds() if stale_at else 0
    logger.warning(
        "[analytics] failing stale breakdown id=%s status=%s age_sec=%.0f",
        breakdown_id,
        row.get("status"),
        age_sec,
    )
    update_breakdown(
        breakdown_id,
        {
            "status": "failed",
            "error_message": "Analysis interrupted — please retry.",
            "completed_at": _now(),
        },
    )
    user_id = str(row.get("user_id") or "")
    refreshed = get_breakdown(user_id, breakdown_id) if user_id else None
    return refreshed or {**row, "status": "failed", "error_message": "Analysis interrupted — please retry."}


def update_breakdown(breakdown_id: str, updates: dict) -> None:
    """Update a breakdown row. Strips optional columns and retries once if migrations
    063/064 have not been applied yet — analysis must keep working without them."""
    sb = get_supabase()
    payload = dict(updates)
    payload["updated_at"] = _now()
    try:
        sb.table("analytics_video_breakdowns").update(payload).eq("id", breakdown_id).execute()
    except Exception as exc:
        if not _is_missing_optional_column_error(exc):
            raise
        stripped = {k: v for k, v in payload.items() if k not in _OPTIONAL_BREAKDOWN_COLUMNS}
        if stripped == payload:
            raise
        logger.warning(
            "[analytics] optional breakdown columns missing — "
            "retrying without output_locale/locale_variants/updated_at: %s",
            exc,
        )
        sb.table("analytics_video_breakdowns").update(stripped).eq("id", breakdown_id).execute()


def list_breakdown_statuses_for_posts(user_id: str, posts: list[dict]) -> dict[str, str]:
    """Return {analytics_post_id: status} for each post in the list."""
    if not posts:
        return {}
    post_ids = [str(p["id"]) for p in posts if p.get("id")]
    video_job_ids = [str(p["video_job_id"]) for p in posts if p.get("video_job_id")]
    sb = get_supabase()
    out: dict[str, str] = {}

    if post_ids:
        res = (
            sb.table("analytics_video_breakdowns")
            .select("analytics_post_id,status")
            .eq("user_id", user_id)
            .in_("analytics_post_id", post_ids)
            .execute()
        )
        for row in res.data or []:
            pid = row.get("analytics_post_id")
            if pid:
                out[str(pid)] = row["status"]

    if video_job_ids:
        res = (
            sb.table("analytics_video_breakdowns")
            .select("video_job_id,status")
            .eq("user_id", user_id)
            .in_("video_job_id", video_job_ids)
            .execute()
        )
        job_status = {
            str(row["video_job_id"]): row["status"]
            for row in (res.data or [])
            if row.get("video_job_id")
        }
        for post in posts:
            pid = str(post.get("id") or "")
            if pid and pid in out:
                continue
            jid = post.get("video_job_id")
            if jid and str(jid) in job_status:
                out[pid] = job_status[str(jid)]

    return out


# ── social_posts back-link helpers ──────────────────────────────────────────

def find_social_post_by_url(user_id: str, post_url: str) -> Optional[dict]:
    """Best-effort backfill — if the user pasted a URL that matches one of our
    published Ayrshare posts we link the analytics row back to the social_post
    + video_job for free thumbnails and metadata."""
    if not post_url:
        return None
    sb = get_supabase()
    # Match either the canonical post URL stored in social_posts (if any) or
    # any post whose video_job's final_video_url matches. We only support the
    # exact-match case for now; the FE expects the user to paste the live URL.
    res = (
        sb.table("social_posts")
        .select("*")
        .eq("user_id", user_id)
        .limit(50)
        .execute()
    )
    for row in res.data or []:
        candidate = row.get("post_url") or row.get("permalink") or ""
        if candidate and candidate.rstrip("/") == post_url.rstrip("/"):
            return row
    return None


def get_video_job(user_id: str, video_job_id: str) -> Optional[dict]:
    """Load a video job, tolerating optional columns missing from older schemas."""
    sb = get_supabase()
    column_sets = (
        "id,user_id,final_video_url,preview_url,thumbnail_url,reference_image_url",
        "id,user_id,final_video_url,preview_url,reference_image_url",
        "id,user_id,final_video_url,preview_url",
        "id,user_id,final_video_url",
    )
    last_err: Optional[Exception] = None
    for columns in column_sets:
        try:
            res = (
                sb.table("video_jobs")
                .select(columns)
                .eq("user_id", user_id)
                .eq("id", video_job_id)
                .limit(1)
                .execute()
            )
            return (res.data or [None])[0]
        except Exception as err:
            last_err = err
            if _missing_column_from_error(err):
                continue
            raise
    if last_err:
        return None
    return None


def enrich_post_media_preview(
    user_id: str,
    post: dict,
    *,
    job: Optional[dict] = None,
) -> dict:
    """Ensure Studio / internal rows expose a stable poster + playable URL.

    Analytics list/detail UIs and the AI breakdown all expect
    ``thumbnail_url`` (image) and ``storage_video_url`` (mp4) to be populated.
    Studio sync stamps these when possible, but older rows — or rows synced
    before a video job finished rendering — may be missing them. We backfill
    from the linked ``video_jobs`` row without mutating the DB so every
    surface (By Video, post grid, single-post modal) renders the same preview.
    """
    vid = post.get("video_job_id")
    if not vid:
        return post

    if job is None:
        try:
            job = get_video_job(user_id, str(vid))
        except Exception:
            job = None
    if not job:
        return post

    if not post.get("storage_video_url") and job.get("final_video_url"):
        post["storage_video_url"] = job["final_video_url"]

    thumb = post.get("thumbnail_url")
    has_image_thumb = bool(
        thumb
        and not _is_video_preview_url(str(thumb))
        and (
            "supabase.co/storage" in str(thumb)
            or not _VIDEO_PREVIEW_RE.search(str(thumb))
        )
    )
    if not has_image_thumb:
        for key in ("thumbnail_url", "reference_image_url", "preview_url"):
            candidate = job.get(key)
            if candidate and not _is_video_preview_url(str(candidate)):
                post["thumbnail_url"] = candidate
                has_image_thumb = True
                break

    media = post.get("media_urls")
    if not media and job.get("final_video_url"):
        post["media_urls"] = [{"url": job["final_video_url"], "type": "video"}]

    return post


def enrich_posts_media_preview(user_id: str, posts: list[dict]) -> list[dict]:
    """Batch variant — one ``video_jobs`` lookup per distinct ``video_job_id``."""
    if not posts:
        return posts
    job_ids = {str(p["video_job_id"]) for p in posts if p.get("video_job_id")}
    cache: dict[str, Optional[dict]] = {}
    for jid in job_ids:
        try:
            cache[jid] = get_video_job(user_id, jid)
        except Exception:
            cache[jid] = None
    for p in posts:
        jid = p.get("video_job_id")
        enrich_post_media_preview(
            user_id,
            p,
            job=cache.get(str(jid)) if jid else None,
        )
    return posts


def sync_studio_publications(
    user_id: str,
    *,
    platform_usernames: dict[str, str],
    connected_platforms: Optional[set[str]] = None,
) -> int:
    """Mirror ``social_posts`` (scheduled + posted) into ``analytics_posts`` as
    ``source=internal`` so the Posts tab "Published Via Studio" filter works.

    Only platforms present in ``connected_platforms`` (OAuth-linked via
    Ayrshare) are synced — e.g. Instagram-only connections never surface
    TikTok rows from legacy ``social_posts`` scheduling attempts.
    """
    from ugc_db.db_manager import get_product_shot

    allowed = (
        connected_platforms
        if connected_platforms is not None
        else set(platform_usernames.keys())
    )
    if not allowed:
        return 0

    sb = get_supabase()
    res = (
        sb.table("social_posts")
        .select("*")
        .eq("user_id", user_id)
        .in_("status", ["posted", "scheduled", "posting"])
        .execute()
    )
    payload: list[dict] = []
    for sp in res.data or []:
        sp_id = sp.get("id")
        platform = (sp.get("platform") or "").strip().lower()
        if not sp_id or not platform or platform not in allowed:
            continue

        handle = (
            platform_usernames.get(platform)
            or sp.get("username")
            or "studio"
        )
        handle = str(handle).strip().lower().lstrip("@")

        post_url = f"studio://social-post/{sp_id}"
        media_type = "video"
        thumbnail: Optional[str] = None
        media_urls: list[dict] = []

        video_jid = sp.get("video_job_id")
        shot_id = sp.get("product_shot_id")
        storage_video: Optional[str] = None

        if video_jid:
            try:
                job = get_video_job(user_id, video_jid)
            except Exception:
                job = None
            if job:
                for key in ("thumbnail_url", "reference_image_url", "preview_url"):
                    candidate = job.get(key)
                    if candidate and not _is_video_preview_url(candidate):
                        thumbnail = candidate
                        break
                if job.get("final_video_url"):
                    storage_video = job["final_video_url"]
                    media_urls = [{"url": storage_video, "type": "video"}]
        elif shot_id:
            try:
                shot = get_product_shot(shot_id)
            except Exception:
                shot = None
            if shot:
                media_type = "image"
                img = shot.get("image_url") or shot.get("video_url") or shot.get("result_url")
                thumbnail = img
                if img:
                    media_urls = [{"url": img, "type": "image"}]

        row: dict = {
            "user_id": user_id,
            "source": "internal",
            "social_post_id": sp_id,
            "video_job_id": video_jid,
            "platform": platform,
            "username": handle,
            "post_url": post_url,
            "caption": sp.get("caption"),
            "hashtags": sp.get("hashtags"),
            "media_type": media_type,
            "media_urls": media_urls or None,
            "thumbnail_url": thumbnail,
            "posted_at": sp.get("posted_at") or sp.get("scheduled_at"),
        }
        if storage_video:
            row["storage_video_url"] = storage_video
        payload.append(row)

    if payload:
        upsert_posts(payload)
    return len(payload)


def purge_internal_off_connected_platforms(
    user_id: str,
    connected_platforms: set[str],
) -> int:
    """Remove Studio-published rows for platforms no longer OAuth-linked."""
    sb = get_supabase()
    res = (
        sb.table("analytics_posts")
        .select("id,platform")
        .eq("user_id", user_id)
        .eq("source", "internal")
        .execute()
    )
    delete_ids = [
        row["id"]
        for row in (res.data or [])
        if (row.get("platform") or "").strip().lower() not in connected_platforms
    ]
    if not delete_ids:
        return 0
    sb.table("analytics_posts").delete().in_("id", delete_ids).execute()
    return len(delete_ids)


def purge_external_for_studio_linked_accounts(user_id: str) -> int:
    """Drop BrightData-scraped posts for OAuth-linked handles — Studio accounts
    should only show content published through the app, not full profile scrapes."""
    sb = get_supabase()
    linked = (
        sb.table("analytics_tracked_accounts")
        .select("platform,username")
        .eq("user_id", user_id)
        .eq("linked_via_connections", True)
        .execute()
    )
    if not linked.data:
        return 0

    deleted = 0
    for acct in linked.data:
        plat = (acct.get("platform") or "").strip().lower()
        user = (acct.get("username") or "").strip().lower().lstrip("@")
        if not plat or not user:
            continue
        res = (
            sb.table("analytics_posts")
            .select("id")
            .eq("user_id", user_id)
            .eq("source", "external")
            .eq("platform", plat)
            .eq("username", user)
            .execute()
        )
        ids = [row["id"] for row in (res.data or []) if row.get("id")]
        if ids:
            sb.table("analytics_posts").delete().in_("id", ids).execute()
            deleted += len(ids)
    return deleted


def touch_metrics_refreshed(user_id: str) -> None:
    upsert_analytics_settings(user_id, {"last_metrics_refreshed_at": _now()})


# ── Feedback loop aggregation (analytics_strategy memory) ──────────────────
#
# These helpers feed the AI Analyzer (`ai_analyzer.py`) which writes the
# "Do More / Do Less" strategy report into `agent_memories`. They are
# intentionally additive — the legacy `stats()` and `list_posts()` contracts
# above are not modified.

def get_top_and_bottom_posts(
    user_id: str,
    *,
    limit: int = 5,
    period_days: Optional[int] = 30,
    platform: Optional[str] = None,
    username: Optional[str] = None,
) -> dict:
    """Fetch top and bottom performing posts by Engagement Rate for the AI analyzer.

    Per-post ER = (likes + comments + shares + saves) / follower_count × 100,
    using the stored ``total_engagement`` column when present (see
    ``post_engagement``). Uses each account's stored follower count from the
    latest scrape. When ``platform`` + ``username`` are supplied the scan is
    scoped to that single account (account-level strategy reports); otherwise
    it spans every tracked account (user-level feedback loop).
    """
    scope_plat = (platform or "").strip().lower() or None
    scope_nick = (username or "").strip().lower().lstrip("@") or None

    if scope_plat and scope_nick:
        rows = list_account_posts(
            user_id, platform=scope_plat, username=scope_nick, limit=500,
        )
    else:
        rows = list_posts(user_id, period_days=period_days, limit=500)

    scored: list[dict] = []
    follower_cache: dict[tuple[str, str], int] = {}

    for r in rows:
        plat = (r.get("platform") or "").strip().lower()
        nick = (r.get("username") or "").strip().lower().lstrip("@")
        if not plat or not nick:
            continue
        cache_key = (plat, nick)
        if cache_key not in follower_cache:
            acct = get_tracked_account_by_slug(user_id, platform=plat, username=nick)
            follower_cache[cache_key] = int(
                (acct or {}).get("follower_count")
                or (acct or {}).get("followers")
                or 0
            )
        fc = follower_cache[cache_key]
        if fc <= 0:
            continue
        r["_er"] = round(post_engagement(r) / fc * 100.0, 4)
        scored.append(r)

    if not scored:
        return {"top": [], "bottom": []}

    sorted_rows = sorted(scored, key=lambda r: r["_er"], reverse=True)
    top = sorted_rows[:limit]
    if len(sorted_rows) <= limit:
        bottom: list[dict] = []
    else:
        # Worst first — easier to read in the LLM prompt and matches the
        # natural reading order of "what to fix".
        bottom = list(reversed(sorted_rows[-limit:]))
    return {"top": top, "bottom": bottom}


# ── Self-improvement reflection loop (agent_memories) ───────────────────────
#
# These helpers feed the nightly reflection engine (`reflection_runner.py`)
# and the memory bootstrapper (`memory_bootstrapper.py`). Like the strategy
# report writer in `ai_analyzer.py` they touch `agent_memories` with the
# service-role client + explicit user scoping; the unique `(user_id, path)`
# index from migration 028 keeps upserts idempotent.

def get_agent_memory(user_id: str, path: str) -> Optional[dict]:
    """Fetch one `agent_memories` row (`id`, `content`, `updated_at`) or None."""
    sb = get_supabase()
    res = (
        sb.table("agent_memories")
        .select("id,content,updated_at")
        .eq("user_id", user_id)
        .eq("path", path)
        .limit(1)
        .execute()
    )
    return (res.data or [None])[0]


def upsert_agent_memory(user_id: str, path: str, content: str) -> None:
    """Insert-or-overwrite a memory file for one user.

    Same upsert shape as `ai_analyzer._save_strategy_to_memory` but raises on
    failure like the rest of this module — callers decide how to degrade.
    """
    sb = get_supabase()
    sb.table("agent_memories").upsert(
        {
            "user_id": user_id,
            "path": path,
            "content": content,
            "updated_at": _now(),
        },
        on_conflict="user_id,path",
    ).execute()


def list_breakdowns_for_posts(user_id: str, posts: list[dict]) -> dict[str, dict]:
    """Return {analytics_post_id: breakdown} for completed breakdowns only.

    Mirrors `list_breakdown_statuses_for_posts` (post-id pass, then
    video_job_id fallback for Studio rows) but returns the content columns
    the reflection prompt needs instead of just the status.
    """
    if not posts:
        return {}
    post_ids = [str(p["id"]) for p in posts if p.get("id")]
    video_job_ids = [str(p["video_job_id"]) for p in posts if p.get("video_job_id")]
    sb = get_supabase()
    columns = "analytics_post_id,video_job_id,status,summary,hook,takeaways"
    out: dict[str, dict] = {}

    if post_ids:
        res = (
            sb.table("analytics_video_breakdowns")
            .select(columns)
            .eq("user_id", user_id)
            .in_("analytics_post_id", post_ids)
            .execute()
        )
        for row in res.data or []:
            pid = row.get("analytics_post_id")
            if pid and row.get("status") == "completed":
                out[str(pid)] = row

    if video_job_ids:
        res = (
            sb.table("analytics_video_breakdowns")
            .select(columns)
            .eq("user_id", user_id)
            .in_("video_job_id", video_job_ids)
            .execute()
        )
        job_rows = {
            str(row["video_job_id"]): row
            for row in (res.data or [])
            if row.get("video_job_id") and row.get("status") == "completed"
        }
        for post in posts:
            pid = str(post.get("id") or "")
            if not pid or pid in out:
                continue
            jid = post.get("video_job_id")
            if jid and str(jid) in job_rows:
                out[pid] = job_rows[str(jid)]

    return out


def list_job_models_for_posts(user_id: str, posts: list[dict]) -> dict[str, str]:
    """Return {analytics_post_id: model_api} for Studio-published posts.

    Attribution comes from the linked `video_jobs.model_api` column (e.g.
    "seedance-2.0", "kling-3.0/video", "veo-3.1-fast"). Scraped/external
    posts have no `video_job_id` and are simply absent from the result.
    Tolerates schemas that predate `model_api` by returning {}.
    """
    job_ids = sorted({str(p["video_job_id"]) for p in posts if p.get("video_job_id")})
    if not job_ids:
        return {}
    sb = get_supabase()
    try:
        res = (
            sb.table("video_jobs")
            .select("id,model_api")
            .eq("user_id", user_id)
            .in_("id", job_ids)
            .execute()
        )
    except Exception as err:
        if _missing_column_from_error(err):
            return {}
        raise
    job_models = {
        str(row["id"]): str(row["model_api"])
        for row in (res.data or [])
        if row.get("id") and row.get("model_api")
    }
    return {
        str(p["id"]): job_models[str(p["video_job_id"])]
        for p in posts
        if p.get("id")
        and p.get("video_job_id")
        and str(p["video_job_id"]) in job_models
    }


def list_user_ids_with_active_tracked_accounts() -> list[str]:
    """Distinct user_ids that have at least one active tracked account.

    The one intentionally cross-user read in this module — it feeds the
    secret-guarded nightly sweep, which then processes each user strictly
    per-user through the existing pipeline.
    """
    sb = get_supabase()
    res = (
        sb.table("analytics_tracked_accounts")
        .select("user_id,is_active")
        .limit(10_000)
        .execute()
    )
    seen: list[str] = []
    for row in res.data or []:
        # Match the module-wide convention: only an explicit False is
        # inactive (legacy rows may carry NULL).
        if row.get("is_active") is False:
            continue
        uid = str(row.get("user_id") or "")
        if uid and uid not in seen:
            seen.append(uid)
    return seen


# ── Metric snapshots — engagement received over time (migration 070) ────────
#
# analytics_posts holds only the latest cumulative metrics. These helpers
# append a daily snapshot and compute "received in the last N days" deltas
# (current − snapshot at/before the window start), so the dashboard and the
# reflection loop can see engagement that accrued on OLDER posts — not just
# posts published inside the window. Ayrshare-independent (reads existing
# analytics_posts). All degrade to no-op/empty if the table is absent.

_SNAPSHOT_TABLE = "analytics_post_metric_snapshots"
_SNAPSHOT_METRICS = ("views", "likes", "comments", "shares", "saves", "total_engagement")


def _snapshot_table_missing(exc: Exception) -> bool:
    text = str(exc).lower()
    return "analytics_post_metric_snapshots" in text and (
        "does not exist" in text or "not find" in text or "42p01" in text
        or "pgrst205" in text or "could not find the table" in text
    )


def capture_metric_snapshots(user_id: str) -> int:
    """Append today's snapshot of every post's cumulative metrics.

    Deduped to one row per post per UTC day by the table's UNIQUE
    (analytics_post_id, captured_date). Returns rows offered for insert (0 on
    no posts or when the table doesn't exist yet). Best-effort — never raises.
    """
    sb = get_supabase()
    try:
        posts = (
            sb.table("analytics_posts")
            .select("id,views,likes,comments,shares,saves,total_engagement")
            .eq("user_id", user_id)
            .limit(2000)
            .execute()
        ).data or []
    except Exception as exc:
        logger.warning("[analytics] snapshot post fetch failed for %s: %s", user_id, exc)
        return 0
    if not posts:
        return 0

    today = datetime.now(timezone.utc).date().isoformat()
    rows = [
        {
            "user_id": user_id,
            "analytics_post_id": p["id"],
            "captured_date": today,
            **{m: p.get(m) for m in _SNAPSHOT_METRICS},
        }
        for p in posts
        if p.get("id")
    ]
    try:
        sb.table(_SNAPSHOT_TABLE).upsert(
            rows,
            on_conflict="analytics_post_id,captured_date",
            ignore_duplicates=True,
        ).execute()
    except Exception as exc:
        if _snapshot_table_missing(exc):
            logger.info("[analytics] snapshot table not present yet — skipping capture")
        else:
            logger.warning("[analytics] snapshot write failed for %s: %s", user_id, exc)
        return 0
    return len(rows)


def _baseline_snapshots(user_id: str, cutoff_iso: str) -> dict[str, dict]:
    """{analytics_post_id: latest snapshot with captured_at <= cutoff} — the
    baseline against which "received in period" is measured."""
    sb = get_supabase()
    try:
        rows = (
            sb.table(_SNAPSHOT_TABLE)
            .select("analytics_post_id,views,total_engagement,captured_at")
            .eq("user_id", user_id)
            .lte("captured_at", cutoff_iso)
            .order("captured_at", desc=True)
            .limit(5000)
            .execute()
        ).data or []
    except Exception as exc:
        if not _snapshot_table_missing(exc):
            logger.warning("[analytics] baseline snapshot fetch failed: %s", exc)
        return {}
    baseline: dict[str, dict] = {}
    for r in rows:  # desc order → first seen per post is the latest before cutoff
        pid = str(r.get("analytics_post_id") or "")
        if pid and pid not in baseline:
            baseline[pid] = r
    return baseline


def period_received_metrics(user_id: str, period_days: int) -> dict:
    """Engagement / views RECEIVED in the last ``period_days``.

    Per post: ``current − baseline`` where baseline is the snapshot at or
    before ``now − period_days`` (clamped at 0 to ignore metric corrections).
    Posts with no baseline snapshot yet don't contribute and are counted under
    ``posts_pending`` so the UI can show a "collecting data" state until
    history exists. Returns totals + per-post + per-account deltas.
    """
    now = datetime.now(timezone.utc)
    cutoff_iso = (now - timedelta(days=period_days)).isoformat()
    baseline = _baseline_snapshots(user_id, cutoff_iso)

    sb = get_supabase()
    current = (
        sb.table("analytics_posts")
        .select("id,platform,username,views,total_engagement")
        .eq("user_id", user_id)
        .limit(2000)
        .execute()
    ).data or []

    by_post: dict[str, dict] = {}
    by_account: dict[str, dict] = {}
    tot_v = tot_e = 0
    pending = 0
    for p in current:
        pid = str(p.get("id") or "")
        base = baseline.get(pid)
        if not base:
            pending += 1
            continue
        dv = max(0, int(p.get("views") or 0) - int(base.get("views") or 0))
        de = max(0, int(p.get("total_engagement") or 0) - int(base.get("total_engagement") or 0))
        by_post[pid] = {"views_received": dv, "engagement_received": de}
        tot_v += dv
        tot_e += de
        plat = (p.get("platform") or "").strip().lower()
        nick = (p.get("username") or "").strip().lower().lstrip("@")
        key = f"{plat} @{nick}"
        acc = by_account.setdefault(key, {"views_received": 0, "engagement_received": 0})
        acc["views_received"] += dv
        acc["engagement_received"] += de

    return {
        "period_days": period_days,
        "has_history": bool(baseline),
        "posts_measured": len(by_post),
        "posts_pending": pending,
        "totals": {"views_received": tot_v, "engagement_received": tot_e},
        "by_post": by_post,
        "by_account": by_account,
    }
