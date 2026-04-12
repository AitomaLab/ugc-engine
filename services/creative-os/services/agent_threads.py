"""
Creative OS — Agent Threads persistence

Thin async helper around Supabase REST for the `agent_threads` table.
Mirrors the direct-PostgREST pattern in `core_api_client.create_standalone_shot`:
sends the user's bearer JWT so RLS scopes ownership server-side.

One row per (user_id, project_id). `turns` is a JSONB array capped at the
50 most recent entries.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx

from env_loader import load_env
load_env(Path(__file__))

MAX_TURNS = 50
_TIMEOUT = 15.0


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY for agent_threads")
    return url, anon


def _headers(user_token: str, anon: str, *, prefer_repr: bool = False) -> dict:
    h = {
        "apikey": anon,
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }
    if prefer_repr:
        h["Prefer"] = "return=representation"
    return h


async def get_thread(user_token: str, user_id: str, project_id: str) -> Optional[dict]:
    """Return the thread row for (user, project) or None if it doesn't exist."""
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/agent_threads",
            headers=_headers(user_token, anon),
            params={
                "user_id": f"eq.{user_id}",
                "project_id": f"eq.{project_id}",
                "select": "id,anthropic_session_id,title,turns,created_at,updated_at",
                "limit": 1,
            },
        )
        if resp.status_code != 200:
            print(f"[agent_threads] get_thread error {resp.status_code}: {resp.text}")
            return None
        rows = resp.json()
        return rows[0] if rows else None


async def upsert_thread(
    user_token: str,
    user_id: str,
    project_id: str,
    *,
    anthropic_session_id: Optional[str] = None,
    turns: Optional[list[dict]] = None,
    title: Optional[str] = None,
) -> Optional[dict]:
    """Insert or update the thread row. Only fields explicitly passed are written."""
    url, anon = _supabase_creds()

    payload: dict = {
        "user_id": user_id,
        "project_id": project_id,
    }
    if anthropic_session_id is not None:
        payload["anthropic_session_id"] = anthropic_session_id
    if title is not None:
        payload["title"] = title
    if turns is not None:
        payload["turns"] = turns[-MAX_TURNS:]
    from datetime import datetime, timezone
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()

    headers = _headers(user_token, anon, prefer_repr=True)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"

    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/rest/v1/agent_threads",
            headers=headers,
            params={"on_conflict": "user_id,project_id"},
            json=payload,
        )
        if resp.status_code not in (200, 201):
            print(f"[agent_threads] upsert error {resp.status_code}: {resp.text}")
            return None
        rows = resp.json()
        return rows[0] if rows else None


async def reset_thread(user_token: str, user_id: str, project_id: str) -> bool:
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(
            f"{url}/rest/v1/agent_threads",
            headers=_headers(user_token, anon),
            params={
                "user_id": f"eq.{user_id}",
                "project_id": f"eq.{project_id}",
            },
        )
        if resp.status_code not in (200, 204):
            print(f"[agent_threads] reset error {resp.status_code}: {resp.text}")
            return False
        return True
