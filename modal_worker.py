"""
UGC Engine — Modal Serverless Worker

Wraps core_engine.run_generation_pipeline into a Modal function
that can be triggered via HTTP webhook from the FastAPI backend.

Deploy:  modal deploy modal_worker.py
Test:    modal run modal_worker.py::process_video --job-id <uuid>

All secrets are injected via Modal's secret management (dashboard or CLI).
"""
import os
import sys
from pathlib import Path

import modal

# ---------------------------------------------------------------------------
# Modal App Definition
# ---------------------------------------------------------------------------

app = modal.App(
    name="ugc-engine-worker",
    secrets=[
        modal.Secret.from_name("ugc-engine-secrets"),
    ],
)

# Container image with all dependencies
worker_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install_from_requirements("requirements.txt")
)


# ---------------------------------------------------------------------------
# The Serverless Video Generation Function
# ---------------------------------------------------------------------------

@app.function(
    image=worker_image,
    timeout=600,           # 10 min max per video job
    retries=1,             # Retry once on transient failures
    cpu=2.0,               # 2 vCPUs for ffmpeg
    memory=2048,           # 2 GB RAM
)
def process_video(job_id: str):
    """
    Self-contained video generation function.

    Accepts a job_id, fetches all data from Supabase,
    runs the full generation pipeline, and uploads
    the result back to Supabase Storage.

    This mirrors exactly what the Celery worker does in
    ugc_worker/tasks.py -> generate_ugc_video(job_id).
    """
    # Ensure project root is in path
    root = str(Path(__file__).parent.absolute())
    if root not in sys.path:
        sys.path.insert(0, root)

    # Import the Celery task's core logic (not the Celery decorator)
    from ugc_worker.tasks import generate_ugc_video

    print(f"[MODAL] Starting job: {job_id}")
    try:
        # Call the task function directly (same logic as Celery)
        generate_ugc_video(job_id)
        print(f"[MODAL] Job {job_id} completed successfully")
    except Exception as e:
        print(f"[MODAL] Job {job_id} failed: {e}")
        # Update job status in Supabase
        from ugc_db.db_manager import update_job
        update_job(job_id, {"status": "failed", "error_message": str(e)})
        raise


# ---------------------------------------------------------------------------
# Web Endpoint — Triggered by FastAPI backend via HTTP POST
# ---------------------------------------------------------------------------

@app.function(
    image=worker_image,
    timeout=10,  # Webhook handler responds fast, spawns the real work
)
@modal.web_endpoint(method="POST")
def trigger_job(request: dict):
    """
    HTTP webhook endpoint.
    Called by the FastAPI backend when USE_MODAL_WORKER=true.

    Expects JSON body: {"job_id": "<uuid>"}
    """
    job_id = request.get("job_id")
    if not job_id:
        return {"error": "job_id is required"}, 400

    # Spawn the heavy processing as a separate Modal function call
    process_video.spawn(job_id)

    return {"status": "dispatched", "job_id": job_id}
