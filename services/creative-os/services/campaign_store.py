"""
Creative OS — Campaign Store

Thin Supabase REST wrapper for the `campaigns` and `campaign_plan_items`
tables. Used by the agent tools (plan/execute/status) and the background
watcher. Operates with the user's JWT so RLS scopes everything to the
caller; the watcher uses the service key since it runs without a user
context.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx


def _supabase_base() -> str:
    url = os.getenv("SUPABASE_URL")
    if not url:
        raise RuntimeError("SUPABASE_URL is not set")
    return url.rstrip("/")


def _headers(token: Optional[str] = None, *, service: bool = False) -> dict[str, str]:
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    service_key = os.getenv("SUPABASE_SERVICE_KEY")
    if service:
        key = service_key or anon
    else:
        key = anon
    if not key:
        raise RuntimeError("No Supabase key available (SUPABASE_ANON_KEY / SUPABASE_SERVICE_KEY)")
    h = {
        "apikey": key,
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    if service:
        h["Authorization"] = f"Bearer {service_key or key}"
    else:
        h["Authorization"] = f"Bearer {token}" if token else f"Bearer {anon}"
    return h


# ── Writes ─────────────────────────────────────────────────────────────
async def insert_campaign(
    user_token: str,
    *,
    user_id: str,
    name: str,
    project_id: Optional[str],
    product_id: Optional[str],
    goal: Optional[str],
    branding_notes: dict,
    start_date: Optional[str],
    end_date: Optional[str],
    cadence: dict,
    plan_json: Optional[dict] = None,
) -> dict:
    row = {
        "user_id": user_id,
        "name": name,
        "project_id": project_id,
        "product_id": product_id,
        "goal": goal,
        "branding_notes": branding_notes or {},
        "start_date": start_date,
        "end_date": end_date,
        "cadence": cadence or {"interval": "daily", "time_utc": "15:00"},
        "status": "planning",
        "plan_json": plan_json,
    }
    row = {k: v for k, v in row.items() if v is not None}
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.post(
            f"{_supabase_base()}/rest/v1/campaigns",
            headers=_headers(user_token),
            json=row,
        )
    resp.raise_for_status()
    rows = resp.json()
    return rows[0] if rows else row


async def insert_plan_items(user_token: str, campaign_id: str, items: list[dict]) -> list[dict]:
    if not items:
        return []
    rows = [{**item, "campaign_id": campaign_id} for item in items]
    async with httpx.AsyncClient(timeout=20.0) as http:
        resp = await http.post(
            f"{_supabase_base()}/rest/v1/campaign_plan_items",
            headers=_headers(user_token),
            json=rows,
        )
    resp.raise_for_status()
    return resp.json() or []


async def update_campaign(
    user_token: str,
    campaign_id: str,
    patch: dict,
    *,
    service: bool = False,
) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.patch(
            f"{_supabase_base()}/rest/v1/campaigns?id=eq.{campaign_id}",
            headers=_headers(user_token, service=service),
            json=patch,
        )
    resp.raise_for_status()
    rows = resp.json() or []
    return rows[0] if rows else {}


async def update_plan_item(
    user_token: Optional[str],
    item_id: str,
    patch: dict,
    *,
    service: bool = False,
) -> dict:
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.patch(
            f"{_supabase_base()}/rest/v1/campaign_plan_items?id=eq.{item_id}",
            headers=_headers(user_token, service=service),
            json=patch,
        )
    resp.raise_for_status()
    rows = resp.json() or []
    return rows[0] if rows else {}


# ── Reads ──────────────────────────────────────────────────────────────
async def list_campaigns(user_token: str, *, status: Optional[str] = None, limit: int = 50) -> list[dict]:
    params: dict[str, Any] = {
        "select": "*",
        "order": "updated_at.desc",
        "limit": str(limit),
    }
    if status:
        params["status"] = f"eq.{status}"
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(
            f"{_supabase_base()}/rest/v1/campaigns",
            headers=_headers(user_token),
            params=params,
        )
    if resp.status_code != 200:
        return []
    return resp.json() or []


async def get_campaign(user_token: str, campaign_id: str) -> Optional[dict]:
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(
            f"{_supabase_base()}/rest/v1/campaigns",
            headers=_headers(user_token),
            params={"select": "*", "id": f"eq.{campaign_id}", "limit": "1"},
        )
    if resp.status_code != 200:
        return None
    rows = resp.json() or []
    return rows[0] if rows else None


async def list_plan_items(
    user_token: Optional[str],
    campaign_id: str,
    *,
    status: Optional[str] = None,
    service: bool = False,
) -> list[dict]:
    params: dict[str, Any] = {
        "select": "*",
        "campaign_id": f"eq.{campaign_id}",
        "order": "slot_index.asc",
    }
    if status:
        params["status"] = f"eq.{status}"
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(
            f"{_supabase_base()}/rest/v1/campaign_plan_items",
            headers=_headers(user_token, service=service),
            params=params,
        )
    if resp.status_code != 200:
        return []
    return resp.json() or []


async def list_items_by_status(statuses: list[str], *, limit: int = 100) -> list[dict]:
    """Service-role read used by the background worker. Returns items across
    all users whose status is in `statuses`."""
    if not statuses:
        return []
    status_filter = "in.(" + ",".join(statuses) + ")"
    async with httpx.AsyncClient(timeout=15.0) as http:
        resp = await http.get(
            f"{_supabase_base()}/rest/v1/campaign_plan_items",
            headers=_headers(None, service=True),
            params={
                "select": "*,campaigns(id,user_id,branding_notes,status)",
                "status": status_filter,
                "order": "updated_at.asc",
                "limit": str(limit),
            },
        )
    if resp.status_code != 200:
        return []
    return resp.json() or []
