"""
Async-agent dispatcher — fire-and-return image submission.

Tracer-bullet scope (Layer 1): proves the architecture end-to-end for
generate_image. Submits a NanoBanana Pro task to KIE, records the row in
`async_image_jobs`, spawns a background poller, and returns a `job_id`
to the caller within seconds. The agent's turn ends immediately; the
frontend learns about completion via Supabase Realtime on the row.

This module is fully isolated from the existing sync pipeline:
- Does NOT import from routers/generate_image.py.
- Writes only to `async_image_jobs` (additive table from migration 030).
- Reuses the KIE submit shape from _generate_nanobanana_direct without
  importing it (rewritten here on purpose so a refactor of the existing
  function can never affect this path).
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

# Realtime + Supabase REST credentials are read at submit time so the same
# pattern as services/agent_threads.py applies (no module-level state).
_KIE_TIMEOUT = 30.0
_REST_TIMEOUT = 15.0


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY for async_agent")
    return url, anon


def _kie_creds() -> tuple[str, str]:
    url = os.getenv("KIE_API_URL", "https://api.kie.ai")
    key = os.getenv("KIE_API_KEY", "")
    if not key:
        raise RuntimeError("Missing KIE_API_KEY for async_agent.dispatcher")
    return url, key


def _rest_headers(user_token: str, anon: str, *, prefer_repr: bool = False) -> dict:
    h = {
        "apikey": anon,
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }
    if prefer_repr:
        h["Prefer"] = "return=representation"
    return h


async def _insert_image_job(
    user_token: str,
    user_id: str,
    project_id: str,
    prompt: str,
    kie_task_id: str,
    agent_session_id: Optional[str],
) -> dict:
    url, anon = _supabase_creds()
    payload = {
        "user_id": user_id,
        "project_id": project_id,
        "agent_session_id": agent_session_id,
        "kie_task_id": kie_task_id,
        "prompt": prompt,
        "status": "dispatched",
    }
    async with httpx.AsyncClient(timeout=_REST_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/rest/v1/async_image_jobs",
            headers=_rest_headers(user_token, anon, prefer_repr=True),
            json=payload,
        )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"async_image_jobs insert failed ({resp.status_code}): {resp.text[:300]}")
    rows = resp.json()
    return rows[0] if isinstance(rows, list) else rows


async def _submit_kie_image(prompt: str, image_input: list[str], aspect_ratio: str) -> str:
    """Submit a NanoBanana Pro task to KIE. Returns the taskId.

    Mirrors the submit half of routers/generate_image._generate_nanobanana_direct
    (lines ~620-655 at HEAD 0b74655). The poll half lives in poller.py.
    """
    kie_url, kie_key = _kie_creds()
    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": prompt,
            "negative_prompt": (
                "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, "
                "extra limb, missing limb, floating limbs, "
                "(mutated hands and fingers:1.4), blurry, extra fingers"
            ),
            "aspect_ratio": aspect_ratio,
            "resolution": "4K",
        },
    }
    if image_input:
        payload["input"]["image_input"] = image_input

    headers = {"Authorization": f"Bearer {kie_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=_KIE_TIMEOUT) as http:
        resp = await http.post(f"{kie_url}/api/v1/jobs/createTask", headers=headers, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"KIE submit error ({resp.status_code}): {resp.text[:300]}")
    body = resp.json()
    if body.get("code") != 200:
        raise RuntimeError(f"KIE submit error: {body.get('msg', str(body))}")
    return body["data"]["taskId"]


async def submit_image_job(
    *,
    user_token: str,
    user_id: str,
    project_id: str,
    prompt: str,
    image_input: Optional[list[str]] = None,
    aspect_ratio: str = "9:16",
    agent_session_id: Optional[str] = None,
) -> dict:
    """Fire-and-return entry point.

    Returns a dict shaped like the tool result the agent will see:
        {"job_id": <uuid>, "status": "dispatched", "kie_task_id": <str>}

    The actual KIE poll runs in the background; the row in async_image_jobs
    transitions through `running -> finishing -> success/failed` and the
    frontend swaps placeholders via Realtime.
    """
    if not prompt.strip():
        raise ValueError("prompt is required")

    kie_task_id = await _submit_kie_image(prompt.strip(), image_input or [], aspect_ratio)

    row = await _insert_image_job(
        user_token=user_token,
        user_id=user_id,
        project_id=project_id,
        prompt=prompt.strip(),
        kie_task_id=kie_task_id,
        agent_session_id=agent_session_id,
    )

    job_id = row["id"]

    from services.async_agent.poller import poll_image_job_in_background
    poll_image_job_in_background(
        user_token=user_token,
        job_id=job_id,
        kie_task_id=kie_task_id,
    )

    return {"job_id": job_id, "status": "dispatched", "kie_task_id": kie_task_id}


async def cancel_image_job(*, user_token: str, job_id: str) -> dict:
    """Mark a dispatched/running image job as cancelled.

    The KIE API does not currently expose a public cancel endpoint for
    NanoBanana tasks, so cancelling here only stops local polling and
    flips the row to `cancelled`. Any KIE charge already incurred is
    written off (KIE only debits on success in current pricing). The
    poller checks the row's status before each tick and exits on cancel.
    """
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_REST_TIMEOUT) as client:
        resp = await client.patch(
            f"{url}/rest/v1/async_image_jobs",
            headers=_rest_headers(user_token, anon, prefer_repr=True),
            params={"id": f"eq.{job_id}", "status": "in.(dispatched,running,finishing)"},
            json={"status": "cancelled"},
        )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"cancel failed ({resp.status_code}): {resp.text[:300]}")
    return {"job_id": job_id, "status": "cancelled"}
