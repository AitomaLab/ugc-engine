"""
Creative OS — Campaign Watcher

Async loop that drives `campaign_plan_items` to completion:
  pending     — awaiting execute_campaign (no-op here)
  generating  — a job is running; poll for completion
  ready_to_post — asset is ready; auto-schedule via Ayrshare / schedule_posts
  scheduled   — terminal (social post created)
  posted      — terminal (Ayrshare webhook confirms)
  failed      — terminal
  cancelled   — terminal

Runs one tick every WATCH_INTERVAL_SECONDS. Safe to restart mid-cycle;
each transition is status-guarded so repeats are no-ops.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Optional

import httpx

from env_loader import load_env
from services.campaign_store import (
    list_items_by_status,
    update_campaign,
    update_plan_item,
)

load_env(Path(__file__))

WATCH_INTERVAL_SECONDS = int(os.getenv("CAMPAIGN_WATCHER_INTERVAL", "30"))
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8000")


def _service_headers() -> dict[str, str]:
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    return {
        "apikey": key or "",
        "Authorization": f"Bearer {key or ''}",
        "Content-Type": "application/json",
    }


async def _poll_video_job(job_id: str) -> dict:
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(
            f"{url}/rest/v1/video_jobs",
            headers=_service_headers(),
            params={
                "select": "id,status,final_video_url,error_message",
                "id": f"eq.{job_id}",
                "limit": "1",
            },
        )
    if resp.status_code != 200:
        return {}
    rows = resp.json() or []
    return rows[0] if rows else {}


async def _ayrshare_profile_key(user_id: str) -> Optional[str]:
    """Look up the Ayrshare profile_key for a given user_id via service role."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.get(
            f"{url}/rest/v1/ayrshare_profiles",
            headers=_service_headers(),
            params={
                "select": "ayrshare_profile_key",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )
    if resp.status_code != 200:
        return None
    rows = resp.json() or []
    return rows[0].get("ayrshare_profile_key") if rows else None


async def _insert_social_post(row: dict) -> Optional[str]:
    """Insert a social_posts row via service role. Returns new id or None."""
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    headers = {**_service_headers(), "Prefer": "return=representation"}
    async with httpx.AsyncClient(timeout=10.0) as http:
        resp = await http.post(
            f"{url}/rest/v1/social_posts",
            headers=headers,
            json=row,
        )
    if resp.status_code not in (200, 201):
        print(f"[campaign_watcher] social_posts insert failed {resp.status_code}: {resp.text[:200]}")
        return None
    rows = resp.json() or []
    return rows[0].get("id") if rows else None


async def _schedule_via_ayrshare(
    *,
    user_id: str,
    video_job_id: str,
    asset_url: str,
    platforms: list[str],
    scheduled_at: str,
    caption: Optional[str],
) -> dict:
    """Book the post with Ayrshare and write a social_posts row per platform.
    Mirrors the backend's POST /api/schedule/bulk logic but runs with service
    credentials, so the watcher can post on any user's behalf.
    """
    profile_key = await _ayrshare_profile_key(user_id)
    if not profile_key:
        return {"error": "user has no connected Ayrshare profile"}

    # Call Ayrshare once per platform list — simpler than one call per platform.
    try:
        from ugc_backend.ayrshare_client import create_post as _ayr_create
    except Exception as e:
        return {"error": f"ayrshare client unavailable: {e}"}

    post_payload = {
        "post": caption or "",
        "platforms": platforms,
        "mediaUrls": [asset_url],
        "scheduleDate": scheduled_at,
    }
    try:
        ayr_resp = await _ayr_create(profile_key, post_payload)
    except Exception as e:
        return {"error": f"ayrshare create_post failed: {e}"[:400]}

    ayr_id = ayr_resp.get("id") if isinstance(ayr_resp, dict) else None

    # One DB row per platform, matching the backend's existing logic.
    first_id: Optional[str] = None
    for platform in platforms:
        row = {
            "user_id": user_id,
            "video_job_id": video_job_id,
            "ayrshare_post_id": ayr_id,
            "status": "scheduled",
            "platform": platform,
            "caption": caption,
            "scheduled_at": scheduled_at,
        }
        inserted = await _insert_social_post(row)
        if inserted and not first_id:
            first_id = inserted
    return {"scheduled_post_id": first_id, "ayrshare_post_id": ayr_id}


async def _progress_item(item: dict) -> None:
    """Advance one plan_item through the pipeline."""
    item_id = item["id"]
    status = item.get("status")
    campaign = item.get("campaigns") or {}
    user_id = campaign.get("user_id")

    # generating → ready_to_post (check the underlying job)
    if status == "generating":
        job_id = item.get("job_id")
        if not job_id:
            await update_plan_item(None, item_id, {
                "status": "failed",
                "error": "generating but no job_id",
            }, service=True)
            return
        job = await _poll_video_job(job_id)
        job_status = job.get("status")
        if job_status == "success":
            url = job.get("final_video_url")
            if not url:
                await update_plan_item(None, item_id, {
                    "status": "failed",
                    "error": "job succeeded but no final_video_url",
                }, service=True)
                return
            await update_plan_item(None, item_id, {
                "status": "ready_to_post",
                "asset_url": url,
            }, service=True)
            return
        if job_status in ("failed", "cancelled"):
            await update_plan_item(None, item_id, {
                "status": "failed",
                "error": (job.get("error_message") or f"job {job_status}")[:400],
            }, service=True)
            return
        return  # still running

    # ready_to_post → scheduled (book the Ayrshare post)
    if status == "ready_to_post":
        if not user_id:
            await update_plan_item(None, item_id, {
                "status": "failed",
                "error": "no user_id on campaign",
            }, service=True)
            return

        platforms = item.get("platforms") or []
        if not platforms:
            await update_plan_item(None, item_id, {
                "status": "failed",
                "error": "no platforms on plan item",
            }, service=True)
            return

        asset_url = item.get("asset_url")
        if not asset_url:
            await update_plan_item(None, item_id, {
                "status": "failed",
                "error": "no asset_url on plan item",
            }, service=True)
            return

        result = await _schedule_via_ayrshare(
            user_id=user_id,
            video_job_id=item.get("job_id") or "",
            asset_url=asset_url,
            platforms=platforms,
            scheduled_at=item.get("scheduled_at") or "",
            caption=item.get("caption"),
        )
        if result.get("error"):
            await update_plan_item(None, item_id, {
                "status": "failed",
                "error": result["error"][:400],
            }, service=True)
            return

        patch: dict = {"status": "scheduled"}
        if result.get("scheduled_post_id"):
            patch["scheduled_post_id"] = result["scheduled_post_id"]
        await update_plan_item(None, item_id, patch, service=True)
        return


async def _roll_up_campaigns(touched_campaign_ids: set[str]) -> None:
    """Mark a campaign 'completed' when every item reaches a terminal state."""
    if not touched_campaign_ids:
        return
    url = os.getenv("SUPABASE_URL", "").rstrip("/")
    for cid in touched_campaign_ids:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.get(
                f"{url}/rest/v1/campaign_plan_items",
                headers=_service_headers(),
                params={
                    "select": "status",
                    "campaign_id": f"eq.{cid}",
                },
            )
        if resp.status_code != 200:
            continue
        rows = resp.json() or []
        if not rows:
            continue
        terminals = {"scheduled", "posted", "failed", "cancelled"}
        if all(r.get("status") in terminals for r in rows):
            try:
                await update_campaign(None, cid, {"status": "completed"}, service=True)
            except Exception:
                pass


async def run_once() -> None:
    """One full watcher tick. Exposed for tests / manual runs."""
    try:
        items = await list_items_by_status(["generating", "ready_to_post"], limit=100)
    except Exception as e:
        print(f"[campaign_watcher] list failed: {e}")
        return

    if not items:
        return

    touched: set[str] = set()
    for it in items:
        try:
            await _progress_item(it)
        except Exception as e:
            print(f"[campaign_watcher] item {it.get('id')} error: {e}")
            continue
        cid = (it.get("campaigns") or {}).get("id") or it.get("campaign_id")
        if cid:
            touched.add(cid)

    await _roll_up_campaigns(touched)


async def watcher_loop(stop_event: asyncio.Event) -> None:
    print(f"[campaign_watcher] starting, interval={WATCH_INTERVAL_SECONDS}s")
    while not stop_event.is_set():
        try:
            await run_once()
        except Exception as e:
            print(f"[campaign_watcher] tick failed: {e}")
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=WATCH_INTERVAL_SECONDS)
        except asyncio.TimeoutError:
            continue
    print("[campaign_watcher] stopped")
