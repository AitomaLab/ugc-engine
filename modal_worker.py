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


# ---------------------------------------------------------------------------
# Editor Render — Remotion-based server-side video rendering
# ---------------------------------------------------------------------------

@app.function(
    image=worker_image,
    timeout=600,           # 10 min max per editor render
    cpu=2.0,
    memory=4096,           # 4 GB RAM for Chromium + video rendering
)
def render_editor_video(render_id: str, editor_state: dict, codec: str = "h264"):
    """
    Renders a Remotion composition from the Editor's state JSON.
    Runs the Remotion renderer server as a subprocess, posts the editor state,
    streams the resulting MP4, and uploads to Supabase Storage.
    """
    import subprocess
    import time
    import json
    import tempfile
    import requests as _req

    project_root = "/root/project"
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    remotion_dir = "/root/remotion_renderer"
    server_script = os.path.join(remotion_dir, "server.js")

    if not os.path.isfile(server_script):
        raise RuntimeError(f"Remotion server.js not found: {server_script}")

    # Start the Remotion renderer HTTP server on a random port
    port = 8090
    print(f"[EDITOR RENDER] Starting Remotion renderer on port {port}...")
    env = os.environ.copy()
    env["PORT"] = str(port)
    env["DBUS_SESSION_BUS_ADDRESS"] = "/dev/null"

    proc = subprocess.Popen(
        ["node", server_script],
        cwd=remotion_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Wait for server to be ready (up to 60s for first-time bundle)
    renderer_url = f"http://localhost:{port}"
    ready = False
    for i in range(120):
        time.sleep(0.5)
        try:
            resp = _req.get(f"{renderer_url}/health", timeout=2)
            if resp.status_code == 200:
                ready = True
                print(f"[EDITOR RENDER] Renderer ready after {(i+1)*0.5:.1f}s")
                break
        except Exception:
            pass

    if not ready:
        proc.kill()
        stdout = proc.stdout.read().decode() if proc.stdout else ""
        raise RuntimeError(f"Remotion renderer failed to start. Output: {stdout[:2000]}")

    try:
        # Call the /render-editor endpoint
        print(f"[EDITOR RENDER] Sending editor state to renderer...")
        response = _req.post(
            f"{renderer_url}/render-editor",
            json={"editorState": editor_state, "codec": codec},
            timeout=540,
            stream=True,
        )

        if response.status_code != 200:
            raise RuntimeError(
                f"Renderer returned {response.status_code}: {response.text[:500]}"
            )

        # Stream the MP4 to a temp file
        from datetime import datetime as _dt
        timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
        storage_filename = f"edited_{render_id[:8]}_{timestamp}.mp4"

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            tmp_path = tmp.name

        output_size = os.path.getsize(tmp_path)
        print(f"[EDITOR RENDER] Rendered {output_size / 1024 / 1024:.1f} MB")

        # Upload to Supabase Storage
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        with open(tmp_path, "rb") as f:
            sb.storage.from_("generated-videos").upload(
                storage_filename, f,
                file_options={"content-type": "video/mp4"},
            )
        output_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)

        os.unlink(tmp_path)
        print(f"[EDITOR RENDER] ✓ Render {render_id} done: {output_url}")

        # Notify the backend so the frontend progress polling picks up the result
        callback_base = os.environ.get("BACKEND_CALLBACK_URL", "https://studio.aitoma.ai")
        try:
            _req.post(
                f"{callback_base}/api/editor/render/{render_id}/callback",
                json={
                    "status": "done",
                    "output_url": output_url,
                    "output_size": output_size,
                },
                timeout=10,
            )
            print(f"[EDITOR RENDER] Callback sent to {callback_base}")
        except Exception as cb_err:
            print(f"[EDITOR RENDER] Callback failed (non-fatal): {cb_err}")

        return {
            "status": "done",
            "render_id": render_id,
            "output_url": output_url,
            "output_size": output_size,
        }

    except Exception as e:
        print(f"[EDITOR RENDER] ✗ Render {render_id} failed: {e}")
        # Notify backend of failure
        callback_base = os.environ.get("BACKEND_CALLBACK_URL", "https://studio.aitoma.ai")
        try:
            _req.post(
                f"{callback_base}/api/editor/render/{render_id}/callback",
                json={"status": "failed", "error": str(e)[:500]},
                timeout=10,
            )
        except Exception:
            pass
        raise

    finally:
        proc.kill()
        proc.wait()


@app.function(
    image=worker_image,
    timeout=10,
)
@modal.fastapi_endpoint(method="POST")
def trigger_editor_render(request: dict):
    """
    HTTP webhook endpoint for Editor render jobs.
    Called by the FastAPI backend.

    Expects JSON body: {"render_id": "<uuid>", "editor_state": {...}, "codec": "h264"}
    Returns immediately after spawning the render function.
    """
    render_id = request.get("render_id")
    editor_state = request.get("editor_state")
    codec = request.get("codec", "h264")

    if not render_id or not editor_state:
        return {"error": "render_id and editor_state are required"}, 400

    # Spawn the heavy rendering as a separate Modal function call
    render_editor_video.spawn(render_id, editor_state, codec)

    return {"status": "dispatched", "render_id": render_id}
