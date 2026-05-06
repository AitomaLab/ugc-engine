"""
Creative OS — Async Agent Router (tracer-bullet, Layer 1)

Endpoints:
  GET  /creative-os/async-agent/health                 readiness probe for the frontend wrapper
  POST /creative-os/async-agent/dispatch-image         fire-and-return image job
  POST /creative-os/async-agent/jobs/{job_id}/cancel   cancel an in-flight image job
  GET  /creative-os/async-agent/jobs?project_id=...    list active image jobs for a project

This router is fully isolated from routers/agent.py. The existing sync
agent flow (/creative-os/agent/*) is untouched. The frontend chooses
between this router and the sync one via the AgentPanelRouter wrapper.

Layer 1 (this file): proves the architecture for generate_image — user
provides a prompt, server submits to KIE, returns a job_id within
seconds, frontend tracks via Realtime on async_image_jobs.

Layer 2 (next): wraps this dispatcher in an Anthropic Managed Agents
session so the user can chat naturally instead of providing a raw
prompt. Same dispatcher, same poller, same table.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from auth import get_current_user
from services.async_agent.dispatcher import submit_image_job, cancel_image_job

router = APIRouter(prefix="/async-agent", tags=["async-agent"])


class DispatchImageRequest(BaseModel):
    project_id: str
    prompt: str
    image_input: Optional[list[str]] = None
    aspect_ratio: str = "9:16"
    agent_session_id: Optional[str] = None


@router.get("/health")
async def health() -> dict:
    """Cheap probe used by the frontend wrapper to decide async vs sync."""
    return {"ok": True, "module": "async_agent", "layer": 1}


@router.post("/dispatch-image")
async def dispatch_image(
    data: DispatchImageRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    if not data.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt is required")
    if not data.project_id.strip():
        raise HTTPException(status_code=400, detail="project_id is required")

    try:
        result = await submit_image_job(
            user_token=user["token"],
            user_id=user["id"],
            project_id=data.project_id,
            prompt=data.prompt,
            image_input=data.image_input,
            aspect_ratio=data.aspect_ratio,
            agent_session_id=data.agent_session_id,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        **result,
        "agent_text": "Generating now — I'll let you know when it's ready.",
    }


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    user: dict = Depends(get_current_user),
) -> dict:
    try:
        return await cancel_image_job(user_token=user["token"], job_id=job_id)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/jobs")
async def list_jobs(
    project_id: str = Query(...),
    user: dict = Depends(get_current_user),
) -> dict:
    """Hydration on panel mount — returns recent image jobs for the project.

    The frontend renders these as initial tiles, then receives Realtime
    updates from there. Image-only for the tracer; videos land in Layer 2.
    """
    import os
    import httpx

    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not anon:
        raise HTTPException(status_code=500, detail="Supabase env not configured")

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{url}/rest/v1/async_image_jobs",
            headers={"apikey": anon, "Authorization": f"Bearer {user['token']}"},
            params={
                "project_id": f"eq.{project_id}",
                "order": "created_at.desc",
                "limit": 50,
                "select": "id,prompt,status,image_url,error,created_at,updated_at,kie_task_id",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Supabase fetch failed: {resp.text[:300]}")
    return {"image_jobs": resp.json()}
