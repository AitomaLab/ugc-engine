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
    # Remotion renderer: copy into image, install deps, pre-download Chrome
    # (must come before add_local_python_source because run_commands follows)
    .add_local_dir("remotion_renderer", remote_path="/root/remotion_renderer",
                   ignore=["node_modules", "dist", "*.mp4", "output"], copy=True)
    .run_commands(
        "cd /root/remotion_renderer && npm install",
    )
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
        "clone_engine",
        # Packages (directories with __init__.py)
        "ugc_worker",
        "ugc_db",
        "ugc_backend",
        "kie_ai",
    )
    # Non-Python data files the pipeline needs
    .add_local_dir("prompts", remote_path="/root/project/prompts")
    .add_local_file("ugc_backend/cost_config.json", remote_path="/root/project/ugc_backend/cost_config.json")
)


# ---------------------------------------------------------------------------
# The Serverless Video Generation Function
# ---------------------------------------------------------------------------

@app.function(
    image=worker_image,
    timeout=1800,          # 30 min max per video job
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


# ---------------------------------------------------------------------------
# AI Clone Video Generation — Completely Separate from Standard Pipeline
# ---------------------------------------------------------------------------

@app.function(
    image=worker_image,
    timeout=1800,          # 30 min max per clone video job
    retries=1,
    cpu=2.0,
    memory=4096,
)
def process_clone_video(job_id: str):
    """
    AI Clone video generation function.

    Fetches job data from clone_video_jobs, runs the isolated
    clone_engine pipeline (ElevenLabs TTS → InfiniteTalk lipsync),
    and uploads the result to Supabase Storage.

    This does NOT import or call core_engine or ugc_worker/tasks.
    """
    import random

    project_root = "/root/project"
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from ugc_db.db_manager import get_supabase
    import clone_engine

    print(f"[MODAL CLONE] Starting clone job: {job_id}")

    # Early validation: fail fast with a clear message if Modal secrets are incomplete
    _required_keys = ["WAVESPEED_API_KEY", "ELEVENLABS_API_KEY", "SUPABASE_URL"]
    _missing = [k for k in _required_keys if not os.getenv(k)]
    if _missing:
        raise RuntimeError(
            f"Missing Modal secrets: {', '.join(_missing)}. "
            f"Run: ./scripts/sync_modal_secrets.sh && modal deploy modal_worker.py"
        )

    sb = get_supabase()

    def update_job(updates: dict):
        get_supabase().table("clone_video_jobs").update(updates).eq("id", job_id).execute()

    # 1. Fetch the job record
    job_result = sb.table("clone_video_jobs").select("*").eq("id", job_id).execute()
    if not job_result.data:
        print(f"[MODAL CLONE] ERROR: Job {job_id} not found in clone_video_jobs")
        return

    job = job_result.data[0]

    try:
        update_job({"status": "processing", "progress": 5})

        # 2. Fetch the clone profile (ElevenLabs Voice ID)
        clone_result = sb.table("user_ai_clones").select("*").eq("id", job["clone_id"]).execute()
        if not clone_result.data:
            raise RuntimeError(f"Clone {job['clone_id']} not found")
        clone = clone_result.data[0]
        update_job({"progress": 10})

        # 3. Determine which Look image to use
        if job.get("look_id"):
            look_result = (
                sb.table("user_ai_clone_looks")
                .select("*")
                .eq("id", job["look_id"])
                .execute()
            )
            if not look_result.data:
                raise RuntimeError(f"Look {job['look_id']} not found")
            clone_image_url = look_result.data[0]["image_url"]
            print(f"[MODAL CLONE] Using specified look: {job['look_id']}")
        else:
            # Random look selection
            all_looks = (
                sb.table("user_ai_clone_looks")
                .select("*")
                .eq("clone_id", job["clone_id"])
                .execute()
            )
            if not all_looks.data:
                raise RuntimeError(f"No looks found for clone {job['clone_id']}")
            chosen_look = random.choice(all_looks.data)
            clone_image_url = chosen_look["image_url"]
            print(f"[MODAL CLONE] Random look selected: {chosen_look['id']} ({chosen_look['label']})")

        update_job({"progress": 15})

        # 4. Fetch product name for subtitle brand hint (optional)
        product_name = ""
        if job.get("product_id"):
            prod_result = (
                sb.table("products")
                .select("name")
                .eq("id", job["product_id"])
                .execute()
            )
            if prod_result.data:
                product_name = prod_result.data[0].get("name", "")

        update_job({"progress": 20})

        # 5. Run the clone engine
        print(f"[MODAL CLONE] Dispatching to clone_engine.generate_clone_video...")

        def on_progress(pct: int, msg: str):
            update_job({"progress": pct, "status_message": msg})
            print(f"[MODAL CLONE] {pct}% — {msg}")

        final_url = clone_engine.generate_clone_video(
            job_id=job_id,
            clone_image_url=clone_image_url,
            elevenlabs_voice_id=clone["elevenlabs_voice_id"],
            script_text=job["script_text"],
            subtitles_enabled=job.get("subtitles_enabled", True),
            subtitle_style=job.get("subtitle_style", "hormozi"),
            subtitle_placement=job.get("subtitle_placement", "middle"),
            product_name=product_name,
            progress_callback=on_progress,
        )

        # 6. Mark job as complete
        update_job({
            "status": "complete",
            "progress": 100,
            "final_video_url": final_url,
        })
        print(f"[MODAL CLONE] ✓ Job {job_id} complete: {final_url}")

    except Exception as e:
        error_msg = str(e)
        print(f"[MODAL CLONE] ✗ Job {job_id} failed: {error_msg}")
        update_job({
            "status": "failed",
            "error_message": error_msg[:1000],
        })
        raise


@app.function(
    image=worker_image,
    timeout=10,
)
@modal.fastapi_endpoint(method="POST")
def trigger_clone_job(request: dict):
    """
    HTTP webhook endpoint for AI Clone jobs.
    Called by the FastAPI backend when USE_MODAL_WORKER=true.

    Expects JSON body: {"job_id": "<uuid>"}
    """
    job_id = request.get("job_id")
    if not job_id:
        return {"error": "job_id is required"}, 400

    # Spawn the heavy processing as a separate Modal function call
    process_clone_video.spawn(job_id)

    return {"status": "dispatched", "job_id": job_id}
