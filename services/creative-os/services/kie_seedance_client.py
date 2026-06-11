"""Kie.ai Seedance 2.0 async wrapper for cinematic-ads animate stage.

Mirrors the public shape of fal_client.animate_storyboard_seedance so the
cinematic-ads tool can swap providers with a one-line import change.
Internally translates `image_urls` -> Kie's `reference_image_urls`,
`duration` str -> int, and polls /api/v1/jobs/recordInfo every 10s.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Optional

import httpx


KIE_CREATE_URL = "https://api.kie.ai/api/v1/jobs/createTask"
KIE_POLL_URL = "https://api.kie.ai/api/v1/jobs/recordInfo"
SEEDANCE_MODEL = "bytedance/seedance-2"


class KieError(Exception):
    def __init__(self, message: str, *, raw: Optional[dict] = None):
        super().__init__(message)
        self.raw = raw or {}


def _key() -> str:
    k = os.getenv("KIE_API_KEY")
    if not k:
        raise KieError("KIE_API_KEY not set in environment")
    return k


async def animate_storyboard_kie_seedance(
    *,
    prompt: str,
    image_urls: list[str],
    duration: int | str = 15,
    resolution: str = "720p",
    aspect_ratio: str = "16:9",
    generate_audio: bool = True,
    negative_prompt: str = "",
    poll_interval: float = 10.0,
    max_iters: int = 240,
    on_submitted=None,
) -> dict:
    """Animate via Kie.ai Seedance 2.0.

    Returns {"url": <mp4 url>, "task_id": str, "seed": None, "raw": <poll data>}.
    `seed` is always None — Kie does not surface a seed in its response. Kept
    in the return dict for shape-compat with the Fal wrapper.

    `on_submitted("kie:<taskId>")` fires right after the create call so the
    caller can persist the provider job reference for crash recovery.
    """
    if not image_urls:
        raise KieError("animate_storyboard_kie_seedance requires at least one image_url")

    headers = {
        "Authorization": f"Bearer {_key()}",
        "Content-Type": "application/json",
    }
    _input: dict = {
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "resolution": resolution,
        "duration": int(duration),
        "generate_audio": bool(generate_audio),
        "reference_image_urls": list(image_urls),
    }
    if negative_prompt:
        _input["negative_prompt"] = negative_prompt
    payload = {"model": SEEDANCE_MODEL, "input": _input}
    print(
        f"[kie] seedance create model={SEEDANCE_MODEL} dur={duration} "
        f"res={resolution} ar={aspect_ratio} imgs={len(image_urls)} audio={generate_audio} "
        f"neg_prompt_len={len(negative_prompt) if negative_prompt else 0}"
    )

    async with httpx.AsyncClient(timeout=60.0) as http:
        try:
            r = await http.post(KIE_CREATE_URL, headers=headers, json=payload)
        except Exception as e:
            raise KieError(f"Kie create request failed: {e}")
        if r.status_code != 200:
            raise KieError(f"Kie create failed {r.status_code}: {r.text[:300]}")
        try:
            create_data = r.json()
        except Exception as e:
            raise KieError(f"Kie create returned non-JSON: {e} body={r.text[:300]}")
        task_id = ((create_data.get("data") or {}).get("taskId"))
        if not task_id:
            raise KieError(f"Kie create returned no taskId: {create_data}", raw=create_data)
        print(f"[kie] seedance task_id={task_id}, polling every {poll_interval}s (max {max_iters})")
        if on_submitted:
            try:
                await on_submitted(f"kie:{task_id}")
            except Exception as cb_err:
                print(f"[kie] on_submitted callback failed: {cb_err}")

        for i in range(max_iters):
            await asyncio.sleep(poll_interval)
            try:
                pr = await http.get(KIE_POLL_URL, headers=headers, params={"taskId": task_id})
            except Exception as e:
                print(f"[kie] poll iter={i} transient error: {e}")
                continue
            if pr.status_code != 200:
                print(f"[kie] poll iter={i} status={pr.status_code}")
                continue
            try:
                pd = (pr.json().get("data") or {})
            except Exception:
                continue
            state = pd.get("state")
            # Heartbeat every ~60s so a long-queued task isn't invisible.
            if i > 0 and i % 6 == 0:
                print(f"[kie] poll iter={i} elapsed={int(i * poll_interval)}s state={state!r} task_id={task_id}")
            if state == "success":
                try:
                    result_json = json.loads(pd.get("resultJson", "{}"))
                except Exception as e:
                    raise KieError(f"Kie success but resultJson unparsable: {e}", raw=pd)
                url = (result_json.get("resultUrls") or [None])[0]
                if not url:
                    raise KieError(f"Kie success but no resultUrl: {pd}", raw=pd)
                print(f"[kie] seedance OK url={url[:80]}... task_id={task_id}")
                return {"url": url, "task_id": task_id, "seed": None, "raw": pd}
            if state == "fail":
                fail_msg = pd.get("failMsg") or pd.get("failReason") or str(pd)
                raise KieError(f"Kie seedance failed: {fail_msg}", raw=pd)
            # else: queuing / in_progress — keep polling

        raise KieError(
            f"Kie task {task_id} did not complete within {max_iters * poll_interval / 60:.0f} min — "
            f"stuck in Kie's queue or the ByteDance backend. The task may still finish on Kie's side; "
            f"check https://kie.ai dashboard. Retry after 15 min if you need the video now.",
            raw={"taskId": task_id, "timeout_seconds": int(max_iters * poll_interval)},
        )
