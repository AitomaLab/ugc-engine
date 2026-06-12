"""Background job runners for the Analytics module.

Analytics jobs are short and bursty — they don't need the Modal/Celery
plumbing used by video generation. We default to in-process daemon threads
and persist status transitions to ``analytics_scrape_jobs`` /
``analytics_video_breakdowns`` so the frontend can poll for completion.

If you ever need to scale, swap in the global ``_dispatch_worker`` from
``ugc_backend.main`` — the persistence model is already compatible.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Optional

from . import db as analytics_db
from . import scraper_service
from . import vision_service

logger = logging.getLogger(__name__)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_breakdown_in_background(
    *,
    breakdown_id: str,
    user_id: str,
    video_url: str,
    metrics: Optional[dict] = None,
) -> None:
    """Spawn a daemon thread that runs the two-pass vision pipeline and
    persists the result. Idempotent at the DB layer — re-running on the same
    breakdown_id overwrites the row.
    """

    def _runner():
        try:
            analytics_db.update_breakdown(breakdown_id, {"status": "running"})
            result = vision_service.analyze_video(video_url=video_url, metrics=metrics or {})
            updates = result.as_db_updates()
            if result.error_message and not result.summary:
                updates.update({"status": "failed", "completed_at": _iso_now()})
            else:
                updates.update({"status": "completed", "completed_at": _iso_now()})
            analytics_db.update_breakdown(breakdown_id, updates)
        except Exception as e:
            # Same sanitizer as the vision service uses for in-pipeline
            # errors — keeps raw exception text out of the breakdown row
            # and out of the UI.
            analytics_db.update_breakdown(
                breakdown_id,
                {
                    "status": "failed",
                    "error_message": vision_service._friendly_error(e),
                    "completed_at": _iso_now(),
                },
            )

    thread = threading.Thread(
        target=_runner, daemon=True, name=f"analytics-breakdown-{breakdown_id[:8]}"
    )
    thread.start()


def run_linked_account_analyze_in_background(
    user_id: str,
    *,
    platform: str,
    username: str,
    profile_key: Optional[str],
    platform_usernames: dict[str, str],
) -> None:
    """Auto-analyze an OAuth-linked account: BrightData feed scrape + Studio pipeline."""

    def _runner() -> None:
        async def _run() -> None:
            # Lazy import avoids circular dependency (router → studio_service).
            from ugc_backend.analytics.router import _scrape_account_for_user

            from ugc_backend.analytics import db as analytics_db

            acct = analytics_db.get_tracked_account_by_slug(
                user_id, platform=platform, username=username,
            )
            await _scrape_account_for_user(
                user_id=user_id,
                platform=platform,
                username=username,
                top_n=acct.get("top_n_retention") if acct else None,
                follower_count=(
                    acct.get("follower_count") or acct.get("followers")
                ) if acct else None,
            )
            from ugc_backend.analytics import studio_service

            if profile_key and platform_usernames:
                await studio_service.run_connected_accounts_pipeline(
                    user_id,
                    profile_key,
                    platform_usernames,
                    force_metrics=True,
                )

        try:
            asyncio.run(_run())
        except Exception as exc:
            logger.warning(
                "[analytics] linked account auto-analyze failed %s/%s: %s",
                platform,
                username,
                exc,
            )

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"analytics-linked-{platform}-{username[:8]}",
    ).start()


def run_scrape_resume_in_background(
    user_id: str,
    job_id: str,
    *,
    kind: str,
    platform: str,
    username: Optional[str] = None,
    top_n: Optional[int] = None,
) -> None:
    """Resume a BrightData snapshot that outlived the synchronous HTTP poll."""

    def _runner() -> None:
        try:
            result = asyncio.run(
                scraper_service.resume_pending_scrape_job(
                    user_id,
                    job_id,
                    top_n=top_n,
                )
            )
            if result.status == "pending":
                analytics_db.update_scrape_job(
                    job_id,
                    {
                        "status": "failed",
                        "error_message": (
                            "BrightData snapshot timed out — try again shortly."
                        ),
                        "completed_at": _iso_now(),
                    },
                )
                return
            scraper_service.persist_scrape_job_result(
                user_id,
                job_id,
                result,
                kind=kind,
                platform=platform,
                username=username,
                top_n=top_n,
            )
        except Exception as e:
            analytics_db.update_scrape_job(
                job_id,
                {
                    "status": "failed",
                    "error_message": str(e)[:500],
                    "completed_at": _iso_now(),
                },
            )

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"analytics-scrape-resume-{job_id[:8]}",
    ).start()
