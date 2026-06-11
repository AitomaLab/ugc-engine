"""
Creative OS — WaveSpeed webhook receiver.

WaveSpeed POSTs prediction completion to this endpoint when the original
submit appended `?webhook=<this-url>` to the model URL. The server
guarantees 3 retries with exponential backoff, 20-min ack window, and
auto-refunds credits if every retry fails — so this handler MUST:

  - Verify the signature (when configured).
  - Return 2xx fast (≤5s).
  - Be idempotent (the same prediction may be delivered multiple times).

Polling in services/wavespeed_client.py is still the source of truth
for job-state transitions. This webhook is a latency optimization that
wakes any in-process poller waiting on the prediction_id, so jobs
finish faster than the 5-second poll cadence.

Config:
  WAVESPEED_WEBHOOK_SECRET: shared secret returned by
    GET /api/v3/webhook/secret (with `whsec_` prefix stripped).
    If unset, signature verification is skipped (dev mode).
  WAVESPEED_WEBHOOK_BASE: public base URL (e.g. Railway public URL).
    The submit() helper appends `/creative-os/wavespeed/webhook` and
    passes the result as ?webhook=… on each request.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import time
from typing import Any

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()


# ── In-process completion registry ──────────────────────────────────────
# Pollers that want to short-circuit on webhook delivery register a
# Future keyed by prediction_id. The webhook handler resolves the future
# with the WaveSpeed payload. Cross-process delivery (multiple workers,
# different machines) still falls back to polling.

_PENDING: dict[str, asyncio.Future] = {}
_PENDING_LOCK = asyncio.Lock()


async def register_prediction(prediction_id: str) -> asyncio.Future:
    """Register a future that resolves when the webhook fires for this id."""
    loop = asyncio.get_running_loop()
    fut: asyncio.Future = loop.create_future()
    async with _PENDING_LOCK:
        _PENDING[prediction_id] = fut
    return fut


async def discard_prediction(prediction_id: str) -> None:
    async with _PENDING_LOCK:
        _PENDING.pop(prediction_id, None)


async def _resolve_prediction(prediction_id: str, payload: dict[str, Any]) -> bool:
    async with _PENDING_LOCK:
        fut = _PENDING.pop(prediction_id, None)
    if fut is None or fut.done():
        return False
    fut.set_result(payload)
    return True


# ── Signature verification ──────────────────────────────────────────────

def _verify_signature(headers: dict[str, str], raw_body: bytes) -> bool:
    secret = os.getenv("WAVESPEED_WEBHOOK_SECRET", "").strip()
    if not secret:
        # Dev mode: no secret configured.
        return True
    if secret.startswith("whsec_"):
        secret = secret[len("whsec_"):]

    webhook_id = headers.get("webhook-id", "")
    webhook_ts = headers.get("webhook-timestamp", "")
    sig_header = headers.get("webhook-signature", "")
    if not webhook_id or not webhook_ts or not sig_header:
        return False

    # Reject events older than 5 minutes.
    try:
        ts = int(webhook_ts)
        if abs(time.time() - ts) > 300:
            return False
    except ValueError:
        return False

    signed = f"{webhook_id}.{webhook_ts}.".encode("utf-8") + raw_body
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()

    # Header may carry multiple space-separated `v3,<hex>` pairs; any match is OK.
    for entry in sig_header.split():
        if "," not in entry:
            continue
        version, candidate = entry.split(",", 1)
        if version != "v3":
            continue
        if hmac.compare_digest(candidate, expected):
            return True
    return False


# ── DB finalization ──────────────────────────────────────────────────────
# Besides waking in-process pollers, a completed/failed webhook proactively
# finalizes any product_shots / video_jobs rows that recorded this
# prediction as their provider_job_id ("wavespeed:<id>"). This makes
# completion restart-proof: even if the poller task died with the process,
# the webhook (or the jobs-status recovery sweep) lands the asset.

_INFLIGHT_STATUSES = "in.(processing,pending,generating,queued)"


def _service_rest() -> tuple[str, dict] | None:
    """(supabase_url, headers) using the service-role key, or None if unset."""
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not supabase_url or not (service_key or anon_key):
        return None
    key = service_key or anon_key
    return supabase_url, {
        "apikey": service_key or anon_key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _payload_output_url(payload: dict[str, Any]) -> str | None:
    inner = payload.get("data", payload)
    outputs = inner.get("outputs") or []
    if not outputs:
        return None
    first = outputs[0]
    if isinstance(first, str):
        return first
    if isinstance(first, dict):
        return first.get("url") or first.get("output")
    return None


async def _finalize_rows_for_prediction(prediction_id: str, payload: dict[str, Any]) -> None:
    """Finalize in-flight DB rows tagged with this prediction's provider_job_id."""
    import httpx

    rest = _service_rest()
    if rest is None:
        return
    supabase_url, headers = rest
    provider_job_id = f"wavespeed:{prediction_id}"
    status = str(payload.get("status") or payload.get("data", {}).get("status") or "").lower()
    media_url = _payload_output_url(payload) if status == "completed" else None
    if status == "completed" and not media_url:
        return  # nothing usable in the payload — polling/sweep will handle it

    try:
        async with httpx.AsyncClient(timeout=15.0) as http:
            shot_rows, job_rows = [], []
            for table, target in (("product_shots", "shot_rows"), ("video_jobs", "job_rows")):
                resp = await http.get(
                    f"{supabase_url}/rest/v1/{table}",
                    headers=headers,
                    params={
                        "provider_job_id": f"eq.{provider_job_id}",
                        "status": _INFLIGHT_STATUSES,
                        "select": "id",
                    },
                )
                rows = resp.json() if resp.status_code == 200 else []
                if target == "shot_rows":
                    shot_rows = rows or []
                else:
                    job_rows = rows or []

            if not shot_rows and not job_rows:
                return

            patch_headers = {**headers, "Prefer": "return=minimal"}

            # Status-first completion: PATCH status + provider URL immediately
            # so the 2s gallery poll flips the card right away, THEN mirror to
            # Supabase storage and swap in the durable URL. Mirroring a 4K
            # asset can take tens of seconds — it must not gate completion.
            for row in shot_rows:
                shot_id = str(row["id"])
                if status == "completed":
                    fields = {"status": "image_completed", "image_url": media_url}
                else:
                    fields = {"status": "failed"}
                await http.patch(
                    f"{supabase_url}/rest/v1/product_shots",
                    headers=patch_headers,
                    params={"id": f"eq.{shot_id}"},
                    json=fields,
                )
                print(f"[WaveSpeed Webhook] finalized shot {shot_id} -> {fields['status']}")
                if status == "completed":
                    try:
                        from utils.persist_media import finalize_image_url
                        stored = await finalize_image_url(media_url, shot_id=shot_id, path_prefix="project_shots")
                        if stored and stored != media_url:
                            await http.patch(
                                f"{supabase_url}/rest/v1/product_shots",
                                headers=patch_headers,
                                params={"id": f"eq.{shot_id}"},
                                json={"image_url": stored},
                            )
                    except Exception as e:
                        print(f"[WaveSpeed Webhook] mirror failed for shot {shot_id}, keeping provider URL: {e}")

            for row in job_rows:
                job_id = str(row["id"])
                if status == "completed":
                    fields = {
                        "status": "success",
                        "progress": 100,
                        "final_video_url": media_url,
                        "preview_url": None,
                        "status_message": None,
                    }
                else:
                    err = str(payload.get("error") or payload.get("data", {}).get("error") or "failed")
                    fields = {"status": "failed", "error_message": err[:500]}
                await http.patch(
                    f"{supabase_url}/rest/v1/video_jobs",
                    headers=patch_headers,
                    params={"id": f"eq.{job_id}"},
                    json=fields,
                )
                print(f"[WaveSpeed Webhook] finalized video job {job_id} -> {fields['status']}")
                if status == "completed":
                    try:
                        from utils.persist_media import finalize_video_url
                        final_url = await finalize_video_url(
                            media_url, storage_filename=f"webhook_{job_id[:8]}_{prediction_id[:8]}.mp4",
                        )
                        if final_url and final_url != media_url:
                            await http.patch(
                                f"{supabase_url}/rest/v1/video_jobs",
                                headers=patch_headers,
                                params={"id": f"eq.{job_id}"},
                                json={"final_video_url": final_url},
                            )
                    except Exception as e:
                        print(f"[WaveSpeed Webhook] mirror failed for video {job_id}, keeping provider URL: {e}")
    except Exception as e:
        print(f"[WaveSpeed Webhook] DB finalize failed for {prediction_id}: {e}")


# ── Endpoint ────────────────────────────────────────────────────────────

@router.post("/wavespeed/webhook")
async def wavespeed_webhook(request: Request) -> dict[str, Any]:
    raw = await request.body()
    headers = {k.lower(): v for k, v in request.headers.items()}

    if not _verify_signature(headers, raw):
        # Don't tell WaveSpeed details — just 401 so the retry won't deliver.
        raise HTTPException(status_code=401, detail="invalid signature")

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid json body")

    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="payload must be a json object")

    prediction_id = str(payload.get("id") or "")
    status = str(payload.get("status") or "")
    model = str(payload.get("model") or "")
    print(f"[WaveSpeed Webhook] id={prediction_id} model={model} status={status}")

    if not prediction_id:
        # Acknowledge so WaveSpeed doesn't retry, but ignore.
        return {"ok": True, "skipped": "no prediction id"}

    woke = await _resolve_prediction(prediction_id, payload)

    # Finalize DB rows in the background so we ack WaveSpeed within its 5s
    # window. If the process dies mid-finalize, the jobs-status recovery
    # sweep picks the row up via provider_job_id — nothing is lost.
    if status.lower() in ("completed", "failed"):
        asyncio.create_task(_finalize_rows_for_prediction(prediction_id, payload))

    return {"ok": True, "woke_poller": woke}
