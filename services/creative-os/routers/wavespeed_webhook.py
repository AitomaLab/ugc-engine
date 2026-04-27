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
    return {"ok": True, "woke_poller": woke}
