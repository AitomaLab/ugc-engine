"""
Creative OS — Managed Agent Router

Endpoints:
  GET  /creative-os/agent/thread?project_id=...   load persisted thread
  POST /creative-os/agent/stream                  SSE stream of one turn
  POST /creative-os/agent/reset                   delete the thread
  POST /creative-os/agent/stop                    interrupt the active run

The frontend talks to this router. The router talks to the
ManagedAgentClient (which talks to Anthropic) and to the agent_threads
Supabase table for persistence. Supabase is the source of truth.
"""
from __future__ import annotations

import asyncio
import json
from time import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from services.agent_threads import get_thread, reset_thread, upsert_thread
from services.managed_agent_client import get_managed_agent_client

router = APIRouter(prefix="/agent", tags=["managed-agent"])

# Per-project concurrency guard — prevents duplicate stream requests from
# crashing the active Anthropic session (which rejects user.message while
# tool calls are pending).
_active_streams: dict[str, asyncio.Lock] = {}


# ── Schemas ────────────────────────────────────────────────────────────
class AgentRef(BaseModel):
    type: str  # 'product' | 'influencer' | 'image' | 'video'
    tag: str   # the @-token the user typed, e.g. 'tea_94802f09'
    name: Optional[str] = None
    id: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    shot_id: Optional[str] = None
    job_id: Optional[str] = None


class AgentRunRequest(BaseModel):
    brief: str
    project_id: str
    refs: Optional[list[AgentRef]] = None


class AgentResetRequest(BaseModel):
    project_id: str


class AgentStopRequest(BaseModel):
    project_id: str


def _now_ms() -> int:
    return int(time() * 1000)


# ── GET /agent/thread ──────────────────────────────────────────────────
@router.get("/thread")
async def get_agent_thread(
    project_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    thread = await get_thread(user["token"], user["id"], project_id)
    if not thread:
        return {"session_id": None, "turns": []}
    return {
        "session_id": thread.get("anthropic_session_id"),
        "turns": thread.get("turns") or [],
    }


# ── POST /agent/reset ──────────────────────────────────────────────────
@router.post("/reset")
async def reset_agent_thread(
    data: AgentResetRequest,
    user: dict = Depends(get_current_user),
):
    ok = await reset_thread(user["token"], user["id"], data.project_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to reset thread")
    return {"ok": True}


# ── POST /agent/stop ───────────────────────────────────────────────────
@router.post("/stop")
async def stop_agent(
    data: AgentStopRequest,
    user: dict = Depends(get_current_user),
):
    thread = await get_thread(user["token"], user["id"], data.project_id)
    session_id = thread.get("anthropic_session_id") if thread else None
    if not session_id:
        return {"ok": False, "reason": "no active session"}
    try:
        client = get_managed_agent_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    await client.interrupt_session(session_id)
    return {"ok": True}


# ── POST /agent/stream (SSE) ───────────────────────────────────────────
@router.post("/stream")
async def agent_stream(
    data: AgentRunRequest,
    user: dict = Depends(get_current_user),
):
    if not data.brief.strip():
        raise HTTPException(status_code=400, detail="brief is required")

    # Concurrency guard: one stream per project at a time.
    if data.project_id not in _active_streams:
        _active_streams[data.project_id] = asyncio.Lock()
    lock = _active_streams[data.project_id]
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Agent is already running for this project. Wait for it to finish or stop it first.",
        )

    try:
        client = get_managed_agent_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    user_token = user["token"]
    user_id = user["id"]
    project_id = data.project_id
    brief = data.brief
    refs = data.refs or []

    # Build a structured "Referenced assets" preface so the model receives
    # explicit IDs / URLs for everything the user @-mentioned. This is what
    # the agent reads when deciding which tool to call.
    augmented_brief = brief
    if refs:
        lines = ["[Referenced assets — these are the EXACT items the user is talking about]"]
        for r in refs:
            parts = [f"@{r.tag} ({r.type})"]
            if r.name:
                parts.append(f"name={r.name!r}")
            if r.id:
                parts.append(f"id={r.id}")
            if r.shot_id:
                parts.append(f"shot_id={r.shot_id}")
            if r.job_id:
                parts.append(f"job_id={r.job_id}")
            if r.image_url:
                parts.append(f"image_url={r.image_url}")
            if r.video_url:
                parts.append(f"video_url={r.video_url}")
            lines.append("- " + ", ".join(parts))
        lines.append("")
        lines.append("Use these IDs/URLs directly. Do not call list_project_assets to look them up.")
        lines.append("")
        lines.append("User message: " + brief)
        augmented_brief = "\n".join(lines)

    async def gen():
        async with lock:
            thread = await get_thread(user_token, user_id, project_id)
            session_id: Optional[str] = thread.get("anthropic_session_id") if thread else None
            turns: list[dict] = list((thread or {}).get("turns") or [])

            # Append user turn immediately so a refresh during the run shows it.
            # We persist the *original* brief (what the user typed) — the augmented
            # version with reference URLs is only sent to the model.
            user_turn: dict = {"role": "user", "text": brief, "ts": _now_ms()}
            if refs:
                user_turn["refs"] = [r.model_dump(exclude_none=True) for r in refs]
            turns.append(user_turn)
            await upsert_thread(
                user_token, user_id, project_id,
                anthropic_session_id=session_id,
                turns=turns,
                title=(turns[0]["text"][:80] if turns and turns[0].get("role") == "user" else None),
            )

            agent_text_parts: list[str] = []
            agent_artifacts: list[dict] = []
            agent_tool_calls: list[dict] = []
            interrupted = False

            try:
                async for ev in client.run_stream(
                    brief=augmented_brief,
                    user_token=user_token,
                    project_id=project_id,
                    session_id=session_id,
                ):
                    t = ev.get("type")
                    if t == "session":
                        session_id = ev["session_id"]
                        # Persist new/refreshed session id immediately.
                        await upsert_thread(
                            user_token, user_id, project_id,
                            anthropic_session_id=session_id,
                        )
                    elif t == "agent_message":
                        agent_text_parts.append(ev["text"])
                    elif t == "tool_call":
                        agent_tool_calls.append({
                            "name": ev["name"],
                            "input_summary": ev.get("input_summary", ""),
                        })
                    elif t == "artifact":
                        agent_artifacts.append(ev["artifact"])
                    yield f"data: {json.dumps(ev)}\n\n"

            except asyncio.CancelledError:
                interrupted = True
                yield f"data: {json.dumps({'type': 'interrupted'})}\n\n"
                raise
            finally:
                # Persist the agent turn (always — even on partial / errored runs).
                if agent_text_parts or agent_artifacts or agent_tool_calls or interrupted:
                    turns.append({
                        "role": "agent",
                        "text": "\n\n".join(agent_text_parts),
                        "artifacts": agent_artifacts,
                        "tool_calls": agent_tool_calls,
                        "interrupted": interrupted,
                        "ts": _now_ms(),
                    })
                    try:
                        await upsert_thread(
                            user_token, user_id, project_id,
                            anthropic_session_id=session_id,
                            turns=turns,
                        )
                    except Exception as e:
                        print(f"[agent_stream] final upsert failed: {e}")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
