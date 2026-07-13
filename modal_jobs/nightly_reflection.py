"""
UGC Engine — Nightly Self-Improvement Cron (Modal)

Pure alarm clock: fires at 02:00 UTC and POSTs the backend's internal
sweep endpoint, which runs the full analytics pipeline (scrape sync →
metrics refresh → AI breakdowns → strategy report → reflection) for every
user with active tracked accounts. All business logic stays in the
backend; deterministic token gates there ensure LLM stages only run for
accounts whose data actually changed.

Deploy:  modal deploy modal_jobs/nightly_reflection.py
Test:    modal run modal_jobs/nightly_reflection.py::trigger_nightly_sweep

Required keys in the dedicated `ugc-engine-nightly-secrets` Modal secret
(separate from the video worker's `ugc-engine-secrets` on purpose — this
app never needs the full credential set):
- BACKEND_BASE_URL       e.g. https://api.aitoma.ai (no trailing slash)
- ANALYTICS_CRON_SECRET  must match the backend env var of the same name
"""
import os
import time

import modal

app = modal.App(name="ugc-engine-nightly")

image = modal.Image.debian_slim(python_version="3.11").pip_install("httpx")


@app.function(
    image=image,
    schedule=modal.Cron("0 2 * * *"),
    secrets=[modal.Secret.from_name("ugc-engine-nightly-secrets")],
    timeout=120,
)
def trigger_nightly_sweep() -> None:
    import httpx

    base_url = (os.environ.get("BACKEND_BASE_URL") or "").rstrip("/")
    secret = os.environ.get("ANALYTICS_CRON_SECRET") or ""
    if not base_url or not secret:
        print(
            "[nightly] BACKEND_BASE_URL / ANALYTICS_CRON_SECRET missing from "
            "the ugc-engine-secrets Modal secret — skipping."
        )
        return

    url = f"{base_url}/api/analytics/internal/cron/nightly"
    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            resp = httpx.post(
                url,
                headers={"X-Cron-Secret": secret},
                timeout=30,
            )
            print(f"[nightly] attempt {attempt}: {resp.status_code} {resp.text[:200]}")
            if resp.status_code == 202:
                return
            # 4xx = configuration problem; retrying won't help.
            if 400 <= resp.status_code < 500:
                return
        except Exception as exc:
            last_error = exc
            print(f"[nightly] attempt {attempt} failed: {exc}")
        time.sleep(10)

    print(f"[nightly] all attempts failed; next cron run retries. last={last_error}")
