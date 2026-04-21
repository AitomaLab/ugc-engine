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
    app_clip_id: Optional[str] = None
    product_type: Optional[str] = None  # 'physical' | 'digital'


class AgentRunRequest(BaseModel):
    brief: str
    project_id: str
    refs: Optional[list[AgentRef]] = None
    use_seedance: bool = False
    lang: Optional[str] = None  # 'en' | 'es' — steers conversational reply language


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
    # Always clear the project's concurrency lock so the next /stream can start
    # fresh, even if the previous run is wedged (hung SSE, dropped client, etc).
    # A still-running task in the old lock finishes harmlessly into a lock no
    # one is waiting on.
    _active_streams.pop(data.project_id, None)

    thread = await get_thread(user["token"], user["id"], data.project_id)
    session_id = thread.get("anthropic_session_id") if thread else None
    if not session_id:
        return {"ok": True, "lock_cleared": True, "session_interrupted": False}
    try:
        client = get_managed_agent_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        await client.interrupt_session(session_id)
    except Exception as e:
        return {"ok": True, "lock_cleared": True, "session_interrupted": False, "interrupt_error": str(e)}
    return {"ok": True, "lock_cleared": True, "session_interrupted": True}


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
    seedance_marker = (
        "[ENGINE=seedance — use seedance_2_ugc / seedance_2_cinematic / seedance_2_product "
        "video modes for this turn. Do NOT use ugc or cinematic_video modes.]"
    )
    # Explicit negative marker when the toggle is OFF. Without this, the agent
    # carries Seedance preference over from earlier turns (sessions are
    # persistent) — an absent marker is not a strong enough signal to override
    # prior-turn behavior.
    default_marker = (
        "[ENGINE=default — use Veo 3.1 for `ugc` and Kling 3.0 for `cinematic_video` this turn. "
        "Do NOT use seedance_2_ugc / seedance_2_cinematic / seedance_2_product, regardless of "
        "what was used in earlier turns.]"
    )
    engine_marker = seedance_marker if data.use_seedance else default_marker
    if not refs:
        augmented_brief = engine_marker + "\n\n" + augmented_brief
    if refs:
        lines = [engine_marker, ""]
        lines.append("[Referenced assets — these are the EXACT items the user is talking about]")
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
            if r.app_clip_id:
                parts.append(f"app_clip_id={r.app_clip_id}")
            if r.product_type:
                parts.append(f"product_type={r.product_type}")
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

            # Fire the initial upsert in the background so it doesn't block
            # client.run_stream from starting. Saves ~300-600ms on first-token
            # latency per turn. A refresh mid-run may briefly miss the new user
            # turn, but the final upsert in `finally` always persists it.
            async def _initial_upsert():
                try:
                    await upsert_thread(
                        user_token, user_id, project_id,
                        anthropic_session_id=session_id,
                        turns=turns,
                        title=(turns[0]["text"][:80] if turns and turns[0].get("role") == "user" else None),
                    )
                except Exception as e:
                    print(f"[agent_stream] initial upsert failed: {e}")

            asyncio.create_task(_initial_upsert())

            interrupted = False
            # `prior_turns` is everything persisted before this run (excluding
            # the user turn we just appended). The client replays this as a
            # context primer if the session has to be reset mid-run, so the
            # agent keeps memory across Anthropic session resets.
            prior_turns = turns[:-1]

            def _ensure_agent_turn() -> dict:
                """Return the current agent turn, appending a new one if needed."""
                if not turns or turns[-1].get("role") != "agent":
                    turns.append({
                        "role": "agent",
                        "text": "",
                        "artifacts": [],
                        "tool_calls": [],
                        "ts": _now_ms(),
                    })
                return turns[-1]

            try:
                dirty = False  # set when turns changed since last persist
                last_persist = 0

                async def _maybe_persist(force: bool = False):
                    """Upsert turns to Supabase. Throttled to at most once per 3s
                    unless forced, so the SSE hot path isn't dominated by I/O."""
                    nonlocal dirty, last_persist
                    if not dirty:
                        return
                    now = _now_ms()
                    if not force and (now - last_persist) < 3000:
                        return
                    try:
                        await upsert_thread(
                            user_token, user_id, project_id,
                            anthropic_session_id=session_id,
                            turns=turns,
                        )
                        dirty = False
                        last_persist = now
                    except Exception as e:
                        print(f"[agent_stream] mid-run upsert failed: {e}")

                image_urls = [r.image_url for r in refs if r.image_url]
                async for ev in client.run_stream(
                    brief=augmented_brief,
                    user_token=user_token,
                    project_id=project_id,
                    session_id=session_id,
                    prior_turns=prior_turns,
                    lang=data.lang,
                    image_urls=image_urls or None,
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
                        current = _ensure_agent_turn()
                        if not current["text"] and not current["artifacts"] and not current["tool_calls"]:
                            current["text"] = ev["text"]
                        else:
                            turns.append({
                                "role": "agent",
                                "text": ev["text"],
                                "artifacts": [],
                                "tool_calls": [],
                                "ts": _now_ms(),
                            })
                        dirty = True
                    elif t == "tool_call":
                        _ensure_agent_turn()["tool_calls"].append({
                            "name": ev["name"],
                            "input_summary": ev.get("input_summary", ""),
                            "mode": ev.get("mode"),
                        })
                        dirty = True
                    elif t == "artifact":
                        _ensure_agent_turn()["artifacts"].append(ev["artifact"])
                        dirty = True
                    # Persist incrementally so clients that lost the SSE can
                    # recover full state via GET /agent/thread.
                    await _maybe_persist()
                    yield f"data: {json.dumps(ev)}\n\n"

            except asyncio.CancelledError:
                interrupted = True
                yield f"data: {json.dumps({'type': 'interrupted'})}\n\n"
                raise
            finally:
                # Mark interruption on the active agent turn, then persist.
                if interrupted and turns and turns[-1].get("role") == "agent":
                    turns[-1]["interrupted"] = True
                if len(turns) > (len(prior_turns) + 1) or interrupted:
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
