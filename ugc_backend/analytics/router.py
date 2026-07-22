"""FastAPI router for the Analytics module.

Mounted in ``ugc_backend/main.py`` with::

    from ugc_backend.analytics.router import router as analytics_router
    app.include_router(analytics_router)

All routes are under ``/api/analytics`` and require an authenticated user via
the existing ``get_current_user`` dependency.
"""

from __future__ import annotations

import csv
import hmac
import io
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ugc_backend.auth import get_current_user

from ugc_backend import ayrshare_client

from . import db as analytics_db
from . import jobs as analytics_jobs
from . import locale_content as analytics_locale
from . import reflection_runner
from . import scraper_service
from . import studio_service
from .models import (
    AccountAggregatesResponse,
    AccountStrategyReportResponse,
    AccountTopPostsResponse,
    AccountTrendResponse,
    AnalyticsPostOut,
    AnalyticsSettingsOut,
    AnalyticsSettingsPatch,
    AnalyzeVideoRequest,
    AnalyzeVideoResponse,
    BreakdownOut,
    CreativeGuidelinesResponse,
    CumulativeStatsResponse,
    EnsureThumbnailsRequest,
    EnsureThumbnailsResponse,
    PostDetailResponse,
    PostDurationPatch,
    PostRefreshRequest,
    PostsListResponse,
    RefreshAllResponse,
    RefreshStatusResponse,
    ScrapeRequest,
    ScrapeResponse,
    StatsResponse,
    SyncStudioConnectionsResponse,
    TrackedAccountAggregateOut,
    TrackedAccountConfigPatch,
    TrackedAccountCreate,
    TrackedAccountOut,
    TrackedAccountWithJob,
    TrendPoint,
    VideoPrepResponse,
)
from .url_parser import detect

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

DEFAULT_ANALYTICS_PERIOD = "7d"

_ANALYTICS_PLATFORMS = studio_service.ANALYTICS_PLATFORMS

_refresh_jobs: dict[str, dict] = {}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _period_days(period: Optional[str]) -> Optional[int]:
    return {"7d": 7, "30d": 30, "90d": 90, "all": None, None: None}.get(period or "all", None)


def _annotate_breakdown_status(user_id: str, posts: list[dict]) -> list[dict]:
    """Join breakdown status + stable media previews onto each post."""
    if not posts:
        return posts
    statuses = analytics_db.list_breakdown_statuses_for_posts(user_id, posts)
    for p in posts:
        p["breakdown_status"] = statuses.get(p["id"], "none")
        p["permalink"] = scraper_service.permalink_from_post(p)
    return analytics_db.enrich_posts_media_preview(user_id, posts)


def _platform_profile_url(platform: str, username: str) -> str:
    u = username.lstrip("@").lower()
    if platform == "instagram":
        return f"https://www.instagram.com/{u}/"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{u}"
    if platform == "youtube":
        return f"https://www.youtube.com/@{u}"
    if platform == "facebook":
        return f"https://www.facebook.com/{u}"
    return ""


def _effective_top_n(
    user_id: str,
    override: Optional[int],
    *,
    follower_count: Optional[int] = None,
) -> int:
    """Resolve top-N for a scrape job (see ``db.resolve_scrape_top_n``)."""
    return analytics_db.resolve_scrape_top_n(
        user_id, override, follower_count=follower_count,
    )


def _stable_avatar_url(
    user_id: str,
    *,
    platform: str,
    username: str,
    avatar_url: Optional[str],
) -> Optional[str]:
    """Mirror IG/TikTok CDN avatars into Supabase so the browser can render them."""
    if not avatar_url:
        return None
    if scraper_service._is_supabase_storage_url(avatar_url):
        return avatar_url
    slug = f"{platform}_{username.lstrip('@')}"
    mirrored = scraper_service.mirror_avatar_to_storage(
        image_url=avatar_url,
        user_id=user_id,
        slug=slug,
    )
    return mirrored or avatar_url


def _account_follower_count(account: dict) -> Optional[int]:
    fc = account.get("follower_count") or account.get("followers")
    try:
        return int(fc) if fc else None
    except (TypeError, ValueError):
        return None


async def _scrape_account_for_user(
    *, user_id: str, platform: str, username: str,
    top_n: Optional[int] = None,
    follower_count: Optional[int] = None,
    job_id: Optional[str] = None,
) -> dict:
    """Run an account-scrape end-to-end and return the result envelope used by
    `POST /tracked-accounts` and `POST /tracked-accounts/{id}/refresh`.

    Mirrors the same pipeline as `/scrape`: create job → BrightData (capped at
    top_n) → upsert_posts → mirror videos to Storage in background → finalize
    job → prune the long tail. Returns dict with `job_id`, `status`, `posts`,
    `error_message`.
    """
    profile_url = _platform_profile_url(platform, username)
    if not profile_url:
        return {"job_id": None, "status": "failed", "posts": [],
                "error_message": f"Unsupported platform: {platform}"}

    cap = _effective_top_n(user_id, top_n, follower_count=follower_count)
    if job_id:
        analytics_db.update_scrape_job(job_id, {"status": "running"})
    else:
        job = analytics_db.create_scrape_job(
            user_id, kind="account", input_value=profile_url, platform=platform
        )
        job_id = job["id"]
    result = await scraper_service.scrape(
        input_value=profile_url,
        user_id=user_id,
        job_id=job_id,
        kind_override="account",
        platform_override=platform,
        top_n=cap,
    )

    saved: list[dict] = []
    follower_count: Optional[int] = None
    avatar_url: Optional[str] = None
    if result.posts:
        # Peel off the `_owner_followers` side-channel before upsert (it's
        # not a column on analytics_posts; Supabase would reject the row).
        # We take the max across the scrape rather than the first one we
        # see — BrightData occasionally returns 0 for some rows and the
        # real value for others within the same snapshot.
        for row in result.posts:
            fc = row.pop("_owner_followers", None)
            if fc and fc > 0 and (follower_count is None or fc > follower_count):
                follower_count = fc
            av = row.pop("_owner_avatar_url", None)
            if av and not avatar_url:
                avatar_url = str(av)[:8000]

        rows = [{**row, "user_id": user_id} for row in result.posts]
        saved = analytics_db.upsert_posts(rows)
        scraper_service._mirror_posts_in_background(saved)
        # History preservation: no longer pruning the long tail — the
        # dashboard needs the full post history for accurate trend analysis.

    analytics_db.update_scrape_job(
        job_id,
        {
            "status": result.status,
            "posts_found": len(saved),
            "brightdata_calls": result.brightdata_calls,
            "estimated_cost_usd": result.estimated_cost_usd,
            "error_message": result.error_message,
            "completed_at": _iso_now() if result.status in ("completed", "failed") else None,
        },
    )
    if result.status == "pending":
        analytics_jobs.run_scrape_resume_in_background(
            user_id,
            job_id,
            kind="account",
            platform=platform,
            username=username,
            top_n=cap,
        )

    annotated = _annotate_breakdown_status(user_id, saved)
    account_extras: dict = {
        "total_posts": len(saved) or None,
    }
    # Only stamp last_scraped_at when the scrape finished in this request.
    # Pending BrightData snapshots update the timestamp when resume completes.
    if result.status == "completed":
        account_extras["last_scraped_at"] = _iso_now()
    if follower_count is not None:
        # Migration 035 added `follower_count`; legacy `followers` from
        # migration 033 is kept in lock-step so any older code path that
        # reads `followers` still sees a fresh value.
        account_extras["follower_count"] = follower_count
        account_extras["followers"] = follower_count
    if avatar_url:
        account_extras["avatar_url"] = _stable_avatar_url(
            user_id,
            platform=platform,
            username=username,
            avatar_url=avatar_url,
        )
    analytics_db.upsert_tracked_account(
        user_id,
        platform=platform,
        username=username,
        extras=account_extras,
    )
    import threading
    plat, nick = platform, username
    threading.Thread(
        target=lambda: studio_service.enqueue_account_breakdowns(
            user_id, platform=plat, username=nick,
        ),
        daemon=True,
        name=f"analytics-breakdowns-{username[:8]}",
    ).start()
    return {
        "job_id": job_id,
        "status": result.status,
        "posts": annotated,
        "error_message": result.error_message,
    }


# ── POST /scrape ────────────────────────────────────────────────────────────

@router.post("/scrape", response_model=ScrapeResponse)
async def api_scrape(
    body: ScrapeRequest,
    user: dict = Depends(get_current_user),
):
    user_id = user["id"]
    parsed = detect(body.input)
    kind = body.kind or parsed.kind
    if not parsed.platform and not body.platform:
        raise HTTPException(
            status_code=400,
            detail="Could not detect platform. Pass platform explicitly when using a bare handle.",
        )
    platform = parsed.platform or body.platform

    job = analytics_db.create_scrape_job(
        user_id,
        kind=kind,
        input_value=body.input,
        platform=platform,
    )
    job_id = job["id"]

    result = await scraper_service.scrape(
        input_value=body.input,
        user_id=user_id,
        job_id=job_id,
        kind_override=kind,
        platform_override=body.platform,
    )

    # If scraper returned posts, upsert and (optionally) backfill internal link.
    saved: list[dict] = []
    follower_count: Optional[int] = None
    avatar_url: Optional[str] = None
    if result.posts:
        rows = []
        for row in result.posts:
            # Side-channel fields from the normalisers — not columns on
            # analytics_posts. Strip before upsert; the values feed the
            # tracked-account upsert below so the AccountCard /
            # AccountDetailModal can render a real photo + follower count
            # right after the user pastes a single @handle into the
            # AnalyzeSearchBar (no separate profile-dataset round-trip).
            fc = row.pop("_owner_followers", None)
            if fc and fc > 0 and (follower_count is None or fc > follower_count):
                follower_count = fc
            av = row.pop("_owner_avatar_url", None)
            if av and not avatar_url:
                avatar_url = str(av)[:8000]
            row = {**row, "user_id": user_id}
            # Studio attribution from the internal twin (source stays
            # external; twins are collapsed at read time). See
            # persist_scrape_job_result for the rationale.
            try:
                twin = analytics_db.find_internal_twin(user_id, row)
            except Exception:
                twin = None
            if twin:
                row.setdefault("social_post_id", twin.get("social_post_id"))
                row.setdefault("video_job_id", twin.get("video_job_id"))
            rows.append(row)
        saved = analytics_db.upsert_posts(rows)
        # Best-effort mirror of each post's video URL (and/or thumbnail) to
        # Supabase Storage so inline playback + Gemini analysis use a stable
        # URL instead of the short-lived BrightData CDN one. Runs in a
        # daemon thread.
        scraper_service._mirror_posts_in_background(saved)

    # Auto-track the account if the input was an @handle / profile.
    tracked = None
    if kind == "account" and platform and parsed.username:
        track_extras: dict = {"last_scraped_at": _iso_now()}
        if follower_count is not None:
            track_extras["follower_count"] = follower_count
            track_extras["followers"] = follower_count
        if avatar_url:
            track_extras["avatar_url"] = _stable_avatar_url(
                user_id,
                platform=platform,
                username=parsed.username,
                avatar_url=avatar_url,
            )
        tracked = analytics_db.upsert_tracked_account(
            user_id,
            platform=platform,
            username=parsed.username,
            extras=track_extras,
        )

    analytics_db.update_scrape_job(
        job_id,
        {
            "status": result.status,
            "posts_found": len(saved),
            "brightdata_calls": result.brightdata_calls,
            "estimated_cost_usd": result.estimated_cost_usd,
            "error_message": result.error_message,
            "completed_at": _iso_now() if result.status in ("completed", "failed") else None,
        },
    )
    if result.status == "pending":
        analytics_jobs.run_scrape_resume_in_background(
            user_id,
            job_id,
            kind=kind,
            platform=platform,
            username=parsed.username if kind == "account" else None,
            top_n=_effective_top_n(user_id, None) if kind == "account" else None,
        )

    annotated = _annotate_breakdown_status(user_id, saved)
    return ScrapeResponse(
        job_id=job_id,
        status=result.status,  # type: ignore[arg-type]
        posts=[AnalyticsPostOut(**p) for p in annotated],
        tracked_account=TrackedAccountOut(**tracked) if tracked else None,
        error_message=result.error_message,
    )


# ── GET /posts ──────────────────────────────────────────────────────────────

@router.get("/posts", response_model=PostsListResponse)
def api_list_posts(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
    period: Optional[str] = Query(default=DEFAULT_ANALYTICS_PERIOD),
    platform: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    username: Optional[str] = Query(
        default=None,
        description="Filter to a single account (used by the Account filter pills).",
    ),
    sort: str = Query(default="engagement"),
    q: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=100),
):
    background_tasks.add_task(_background_stale_metrics_refresh, user["id"])
    rows = analytics_db.list_posts(
        user["id"],
        period_days=_period_days(period),
        platform=platform,
        source=source,
        username=username,
        sort=sort,
        q=q,
        limit=limit,
        cursor=cursor,
    )
    # Mixed-source listings collapse internal+external twins (one card per
    # physical post, fresh scraped metrics). Source-pinned views keep raw rows.
    if not source or source == "all":
        rows = analytics_db.dedupe_physical_posts(rows)
    annotated = _annotate_breakdown_status(user["id"], rows)
    next_cursor = annotated[-1]["scraped_at"] if len(annotated) == limit else None
    return PostsListResponse(
        items=[AnalyticsPostOut(**p) for p in annotated],
        next_cursor=next_cursor,
    )


# ── GET /posts/{id} ────────────────────────────────────────────────────────

@router.get("/posts/{post_id}", response_model=PostDetailResponse)
def api_get_post(
    post_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    locale = analytics_locale.resolve_request_locale(request, user["id"])
    post = analytics_db.get_post(user["id"], post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    annotated = _annotate_breakdown_status(user["id"], [post])[0]
    breakdown_row = analytics_db.get_breakdown_for_post(user["id"], post)
    if breakdown_row:
        stale = analytics_db.fail_stale_breakdown_if_needed(breakdown_row["id"], breakdown_row)
        if stale:
            breakdown_row = stale
        breakdown_row = analytics_locale.localize_breakdown(
            breakdown_row,
            locale,
            sync=analytics_locale.request_wants_sync_locale(request),
        )
    breakdown = BreakdownOut(**breakdown_row) if breakdown_row else None
    return PostDetailResponse(post=AnalyticsPostOut(**annotated), breakdown=breakdown)


# ── DELETE /posts/{id} ─────────────────────────────────────────────────────
#
# Lets the Posts grid surface a subtle "remove" affordance on each card so
# the user can prune the analyzed set. CASCADE on
# analytics_video_breakdowns(analytics_post_id) takes care of breakdown
# cleanup; we don't touch internal `social_posts` / `video_jobs` rows.

@router.delete("/posts/{post_id}")
def api_delete_post(
    post_id: str,
    user: dict = Depends(get_current_user),
):
    ok = analytics_db.delete_post(user["id"], post_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Post not found")
    return {"ok": True}


# ── POST /posts/refresh ────────────────────────────────────────────────────

@router.post("/posts/refresh", response_model=AnalyticsPostOut)
async def api_refresh_post(
    body: PostRefreshRequest,
    user: dict = Depends(get_current_user),
):
    post = analytics_db.get_post(user["id"], body.post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    job = analytics_db.create_scrape_job(
        user["id"], kind="post", input_value=post["post_url"], platform=post["platform"]
    )
    result = await scraper_service.scrape(
        input_value=post["post_url"],
        user_id=user["id"],
        job_id=job["id"],
        kind_override="post",
    )
    if result.posts:
        # Drop the side-channel metadata so the upsert payload is pure
        # analytics_posts columns. We don't bother capturing follower
        # count here — single-post refreshes don't justify writing it.
        for r in result.posts:
            r.pop("_owner_followers", None)
            r.pop("_owner_avatar_url", None)
        merged = [{**row, "user_id": user["id"]} for row in result.posts]
        saved = analytics_db.upsert_posts(merged)
        scraper_service._mirror_posts_in_background(saved)
        analytics_db.update_scrape_job(
            job["id"],
            {
                "status": "completed",
                "posts_found": len(saved),
                "brightdata_calls": result.brightdata_calls,
                "estimated_cost_usd": result.estimated_cost_usd,
                "completed_at": _iso_now(),
            },
        )
        if saved:
            return AnalyticsPostOut(**_annotate_breakdown_status(user["id"], [saved[0]])[0])
    analytics_db.update_scrape_job(
        job["id"], {"status": result.status, "error_message": result.error_message, "completed_at": _iso_now()}
    )
    return AnalyticsPostOut(**_annotate_breakdown_status(user["id"], [post])[0])


# ── POST /posts/{id}/duration ──────────────────────────────────────────────
#
# Cheap way to backfill `duration_seconds` for posts where BrightData didn't
# return it. The modal derives the value from the `<video>` element's
# `loadedmetadata` event (literally free) and POSTs it here so subsequent
# loads (and the AI breakdown) don't have to re-derive it.

@router.post("/posts/{post_id}/duration")
def api_set_post_duration(
    post_id: str,
    body: PostDurationPatch,
    user: dict = Depends(get_current_user),
):
    post = analytics_db.get_post(user["id"], post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    # Idempotent — overwriting an existing duration with a fresh one from the
    # currently-playing file is safe and lets us self-heal stale rows.
    analytics_db.set_post_duration(post_id, body.duration_seconds)
    return {"ok": True, "duration_seconds": body.duration_seconds}


# ── POST /posts/{id}/prepare-video ─────────────────────────────────────────
#
# Lazy-mirror endpoint used by the post detail modal. The frontend POSTs here
# once to kick off (or force-restart) prep, then polls GET …/status every ~2s
# until status="ready" or "failed".

def _video_prep_response(user_id: str, post_id: str, post: dict, state: dict) -> VideoPrepResponse:
    fresh = analytics_db.get_post(user_id, post_id) or post
    return VideoPrepResponse(
        status=state["status"],
        progress_pct=state.get("progress_pct", 0),
        error_message=state.get("error_message"),
        storage_video_url=fresh.get("storage_video_url"),
    )


@router.get("/posts/{post_id}/prepare-video/status", response_model=VideoPrepResponse)
def api_prepare_video_status(
    post_id: str,
    user: dict = Depends(get_current_user),
):
    post = analytics_db.get_post(user["id"], post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    state = scraper_service.video_prep_snapshot(user["id"], post)
    return _video_prep_response(user["id"], post_id, post, state)


@router.post("/posts/{post_id}/prepare-video", response_model=VideoPrepResponse)
def api_prepare_video(
    post_id: str,
    force: bool = Query(
        default=False,
        description="Restart a stuck in-memory prep job (orphaned after server reload).",
    ),
    user: dict = Depends(get_current_user),
):
    post = analytics_db.get_post(user["id"], post_id)
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    # Internal/UGC posts already have a stable URL via video_jobs.final_video_url —
    # surface that through storage_video_url so the modal can play it directly.
    if not post.get("storage_video_url") and post.get("video_job_id"):
        job = analytics_db.get_video_job(user["id"], post["video_job_id"])
        if job and job.get("final_video_url"):
            try:
                analytics_db.set_post_storage_video_url(post_id, job["final_video_url"])
                post["storage_video_url"] = job["final_video_url"]
            except Exception:
                pass  # Best-effort; the prep pipeline will handle the fallback.

    state = scraper_service.start_video_prep(user["id"], post, force=force)
    return _video_prep_response(user["id"], post_id, post, state)


# ── POST /analyze-video ────────────────────────────────────────────────────

@router.post("/analyze-video", response_model=AnalyzeVideoResponse)
def api_analyze_video(
    body: AnalyzeVideoRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    locale = analytics_locale.resolve_request_locale(request, user["id"])
    video_url: Optional[str] = None
    metrics: dict = {}
    post: Optional[dict] = None

    if body.analytics_post_id:
        post = analytics_db.get_post(user["id"], body.analytics_post_id)
        if not post:
            raise HTTPException(status_code=404, detail="Analytics post not found")
        # Prefer the Supabase-mirrored URL (stable, downloadable) over the
        # raw BrightData CDN URL (short-lived, CORS-restricted, often
        # unreachable by the time Gemini tries to fetch it). Final fallback
        # to the thumbnail is intentional — image-only analysis is poor but
        # better than nothing for posts where the mirror hasn't completed.
        video_url = post.get("storage_video_url")
        if not video_url:
            media_urls = post.get("media_urls") or []
            if isinstance(media_urls, list) and media_urls and isinstance(media_urls[0], dict):
                video_url = (media_urls[0] or {}).get("url")
        video_url = video_url or post.get("thumbnail_url")
        metrics = {
            "views": post.get("views"),
            "likes": post.get("likes"),
            "comments": post.get("comments"),
            "shares": post.get("shares"),
            "saves": post.get("saves"),
            "duration_seconds": post.get("duration_seconds"),
        }
    else:
        job = analytics_db.get_video_job(user["id"], body.video_job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Video job not found")
        video_url = job.get("final_video_url")

    if not video_url:
        raise HTTPException(
            status_code=422,
            detail=(
                "This post doesn't have a downloadable video yet. Try "
                "refreshing the post or wait a few seconds for the video "
                "mirror to finish."
            ),
        )

    if post:
        existing = analytics_db.get_breakdown_for_post(user["id"], post)
    else:
        existing = analytics_db.get_breakdown_by_target(
            user["id"], video_job_id=body.video_job_id,
        )
    if existing and existing["status"] in ("pending", "running"):
        if not analytics_db.breakdown_is_stale(existing):
            return AnalyzeVideoResponse(breakdown_id=existing["id"], status=existing["status"])

    if existing:
        # Re-run — reset row and kick off again.
        reset_payload = {
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
        }
        try:
            analytics_db.update_breakdown(existing["id"], reset_payload)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=(
                    "Could not reset the existing analysis row. "
                    "If this persists, ensure migration 063_analytics_locale_variants "
                    "has been applied to Supabase."
                ),
            ) from exc
        breakdown = existing
    else:
        create_post_id = body.analytics_post_id or (str(post["id"]) if post else None)
        breakdown = analytics_db.create_breakdown(
            user["id"],
            analytics_post_id=create_post_id,
            video_job_id=body.video_job_id,
        )

    analytics_jobs.run_breakdown_in_background(
        breakdown_id=breakdown["id"],
        user_id=user["id"],
        video_url=video_url,
        metrics=metrics,
        locale=locale,
    )
    return AnalyzeVideoResponse(breakdown_id=breakdown["id"], status="pending")


# ── GET /breakdowns/{id} ───────────────────────────────────────────────────

@router.get("/breakdowns/{breakdown_id}", response_model=BreakdownOut)
def api_get_breakdown(
    breakdown_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    locale = analytics_locale.resolve_request_locale(request, user["id"])
    row = analytics_db.get_breakdown(user["id"], breakdown_id)
    if not row:
        raise HTTPException(status_code=404, detail="Breakdown not found")
    stale = analytics_db.fail_stale_breakdown_if_needed(breakdown_id, row)
    if stale:
        row = stale
    row = analytics_locale.localize_breakdown(
        row,
        locale,
        sync=analytics_locale.request_wants_sync_locale(request),
    )
    return BreakdownOut(**row)


def _enqueue_studio_breakdowns(user_id: str) -> None:
    """Background hook — auto-run AI breakdowns for all video posts."""
    try:
        studio_service.enqueue_all_account_breakdowns(user_id)
    except Exception as e:
        print(f"[analytics] breakdown enqueue failed: {e}")


def _background_stale_metrics_refresh(user_id: str) -> None:
    """Refresh connected-account Ayrshare metrics when last refresh is >24h."""
    import asyncio

    try:
        settings = analytics_db.get_analytics_settings(user_id)
        if not studio_service.metrics_refresh_is_stale(settings):
            return
        profile_key = analytics_db.get_ayrshare_profile_key(user_id)
        if not profile_key:
            return

        async def _run() -> None:
            usernames = await studio_service._connected_platform_usernames(
                user_id, profile_key,
            )
            if usernames:
                await studio_service.run_connected_accounts_pipeline(
                    user_id,
                    profile_key,
                    usernames,
                    force_metrics=False,
                )

        asyncio.run(_run())
    except Exception as e:
        print(f"[analytics] stale metrics background refresh failed: {e}")


# ── /tracked-accounts ───────────────────────────────────────────────────────

@router.post("/sync-studio-connections", response_model=SyncStudioConnectionsResponse)
async def api_sync_studio_connections(
    background_tasks: BackgroundTasks,
    force: bool = Query(default=False, description="Force live Ayrshare metrics refresh"),
    user: dict = Depends(get_current_user),
):
    """Mirror OAuth-linked profiles into `analytics_tracked_accounts`.

    Linking completes in the HTTP response; metrics refresh runs in the
    background unless data is fresh (<24h) and ``force`` is false."""
    user_id = user["id"]
    settings = analytics_db.get_analytics_settings(user_id)
    counts = await studio_service.sync_studio_connections_for_user(
        user_id,
        force_metrics=force,
        skip_pipeline=True,
    )
    profile_key = analytics_db.get_ayrshare_profile_key(user_id)
    if profile_key:
        platform_usernames = await studio_service._connected_platform_usernames(
            user_id, profile_key,
        )
        should_refresh = force or studio_service.metrics_refresh_is_stale(settings)
        if platform_usernames and should_refresh:
            background_tasks.add_task(
                studio_service.run_studio_pipeline_background,
                user_id,
                profile_key,
                platform_usernames,
                force_metrics=True,
            )
    return SyncStudioConnectionsResponse(**counts)


async def _execute_refresh_all(user_id: str) -> None:
    """Background worker for POST /refresh-all."""
    _refresh_jobs[user_id] = {
        "status": "running",
        "started_at": _iso_now(),
        "finished_at": None,
        "error_message": None,
    }
    try:
        sync = await studio_service.sync_studio_connections_for_user(
            user_id,
            force_metrics=True,
            skip_pipeline=False,
        )
        profile_key = analytics_db.get_ayrshare_profile_key(user_id)
        metric_counts = await studio_service.refresh_all_post_metrics(
            user_id, profile_key, include_external=False,
        )
        metrics_refreshed = metric_counts.get("studio", 0) + metric_counts.get("external", 0)
        breakdowns_queued = studio_service.enqueue_all_account_breakdowns(
            user_id,
            force=False,
        )
        settings = analytics_db.get_analytics_settings(user_id)
        _refresh_jobs[user_id] = {
            "status": "completed",
            "started_at": _refresh_jobs[user_id].get("started_at"),
            "finished_at": _iso_now(),
            "error_message": None,
            "last_metrics_refreshed_at": settings.get("last_metrics_refreshed_at"),
            "publications_synced": sync.get("publications_synced", 0),
            "metrics_refreshed": metrics_refreshed,
            "breakdowns_queued": breakdowns_queued,
            "linked_profiles": sync.get("linked_profiles", 0),
            "tracked_rows_linked": sync.get("tracked_rows_linked", 0),
            "scrape_jobs_enqueued": sync.get("scrape_jobs_enqueued", 0),
        }
    except Exception as exc:
        settings = analytics_db.get_analytics_settings(user_id)
        _refresh_jobs[user_id] = {
            "status": "failed",
            "started_at": _refresh_jobs.get(user_id, {}).get("started_at"),
            "finished_at": _iso_now(),
            "error_message": str(exc),
            "last_metrics_refreshed_at": settings.get("last_metrics_refreshed_at"),
        }


@router.post("/refresh-all", response_model=RefreshAllResponse, status_code=202)
async def api_refresh_all(
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_current_user),
):
    """Full analytics refresh — queued for background processing.

    External (BrightData) accounts are deliberately NOT re-scraped here — they
    are analyzed once on first add and afterwards only via the per-account
    "Analyze" button (``POST /tracked-accounts/{id}/refresh``)."""
    user_id = user["id"]
    studio_service.allow_immediate_sync(user_id)
    _refresh_jobs[user_id] = {
        "status": "queued",
        "started_at": _iso_now(),
        "finished_at": None,
        "error_message": None,
    }
    background_tasks.add_task(_execute_refresh_all, user_id)
    return RefreshAllResponse(status="queued")


@router.get("/refresh-status", response_model=RefreshStatusResponse)
def api_refresh_status(user: dict = Depends(get_current_user)):
    """Poll refresh job state + last known metrics timestamp."""
    user_id = user["id"]
    settings = analytics_db.get_analytics_settings(user_id)
    job = _refresh_jobs.get(user_id) or {}
    status = job.get("status") or "idle"
    return RefreshStatusResponse(
        status=status,
        last_metrics_refreshed_at=settings.get("last_metrics_refreshed_at"),
        started_at=job.get("started_at"),
        finished_at=job.get("finished_at"),
        error_message=job.get("error_message"),
    )


@router.get("/tracked-accounts", response_model=list[TrackedAccountOut])
def api_list_tracked_accounts(user: dict = Depends(get_current_user)):
    rows = analytics_db.list_tracked_accounts(user["id"])
    return [TrackedAccountOut(**r) for r in rows]


@router.post("/tracked-accounts", response_model=TrackedAccountWithJob)
async def api_create_tracked_account(
    body: TrackedAccountCreate,
    user: dict = Depends(get_current_user),
):
    """Save the tracked account AND immediately scrape its recent posts.

    The auto-scrape is synchronous so the frontend's "Add" button surfaces
    the resulting posts in one round-trip — typical run is 8-15 seconds.
    Per-account refresh later goes through `POST /tracked-accounts/{id}/refresh`.

    v2 — body may include `scrape_frequency` and `top_n_retention`. When
    omitted, the user's analytics_settings defaults are inherited (so the
    Add Account modal can leave them blank if the user is fine with the
    tenant default).
    """
    settings = analytics_db.get_analytics_settings(user["id"])
    extras = {
        "scrape_frequency": body.scrape_frequency or settings.get("default_scrape_frequency") or "daily",
        "top_n_retention": body.top_n_retention or settings.get("default_top_n") or analytics_db.DEFAULT_TOP_N,
    }
    # Persist the row first so we always have it on file even if scraping fails.
    row = analytics_db.upsert_tracked_account(
        user["id"], platform=body.platform, username=body.username, extras=extras,
    )
    result = await _scrape_account_for_user(
        user_id=user["id"], platform=body.platform, username=body.username,
        top_n=extras["top_n_retention"],
        follower_count=None,
    )
    # Re-read the account so the response carries the freshly-stamped
    # last_scraped_at / total_posts.
    refreshed = analytics_db.get_tracked_account(user["id"], row["id"]) or row
    return TrackedAccountWithJob(
        account=TrackedAccountOut(**refreshed),
        job_id=result["job_id"],
        status=result["status"],
        posts=[AnalyticsPostOut(**p) for p in result["posts"]],
        error_message=result["error_message"],
    )


async def _refresh_tracked_account_pipeline(
    user_id: str,
    account_id: str,
    *,
    job_id: Optional[str] = None,
) -> dict:
    """Full refresh pipeline for one tracked account (scrape + metrics)."""
    account = analytics_db.get_tracked_account(user_id, account_id)
    if not account:
        return {
            "job_id": job_id,
            "status": "failed",
            "posts": [],
            "error_message": "Tracked account not found",
        }

    if account.get("linked_via_connections"):
        profile_key = analytics_db.get_ayrshare_profile_key(user_id)
        usernames = (
            await studio_service._connected_platform_usernames(user_id, profile_key)
            if profile_key
            else {}
        )
        result = await _scrape_account_for_user(
            user_id=user_id,
            platform=account["platform"],
            username=account["username"],
            top_n=account.get("top_n_retention"),
            follower_count=_account_follower_count(account),
            job_id=job_id,
        )
        if profile_key and usernames:
            await studio_service.run_connected_accounts_pipeline(
                user_id,
                profile_key,
                usernames,
                force_metrics=True,
            )
        await studio_service.refresh_account_metrics(
            user_id,
            platform=account["platform"],
            username=account["username"],
            profile_key=profile_key,
        )
        return result

    result = await _scrape_account_for_user(
        user_id=user_id,
        platform=account["platform"],
        username=account["username"],
        top_n=account.get("top_n_retention"),
        follower_count=_account_follower_count(account),
        job_id=job_id,
    )
    await studio_service.refresh_account_metrics(
        user_id,
        platform=account["platform"],
        username=account["username"],
        profile_key=None,
    )
    return result


@router.post("/tracked-accounts/{account_id}/refresh", response_model=TrackedAccountWithJob)
async def api_refresh_tracked_account(
    account_id: str,
    user: dict = Depends(get_current_user),
):
    """Refresh metrics for a tracked account.

    Returns immediately with a scrape ``job_id`` while BrightData / Ayrshare
    work runs in a background thread. Poll ``GET /scrape-jobs/{job_id}`` for
    completion, then re-fetch account posts.
    """
    user_id = user["id"]
    account = analytics_db.get_tracked_account(user_id, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Tracked account not found")

    profile_url = _platform_profile_url(account["platform"], account["username"])
    if not profile_url:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {account['platform']}")

    job = analytics_db.create_scrape_job(
        user_id,
        kind="account",
        input_value=profile_url,
        platform=account["platform"],
    )
    job_id = job["id"]
    analytics_db.update_scrape_job(job_id, {"status": "running"})

    analytics_jobs.run_account_refresh_in_background(
        user_id,
        account_id,
        job_id,
    )

    return TrackedAccountWithJob(
        account=TrackedAccountOut(**account),
        job_id=job_id,
        status="running",
        posts=[],
    )


@router.put("/tracked-accounts/{account_id}", response_model=TrackedAccountOut)
def api_update_tracked_account(
    account_id: str,
    body: TrackedAccountConfigPatch,
    user: dict = Depends(get_current_user),
):
    """Patch the per-account scrape config (frequency, top_n, active)."""
    account = analytics_db.get_tracked_account(user["id"], account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Tracked account not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        return TrackedAccountOut(**account)
    updated = analytics_db.update_tracked_account_config(user["id"], account_id, updates) or account
    return TrackedAccountOut(**updated)


@router.delete("/tracked-accounts/{account_id}")
def api_delete_tracked_account(
    account_id: str,
    user: dict = Depends(get_current_user),
):
    ok = analytics_db.delete_tracked_account(user["id"], account_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Tracked account not found")
    return {"ok": True}


@router.get(
    "/tracked-accounts/{account_id}/strategy-report",
    response_model=AccountStrategyReportResponse,
)
def api_account_strategy_report(
    account_id: str,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Latest AI "Do More / Do Less" strategy report for one tracked account.

    Returns ``report=null`` when none has been generated yet — the report is
    produced asynchronously by ``ai_analyzer`` after each account refresh, so
    the UI should treat a null report as "pending".
    """
    locale = analytics_locale.resolve_request_locale(request, user["id"])
    account = analytics_db.get_tracked_account(user["id"], account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Tracked account not found")
    data = analytics_db.get_account_strategy_report(user["id"], account_id)
    report = analytics_locale.localize_strategy_report(
        report=data.get("report"),
        report_locale=data.get("report_locale"),
        i18n_cache=data.get("report_i18n"),
        target_locale=locale,
        user_id=user["id"],
        account_id=account_id,
        sync=analytics_locale.request_wants_sync_locale(request),
    )
    return AccountStrategyReportResponse(
        account_id=account_id,
        report=report,
        generated_at=data.get("generated_at"),
    )


@router.get("/creative-guidelines", response_model=CreativeGuidelinesResponse)
def api_creative_guidelines(user: dict = Depends(get_current_user)):
    """The user-level "What Your AI Has Learned" guidelines panel.

    Reads the reflection loop's ``/memories/creative_guidelines.md`` from
    ``agent_memories`` and returns it cleaned for display. ``guidelines=null``
    means the AI hasn't learned enough yet (no reflection has run), which the
    UI treats as a "still learning" state — mirrors the null-is-pending
    contract of the account strategy report above.
    """
    row = analytics_db.get_agent_memory(
        user["id"], reflection_runner.GUIDELINES_PATH
    )
    cleaned = (
        reflection_runner.strip_guidelines_for_display(row.get("content"))
        if row
        else None
    )
    return CreativeGuidelinesResponse(
        guidelines=cleaned,
        updated_at=row.get("updated_at") if row else None,
    )


# ── GET /stats ──────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsResponse)
def api_stats(
    period: Optional[str] = Query(default=DEFAULT_ANALYTICS_PERIOD),
    platform: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Composed dashboard stats response.

    Blends three independently-shaped helpers in db.py — `stats()` (legacy
    KPI strip), `stats_extras()` (sparklines + period-over-period deltas),
    and `stats_distribution()` (platform / content-type breakdowns) — into
    the single ``StatsResponse`` shape consumed by the dashboard. Keeping
    the helpers separate respects the architecture guardrail to not mutate
    the legacy `stats()` contract while still letting the FE pull
    everything in one round-trip.
    """
    import time as _time
    _t0 = _time.perf_counter()
    days = _period_days(period)
    period_rows, all_rows = analytics_db._fetch_dashboard_posts(
        user["id"],
        period_days=days,
        platform=platform,
        source=source,
        username=username,
        limit=500,
    )
    base = analytics_db.stats_from_rows(
        user["id"],
        period_rows,
        all_rows,
        platform=platform,
        source=source,
        username=username,
    )
    extras = analytics_db.stats_extras_from_rows(
        period_rows, all_rows, period_days=days,
    )
    dist = analytics_db.stats_distribution_from_rows(period_rows)
    # Received-in-window deltas (engagement gained during the period, incl. on
    # older posts). Best-effort — empty until snapshot history exists.
    try:
        received = analytics_db.period_received_metrics(user["id"], days)
    except Exception:
        received = {"has_history": False, "posts_pending": 0,
                    "totals": {"views_received": 0, "engagement_received": 0}}
    _elapsed_ms = (_time.perf_counter() - _t0) * 1000
    if _elapsed_ms > 1500:
        print(
            f"[analytics perf] GET /stats user={str(user['id'])[:8]} "
            f"ms={_elapsed_ms:.0f} period_rows={len(period_rows)} all_rows={len(all_rows)}",
            flush=True,
        )
    return StatsResponse(
        **base,
        **extras,
        platform_distribution=dist["platform_distribution"],
        content_type_distribution=dist["content_type_distribution"],
        received_views=int(received.get("totals", {}).get("views_received") or 0),
        received_engagement=int(received.get("totals", {}).get("engagement_received") or 0),
        received_has_history=bool(received.get("has_history")),
        received_posts_pending=int(received.get("posts_pending") or 0),
        received_partial=bool(received.get("partial_window")),
        received_since=received.get("measured_since"),
    )


@router.get("/stats/distribution")
def api_stats_distribution(
    period: Optional[str] = Query(default=DEFAULT_ANALYTICS_PERIOD),
    platform: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Distribution endpoint — architecture-reference contract.

    Returns the compact ``{platforms, media_types}`` shape the architecture
    doc specifies. The richer array form is also embedded in `/stats`
    for the dashboard panels — both are kept in sync because they share
    the same underlying helper in db.py.
    """
    data = analytics_db.stats_distribution(
        user["id"],
        period_days=_period_days(period),
        platform=platform,
        source=source,
        username=username,
    )
    return {
        "platforms": data["platforms"],
        "media_types": data["media_types"],
    }


@router.get("/stats/cumulative", response_model=CumulativeStatsResponse)
def api_stats_cumulative(
    period: Optional[str] = Query(default=DEFAULT_ANALYTICS_PERIOD),
    platform: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    """Daily cumulative totals — feeds the dashboard's Cumulative Growth chart.

    Includes pre-period rows so the curve reflects lifetime-accumulated values
    at each day, not just what was added inside the window.
    """
    days = _period_days(period) or 30
    data = analytics_db.stats_cumulative(
        user["id"],
        period_days=days,
        platform=platform,
        source=source,
        username=username,
    )
    return CumulativeStatsResponse(**data)


# ── Accounts dashboard (v2) ────────────────────────────────────────────────
#
# Aggregates per-tracked-account metrics by running list_account_posts once
# per account. This is O(n_accounts) round-trips to Supabase but n is tiny
# (≤ a few dozen accounts per user in any realistic scenario) and the
# response payload is small enough that the FE doesn't need pagination here.


def _health_label_from_score(score: Optional[int]) -> str:
    """Map a 0-100 health score to the badge label the FE renders.
    Thresholds tuned around what looks sensible for engagement-rate norms
    (1%+ is healthy for an organic social account)."""
    if score is None:
        return "unknown"
    if score >= 70:
        return "good"
    if score >= 40:
        return "warning"
    return "at_risk"


def _compute_health_score(*, avg_engagement_rate: float, posts_in_period: int) -> Optional[int]:
    """Heuristic 0-100 health score. We weight engagement rate the most
    (a 5%+ rate maxes out the engagement component) and add a small bonus
    for "is the account actually posting" so dormant handles drop visibly
    below active ones with similar avg engagement rates."""
    if posts_in_period == 0:
        return 0
    # Engagement rate component — 0 at 0%, 80 at 5%+. Clamp.
    eng_component = min(80.0, (avg_engagement_rate / 5.0) * 80.0)
    # Cadence component — 20 if ≥4 posts in the period, scaled below that.
    cadence_component = min(20.0, (posts_in_period / 4.0) * 20.0)
    return int(round(eng_component + cadence_component))


@router.get("/accounts", response_model=AccountAggregatesResponse)
def api_list_accounts_with_aggregates(
    background_tasks: BackgroundTasks,
    period: Optional[str] = Query(default=DEFAULT_ANALYTICS_PERIOD),
    user: dict = Depends(get_current_user),
):
    import time as _time
    _t0 = _time.perf_counter()
    background_tasks.add_task(_background_stale_metrics_refresh, user["id"])
    period_days = _period_days(period)
    accounts = analytics_db.list_tracked_accounts(user["id"])
    all_posts = analytics_db.fetch_all_posts_for_account_aggregates(user["id"])
    posts_by_account = analytics_db.group_posts_by_account(all_posts)
    aggregates: list[TrackedAccountAggregateOut] = []
    total_posts_all = 0
    health_scores: list[int] = []

    for a in accounts:
        plat = (a.get("platform") or "").strip().lower()
        nick = (a.get("username") or "").strip().lower().lstrip("@")
        account_posts = posts_by_account.get((plat, nick), [])
        posts_in_period = analytics_db._filter_posts_by_period(account_posts, period_days)
        total_views = sum(int(p.get("views") or 0) for p in posts_in_period)
        total_eng = sum(int(p.get("total_engagement") or 0) for p in posts_in_period)
        posts_in_period_count = len(posts_in_period)
        followers = int(a.get("follower_count") or a.get("followers") or 0)
        avg_eng_rate = analytics_db.compute_engagement_rate(account_posts, followers)
        total_posts_all += posts_in_period_count
        score = a.get("health_score")
        if score is None:
            score = _compute_health_score(
                avg_engagement_rate=avg_eng_rate,
                posts_in_period=posts_in_period_count,
            )
        if score is not None:
            health_scores.append(score)
        aggregates.append(TrackedAccountAggregateOut(
            **a,
            total_views=total_views,
            total_engagement=total_eng,
            avg_engagement_rate=avg_eng_rate,
            posts_in_period=posts_in_period_count,
            health_label=_health_label_from_score(score),
        ))

    avg_health = round(sum(health_scores) / len(health_scores), 1) if health_scores else None
    _elapsed_ms = (_time.perf_counter() - _t0) * 1000
    if _elapsed_ms > 1500:
        print(
            f"[analytics perf] GET /accounts user={str(user['id'])[:8]} "
            f"ms={_elapsed_ms:.0f} accounts={len(accounts)} posts={len(all_posts)}",
            flush=True,
        )
    return AccountAggregatesResponse(
        accounts=aggregates,
        total_accounts=len(accounts),
        total_scraped_posts=total_posts_all,
        avg_health_score=avg_health,
    )


@router.get("/accounts/{account_id}/trend", response_model=AccountTrendResponse)
def api_account_trend(
    account_id: str,
    days: int = Query(default=30, ge=1, le=180),
    user: dict = Depends(get_current_user),
):
    account = analytics_db.get_tracked_account(user["id"], account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Tracked account not found")
    post_source = None if account.get("linked_via_connections") else None
    posts = analytics_db.list_account_posts(
        user["id"],
        platform=account["platform"],
        username=account["username"],
        period_days=days,
        source=post_source,
    )
    # Collapse internal+external twins so a Studio post scraped by BrightData
    # isn't summed twice into the daily buckets.
    posts = analytics_db.dedupe_physical_posts(posts)
    # Bucket posts by their posted_at (falling back to scraped_at) date so the
    # chart matches the user's mental model of "what got posted that day". Any
    # post missing both timestamps is dropped from the chart.
    buckets: dict[str, dict[str, int]] = {}
    for p in posts:
        ts = p.get("posted_at") or p.get("added_at") or p.get("scraped_at")
        if not ts:
            continue
        try:
            day = datetime.fromisoformat(ts.replace("Z", "+00:00")).date().isoformat()
        except Exception:
            continue
        b = buckets.setdefault(day, {"engagement": 0, "views": 0, "posts": 0})
        b["engagement"] += int(p.get("total_engagement") or 0)
        b["views"] += int(p.get("views") or 0)
        b["posts"] += 1
    # Backfill missing days with zeros so the chart shows a continuous x-axis.
    today = datetime.now(timezone.utc).date()
    points: list[TrendPoint] = []
    for offset in range(days - 1, -1, -1):
        d = (today - timedelta(days=offset)).isoformat()
        b = buckets.get(d, {"engagement": 0, "views": 0, "posts": 0})
        points.append(TrendPoint(date=d, engagement=b["engagement"], views=b["views"], posts=b["posts"]))
    return AccountTrendResponse(account_id=account_id, points=points)


@router.get("/accounts/{account_id}/top-posts", response_model=AccountTopPostsResponse)
def api_account_top_posts(
    account_id: str,
    limit: int = Query(default=48, ge=1, le=200),
    sort: str = Query(default="recent", pattern="^(recent|engagement)$"),
    user: dict = Depends(get_current_user),
):
    account = analytics_db.get_tracked_account(user["id"], account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Tracked account not found")

    plat = account["platform"]
    username = account["username"]
    user_id = user["id"]

    # Sync Studio metrics onto matching scraped duplicates (cheap DB patches).
    metrics_updated = studio_service.propagate_studio_metrics_to_scraped_posts(
        user_id,
        platform=plat,
        username=username,
    )

    # One full fetch for header averages; re-fetch only when propagation changed rows.
    all_posts = analytics_db.list_account_posts(
        user_id,
        platform=plat,
        username=username,
        source=None,
        sort=sort,
        limit=500,
    )
    if metrics_updated > 0:
        all_posts = analytics_db.list_account_posts(
            user_id,
            platform=plat,
            username=username,
            source=None,
            sort=sort,
            limit=500,
        )

    # Collapse internal+external twins: one card per physical post, fresh
    # scraped metrics on Studio rows. Also makes the Studio-vs-organic delta
    # below honest — it now compares Studio posts against genuinely-organic
    # posts instead of against stale copies of themselves.
    all_posts = analytics_db.dedupe_physical_posts(all_posts)

    # Studio-vs-external delta for the modal header (computed from full set).
    internal_eng = [int(p.get("total_engagement") or 0) for p in all_posts if p.get("source") == "internal"]
    external_eng = [int(p.get("total_engagement") or 0) for p in all_posts if p.get("source") == "external"]
    studio_avg = round(sum(internal_eng) / len(internal_eng), 1) if internal_eng else None
    external_avg = round(sum(external_eng) / len(external_eng), 1) if external_eng else None
    delta_pct: Optional[float] = None
    if studio_avg is not None and external_avg and external_avg > 0:
        delta_pct = round(((studio_avg - external_avg) / external_avg) * 100.0, 1)

    # Return only the requested page — no synchronous thumbnail mirroring on GET.
    page_posts = all_posts[:limit]
    top_posts = _annotate_breakdown_status(user_id, page_posts)

    # Kick off background mirroring for cards that still lack a stable poster.
    needs_mirror = [
        p for p in top_posts
        if not scraper_service._stable_image_thumbnail(p.get("thumbnail_url"))
    ]
    if needs_mirror:
        scraper_service._mirror_posts_in_background([
            {**p, "user_id": user_id} for p in needs_mirror
        ])

    return AccountTopPostsResponse(
        account_id=account_id,
        posts=[AnalyticsPostOut(**p) for p in top_posts],
        studio_avg_engagement=studio_avg,
        external_avg_engagement=external_avg,
        studio_vs_external_pct=delta_pct,
    )


# ── Thumbnail backfill (one-shot maintenance) ─────────────────────────────

@router.post("/posts/ensure-thumbnails", response_model=EnsureThumbnailsResponse)
def api_ensure_post_thumbnails(
    body: EnsureThumbnailsRequest,
    user: dict = Depends(get_current_user),
):
    """Mirror or generate stable poster images for analytics post cards.

    Fast path (image CDN copy + ffmpeg remote frame grab) runs synchronously.
    Full video mirrors are queued in the background so the UI can paint
    thumbnails progressively without blocking the account modal.
    """
    user_id = user["id"]
    post_ids = [pid for pid in (body.post_ids or []) if pid][:48]
    if not post_ids:
        return EnsureThumbnailsResponse(thumbnails={}, pending=0)

    rows = analytics_db.list_posts_by_ids(user_id, post_ids)
    if not rows:
        return EnsureThumbnailsResponse(thumbnails={}, pending=0)

    updated, deferred = scraper_service.ensure_post_thumbnails_sync(
        rows,
        user_id=user_id,
        allow_full_video_mirror=False,
    )
    if deferred:
        scraper_service._mirror_posts_in_background(deferred)

    thumbnails: dict[str, str] = {}
    for post in updated:
        pid = str(post.get("id") or "")
        thumb = post.get("thumbnail_url")
        if pid and scraper_service._stable_image_thumbnail(thumb):
            thumbnails[pid] = thumb

    return EnsureThumbnailsResponse(
        thumbnails=thumbnails,
        pending=len(deferred),
    )


@router.post("/posts/backfill-thumbnails")
def api_backfill_thumbnails(
    user: dict = Depends(get_current_user),
):
    """Re-mirror every post whose `thumbnail_url` still points at an
    external CDN (IG / TikTok) so the browser can render it without CORS
    failures.

    One-shot maintenance endpoint. Safe to call repeatedly — posts already
    pointing at our Supabase bucket are skipped. Returns a count of posts
    queued for re-mirror so the UI can show a toast.
    """
    posts = analytics_db.list_posts(
        user["id"], period_days=None, limit=500,
    )
    # Pretend none of them have been mirrored — the mirror helper itself
    # skips Storage-hosted thumbnails and only queues real candidates.
    scraper_service._mirror_posts_in_background([
        {**p, "user_id": user["id"]} for p in posts
    ])
    return {
        "queued": sum(
            1 for p in posts
            if p.get("thumbnail_url")
            and not scraper_service._is_supabase_storage_url(p.get("thumbnail_url"))
        ),
        "total": len(posts),
    }


# ── Scrape jobs log (account detail drawer) ───────────────────────────────

@router.get("/scrape-jobs/{job_id}")
def api_get_scrape_job(
    job_id: str,
    user: dict = Depends(get_current_user),
):
    """Poll a single scrape job — used while BrightData snapshots are still running."""
    row = analytics_db.get_scrape_job(user["id"], job_id)
    if not row:
        raise HTTPException(status_code=404, detail="Scrape job not found")
    return {
        "job_id": row["id"],
        "status": row.get("status"),
        "posts_found": row.get("posts_found") or 0,
        "error_message": row.get("error_message"),
    }


@router.get("/scrape-jobs")
def api_list_scrape_jobs(
    platform: Optional[str] = Query(default=None),
    input: Optional[str] = Query(default=None),
    limit: int = Query(default=20, le=100),
    user: dict = Depends(get_current_user),
):
    """Recent scrape jobs, optionally narrowed to a single (platform, input)
    tuple. Used by the lightweight "Scrape Jobs" drawer on the account
    detail modal. Returns minimal fields — no point sending the full row."""
    from ugc_db.db_manager import get_supabase
    sb = get_supabase()
    qry = (
        sb.table("analytics_scrape_jobs")
        .select("id,status,posts_found,estimated_cost_usd,error_message,started_at,completed_at,input")
        .eq("user_id", user["id"])
    )
    if platform:
        qry = qry.eq("platform", platform)
    if input:
        # `input` for account scrapes is the canonical profile URL — match
        # by ilike so a user typing `@nike` still surfaces jobs for
        # `https://instagram.com/nike/`.
        qry = qry.ilike("input", f"%{input}%")
    qry = qry.order("started_at", desc=True).limit(min(limit, 100))
    return {"jobs": (qry.execute().data or [])}


# ── Settings ──────────────────────────────────────────────────────────────

def _brightdata_configured() -> bool:
    return bool(os.getenv("BRIGHTDATA_API_KEY"))


@router.get("/settings", response_model=AnalyticsSettingsOut)
def api_get_settings(user: dict = Depends(get_current_user)):
    row = analytics_db.get_analytics_settings(user["id"])
    return AnalyticsSettingsOut(
        default_scrape_frequency=row.get("default_scrape_frequency") or "daily",
        default_top_n=int(row.get("default_top_n") or analytics_db.DEFAULT_TOP_N),
        monthly_budget_limit_usd=float(row.get("monthly_budget_limit_usd") or 10.00),
        alert_threshold_usd=float(row.get("alert_threshold_usd") or 0.05),
        brightdata_configured=_brightdata_configured(),
    )


@router.put("/settings", response_model=AnalyticsSettingsOut)
def api_update_settings(
    body: AnalyticsSettingsPatch,
    user: dict = Depends(get_current_user),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    saved = analytics_db.upsert_analytics_settings(user["id"], updates)
    return AnalyticsSettingsOut(
        default_scrape_frequency=saved.get("default_scrape_frequency") or "daily",
        default_top_n=int(saved.get("default_top_n") or analytics_db.DEFAULT_TOP_N),
        monthly_budget_limit_usd=float(saved.get("monthly_budget_limit_usd") or 10.00),
        alert_threshold_usd=float(saved.get("alert_threshold_usd") or 0.05),
        brightdata_configured=_brightdata_configured(),
    )


# ── CSV Export ────────────────────────────────────────────────────────────
#
# Streams the currently-filtered post list as CSV. Reuses the same query
# params as GET /posts so a frontend that already knows how to build them
# can hit /export/csv with identical args and get a 1:1 export.

@router.get("/export/csv")
def api_export_csv(
    period: Optional[str] = Query(default=DEFAULT_ANALYTICS_PERIOD),
    platform: Optional[str] = Query(default=None),
    source: Optional[str] = Query(default=None),
    username: Optional[str] = Query(default=None),
    sort: str = Query(default="engagement"),
    q: Optional[str] = Query(default=None),
    user: dict = Depends(get_current_user),
):
    rows = analytics_db.list_posts(
        user["id"],
        period_days=_period_days(period),
        platform=platform,
        source=source,
        username=username,
        sort=sort,
        q=q,
        limit=500,  # CSV exports are typically used for full-period snapshots
    )

    def _iter() -> "io.StringIO":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "post_id", "platform", "username", "source", "post_url",
            "posted_at", "added_at", "views", "likes", "comments",
            "shares", "saves", "total_engagement", "caption",
        ])
        for r in rows:
            writer.writerow([
                r.get("id", ""), r.get("platform", ""), r.get("username", ""),
                r.get("source", ""), r.get("post_url", ""),
                r.get("posted_at", "") or "", r.get("added_at", "") or "",
                r.get("views") or 0, r.get("likes") or 0, r.get("comments") or 0,
                r.get("shares") or 0, r.get("saves") or 0,
                r.get("total_engagement") or 0,
                (r.get("caption") or "").replace("\n", " ").replace("\r", " "),
            ])
        buf.seek(0)
        # Stream in one chunk — datasets are bounded at 500 rows so memory is
        # never a concern. Avoids the complexity of incremental generation.
        yield buf.getvalue()

    filename = f"analytics_{period or 'all'}_{datetime.now(timezone.utc).date().isoformat()}.csv"
    return StreamingResponse(
        _iter(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Brand research: audience layer (Slice 2) ────────────────────────────────

@router.post("/research/audience/refresh", status_code=202)
async def api_refresh_audience_research(user: dict = Depends(get_current_user)):
    """Kick a background audience-research pass (Reddit subs + PAA -> records
    -> personas -> brief). Costs a few cents of scraper credit per run."""
    from ugc_backend.research.audience import enqueue_audience_research

    enqueue_audience_research(user["id"])
    return {"status": "started"}


@router.get("/research/audience")
async def api_get_audience_research(user: dict = Depends(get_current_user)):
    """Audience research for the Market Intelligence tab + persona viewer.

    Observations ship with their provenance (source_url + scraped_at) —
    records without it cannot exist by schema, so 'no provenance, no
    display' holds. Personas are interpretations and are labelled as such
    with their supporting-observation count."""
    from ugc_db.db_manager import get_supabase

    from ugc_backend.research import records as research_records

    user_id = user["id"]
    sb_rows = get_supabase().table("brand_profiles").select(
        "audience"
    ).eq("user_id", user_id).limit(1).execute().data or []
    audience_doc = (sb_rows[0].get("audience") if sb_rows else None) or {}

    def _dedupe(rows: list[dict]) -> list[dict]:
        # newest-first input; drop older twins (multi-worker refreshes can
        # still race across processes — read-time dedupe is the backstop)
        seen: set[tuple] = set()
        out = []
        for r in rows:
            key = (r.get("insight_type"), r.get("subject"), r.get("source_url") or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(r)
        return out

    obs = _dedupe(research_records.list_records(user_id, kind="observation", limit=120))
    personas = _dedupe(
        research_records.list_records(user_id, kind="interpretation", insight_type="persona")
    )

    def _obs_out(r: dict) -> dict:
        return {
            "id": r["id"],
            "type": r["insight_type"],
            "text": (r.get("payload") or {}).get("text") or r.get("subject"),
            "language": r.get("language"),
            "source": r.get("source"),
            "source_url": r.get("source_url"),
            "scraped_at": r.get("scraped_at"),
            "extra": {
                k: (r.get("payload") or {}).get(k)
                for k in ("upvotes", "community", "query")
                if (r.get("payload") or {}).get(k) is not None
            },
        }

    return {
        "personas": [
            {
                **(r.get("payload") or {}),
                "language": r.get("language"),
                "based_on": len(r.get("refs") or []),
                "ai_generated": True,
            }
            for r in personas
        ],
        "questions": [_obs_out(r) for r in obs if r["insight_type"] == "audience_question"][:40],
        "phrases": [_obs_out(r) for r in obs if r["insight_type"] == "audience_phrase"][:40],
        "coverage": audience_doc.get("coverage") or {},
        "updated_at": audience_doc.get("updated_at"),
    }


@router.get("/research/hooks")
async def api_get_hook_suggestions(user: dict = Depends(get_current_user)):
    """System-scored hook suggestions. Each carries its transparent score
    breakdown (computed in code, never by the model) and the verbatim
    audience observations it echoes."""
    from ugc_backend.research import records as research_records

    rows = research_records.list_records(
        user["id"], kind="interpretation", insight_type="hook_suggestion"
    )
    seen: set[str] = set()
    out = []
    for r in rows:
        if r["subject"] in seen:
            continue
        seen.add(r["subject"])
        p = r.get("payload") or {}
        out.append(
            {
                "hook": p.get("hook"),
                "hook_type": p.get("hook_type"),
                "score": p.get("score"),
                "audience_echo": p.get("audience_echo"),
                "brand_terms": p.get("brand_terms") or [],
                "echoes": p.get("echoes") or [],
                "status": p.get("status") or "suggested",
                "based_on": len(r.get("refs") or []),
                "ai_generated": True,
                "created_at": r.get("created_at"),
            }
        )
    out.sort(key=lambda s: -(s.get("score") or 0))
    return {"suggestions": out}


# ── Internal cron trigger (nightly self-improvement sweep) ──────────────────
#
# Called by the Modal cron (modal_jobs/nightly_reflection.py), NOT by users —
# hence no get_current_user. Auth is a shared secret: the endpoint is
# disabled (404) until ANALYTICS_CRON_SECRET is set in the environment.

@router.post("/internal/cron/nightly", status_code=202)
def api_internal_cron_nightly(request: Request):
    secret = os.environ.get("ANALYTICS_CRON_SECRET") or ""
    if not secret:
        raise HTTPException(status_code=404, detail="Not found")
    provided = request.headers.get("x-cron-secret") or ""
    if not hmac.compare_digest(provided, secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    queued_users = studio_service.start_nightly_sweep_thread()
    return {"status": "started", "queued_users": queued_users}
