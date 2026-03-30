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

# Container image with all dependencies + project source code
worker_image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install(
        # FFmpeg for video assembly
        "ffmpeg",
        # Chrome Headless Shell dependencies for Remotion rendering
        "libnss3",
        "libatk-bridge2.0-0",
        "libdrm2",
        "libxcomposite1",
        "libxdamage1",
        "libxrandr2",
        "libgbm1",
        "libasound2",
        "libpangocairo-1.0-0",
        "libgtk-3-0",
        "libxshmfence1",
        "fonts-liberation",
        "fonts-noto-color-emoji",
        "libx11-xcb1",
        "libxcb-dri3-0",
        "libxss1",
        "libxtst6",
        "xdg-utils",
        "dbus",
        # curl for downloading Node.js
        "curl",
        "ca-certificates",
    )
    # Install Node.js 20 via NodeSource
    .run_commands(
        "curl -fsSL https://deb.nodesource.com/setup_20.x | bash -",
        "apt-get install -y nodejs",
        "node --version && npm --version",
    )
    .pip_install_from_requirements("requirements.txt")
    # Root-level Python modules the pipeline needs
    .add_local_python_source(
        "config",
        "core_engine",
        "generate_scenes",
        "scene_builder",
        "subtitle_engine",
        "assemble_video",
        "elevenlabs_client",
        "storage_helper",
        "social_media_poster",
        # Packages (directories with __init__.py)
        "ugc_worker",
        "ugc_db",
        "ugc_backend",
        "kie_ai",
    )
    # Non-Python data files the pipeline needs
    .add_local_dir("prompts", remote_path="/root/project/prompts")
    .add_local_file("ugc_backend/cost_config.json", remote_path="/root/project/ugc_backend/cost_config.json")
    # Remotion renderer (Node.js project) — exclude node_modules (installed in container)
    .add_local_dir("remotion_renderer", remote_path="/root/remotion_renderer",
                   ignore=["node_modules", "dist", "*.mp4", "output"])
    # Install Remotion npm dependencies and pre-download Chrome Headless Shell
    .run_commands(
        "cd /root/remotion_renderer && npm install",
        "cd /root/remotion_renderer && npx remotion browser ensure",
    )
)


# ---------------------------------------------------------------------------
# The Serverless Video Generation Function
# ---------------------------------------------------------------------------

@app.function(
    image=worker_image,
    timeout=600,           # 10 min max per video job
    retries=1,             # Retry once on transient failures
    cpu=2.0,               # 2 vCPUs for ffmpeg + Remotion
    memory=4096,           # 4 GB RAM — needed for Chromium + video rendering
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
    # Ensure project root is in path so imports resolve
    project_root = "/root/project"
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

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
@modal.fastapi_endpoint(method="POST")
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
