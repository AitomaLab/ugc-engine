"""Minimal Apify client (Slice 2) — async run + poll, never run-sync.

`run-sync-get-dataset-items` caps around 5 minutes and real scrapes exceed
it (measured: a 120-video TikTok run took >6 min), so every call here starts
a run and polls. Stdlib-only on purpose: research executes inside worker
threads in the core backend, and this module must stay importable anywhere.

Cost discipline: every run's `usageTotalUsd` is returned to the caller and
callers pass a `max_cost_usd` — a run that reports usage above it raises so
runaway actors can't silently burn the monthly credit.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

_BASE = "https://api.apify.com/v2"

# measured 2026-07: tiktok 120 videos ≈ $0.44; reddit lite query ≈ $0.10;
# google-search page ≈ $0.001
_DEFAULT_MAX_COST = 1.50


class ApifyError(RuntimeError):
    pass


def _token() -> str:
    tok = (os.getenv("APIFY_TOKEN") or "").strip()
    if not tok:
        raise ApifyError("APIFY_TOKEN not configured")
    return tok


def _req(url: str, payload: dict | None = None, timeout: int = 120) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise ApifyError(f"Apify HTTP {e.code}: {e.read().decode('utf-8', 'ignore')[:300]}") from e


def run_actor(
    actor_id: str,
    run_input: dict,
    *,
    timeout_s: int = 600,
    poll_s: int = 12,
    max_items: int = 200,
    max_cost_usd: float = _DEFAULT_MAX_COST,
) -> tuple[dict, list[dict]]:
    """Start an actor run, poll to completion, return (run_meta, items).

    run_meta includes: run_id, status, usage_usd, dataset_id.
    Raises ApifyError on failure/timeout/cost breach.
    """
    tok = _token()
    run = _req(f"{_BASE}/acts/{actor_id}/runs?token={tok}", run_input)["data"]
    run_id = run["id"]
    status = run["status"]
    t0 = time.time()
    while status in ("READY", "RUNNING") and time.time() - t0 < timeout_s:
        time.sleep(poll_s)
        run = _req(f"{_BASE}/actor-runs/{run_id}?token={tok}")["data"]
        status = run["status"]

    usage = float(run.get("usageTotalUsd") or 0.0)
    meta = {
        "run_id": run_id,
        "status": status,
        "usage_usd": usage,
        "dataset_id": run.get("defaultDatasetId"),
        "actor_id": actor_id,
    }
    if status in ("READY", "RUNNING"):
        # left running server-side; caller decides whether to abort it
        raise ApifyError(f"actor {actor_id} run {run_id} still {status} after {timeout_s}s")
    if status != "SUCCEEDED":
        raise ApifyError(f"actor {actor_id} run {run_id} ended {status}")
    if usage > max_cost_usd:
        raise ApifyError(
            f"actor {actor_id} run {run_id} cost ${usage:.2f} > cap ${max_cost_usd:.2f}"
        )

    items = _req(
        f"{_BASE}/datasets/{meta['dataset_id']}/items?token={tok}&limit={max_items}"
    )
    if not isinstance(items, list):
        items = []
    return meta, items
