"""
Async-agent poller — background KIE polling for fire-and-return image jobs.

Spawned by dispatcher.submit_image_job. Polls KIE every 10s for up to
10 min (matching the existing sync path's bound), and updates the
`async_image_jobs` row through `running -> finishing -> success/failed`.
Each row UPDATE fires Supabase Realtime so the frontend can swap the
placeholder card to a real thumbnail without polling.

In-process asyncio task is acceptable for the tracer-bullet. Production
should move this to a Celery worker so polling survives a service
restart, but the row's terminal status is recoverable on next user
turn via get_job_status either way.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Optional

import httpx

from env_loader import load_env
load_env(Path(__file__))

_KIE_POLL_INTERVAL_S = 10
_KIE_MAX_TICKS = 60          # 10 min total
_REST_TIMEOUT = 15.0


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY for async_agent.poller")
    return url, anon


def _kie_creds() -> tuple[str, str]:
    return os.getenv("KIE_API_URL", "https://api.kie.ai"), os.getenv("KIE_API_KEY", "")


def _rest_headers(user_token: str, anon: str) -> dict:
    return {
        "apikey": anon,
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


async def _patch_row(user_token: str, job_id: str, fields: dict) -> Optional[dict]:
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_REST_TIMEOUT) as client:
        resp = await client.patch(
            f"{url}/rest/v1/async_image_jobs",
            headers=_rest_headers(user_token, anon),
            params={"id": f"eq.{job_id}"},
            json=fields,
        )
    if resp.status_code not in (200, 204):
        print(f"[async_agent.poller] patch failed for {job_id} ({resp.status_code}): {resp.text[:300]}")
        return None
    rows = resp.json() if resp.text else []
    return rows[0] if rows else None


async def _read_status(user_token: str, job_id: str) -> Optional[str]:
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_REST_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/async_image_jobs",
            headers={"apikey": anon, "Authorization": f"Bearer {user_token}"},
            params={"id": f"eq.{job_id}", "select": "status", "limit": 1},
        )
    if resp.status_code != 200:
        return None
    rows = resp.json()
    return rows[0]["status"] if rows else None


async def _poll_kie_image(user_token: str, job_id: str, kie_task_id: str) -> None:
    kie_url, kie_key = _kie_creds()
    headers = {"Authorization": f"Bearer {kie_key}"}
    poll_endpoint = f"{kie_url}/api/v1/jobs/recordInfo"

    await _patch_row(user_token, job_id, {"status": "running"})

    for tick in range(_KIE_MAX_TICKS):
        await asyncio.sleep(_KIE_POLL_INTERVAL_S)

        # Honour cancellation written by /cancel endpoint.
        current = await _read_status(user_token, job_id)
        if current in {"cancelled", "failed", "success"}:
            return

        try:
            async with httpx.AsyncClient(timeout=_REST_TIMEOUT) as http:
                resp = await http.get(poll_endpoint, headers=headers, params={"taskId": kie_task_id})
            body = resp.json()
        except Exception as e:
            print(f"[async_agent.poller] KIE poll error for {job_id}: {e}")
            continue

        if body.get("code") != 200:
            continue

        data = body.get("data") or {}
        state = (data.get("state") or "processing").lower()

        if state == "success":
            result_json = data.get("resultJson", "{}")
            if isinstance(result_json, str):
                try:
                    result_json = json.loads(result_json)
                except Exception:
                    result_json = {}
            image_url = (result_json.get("resultUrls") or [None])[0]
            if image_url:
                await _patch_row(
                    user_token,
                    job_id,
                    {"status": "success", "image_url": image_url},
                )
                return
            await _patch_row(
                user_token,
                job_id,
                {"status": "failed", "error": "KIE reported success with no resultUrl"},
            )
            return

        if state == "fail":
            await _patch_row(
                user_token,
                job_id,
                {"status": "failed", "error": data.get("failMsg") or "KIE generation failed"},
            )
            return

    await _patch_row(
        user_token,
        job_id,
        {"status": "failed", "error": f"KIE poll timed out after {_KIE_MAX_TICKS * _KIE_POLL_INTERVAL_S}s"},
    )


def poll_image_job_in_background(*, user_token: str, job_id: str, kie_task_id: str) -> asyncio.Task:
    """Fire-and-forget background poller. Caller does not await."""
    async def _runner():
        try:
            await _poll_kie_image(user_token, job_id, kie_task_id)
        except Exception as e:
            print(f"[async_agent.poller] runner crashed for {job_id}: {e}")
            try:
                await _patch_row(user_token, job_id, {"status": "failed", "error": f"poller crash: {e}"})
            except Exception:
                pass
    return asyncio.create_task(_runner())
