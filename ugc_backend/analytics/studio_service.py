"""Studio-published post sync helpers — Ayrshare metrics + auto AI breakdowns."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from ugc_backend import ayrshare_client
from ugc_db.db_manager import get_supabase

from . import ai_analyzer
from . import db as analytics_db
from . import jobs as analytics_jobs
from . import scraper_service

logger = logging.getLogger(__name__)

METRICS_REFRESH_INTERVAL_HOURS = 24
ANALYTICS_PLATFORMS = frozenset({"tiktok", "instagram", "youtube", "facebook"})

# Debounce background sync triggered by frequent GET /api/connections polls.
_SYNC_DEBOUNCE: dict[str, float] = {}
SYNC_DEBOUNCE_SECONDS = 15


def _coerce_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _best_int(blob: dict, *keys: str) -> int:
    """Return the largest numeric value among ``keys`` present in ``blob``."""
    vals = [_coerce_int(blob.get(k)) for k in keys if k in blob]
    return max(vals) if vals else 0


def _optional_best_int(blob: dict, *keys: str) -> Optional[int]:
    """Return the largest numeric among keys that are actually present."""
    vals: list[int] = []
    for k in keys:
        if k not in blob:
            continue
        v = _coerce_int(blob.get(k))
        if v is not None:
            vals.append(v)
    return max(vals) if vals else None


def normalize_ayrshare_metrics(platform: str, payload: dict) -> dict:
    """Map Ayrshare ``POST /analytics/post`` payload → analytics_posts columns."""
    plat = (platform or "").strip().lower()
    block = payload.get(plat) if isinstance(payload, dict) else None
    if not isinstance(block, dict):
        # Ayrshare sometimes keys by capitalized platform name.
        for key, val in (payload or {}).items():
            if isinstance(key, str) and key.lower() == plat and isinstance(val, dict):
                block = val
                break
    if not isinstance(block, dict):
        return {}

    analytics = block.get("analytics")
    if not isinstance(analytics, dict):
        analytics = block

    views = _optional_best_int(
        analytics,
        "viewsCount",
        "blueReelsPlayCount",
        "videoViews",
        "videoViewsUnique",
        "playCount",
        "viewCount",
        "views",
        "igReelsAggregatedAllPlaysCount",
        "playsCount",
        "clipsReplaysCount",
        "mediaView",
        "impressionCount",
        "videoViewCount",
    )
    likes = _optional_best_int(
        analytics,
        "likeCount",
        "likesCount",
        "diggCount",
        "favoriteCount",
        "engagementCount",
    )
    comments = _optional_best_int(
        analytics,
        "commentsCount",
        "commentCount",
        "replyCount",
        "totalFirstLevelComments",
    )
    shares = _optional_best_int(
        analytics,
        "shareCount",
        "sharesCount",
        "repostCount",
    )
    saves = _optional_best_int(analytics, "saveCount", "savedCount", "collectCount")

    # ── Deeper funnel metrics (v3 dashboard) ─────────────────────────────
    impressions = _optional_best_int(
        analytics,
        "impressionsCount", "impressions", "postImpressions",
        "impressionsUnique", "postImpressionsUnique",
    )
    reach = _optional_best_int(analytics, "reach", "reachCount", "postReach")
    clicks = _optional_best_int(
        analytics,
        "clickCount", "clicks", "linkClicks", "websiteClicks",
        "totalClicks", "postClicks",
    )

    out: dict = {}
    if views is not None:
        out["views"] = views
    if likes is not None:
        out["likes"] = likes
    if comments is not None:
        out["comments"] = comments
    if shares is not None:
        out["shares"] = shares
    if saves is not None:
        out["saves"] = saves
    if impressions is not None:
        out["impressions"] = impressions
    if reach is not None:
        out["reach"] = reach
    if clicks is not None:
        out["clicks"] = clicks
    # CTR — prefer Ayrshare's pre-computed value when present, otherwise
    # derive it from clicks/impressions when both are populated. Stored as a
    # 0.0–1.0 fraction (NUMERIC(6,4) on the column) so the FE can multiply
    # by 100 for display.
    raw_ctr = analytics.get("ctr") or analytics.get("clickThroughRate")
    if isinstance(raw_ctr, (int, float)):
        ctr_value = float(raw_ctr)
        # Ayrshare sometimes returns CTR as a percentage (e.g. 4.2 for 4.2%).
        if ctr_value > 1.0:
            ctr_value = ctr_value / 100.0
        out["ctr"] = round(max(0.0, min(1.0, ctr_value)), 4)
    elif clicks and impressions:
        out["ctr"] = round(min(1.0, clicks / impressions), 4)

    # When IG hasn't hit the 5-view insight threshold, fall back to reach.
    if "views" not in out and reach is not None and reach > 0:
        out["views"] = reach
    elif "views" not in out and impressions is not None and impressions > 0:
        out["views"] = impressions

    # ── media_type sync ─────────────────────────────────────────────────
    # Ayrshare keys vary by platform. Normalize to our four-bucket vocabulary
    # (video / image / carousel / other) so the dashboard's content-type
    # widget aggregates cleanly.
    raw_media = (
        block.get("mediaType")
        or block.get("postType")
        or analytics.get("mediaType")
        or analytics.get("postType")
    )
    normalized_media = _normalize_media_type(raw_media, analytics, block)
    if normalized_media:
        out["media_type"] = normalized_media

    post_url = block.get("postUrl") or analytics.get("postUrl")
    permalink: Optional[str] = None
    if isinstance(post_url, str) and post_url.strip():
        permalink = post_url.strip()[:8000]
        out["post_url"] = permalink
    ext_id = block.get("id") or analytics.get("id")
    shortcode = _instagram_shortcode(permalink) if permalink else None
    if shortcode:
        out["external_post_id"] = shortcode
    elif ext_id:
        out["external_post_id"] = str(ext_id)[:500]
    raw_merge: dict = {}
    if permalink:
        raw_merge["permalink"] = permalink
    if ext_id:
        raw_merge["ayrshare_id"] = str(ext_id)
    if raw_merge:
        out["_raw_payload_merge"] = raw_merge
    return out


def _normalize_media_type(raw: Any, *blobs: dict) -> Optional[str]:
    """Map a platform-specific media type string into one of
    ``video|image|carousel`` so the dashboard aggregates consistently.

    Falls back to inspecting `videoViews`/`videoLength` style fields when no
    explicit type is provided — covers TikTok payloads that don't ship a
    `mediaType` key but always carry video metrics.
    """
    text = str(raw or "").strip().lower()
    if text:
        if any(token in text for token in ("video", "reel", "short", "clip")):
            return "video"
        if "carousel" in text or "album" in text or "slideshow" in text:
            return "carousel"
        if any(token in text for token in ("image", "photo", "picture", "graphic")):
            return "image"
    # Fallback heuristics — sniff numeric fields that imply a video.
    for blob in blobs:
        if not isinstance(blob, dict):
            continue
        if any(blob.get(k) for k in ("videoViews", "videoLength", "videoDuration", "playCount")):
            return "video"
    return None


def resolve_internal_video_url(user_id: str, post: dict) -> Optional[str]:
    """Stable playable URL for Studio videos — mirrors prepare-video fast path."""
    if post.get("storage_video_url"):
        return str(post["storage_video_url"])

    post_id = post.get("id")
    video_jid = post.get("video_job_id")
    if video_jid:
        job = analytics_db.get_video_job(user_id, video_jid)
        if job and job.get("final_video_url"):
            url = str(job["final_video_url"])
            if post_id:
                try:
                    analytics_db.set_post_storage_video_url(post_id, url)
                except Exception:
                    pass
            return url

    media = post.get("media_urls") or []
    if isinstance(media, list) and media:
        entry = media[0]
        if isinstance(entry, dict) and entry.get("url"):
            return str(entry["url"])
        if isinstance(entry, str):
            return entry

    thumb = post.get("thumbnail_url")
    return str(thumb) if thumb else None


def post_metrics_dict(post: dict) -> dict:
    return {
        "views": post.get("views"),
        "likes": post.get("likes"),
        "comments": post.get("comments"),
        "shares": post.get("shares"),
        "saves": post.get("saves"),
        "duration_seconds": post.get("duration_seconds"),
    }


def _social_post_ready_for_metrics(sp: dict) -> bool:
    """True when Ayrshare should have live metrics for a scheduled/posted row."""
    err = (sp.get("error_message") or "").lower()
    if "[ayrshare:186]" in err or "[ayrshare:missing]" in err:
        return False
    status = (sp.get("status") or "").strip().lower()
    if status == "posted":
        return True
    if status != "scheduled":
        return False
    scheduled_at = sp.get("scheduled_at")
    if not scheduled_at:
        return False
    try:
        when = datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        return when <= datetime.now(timezone.utc)
    except (TypeError, ValueError):
        return False


_AYRSHARE_186_LOGGED: set[str] = set()


def _is_ayrshare_post_not_found(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "186" in msg or "post id not found" in msg


def _is_ayrshare_post_missing(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "221" in msg or "history not found" in msg or "not found" in msg


def apply_ayrshare_platform_urls(
    user_id: str,
    social_post_id: str,
    post_ids: list,
    platform: str,
) -> None:
    """Merge permalink + platform IDs from Ayrshare postIds onto analytics row."""
    post = analytics_db.get_analytics_post_by_social_post_id(user_id, social_post_id)
    if not post:
        return
    plat = (platform or "").strip().lower()
    raw_merge: dict = {}
    ext_patch: dict = {}
    for entry in post_ids or []:
        if not isinstance(entry, dict):
            continue
        if (entry.get("platform") or "").strip().lower() != plat:
            continue
        post_url = entry.get("postUrl")
        if isinstance(post_url, str) and post_url.strip():
            raw_merge["permalink"] = post_url.strip()[:8000]
        pid = entry.get("id")
        if pid:
            raw_merge["platform_post_id"] = str(pid)
        shortcode = _instagram_shortcode(
            post_url if isinstance(post_url, str) else None,
        )
        if shortcode:
            ext_patch["external_post_id"] = shortcode
        break
    if raw_merge:
        analytics_db.merge_post_raw_payload(post["id"], raw_merge)
    if ext_patch:
        analytics_db.patch_post_metrics(post["id"], ext_patch)


async def reconcile_scheduled_social_posts(
    user_id: str,
    profile_key: str,
) -> int:
    """Poll Ayrshare for past-due scheduled rows; flip status + store permalinks."""
    if not profile_key:
        return 0
    sb = get_supabase()
    res = (
        sb.table("social_posts")
        .select("*")
        .eq("user_id", user_id)
        .eq("status", "scheduled")
        .execute()
    )
    reconciled = 0
    now = datetime.now(timezone.utc)
    for sp in res.data or []:
        sp_id = sp.get("id")
        ayr_id = sp.get("ayrshare_post_id")
        if not sp_id or not ayr_id:
            continue
        scheduled_at = sp.get("scheduled_at")
        if not scheduled_at:
            continue
        try:
            when = datetime.fromisoformat(str(scheduled_at).replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when > now:
                continue
        except (TypeError, ValueError):
            continue
        platform = (sp.get("platform") or "").strip().lower()
        try:
            body = await ayrshare_client.get_post(profile_key, ayr_id)
        except Exception as exc:
            if _is_ayrshare_post_missing(exc):
                analytics_db.update_social_post(
                    user_id,
                    sp_id,
                    {
                        "status": "failed",
                        "error_message": "[ayrshare:missing] Post not found in Ayrshare.",
                        "updated_at": now.isoformat(),
                    },
                )
                reconciled += 1
            continue
        ayr_status = (body.get("status") or "").strip().lower()
        post_ids = body.get("postIds") or []
        if ayr_status == "success":
            updates: dict = {
                "status": "posted",
                "posted_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }
            analytics_db.update_social_post(user_id, sp_id, updates)
            apply_ayrshare_platform_urls(user_id, sp_id, post_ids, platform)
            reconciled += 1
        elif ayr_status == "error":
            analytics_db.update_social_post(
                user_id,
                sp_id,
                {
                    "status": "failed",
                    "error_message": (
                        body.get("message")
                        or "[ayrshare:missing] Ayrshare reported publish error."
                    ),
                    "updated_at": now.isoformat(),
                },
            )
            reconciled += 1
    return reconciled


def handle_ayrshare_webhook_post(
    ayrshare_id: str,
    payload: dict,
) -> None:
    """Enrich analytics rows when Ayrshare reports a successful publish."""
    sb = get_supabase()
    res = (
        sb.table("social_posts")
        .select("*")
        .eq("ayrshare_post_id", ayrshare_id)
        .limit(5)
        .execute()
    )
    for sp in res.data or []:
        user_id = sp.get("user_id")
        sp_id = sp.get("id")
        platform = sp.get("platform") or ""
        if not user_id or not sp_id:
            continue
        post_ids = payload.get("postIds") or []
        if post_ids:
            apply_ayrshare_platform_urls(user_id, sp_id, post_ids, platform)
        elif payload.get("postUrl"):
            apply_ayrshare_platform_urls(
                user_id,
                sp_id,
                [{"platform": platform, "postUrl": payload.get("postUrl")}],
                platform,
            )


def _instagram_shortcode(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    import re
    match = re.search(
        r"instagram\.com/(?:p|reel|reels|tv)/([^/?#]+)",
        url,
        re.IGNORECASE,
    )
    return match.group(1).lower() if match else None


def _metrics_patch_from_row(row: dict) -> dict:
    patch: dict = {}
    for key in (
        "views", "likes", "comments", "shares", "saves",
        "impressions", "reach", "clicks", "ctr",
    ):
        value = row.get(key)
        if value is None:
            continue
        if key == "views" and int(value or 0) <= 0:
            continue
        patch[key] = value
    return patch


def _internal_has_permalink(post: dict) -> bool:
    raw = post.get("raw_payload")
    if isinstance(raw, dict) and raw.get("permalink"):
        return True
    stored = post.get("post_url") or ""
    if isinstance(stored, str) and stored.strip() and not stored.startswith("studio://"):
        return bool(_instagram_shortcode(stored))
    return False


def _caption_match_key(post: dict) -> str:
    return (post.get("caption") or "").strip().lower()[:240]


def propagate_studio_metrics_to_scraped_posts(
    user_id: str,
    *,
    platform: str,
    username: str,
) -> int:
    """Copy metrics external←internal and permalinks internal←external.

    BrightData account scrapes create ``source=external`` rows with the public
    IG URL, while Schedule creates ``source=internal`` rows keyed by
    ``studio://``. Users see both in account detail — this keeps views and
    permalinks in sync.
    """
    plat = platform.strip().lower()
    nick = username.strip().lower().lstrip("@")
    posts = analytics_db.list_account_posts(
        user_id, platform=plat, username=nick, limit=500,
    )
    internal_by_code: dict[str, dict] = {}
    internal_by_ext: dict[str, dict] = {}
    internal_by_caption: dict[str, list[dict]] = {}
    for post in posts:
        if (post.get("source") or "") != "internal":
            continue
        patch = _metrics_patch_from_row(post)
        if patch:
            code = _instagram_shortcode(post.get("post_url"))
            if code:
                internal_by_code[code] = post
            ext_id = post.get("external_post_id")
            if ext_id:
                internal_by_ext[str(ext_id)] = post
        cap = _caption_match_key(post)
        if cap:
            internal_by_caption.setdefault(cap, []).append(post)

    updated = 0
    for post in posts:
        if (post.get("source") or "") != "external":
            continue

        ext_code = _instagram_shortcode(
            scraper_service.permalink_from_post(post) or post.get("post_url"),
        )
        ext_permalink = scraper_service.permalink_from_post(post)

        # Metrics: Studio → scraped duplicate
        if (post.get("views") or 0) <= 0:
            match: Optional[dict] = None
            if ext_code and ext_code in internal_by_code:
                match = internal_by_code[ext_code]
            elif post.get("external_post_id"):
                match = internal_by_ext.get(str(post.get("external_post_id")))
            if not match:
                cap = _caption_match_key(post)
                candidates = internal_by_caption.get(cap) or []
                match = candidates[0] if len(candidates) == 1 else None
            if match:
                patch = _metrics_patch_from_row(match)
                if patch:
                    analytics_db.patch_post_metrics(post["id"], patch)
                    updated += 1

        # Permalink: scraped duplicate → Studio row
        if ext_permalink and ext_code:
            cap = _caption_match_key(post)
            candidates = internal_by_caption.get(cap) or []
            for internal in candidates:
                if _internal_has_permalink(internal):
                    continue
                raw_merge = {"permalink": ext_permalink}
                ext_patch: dict = {}
                if ext_code:
                    ext_patch["external_post_id"] = ext_code
                analytics_db.merge_post_raw_payload(internal["id"], raw_merge)
                if ext_patch:
                    analytics_db.patch_post_metrics(internal["id"], ext_patch)
                updated += 1
                break

    return updated


def resolve_post_video_url(user_id: str, post: dict) -> Optional[str]:
    """Playable URL for AI breakdown — Studio jobs or mirrored external video."""
    if post.get("storage_video_url"):
        return str(post["storage_video_url"])
    if (post.get("source") or "") == "internal":
        return resolve_internal_video_url(user_id, post)
    return scraper_service._first_media_video_url(post)


def _post_is_video(post: dict) -> bool:
    mt = (post.get("media_type") or "").lower()
    if mt in ("video", "reel", "reels", "clip", "short"):
        return True
    if post.get("video_job_id"):
        return True
    if scraper_service._first_media_video_url(post):
        return True
    return False


def queue_breakdown_for_post(
    user_id: str,
    post: dict,
    *,
    force: bool = False,
) -> bool:
    """Enqueue Gemini breakdown for any video analytics row (Studio or external)."""
    post_id = post.get("id")
    if not post_id or not _post_is_video(post):
        return False

    video_job_id = post.get("video_job_id")
    is_studio_job = (post.get("source") or "") == "internal" and video_job_id

    existing = analytics_db.get_breakdown_for_post(user_id, post)

    if existing and existing["status"] in ("pending", "running"):
        if not analytics_db.breakdown_is_stale(existing):
            return False
    if existing and existing["status"] == "completed" and not force:
        return False

    from . import locale_content

    locale = locale_content.get_profile_ui_language(user_id)
    video_url = resolve_post_video_url(user_id, post)
    if not video_url:
        try:
            from . import scraper_service
            scraper_service.start_video_prep(user_id, post)
        except Exception as exc:
            logger.warning(
                "[analytics] video prep kickoff failed for post %s: %s",
                post_id,
                exc,
            )
        return False

    metrics = post_metrics_dict(post)

    if existing:
        analytics_db.update_breakdown(
            existing["id"],
            {
                "status": "pending",
                "summary": None,
                "hook": None,
                "scenes": None,
                "audio": None,
                "visual_details": None,
                "key_moments": None,
                "takeaways": None,
                "raw_markdown": None,
                "error_message": None,
                "completed_at": None,
                "locale_variants": {},
                "output_locale": locale,
            },
        )
        breakdown = existing
    elif is_studio_job:
        breakdown = analytics_db.create_breakdown(
            user_id,
            analytics_post_id=str(post_id),
            video_job_id=video_job_id,
        )
    else:
        breakdown = analytics_db.create_breakdown(
            user_id, analytics_post_id=str(post_id),
        )

    analytics_jobs.run_breakdown_in_background(
        breakdown_id=breakdown["id"],
        user_id=user_id,
        video_url=video_url,
        metrics=metrics,
        locale=locale,
    )
    return True


async def refresh_studio_post_metrics(
    user_id: str,
    profile_key: str,
    *,
    connected_platforms: Optional[set[str]] = None,
    platform: Optional[str] = None,
    username: Optional[str] = None,
) -> int:
    """Pull live engagement from Ayrshare for posted Studio content."""
    if profile_key:
        try:
            await reconcile_scheduled_social_posts(user_id, profile_key)
        except Exception as exc:
            logger.info(
                "[analytics] scheduled-post reconciliation skipped: %s",
                exc,
            )

    posts = analytics_db.list_internal_posts(user_id)
    refreshed = 0
    scope_platform = (platform or "").strip().lower() or None
    scope_username = (username or "").strip().lower().lstrip("@") or None

    for post in posts:
        platform = (post.get("platform") or "").strip().lower()
        if connected_platforms is not None and platform not in connected_platforms:
            continue
        if scope_platform and platform != scope_platform:
            continue
        post_username = (post.get("username") or "").strip().lower().lstrip("@")
        if scope_username and post_username != scope_username:
            continue

        sp_id = post.get("social_post_id")
        if not sp_id:
            continue
        sp = analytics_db.get_social_post(user_id, sp_id)
        if not sp or not _social_post_ready_for_metrics(sp):
            continue
        ayr_id = sp.get("ayrshare_post_id")
        if not ayr_id:
            continue

        platform = (platform or sp.get("platform") or "").strip().lower()
        if not platform:
            continue

        try:
            raw = await ayrshare_client.get_post_analytics(
                profile_key,
                ayr_id,
                platforms=[platform],
            )
            patch = normalize_ayrshare_metrics(platform, raw)
            if not patch:
                continue
            raw_merge = patch.pop("_raw_payload_merge", None)
            # Internal Studio rows must keep their stable key (``studio://…`` or
            # an existing permalink). Never rewrite ``post_url`` from Ayrshare —
            # a BrightData-scraped duplicate may already own that unique key.
            if (post.get("source") or "") == "internal":
                patch.pop("post_url", None)
            analytics_db.patch_post_metrics(post["id"], patch)
            if raw_merge:
                analytics_db.merge_post_raw_payload(post["id"], raw_merge)
            refreshed += 1
        except Exception as exc:
            post_key = str(post.get("id") or "")
            if _is_ayrshare_post_not_found(exc):
                sp_id = post.get("social_post_id")
                if sp_id:
                    analytics_db.update_social_post(
                        user_id,
                        sp_id,
                        {
                            "error_message": (
                                "[ayrshare:186] Post ID not found in Ayrshare analytics."
                            ),
                        },
                    )
                if post_key not in _AYRSHARE_186_LOGGED:
                    _AYRSHARE_186_LOGGED.add(post_key)
                    logger.info(
                        "[analytics] Ayrshare analytics unavailable for post %s "
                        "(code 186) — skipping until publish is reconciled.",
                        post_key,
                    )
            else:
                logger.warning(
                    "[analytics] Ayrshare metrics refresh failed for post %s: %s",
                    post.get("id"),
                    exc,
                )

    return refreshed


def enqueue_account_breakdowns(
    user_id: str,
    *,
    platform: str,
    username: str,
    force: bool = False,
) -> int:
    """Queue AI breakdowns for every video post on one tracked account."""
    plat = platform.strip().lower()
    nick = username.strip().lower().lstrip("@")
    posts = analytics_db.list_account_posts(
        user_id, platform=plat, username=nick, limit=500,
    )
    queued = 0
    for post in posts:
        try:
            if queue_breakdown_for_post(user_id, post, force=force):
                queued += 1
        except Exception as exc:
            logger.warning(
                "[analytics] breakdown queue skipped for post %s: %s",
                post.get("id"),
                exc,
            )
    return queued


def enqueue_all_account_breakdowns(
    user_id: str,
    *,
    force: bool = False,
) -> int:
    """Queue breakdowns for all video posts across every tracked account."""
    accounts = analytics_db.list_tracked_accounts(user_id)
    total = 0
    for acct in accounts:
        if acct.get("is_active") is False:
            continue
        total += enqueue_account_breakdowns(
            user_id,
            platform=acct["platform"],
            username=acct["username"],
            force=force,
        )
    return total


def enqueue_studio_breakdowns(
    user_id: str,
    *,
    force: bool = False,
    connected_platforms: Optional[set[str]] = None,
    platform: Optional[str] = None,
    username: Optional[str] = None,
) -> int:
    """Queue AI breakdowns for video posts (Studio + external) on scoped accounts."""
    if platform and username:
        return enqueue_account_breakdowns(
            user_id, platform=platform, username=username, force=force,
        )
    accounts = analytics_db.list_tracked_accounts(user_id)
    queued = 0
    scope_platform = (platform or "").strip().lower() or None
    scope_username = (username or "").strip().lower().lstrip("@") or None
    for acct in accounts:
        if acct.get("is_active") is False:
            continue
        plat = (acct.get("platform") or "").strip().lower()
        if connected_platforms is not None and plat not in connected_platforms:
            continue
        nick = (acct.get("username") or "").strip().lower().lstrip("@")
        if scope_platform and plat != scope_platform:
            continue
        if scope_username and nick != scope_username:
            continue
        queued += enqueue_account_breakdowns(
            user_id, platform=plat, username=nick, force=force,
        )
    return queued


def metrics_refresh_is_stale(
    settings: dict,
    *,
    hours: int = METRICS_REFRESH_INTERVAL_HOURS,
) -> bool:
    raw = settings.get("last_metrics_refreshed_at")
    if not raw:
        return True
    try:
        if isinstance(raw, str):
            last = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            last = raw
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        age_hours = (datetime.now(timezone.utc) - last).total_seconds() / 3600.0
        return age_hours >= hours
    except (TypeError, ValueError):
        return True


async def run_connected_accounts_pipeline(
    user_id: str,
    profile_key: Optional[str],
    platform_usernames: dict[str, str],
    *,
    force_metrics: bool = True,
    require_new_signal: bool = False,
) -> dict:
    """Sync Studio publications for OAuth-linked platforms only, purge stale
    rows, refresh Ayrshare metrics, and queue AI breakdowns.

    ``require_new_signal`` is only passed by the nightly sweep: it gates the
    LLM stages (strategy report + reflection) behind the deterministic
    signal fingerprint in ``reflection_runner.has_new_signal`` so quiet
    accounts cost zero tokens. Default False keeps every user-triggered
    call path exactly as before."""
    connected = {p.strip().lower() for p in platform_usernames.keys() if p}

    purged_internal = analytics_db.purge_internal_off_connected_platforms(
        user_id, connected,
    )
    # Keep BrightData-scraped feed rows for OAuth-linked handles — users
    # expect profile metrics on connect, not only Studio-scheduled posts.

    synced = analytics_db.sync_studio_publications(
        user_id,
        platform_usernames=platform_usernames,
        connected_platforms=connected,
    )

    metrics_refreshed = 0
    if profile_key and connected:
        settings = analytics_db.get_analytics_settings(user_id)
        if force_metrics or metrics_refresh_is_stale(settings):
            metrics_refreshed = await refresh_studio_post_metrics(
                user_id,
                profile_key,
                connected_platforms=connected,
            )
            analytics_db.touch_metrics_refreshed(user_id)
            if metrics_refreshed > 0:
                for plat, nick in platform_usernames.items():
                    propagate_studio_metrics_to_scraped_posts(
                        user_id, platform=plat, username=nick,
                    )

    breakdowns_queued = enqueue_studio_breakdowns(
        user_id,
        connected_platforms=connected,
    )

    # Feedback loop — kick off the AI strategy reports once we know there's
    # fresh data worth analyzing. Daemon-thread fire-and-forget so it never
    # delays the API response. See ``ai_analyzer.enqueue_strategy_report``.
    #   • user-level report  → agent_memories (creative-director feedback loop)
    #   • per-account reports → tracked-account rows (Account Detail modal)
    if metrics_refreshed > 0 or synced > 0:
        skip_llm = False
        if require_new_signal:
            # Nightly-sweep token gate — deterministic fingerprint compare,
            # zero LLM cost. Fails open inside has_new_signal.
            try:
                from . import reflection_runner

                skip_llm = not reflection_runner.has_new_signal(user_id)
            except Exception as exc:
                logger.warning(
                    "[analytics] signal gate failed for %s (running anyway): %s",
                    user_id,
                    exc,
                )
        if skip_llm:
            logger.info(
                "[analytics] no new signal for %s — skipping strategy report",
                user_id,
            )
        else:
            ai_analyzer.enqueue_strategy_report(user_id)
            ai_analyzer.enqueue_account_strategy_reports(user_id)

    return {
        "publications_synced": synced,
        "purged_internal": purged_internal,
        "purged_external": 0,
        "metrics_refreshed": metrics_refreshed,
        "breakdowns_queued": breakdowns_queued,
    }


def _metrics_from_scraped_row(row: dict) -> dict:
    return {
        k: row[k]
        for k in ("views", "likes", "comments", "shares", "saves")
        if row.get(k) is not None
    }


async def refresh_external_posts_for_account(
    user_id: str,
    *,
    platform: str,
    username: str,
    limit: int = 25,
) -> int:
    """Re-scrape external posts for one account that still show zero views."""
    plat = platform.strip().lower()
    nick = username.strip().lower().lstrip("@")
    posts = analytics_db.list_account_posts(
        user_id, platform=plat, username=nick, limit=max(limit, 50),
    )
    candidates = [
        p for p in posts
        if (p.get("source") or "") == "external"
        and not (p.get("views") or 0)
        and (p.get("post_url") or "").strip()
        and not str(p.get("post_url")).startswith("studio://")
    ][:limit]
    updated = 0
    for post in candidates:
        post_url = (post.get("post_url") or "").strip()
        try:
            result = await scraper_service.scrape(
                input_value=post_url,
                user_id=user_id,
                kind_override="post",
                platform_override=plat,
            )
        except Exception as exc:
            logger.warning(
                "[analytics] account external metrics refresh failed for %s: %s",
                post.get("id"),
                exc,
            )
            continue
        if not result.posts:
            continue
        row = dict(result.posts[0])
        row.pop("_owner_followers", None)
        row.pop("_owner_avatar_url", None)
        patch = _metrics_from_scraped_row(row)
        if patch:
            analytics_db.patch_post_metrics(post["id"], patch)
            updated += 1
    return updated


async def refresh_account_metrics(
    user_id: str,
    *,
    platform: str,
    username: str,
    profile_key: Optional[str] = None,
) -> dict:
    """Full metrics pass for one tracked account — Ayrshare, scrape backfill,
    duplicate propagation, and AI breakdown queueing."""
    plat = platform.strip().lower()
    nick = username.strip().lower().lstrip("@")

    studio_refreshed = 0
    if profile_key:
        studio_refreshed = await refresh_studio_post_metrics(
            user_id,
            profile_key,
            connected_platforms={plat},
            platform=plat,
            username=nick,
        )

    propagated = propagate_studio_metrics_to_scraped_posts(
        user_id, platform=plat, username=nick,
    )
    external_refreshed = await refresh_external_posts_for_account(
        user_id, platform=plat, username=nick, limit=25,
    )
    breakdowns_queued = enqueue_account_breakdowns(
        user_id,
        platform=plat,
        username=nick,
    )

    if studio_refreshed > 0 or propagated > 0 or external_refreshed > 0:
        ai_analyzer.enqueue_strategy_report(user_id)
        # Per-account report for the Account Detail modal.
        acct = analytics_db.get_tracked_account_by_slug(
            user_id, platform=plat, username=nick,
        )
        if acct and acct.get("id"):
            ai_analyzer.enqueue_strategy_report(user_id, account_id=acct["id"])

    return {
        "studio_refreshed": studio_refreshed,
        "propagated": propagated,
        "external_refreshed": external_refreshed,
        "breakdowns_queued": breakdowns_queued,
    }


async def refresh_external_posts_missing_metrics(
    user_id: str,
    *,
    limit: int = 25,
) -> int:
    """Re-scrape external posts that still show zero views (BrightData per-post)."""
    posts = analytics_db.list_posts_needing_metrics_refresh(
        user_id, source="external", limit=limit,
    )
    updated = 0
    for post in posts:
        post_url = (post.get("post_url") or "").strip()
        if not post_url or post_url.startswith("studio://"):
            continue
        platform = (post.get("platform") or "").strip().lower()
        if not platform:
            continue
        try:
            result = await scraper_service.scrape(
                input_value=post_url,
                user_id=user_id,
                kind_override="post",
                platform_override=platform,
            )
        except Exception as exc:
            logger.warning(
                "[analytics] external metrics refresh failed for %s: %s",
                post.get("id"),
                exc,
            )
            continue
        if not result.posts:
            continue
        row = dict(result.posts[0])
        row.pop("_owner_followers", None)
        row.pop("_owner_avatar_url", None)
        patch = _metrics_from_scraped_row(row)
        if patch:
            analytics_db.patch_post_metrics(post["id"], patch)
            updated += 1
    return updated


async def refresh_all_post_metrics(
    user_id: str,
    profile_key: Optional[str],
    *,
    include_external: bool = False,
) -> dict:
    """Studio (Ayrshare) view/engagement backfill, plus AI breakdowns.

    External (BrightData) accounts are intentionally *excluded* by default:
    per product policy they're analyzed once on first add and afterwards only
    when the user explicitly presses "Analyze" on the account card (which
    routes through ``POST /tracked-accounts/{id}/refresh``). Re-scraping them
    on every global refresh would burn BrightData credits and re-analyze
    accounts the user didn't ask to re-analyze. Pass ``include_external=True``
    only from an explicit per-account/manual path.
    """
    studio = 0
    external = 0
    if profile_key:
        try:
            platform_usernames = await _connected_platform_usernames(user_id, profile_key)
            connected = set(platform_usernames.keys())
            if connected:
                studio = await refresh_studio_post_metrics(
                    user_id,
                    profile_key,
                    connected_platforms=connected,
                )
                analytics_db.touch_metrics_refreshed(user_id)
        except Exception as exc:
            logger.warning("[analytics] studio metrics refresh: %s", exc)
    if include_external:
        try:
            external = await refresh_external_posts_missing_metrics(user_id)
        except Exception as exc:
            logger.warning("[analytics] external metrics refresh: %s", exc)
    return {"studio": studio, "external": external}


async def _connected_platform_usernames(
    user_id: str,
    profile_key: str,
) -> dict[str, str]:
    """Platform → @handle for OAuth-linked profiles (mirrors sync-studio-connections)."""
    try:
        socials_raw = await ayrshare_client.get_user_socials(profile_key)
    except Exception:
        return {}

    out: dict[str, str] = {}
    for blob in socials_raw:
        plat = (blob.get("platform") or "").strip().lower()
        if plat not in ANALYTICS_PLATFORMS:
            continue
        nick = str(blob.get("username") or "").strip().lower().lstrip("@")
        if nick:
            out[plat] = nick
    return out


async def sync_studio_connections_for_user(
    user_id: str,
    *,
    force_metrics: bool = False,
    skip_pipeline: bool = False,
    require_new_signal: bool = False,
) -> dict[str, int]:
    """Mirror OAuth-linked profiles into ``analytics_tracked_accounts``, sync
    Studio ``social_posts`` into ``analytics_posts``, refresh Ayrshare metrics,
    and queue AI breakdowns for Studio videos.

    Idempotent — safe on login, after OAuth connect, after scheduling, etc.
    """
    purged_orphans = analytics_db.purge_orphan_analytics_posts(user_id)
    if purged_orphans:
        logger.info(
            "[analytics] purged %s orphan analytics_posts for %s",
            purged_orphans,
            user_id,
        )
    profile_key = analytics_db.get_ayrshare_profile_key(user_id)
    platform_usernames: dict[str, str] = {}
    counts: dict[str, int] = {
        "linked_profiles": 0,
        "tracked_rows_linked": 0,
        "scrape_jobs_enqueued": 0,
        "publications_synced": 0,
    }

    async def _finish_pipeline() -> None:
        if not platform_usernames or skip_pipeline:
            return
        try:
            result = await run_connected_accounts_pipeline(
                user_id,
                profile_key,
                platform_usernames,
                force_metrics=force_metrics,
                require_new_signal=require_new_signal,
            )
            counts["publications_synced"] = int(result.get("publications_synced") or 0)
        except Exception as exc:
            logger.warning("[analytics] connected accounts pipeline failed: %s", exc)

    if not profile_key:
        return counts

    try:
        socials_raw = await ayrshare_client.get_user_socials(profile_key)
    except ayrshare_client.InvalidProfileKey:
        return counts
    except Exception as exc:
        logger.warning("[analytics] sync-studio-connections Ayrshare error: %s", exc)
        return counts

    alive: set[tuple[str, str]] = set()
    for blob in socials_raw:
        plat = (blob.get("platform") or "").strip().lower()
        if plat not in ANALYTICS_PLATFORMS:
            continue
        nick = str(blob.get("username") or "").strip().lower().lstrip("@")
        if nick:
            alive.add((plat, nick))

    analytics_db.clear_studio_link_flags_missing(user_id, alive)

    settings = analytics_db.get_analytics_settings(user_id)
    default_freq = settings.get("default_scrape_frequency") or "daily"
    default_top = int(settings.get("default_top_n") or analytics_db.DEFAULT_TOP_N)

    tracked_linked = 0
    for blob in socials_raw:
        plat = (blob.get("platform") or "").strip().lower()
        if plat not in ANALYTICS_PLATFORMS:
            continue
        username = str(blob.get("username") or "").strip().lower().lstrip("@")
        if not username:
            continue

        extras: dict = {"linked_via_connections": True}
        pic = blob.get("profilePic")
        if pic:
            extras["avatar_url"] = scraper_service.mirror_avatar_to_storage(
                image_url=str(pic)[:8000],
                user_id=user_id,
                slug=f"{plat}_{username}",
            ) or str(pic)[:8000]

        pre = analytics_db.get_tracked_account_by_slug(user_id, platform=plat, username=username)
        if pre is None:
            extras.setdefault("scrape_frequency", default_freq)
            extras.setdefault("top_n_retention", default_top)
            extras.setdefault("is_active", True)

        analytics_db.upsert_tracked_account(
            user_id, platform=plat, username=username, extras=extras,
        )
        tracked_linked += 1

    if tracked_linked:
        # Best-effort: seed /memories/creative_guidelines.md +
        # account_profile.md when absent (never overwrites existing rows).
        try:
            from . import memory_bootstrapper

            memory_bootstrapper.bootstrap_user_memories(user_id)
        except Exception as exc:
            logger.warning(
                "[analytics] memory bootstrap failed for %s: %s", user_id, exc,
            )

    for plat, nick in alive:
        platform_usernames[plat] = nick

    counts["linked_profiles"] = len(alive)
    counts["tracked_rows_linked"] = tracked_linked
    await _finish_pipeline()
    counts["scrape_jobs_enqueued"] = enqueue_auto_analyze_linked_accounts(
        user_id, profile_key, platform_usernames,
    )
    return counts


async def _background_sync_studio_connections(user_id: str) -> None:
    try:
        await sync_studio_connections_for_user(user_id, force_metrics=False)
    except Exception as exc:
        logger.warning("[analytics] background studio sync failed for %s: %s", user_id, exc)


async def run_studio_pipeline_background(
    user_id: str,
    profile_key: Optional[str],
    platform_usernames: dict[str, str],
    *,
    force_metrics: bool = False,
) -> None:
    """Metrics refresh + breakdown queue — never block read endpoints."""
    if not platform_usernames or not profile_key:
        return
    try:
        await run_connected_accounts_pipeline(
            user_id,
            profile_key,
            platform_usernames,
            force_metrics=force_metrics,
        )
    except Exception as exc:
        logger.warning("[analytics] background pipeline failed for %s: %s", user_id, exc)


# ── Nightly sweep (triggered by the Modal cron via the internal endpoint) ────

NIGHTLY_SWEEP_STAGGER_SECONDS = 3

# Most recent sweep summary, surfaced by the admin reflection viewer. Held in
# memory for the current process AND mirrored to Supabase Storage so the admin
# box reflects production regardless of which host/process serves the request
# (a plain Railway restart would otherwise wipe the in-memory copy).
_LAST_SWEEP: dict[str, Any] = {}
_LAST_SWEEP_BUCKET = "user-uploads"          # existing system-JSON bucket
_LAST_SWEEP_PATH = "system/reflection_last_sweep.json"


def _persist_last_sweep(record: dict) -> None:
    """Best-effort durable write of the sweep summary. Never raises."""
    try:
        import json as _json

        body = _json.dumps(record, sort_keys=True).encode("utf-8")
        get_supabase().storage.from_(_LAST_SWEEP_BUCKET).upload(
            _LAST_SWEEP_PATH, body,
            {"content-type": "application/json", "upsert": "true"},
        )
    except Exception as exc:
        logger.warning("[analytics] last-sweep persist failed: %s", exc)


def get_last_sweep() -> dict[str, Any]:
    """Latest nightly-sweep summary. Prefers the durable Storage copy (survives
    restarts / cross-process) and falls back to the in-memory record."""
    try:
        import json as _json

        buf = get_supabase().storage.from_(_LAST_SWEEP_BUCKET).download(_LAST_SWEEP_PATH)
        if buf:
            return _json.loads(buf.decode("utf-8"))
    except Exception:
        pass  # not-found on first run, or storage hiccup — use in-memory
    return dict(_LAST_SWEEP)


async def run_nightly_analytics_sweep() -> dict[str, int]:
    """Run the full analytics pipeline for every user with active tracked
    accounts — the autonomous path for users who never open the app.

    Reuses ``sync_studio_connections_for_user`` per user (scrape sync →
    metrics refresh → AI breakdowns → strategy report → chained reflection)
    with ``require_new_signal=True`` so the LLM stages only run for accounts
    whose data actually changed since the last reflection. Sequential with a
    small stagger to avoid hammering Ayrshare/Gemini/OpenAI.
    """
    user_ids = analytics_db.list_user_ids_with_active_tracked_accounts()
    counts = {"users_total": len(user_ids), "users_synced": 0, "users_failed": 0}
    started_at = datetime.now(timezone.utc).isoformat()
    _LAST_SWEEP.update(
        {"status": "running", "started_at": started_at, "finished_at": None, **counts}
    )
    await asyncio.to_thread(_persist_last_sweep, dict(_LAST_SWEEP))
    logger.info("[analytics] nightly sweep starting for %s users", len(user_ids))

    for i, user_id in enumerate(user_ids):
        if i:
            await asyncio.sleep(NIGHTLY_SWEEP_STAGGER_SECONDS)
        try:
            await sync_studio_connections_for_user(
                user_id,
                force_metrics=False,
                require_new_signal=True,
            )
            counts["users_synced"] += 1
        except Exception as exc:
            counts["users_failed"] += 1
            logger.warning(
                "[analytics] nightly sweep failed for %s: %s", user_id, exc
            )

    _LAST_SWEEP.update(
        {
            "status": "done",
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            **counts,
        }
    )
    await asyncio.to_thread(_persist_last_sweep, dict(_LAST_SWEEP))
    logger.info("[analytics] nightly sweep done: %s", counts)
    return counts


def start_nightly_sweep_thread() -> int:
    """Spawn the sweep on a daemon thread (the internal cron endpoint must
    return immediately). Returns the number of users that will be processed."""
    user_ids = analytics_db.list_user_ids_with_active_tracked_accounts()

    def _run() -> None:
        try:
            asyncio.run(run_nightly_analytics_sweep())
        except Exception as exc:
            logger.warning("[analytics] nightly sweep thread crashed: %s", exc)

    threading.Thread(
        target=_run,
        daemon=True,
        name="analytics-nightly-sweep",
    ).start()
    return len(user_ids)


def claim_debounced_sync(user_id: str) -> bool:
    """Return True when enough time passed since the last background sync."""
    now = time.monotonic()
    last = _SYNC_DEBOUNCE.get(user_id, 0.0)
    if now - last < SYNC_DEBOUNCE_SECONDS:
        return False
    _SYNC_DEBOUNCE[user_id] = now
    return True


def allow_immediate_sync(user_id: str) -> None:
    """Clear debounce so the next sync runs right away (e.g. after scheduling)."""
    _SYNC_DEBOUNCE.pop(user_id, None)


def _studio_account_needs_scrape(
    user_id: str,
    platform: str,
    username: str,
    account_row: Optional[dict],
) -> bool:
    """True when an OAuth-linked handle should auto-scrape its public feed."""
    if account_row is None or not account_row.get("last_scraped_at"):
        return True
    posts = analytics_db.list_account_posts(
        user_id,
        platform=platform,
        username=username,
        period_days=30,
    )
    if not posts:
        return True
    return metrics_refresh_is_stale(
        {"last_metrics_refreshed_at": account_row.get("last_scraped_at")},
        hours=24,
    )


def enqueue_auto_analyze_linked_accounts(
    user_id: str,
    profile_key: Optional[str],
    platform_usernames: dict[str, str],
) -> int:
    """Background BrightData scrape + Ayrshare pipeline for OAuth-linked rows."""
    enqueued = 0
    for plat, nick in platform_usernames.items():
        acct = analytics_db.get_tracked_account_by_slug(
            user_id, platform=plat, username=nick,
        )
        if not _studio_account_needs_scrape(user_id, plat, nick, acct):
            continue
        analytics_jobs.run_linked_account_analyze_in_background(
            user_id,
            platform=plat,
            username=nick,
            profile_key=profile_key,
            platform_usernames=dict(platform_usernames),
        )
        enqueued += 1
    return enqueued
