"""
Creative OS — Campaigns Router

HTTP access to the campaigns + campaign_plan_items tables for the
frontend "My Campaigns" tab and for cancellation. Reads flow through
the user's JWT so RLS handles scoping automatically.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from auth import get_current_user
from services.campaign_store import (
    get_campaign,
    list_campaigns,
    list_plan_items,
    update_campaign,
    update_plan_item,
)

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.get("/")
async def list_my_campaigns(
    status: str | None = None,
    user: dict = Depends(get_current_user),
) -> list[dict]:
    return await list_campaigns(user["token"], status=status)


@router.get("/{campaign_id}")
async def get_campaign_detail(
    campaign_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    campaign = await get_campaign(user["token"], campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    items = await list_plan_items(user["token"], campaign_id)
    return {**campaign, "items": items}


@router.post("/{campaign_id}/cancel")
async def cancel_campaign(
    campaign_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    """Mark campaign cancelled. Pending items → cancelled; in-flight jobs
    keep running (we don't abort them) but their scheduled posts are
    skipped by the watcher."""
    existing = await get_campaign(user["token"], campaign_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Campaign not found")

    items = await list_plan_items(user["token"], campaign_id)
    for it in items:
        if it.get("status") == "pending":
            try:
                await update_plan_item(user["token"], it["id"], {"status": "cancelled"})
            except Exception:
                pass

    await update_campaign(user["token"], campaign_id, {"status": "cancelled"})
    return {"status": "cancelled", "campaign_id": campaign_id}
