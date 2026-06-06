"""Kie.ai Gemini Omni Video async wrapper — generative video EDITING.

Mirrors the create→poll shape of kie_seedance_client so the agent's
edit_video tool can reuse the exact same KIE infrastructure (same base URL,
same KIE_API_KEY, same /jobs/createTask + /jobs/recordInfo poll loop).

Gemini Omni Video edits an existing source video from a natural-language
prompt: object removal/add/replace, scene/background/mood/angle changes,
material/VFX edits, reference-image transfer, character insertion, etc.

Constraints (from the KIE API doc):
  - Source video ≤ 30s and ≤ 100MB; video_list max 1 item per request.
  - The editable trim window (`ends - start`) must be ≤ 10s.
  - `duration` is required in the schema (4/6/8/10) but ignored when video_list
    is set — we still send a default for parity with the official curl example.
  - `callBackUrl` is optional; we send one (env override or placeholder) and
    still poll recordInfo for results.
  - Quota: (#images) + (#videos × 2) + (#character_ids) ≤ 7. v1 sends only
    a single video (2 units) + reference images, so images ≤ 5.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import httpx


KIE_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_POLL_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
OMNI_VIDEO_MODEL = "gemini-omni-video"
DEFAULT_CALLBACK_URL = "https://example.com/callback"

# Hard caps from the API contract.
MAX_EDIT_WINDOW_SECONDS = 10.0
MAX_PROMPT_CHARS = 20_000
MAX_QUOTA_UNITS = 7


class KieOmniError(Exception):
    def __init__(self, message: str, *, raw: Optional[dict] = None):
        super().__init__(message)
        self.raw = raw or {}


def _key() -> str:
    k = os.getenv("KIE_API_KEY")
    if not k:
        raise KieOmniError("KIE_API_KEY not set in environment")
    return k


async def edit_video_gemini_omni(
    *,
    prompt: str,
    video_url: str,
    start: float = 0.0,
    ends: float = 10.0,
    image_urls: Optional[list[str]] = None,
    character_ids: Optional[list[str]] = None,
    aspect_ratio: Optional[str] = None,
    resolution: str = "720p",
    seed: Optional[int] = None,
    poll_interval: float = 10.0,
    max_iters: int = 240,
) -> dict:
    """Edit a source video via Kie.ai Gemini Omni Video.

    Returns {"url": <mp4 url>, "task_id": str, "raw": <poll data>}.

    `start`/`ends` define the ≤10s window of the source to edit; KIE trims the
    source itself (no local ffmpeg needed for a single-window edit). The output
    corresponds to that window — callers handle re-stitching for >10s clips.
    """
    if not prompt or not prompt.strip():
        raise KieOmniError("edit_video_gemini_omni requires a non-empty prompt")
    if not video_url:
        raise KieOmniError("edit_video_gemini_omni requires a source video_url")

    images = [u for u in (image_urls or []) if u]
    chars = [c for c in (character_ids or []) if c]

    # Window sanity — the API rejects windows > 10s.
    if ends <= start:
        ends = start + MAX_EDIT_WINDOW_SECONDS
    if (ends - start) > MAX_EDIT_WINDOW_SECONDS + 0.05:
        ends = start + MAX_EDIT_WINDOW_SECONDS

    # Quota: images + video(2) + character_ids ≤ 7.
    used = len(images) + 2 + len(chars)
    if used > MAX_QUOTA_UNITS:
        raise KieOmniError(
            f"quota exceeded: images({len(images)}) + video(2) + characters({len(chars)}) "
            f"= {used} > {MAX_QUOTA_UNITS}. Reduce reference images to "
            f"{max(0, MAX_QUOTA_UNITS - 2 - len(chars))} or fewer."
        )

    if resolution not in ("720p", "1080p", "4k"):
        resolution = "720p"

    win_start = round(float(start), 2)
    win_end = round(float(ends), 2)
    win_span = win_end - win_start
    # Schema requires duration (4/6/8/10); ignored when video_list is present.
    _duration = "4" if win_span <= 4.5 else "6" if win_span <= 6.5 else "8" if win_span <= 8.5 else "10"

    _input: dict = {
        "prompt": prompt[:MAX_PROMPT_CHARS],
        "duration": _duration,
        "resolution": resolution,
        "video_list": [{"url": video_url, "start": win_start, "ends": win_end}],
    }
    if images:
        _input["image_urls"] = images
    if chars:
        _input["character_ids"] = chars
    # KIE requires aspect_ratio (it does NOT default to the source) and accepts
    # only 16:9 / 9:16 — omitting it returns a 422. Default to vertical.
    _input["aspect_ratio"] = aspect_ratio if aspect_ratio in ("16:9", "9:16") else "9:16"
    if seed is not None:
        _input["seed"] = int(seed)

    callback_url = (os.getenv("KIE_CALLBACK_URL") or "").strip() or DEFAULT_CALLBACK_URL
    payload = {
        "model": OMNI_VIDEO_MODEL,
        "callBackUrl": callback_url,
        "input": _input,
    }
    headers = {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}
    print(
        f"[kie-omni] edit create model={OMNI_VIDEO_MODEL} res={resolution} "
        f"window=[{start:.2f},{ends:.2f}] imgs={len(images)} chars={len(chars)} "
        f"ar={_input['aspect_ratio']}"
    )

    async with httpx.AsyncClient(timeout=60.0) as http:
        try:
            r = await http.post(KIE_CREATE_URL, headers=headers, json=payload)
        except Exception as e:
            raise KieOmniError(f"Kie create request failed: {e}")
        if r.status_code != 200:
            raise KieOmniError(f"Kie create failed {r.status_code}: {r.text[:300]}")
        try:
            create_data = r.json()
        except Exception as e:
            raise KieOmniError(f"Kie create returned non-JSON: {e} body={r.text[:300]}")
        # KIE signals validation errors with HTTP 200 + an embedded `code` != 200
        # (e.g. {"code":422,"msg":"Aspect ratio only supports [16:9, 9:16]"}).
        code = create_data.get("code")
        if code not in (200, None):
            raise KieOmniError(
                f"Kie create rejected (code {code}): {create_data.get('msg') or create_data}",
                raw=create_data,
            )
        task_id = ((create_data.get("data") or {}).get("taskId"))
        if not task_id:
            raise KieOmniError(f"Kie create returned no taskId: {create_data}", raw=create_data)
        print(f"[kie-omni] task_id={task_id}, polling every {poll_interval}s (max {max_iters})")

        for i in range(max_iters):
            await asyncio.sleep(poll_interval)
            try:
                pr = await http.get(KIE_POLL_URL, headers=headers, params={"taskId": task_id})
            except Exception as e:
                print(f"[kie-omni] poll iter={i} transient error: {e}")
                continue
            if pr.status_code != 200:
                print(f"[kie-omni] poll iter={i} status={pr.status_code}")
                continue
            try:
                pd = (pr.json().get("data") or {})
            except Exception:
                continue
            state = pd.get("state")
            if i > 0 and i % 6 == 0:
                print(f"[kie-omni] poll iter={i} elapsed={int(i * poll_interval)}s state={state!r} task_id={task_id}")
            if state == "success":
                try:
                    result_json = json.loads(pd.get("resultJson", "{}"))
                except Exception as e:
                    raise KieOmniError(f"Kie success but resultJson unparsable: {e}", raw=pd)
                url = (result_json.get("resultUrls") or [None])[0]
                if not url:
                    raise KieOmniError(f"Kie success but no resultUrl: {pd}", raw=pd)
                print(f"[kie-omni] OK url={url[:80]}... task_id={task_id}")
                return {"url": url, "task_id": task_id, "raw": pd}
            if state == "fail":
                fail_msg = pd.get("failMsg") or pd.get("failReason") or str(pd)
                raise KieOmniError(f"Kie omni edit failed: {fail_msg}", raw=pd)
            # else: queuing / in_progress — keep polling

        raise KieOmniError(
            f"Kie task {task_id} did not complete within {max_iters * poll_interval / 60:.0f} min — "
            f"stuck in Kie's queue or the Gemini backend. The task may still finish on Kie's side; "
            f"check https://kie.ai dashboard. Retry after 15 min if you need the edit now.",
            raw={"taskId": task_id, "timeout_seconds": int(max_iters * poll_interval)},
        )
