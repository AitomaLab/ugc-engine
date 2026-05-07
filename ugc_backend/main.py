"""
UGC Engine v3 — FastAPI Backend (Supabase REST API)

Production API using Supabase REST API for all database operations.
No raw PostgreSQL TCP connections needed.
"""
# Fix Windows cp1252 console encoding — allows emoji/unicode in print() calls
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv
load_dotenv(".env.saas")
load_dotenv(".env")

import uuid
import random
from datetime import datetime, timezone

import stripe

from ugc_backend.cost_service import cost_service
from ugc_backend.auth import get_current_user, get_optional_user
from ugc_backend.credit_cost_service import get_video_credit_cost, get_shot_credit_cost

from ugc_db.db_manager import (
    get_supabase,
    get_stats,
    list_influencers, get_influencer, create_influencer, update_influencer, delete_influencer,
    list_projects,
    list_scripts, create_script, update_script, delete_script, get_script,
    bulk_create_scripts, increment_script_usage,
    list_app_clips, list_app_clips_by_product, update_app_clip, create_app_clip, delete_app_clip,
    list_jobs, get_job, create_job, update_job, delete_job,
    list_products, create_product, delete_product, get_product, update_product,
    list_product_shots, get_product_shot, create_product_shot, update_product_shot, delete_product_shot,
    # SaaS layer
    get_profile, update_profile,
    create_project as db_create_project, update_project as db_update_project, delete_project as db_delete_project,
    get_subscription, get_wallet, list_transactions, deduct_credits, refund_credits,
    get_stripe_customer_id, save_stripe_customer_id,
    get_plan_by_stripe_price_id, get_plan_by_id,
    upsert_subscription, cancel_subscription,
    get_user_id_by_stripe_customer, add_credits,
    list_influencers_scoped, list_scripts_scoped, list_products_scoped,
    list_app_clips_scoped, list_jobs_scoped, list_product_shots_scoped,
    get_stats_scoped,
    get_notifications,
)

# Lazy Celery import — avoids blocking the backend if Redis isn't running
def _dispatch_worker(job_id: str) -> bool:
    """Try to dispatch a job to a worker. Returns True if successful.

    Priority order:
    1. Modal serverless worker (if USE_MODAL_WORKER=true)
    2. Celery via Redis (if Redis is reachable)
    3. In-process background thread (always-available fallback)
    """

    # --- Option 1: Modal serverless worker ---
    if os.getenv("USE_MODAL_WORKER", "").lower() == "true":
        modal_url = os.getenv("MODAL_WEBHOOK_URL")
        if modal_url:
            try:
                import requests as _req
                resp = _req.post(modal_url, json={"job_id": job_id}, timeout=10)
                if resp.status_code < 300:
                    print(f"[OK] Job {job_id} dispatched to Modal worker")
                    return True
                else:
                    print(f"!! Modal dispatch returned {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"!! Modal dispatch failed: {e}, falling back to Celery/in-process")
        else:
            print("!! USE_MODAL_WORKER=true but MODAL_WEBHOOK_URL not set, falling back")

    # --- Option 2: Celery via Redis ---
    import socket
    from urllib.parse import urlparse

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    parsed = urlparse(broker_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    # Quick socket check — if Redis isn't reachable, run in-process
    redis_available = False
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        redis_available = True
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass

    if redis_available:
        try:
            from ugc_worker.tasks import generate_ugc_video
            generate_ugc_video.delay(job_id)
            print(f"[OK] Job {job_id} dispatched to Celery worker")
            return True
        except Exception as e:
            print(f"!! Celery dispatch failed: {e}, falling back to in-process")

    # --- Option 3: Fallback — run in background thread ---
    import threading

    def _run_in_background():
        try:
            print(f"[RUN] Running job {job_id} in-process (no Redis)...")
            from ugc_worker.tasks import generate_ugc_video
            # Call the underlying function directly (not as a Celery task)
            generate_ugc_video(job_id)
        except Exception as e:
            print(f"[FAIL] In-process job {job_id} failed: {e}")
            from ugc_db.db_manager import update_job
            update_job(job_id, {"status": "failed", "error_message": str(e)})

    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()
    print(f"[START] Job {job_id} started in background thread (no Redis)")
    return True


def _download_to_path(url: str, path) -> None:
    """Download a file from URL to a local Path. Used by clone B-roll assembly."""
    import requests as _req
    resp = _req.get(str(url), stream=True, timeout=120)
    resp.raise_for_status()
    with open(str(path), "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)


# Lazy dispatch for AI Clone jobs — mirrors _dispatch_worker but uses clone_engine
def _dispatch_clone_worker(job_id: str) -> bool:
    """Try to dispatch a clone job to a worker. Returns True if successful.

    Priority order:
    1. Modal serverless worker (if USE_MODAL_WORKER=true + MODAL_CLONE_WEBHOOK_URL)
    2. In-process background thread (always-available fallback)
    """

    # --- Option 1: Modal serverless worker ---
    if os.getenv("USE_MODAL_WORKER", "").lower() == "true":
        modal_url = os.getenv("MODAL_CLONE_WEBHOOK_URL")
        if modal_url:
            try:
                import requests as _req
                resp = _req.post(modal_url, json={"job_id": job_id}, timeout=10)
                if resp.status_code < 300:
                    print(f"[OK] Clone job {job_id} dispatched to Modal worker")
                    return True
                else:
                    print(f"!! Modal clone dispatch returned {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"!! Modal clone dispatch failed: {e}, falling back to in-process")
        else:
            print("!! MODAL_CLONE_WEBHOOK_URL not set, running clone job in-process")

    # --- Option 2: Fallback — run in background thread ---
    import threading
    import sys as _sys
    import traceback as _tb

    def _run_clone_in_background():
        try:
            print(f"[CLONE-THREAD] Running clone job {job_id} in-process...", flush=True)
            import clone_engine
            import storage_helper
            import subtitle_engine
            from ugc_db.db_manager import get_supabase
            from pathlib import Path
            import random
            import shutil

            sb = get_supabase()

            def update_cjob(updates: dict):
                get_supabase().table("clone_video_jobs").update(updates).eq("id", job_id).execute()

            job_result = sb.table("clone_video_jobs").select("*").eq("id", job_id).execute()
            if not job_result.data:
                print(f"[CLONE-THREAD] FAIL — Clone job {job_id} not found", flush=True)
                return
            job = job_result.data[0]

            update_cjob({"status": "processing", "progress": 5})

            clone_result = sb.table("user_ai_clones").select("*").eq("id", job["clone_id"]).execute()
            if not clone_result.data:
                raise RuntimeError(f"Clone {job['clone_id']} not found")
            clone = clone_result.data[0]

            if job.get("look_id"):
                look_result = sb.table("user_ai_clone_looks").select("*").eq("id", job["look_id"]).execute()
                if not look_result.data:
                    raise RuntimeError(f"Look {job['look_id']} not found")
                clone_image_url = look_result.data[0]["image_url"]
            else:
                all_looks = sb.table("user_ai_clone_looks").select("*").eq("clone_id", job["clone_id"]).execute()
                if not all_looks.data:
                    raise RuntimeError(f"No looks found for clone {job['clone_id']}")
                clone_image_url = random.choice(all_looks.data)["image_url"]

            # ── Fetch product details and B-roll clips ──────────────────────
            product_name = ""
            product_image_url = None
            broll_clips = []       # list of dicts: [{"video_url": ..., "duration": ...}]
            product_type = job.get("product_type", "physical")

            if job.get("product_id"):
                prod_result = sb.table("products").select("*").eq("id", job["product_id"]).execute()
                if prod_result.data:
                    product = prod_result.data[0]
                    product_name = product.get("name", "")
                    product_image_url = product.get("image_url")
                    product_type = job.get("product_type") or product.get("type", "physical")

                    if product_type == "digital":
                        # Fetch app clips for this digital product
                        clips = sb.table("app_clips").select("*").eq("product_id", job["product_id"]).execute()
                        if clips.data:
                            broll_clips = clips.data  # each has: video_url, duration, ...
                            print(f"[CLONE-THREAD] Found {len(broll_clips)} app clips for digital product", flush=True)
                    else:
                        # Fetch cinematic shots (animated) for physical product
                        shots = (
                            sb.table("product_shots")
                            .select("*")
                            .eq("product_id", job["product_id"])
                            .eq("status", "animation_completed")
                            .execute()
                        )
                        if shots.data:
                            broll_clips = [{"video_url": s["video_url"], "duration": 4.0} for s in shots.data]
                            print(f"[CLONE-THREAD] Found {len(broll_clips)} cinematic shots for physical product", flush=True)

            # ── Calculate avatar duration ────────────────────────────────────
            total_duration = job.get("duration", 15)
            has_broll = bool(broll_clips)

            if has_broll:
                # Use the first B-roll clip only (MVP: auto-pick first)
                broll_clip = broll_clips[0]
                broll_duration = float(broll_clip.get("duration", 7.0))
                avatar_duration = max(total_duration - broll_duration, 5.0)  # at least 5s of speaking
                print(f"[CLONE-THREAD] Timing: {total_duration}s total = {avatar_duration:.1f}s avatar + {broll_duration:.1f}s B-roll", flush=True)
            else:
                avatar_duration = None  # no cap — avatar speaks full duration
                print(f"[CLONE-THREAD] No B-roll clips — avatar will speak for full duration", flush=True)

            print(f"[CLONE-THREAD] Clone image: {clone_image_url}", flush=True)
            print(f"[CLONE-THREAD] Product image: {product_image_url or 'None'}", flush=True)
            print(f"[CLONE-THREAD] Script: {job['script_text'][:100]}...", flush=True)
            update_cjob({"progress": 20})

            # ── Generate avatar video (with composite if product provided) ──
            clone_gender = clone.get("gender", "male")
            print(f"[CLONE-THREAD] Clone gender: {clone_gender}", flush=True)

            avatar_url = clone_engine.generate_clone_video(
                job_id=job_id,
                clone_image_url=clone_image_url,
                elevenlabs_voice_id=clone["elevenlabs_voice_id"],
                script_text=job["script_text"],
                subtitles_enabled=job.get("subtitles_enabled", True),
                subtitle_style=job.get("subtitle_style", "hormozi"),
                subtitle_placement=job.get("subtitle_placement", "middle"),
                product_name=product_name,
                product_image_url=product_image_url,
                avatar_duration=avatar_duration,
                skip_subtitles=has_broll,  # skip if we'll assemble + burn externally
                gender=clone_gender,
                video_language=job.get("video_language", "en"),
            )

            update_cjob({"progress": 75})

            # ── Post-Processing: Assemble, Music, Subtitles ─────────────────
            import subprocess
            work_dir = Path(f"/tmp/clone_assembly_{job_id}")
            work_dir.mkdir(parents=True, exist_ok=True)

            try:
                # 1. Prepare Base Video
                avatar_path = work_dir / "avatar.mp4"
                _download_to_path(avatar_url, avatar_path)
                assembled_path = avatar_path

                if has_broll:
                    print(f"[CLONE-THREAD] Assembling avatar video + B-roll clip...", flush=True)
                    # Download first B-roll clip
                    broll_path = work_dir / "broll_0.mp4"
                    _download_to_path(broll_clip["video_url"], broll_path)

                    import sys
                    sys.path.append(str(Path(__file__).parent.parent))
                    from assemble_video import ensure_audio_stream

                    avatar_path_safe = ensure_audio_stream(avatar_path, work_dir)
                    broll_path_safe = ensure_audio_stream(broll_path, work_dir)

                    # Re-encode both for consistent format
                    avatar_enc = work_dir / "avatar_enc.mp4"
                    broll_enc = work_dir / "broll_enc.mp4"

                    for src, dst in [(avatar_path_safe, avatar_enc), (broll_path_safe, broll_enc)]:
                        cmd = [
                            "ffmpeg", "-y", "-i", str(src),
                            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                            "-r", "30",
                            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
                            "-movflags", "+faststart",
                            str(dst),
                        ]
                        subprocess.run(cmd, capture_output=True, check=True)

                    # Get dimensions from avatar to resize B-roll
                    probe_cmd = [
                        "ffprobe", "-v", "quiet", "-print_format", "json",
                        "-show_streams", str(avatar_enc),
                    ]
                    probe_result = subprocess.run(probe_cmd, capture_output=True, text=True)
                    import json
                    probe_data = json.loads(probe_result.stdout)
                    vid_stream = next((s for s in probe_data.get("streams", []) if s["codec_type"] == "video"), {})
                    aw = int(vid_stream.get("width", 720))
                    ah = int(vid_stream.get("height", 1280))

                    # Re-encode B-roll to match avatar dimensions
                    broll_matched = work_dir / "broll_matched.mp4"
                    cmd = [
                        "ffmpeg", "-y", "-i", str(broll_enc),
                        "-vf", f"scale={aw}:{ah}:force_original_aspect_ratio=decrease,pad={aw}:{ah}:(ow-iw)/2:(oh-ih)/2",
                        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
                        "-r", "30",
                        "-movflags", "+faststart",
                        str(broll_matched),
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)

                    # Concat: avatar first, then B-roll
                    concat_list = work_dir / "concat.txt"
                    with open(concat_list, "w") as f:
                        f.write(f"file '{avatar_enc.as_posix()}'\n")
                        f.write(f"file '{broll_matched.as_posix()}'\n")

                    assembled_path = work_dir / "assembled.mp4"
                    cmd = [
                        "ffmpeg", "-y",
                        "-f", "concat", "-safe", "0",
                        "-i", str(concat_list),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                        "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart",
                        str(assembled_path),
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)
                    print(f"[CLONE-THREAD] Assembly complete: {assembled_path.stat().st_size / (1024*1024):.1f} MB", flush=True)

                # ── Generate & Mix Music ─────────────────────────────────────────
                if job.get("music_enabled", True) and not job.get("skip_music", False):
                    print(f"[CLONE-THREAD] Generating background music...", flush=True)
                    try:
                        import generate_scenes
                        theme = job.get("Theme", product_name or "trendy product")
                        music_prompt = f"upbeat trendy background music for a short social media video about {theme}, energetic positive modern pop instrumental"
                        music_url = generate_scenes.generate_music(music_prompt)
                        if music_url:
                            music_path = work_dir / "music.mp3"
                            generate_scenes.download_video(music_url, music_path)
                            print(f"[CLONE-THREAD] Mixing background music...", flush=True)
                            with_music_path = work_dir / "assembled_with_music.mp4"
                            cmd = [
                                "ffmpeg", "-y",
                                "-i", str(assembled_path),
                                "-stream_loop", "-1", "-i", str(music_path),
                                "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:weights=2 0.2[a]",
                                "-map", "0:v", "-map", "[a]",
                                "-c:v", "copy",
                                "-c:a", "aac", "-b:a", "192k",
                                str(with_music_path)
                            ]
                            subprocess.run(cmd, capture_output=True)
                            assembled_path = with_music_path
                    except Exception as music_err:
                        print(f"[CLONE-THREAD] Music generation failed: {music_err}", flush=True)

                update_cjob({"progress": 85})

                # ── Burn Subtitles ───────────────────────────────────────────────
                final_path = assembled_path
                if job.get("subtitles_enabled", True):
                    print(f"[CLONE-THREAD] Burning subtitles on video...", flush=True)
                    subtitle_style = job.get("subtitle_style", "hormozi")
                    subtitle_placement = job.get("subtitle_placement", "middle")
                    use_remotion = os.getenv("USE_REMOTION_SUBTITLES", "true").lower() == "true"
                    
                    try:
                        brand_names = [product_name] if product_name else []
                        transcription = subtitle_engine.extract_transcription_with_whisper(
                            str(assembled_path),
                            brand_names=brand_names or None,
                            script_text=job["script_text"],
                            video_language=job.get("video_language", "en"),
                        )
                        if transcription and transcription.get("words"):
                            captioned_path = None
                            
                            # Remotion Path
                            if use_remotion:
                                try:
                                    print(f"[CLONE-THREAD] Rendering with Remotion (style={subtitle_style})...", flush=True)
                                    import json as _json
                                    import tempfile as _tempfile
                                    
                                    remotion_dir = "/root/remotion_renderer"
                                    if not os.path.isdir(remotion_dir):
                                        remotion_dir = os.path.join(os.path.dirname(__file__), "..", "remotion_renderer")
                                        
                                    render_script = os.path.join(remotion_dir, "render_captions.js")
                                    
                                    props = {
                                        "transcription": transcription,
                                        "subtitleStyle": subtitle_style,
                                        "subtitlePlacement": subtitle_placement,
                                    }
                                    with _tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as pf:
                                        _json.dump(props, pf)
                                        props_path = pf.name
                                        
                                    captioned_output = str(work_dir / "final_remotion.mp4")
                                    cmd = [
                                        "node", render_script,
                                        "--input", str(assembled_path),
                                        "--props", props_path,
                                        "--output", captioned_output,
                                    ]
                                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=remotion_dir)
                                    try:
                                        os.unlink(props_path)
                                    except OSError:
                                        pass
                                        
                                    if result.returncode == 0 and os.path.isfile(captioned_output):
                                        captioned_path = captioned_output
                                        print(f"[CLONE-THREAD] Remotion render complete", flush=True)
                                    else:
                                        print(f"[CLONE-THREAD] Remotion failed, falling back. Code: {result.returncode}, Stderr: {result.stderr}", flush=True)
                                except Exception as rem_err:
                                    print(f"[CLONE-THREAD] Remotion error: {rem_err}, falling back", flush=True)

                            # FFmpeg Fallback Path
                            if not captioned_path:
                                print(f"[CLONE-THREAD] Rendering with FFmpeg fallback...", flush=True)
                                subtitle_path = work_dir / "subtitles.ass"
                                subtitle_engine.generate_subtitles_from_whisper(
                                    transcription, subtitle_path, brand_names=brand_names or None
                                )
                                if subtitle_path.exists() and subtitle_path.stat().st_size > 250:
                                    sub_safe = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
                                    subtitled_path = work_dir / "final_subtitled.mp4"
                                    cmd = [
                                        "ffmpeg", "-y",
                                        "-i", str(assembled_path),
                                        "-vf", f"ass={sub_safe}",
                                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                                        "-c:a", "copy",
                                        str(subtitled_path),
                                    ]
                                    result = subprocess.run(cmd, capture_output=True)
                                    if result.returncode == 0:
                                        captioned_path = str(subtitled_path)
                                        print("[CLONE-THREAD] Subtitles burned with FFmpeg", flush=True)
                                        
                            if captioned_path:
                                final_path = Path(captioned_path)
                    except Exception as sub_err:
                        print(f"[CLONE-THREAD] Subtitle application failed: {sub_err}", flush=True)

                # Upload final assembled video
                destination = f"clone-videos/{job_id}/final.mp4"
                final_url = storage_helper.upload_to_supabase_storage(
                    file_path=str(final_path),
                    bucket="generated-videos",
                    destination_path=destination,
                )
                print(f"[CLONE-THREAD] Final video uploaded: {final_url}", flush=True)
            finally:
                shutil.rmtree(work_dir, ignore_errors=True)

            update_cjob({"status": "complete", "progress": 100, "final_video_url": final_url})
            print(f"[CLONE-THREAD] ✓ Clone job {job_id} complete: {final_url}", flush=True)
        except Exception as e:
            print(f"[CLONE-THREAD] ✗ Clone job {job_id} failed: {e}", flush=True)
            _tb.print_exc()
            _sys.stdout.flush()
            from ugc_db.db_manager import get_supabase
            get_supabase().table("clone_video_jobs").update({
                "status": "failed", "error_message": str(e)[:1000],
            }).eq("id", job_id).execute()

    thread = threading.Thread(target=_run_clone_in_background, daemon=False, name=f"clone-{job_id[:8]}")
    thread.start()
    print(f"[CLONE-THREAD] Clone job {job_id} started in background thread", flush=True)
    return True

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

from ugc_backend.api_clones import router as clones_router

app = FastAPI(title="UGC Engine SaaS API v3")

# Stripe configuration
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")


def _resolve_project_id(request: Request, user: dict | None) -> str | None:
    """Read X-Project-Id header sent by the frontend.
    Falls back to the user's default project if the header is missing.
    Callers that want cross-project data (dashboard aggregations) send
    X-Skip-Project-Scope: 1 — we return None in that case so the caller
    queries across all of the user's projects."""
    if request.headers.get("x-skip-project-scope"):
        return None
    pid = request.headers.get("x-project-id")
    if pid:
        return pid
    if user:
        user_projects = list_projects(user["id"])
        default_proj = next((p for p in (user_projects or []) if p.get("is_default")), (user_projects or [None])[0])
        return default_proj["id"] if default_proj else None
    return None

# CORS — allow origins from environment (comma-separated), defaulting to localhost + production
_cors_env = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,https://studio.aitoma.ai")
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(clones_router)

# Remotion Editor integration — isolated microservice
from ugc_backend.editor_api import router as editor_router
app.include_router(editor_router)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    try:
        get_supabase()
        print(">> Connected to Supabase (REST API)")
    except Exception as e:
        print(f"!! WARNING: Supabase connection failed: {e}")


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class InfluencerCreate(BaseModel):
    name: str
    gender: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    style: Optional[str] = None
    speaking_style: Optional[str] = None
    target_audience: Optional[str] = None
    image_url: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    setting: Optional[str] = None  # Background/environment description (e.g. "outdoor garden with trees")
    character_views: Optional[list] = None  # JSON array of character sheet view URLs

class ScriptCreate(BaseModel):
    """Create a script. Supports both legacy (text only) and v2 (structured JSON)."""
    text: Optional[str] = None             # Legacy ||| delimited string
    name: Optional[str] = None
    script_json: Optional[dict] = None     # New structured format
    category: Optional[str] = "General"
    methodology: Optional[str] = "Hook/Benefit/CTA"
    video_length: Optional[int] = 15
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None
    source: Optional[str] = "manual"

class ScriptUpdate(BaseModel):
    """Partial update for a script."""
    name: Optional[str] = None
    text: Optional[str] = None
    script_json: Optional[dict] = None
    category: Optional[str] = None
    methodology: Optional[str] = None
    video_length: Optional[int] = None
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None

class ScriptBulkItem(BaseModel):
    name: Optional[str] = None
    script_json: dict
    category: str = "General"
    methodology: str = "Hook/Benefit/CTA"
    video_length: int = 15
    source: str = "csv_upload"


class AppClipCreate(BaseModel):
    name: str
    description: Optional[str] = None
    video_url: str
    duration_seconds: Optional[int] = None
    product_id: Optional[str] = None       # NEW: Link to a digital product
    first_frame_url: Optional[str] = None  # NEW: Auto-populated on upload

class ProductCreate(BaseModel):
    name: str
    type: Optional[str] = None              # "physical" or "digital"
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None      # Optional for digital products (auto-populated from clip frame)
    website_url: Optional[str] = None      # NEW: For dual-source AI analysis
    product_views: Optional[list] = None   # 4-view product shots from Generate Shots

class AppClipUpdate(BaseModel):            # NEW: For PATCH endpoint
    product_id: Optional[str] = None
    first_frame_url: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

class ShotGenerateRequest(BaseModel):
    shot_type: str
    variations: int = 1
    prompt: Optional[str] = None  # Custom prompt (e.g. from Creative OS enhance flow)
    influencer_image_url: Optional[str] = None  # Model/influencer face reference for NanoBanana Pro

class TransitionShotRequest(BaseModel):
    transition_type: str = "match_cut"      # 'match_cut', 'whip_pan', 'focus_pull'
    target_style: Optional[str] = None      # 'studio_white', 'natural_setting', 'moody'
    preceding_scene_video_url: str          # URL of the preceding influencer scene video

class JobCreate(BaseModel):
    influencer_id: Optional[str] = None
    script_id: Optional[str] = None
    app_clip_id: Optional[str] = None
    product_id: Optional[str] = None            # NEW for Physical Products
    product_type: str = "digital"               # 'digital' or 'physical'
    hook: Optional[str] = None
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    length: int = 15
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None
    cinematic_shot_ids: Optional[List[str]] = None  # Cinematic Product Shots
    auto_transition_type: Optional[str] = None      # 'match_cut', 'whip_pan', 'focus_pull'
    # Subtitle configuration
    subtitles_enabled: Optional[bool] = True
    subtitle_style: Optional[str] = "hormozi"
    subtitle_placement: Optional[str] = "middle"
    # Language
    video_language: str = "en"                   # 'en' or 'es' — defaults to English
    # Music
    music_enabled: Optional[bool] = True

class BulkJobCreate(BaseModel):
    influencer_id: str
    count: int = 1
    duration: int = 15
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    product_type: str = "digital"               # NEW for Physical Products
    product_id: Optional[str] = None            # NEW for Physical Products
    hook: Optional[str] = None                  # AI-generated script from frontend
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None         # Campaign grouping name
    cinematic_shot_ids: Optional[List[str]] = None  # Cinematic Product Shots
    auto_transition_type: Optional[str] = None      # 'match_cut', 'whip_pan', 'focus_pull'
    # Subtitle configuration
    subtitles_enabled: Optional[bool] = True
    subtitle_style: Optional[str] = "hormozi"
    subtitle_placement: Optional[str] = "middle"
    # Language
    video_language: str = "en"                   # 'en' or 'es' — defaults to English
    # Music
    music_enabled: Optional[bool] = True

class SignedUrlRequest(BaseModel):
    bucket: str = "product-images"
    file_name: str

class CostEstimateRequest(BaseModel):
    script_text: str = ""
    duration: int = 15
    model: str = "seedance-1.5-pro"
    music_enabled: Optional[bool] = True


# ... (existing classes)

# ---------------------------------------------------------------------------
# Products CRUD
# ---------------------------------------------------------------------------

@app.get("/api/products")
def api_list_products(request: Request, category: Optional[str] = None, user: dict = Depends(get_optional_user)):
    try:
        if user:
            pid = _resolve_project_id(request, user)
            if pid:
                products = list_products_scoped(user["id"], pid, category)
            else:
                # Skip-scope: list products across ALL of the user's projects
                sb = get_supabase()
                q = sb.table("products").select("*").eq("user_id", user["id"])
                if category:
                    q = q.eq("category", category)
                products = q.execute().data or []
        else:
            products = list_products(category)

        for p in products:
            if p.get("type") == "digital":
                try:
                    clips = list_app_clips_by_product(p["id"]) or []
                    p["app_clips"] = [
                        {
                            "id": c.get("id"),
                            "name": c.get("name"),
                            "video_url": c.get("video_url"),
                            "first_frame_url": c.get("first_frame_url"),
                            "duration_seconds": c.get("duration_seconds"),
                        }
                        for c in clips
                    ]
                except Exception as clip_err:
                    print(f"WARN: failed to load app clips for product {p.get('id')}: {clip_err}")
                    p["app_clips"] = []
        return products
    except Exception as e:
        print(f"ERROR in api_list_products: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products")
def api_create_product(data: ProductCreate, request: Request, user: dict = Depends(get_optional_user)):
    try:
        payload = data.model_dump(exclude_none=True)
        if user:
            payload["user_id"] = user["id"]
            pid = _resolve_project_id(request, user)
            if pid:
                payload["project_id"] = pid
        # Ensure image_url has a value (DB has NOT NULL constraint).
        # Digital products get their image from the clip's first frame later.
        if "image_url" not in payload:
            payload["image_url"] = ""
        print(f"DEBUG: api_create_product called with {payload}")
        result = create_product(payload)
        print(f"DEBUG: create_product result: {result}")
        return result
    except Exception as e:
        print(f"ERROR in api_create_product: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}")
def api_get_product(product_id: str, user: dict = Depends(get_optional_user)):
    from ugc_db.db_manager import get_product
    p = get_product(product_id)
    if not p:
        raise HTTPException(status_code=404, detail="Product not found")
    if user and p.get("user_id") and p["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="Product not found")
    return p

@app.put("/api/products/{product_id}")
def api_update_product(product_id: str, data: dict):
    try:
        from ugc_db.db_manager import update_product
        print(f"DEBUG: api_update_product {product_id} with {data}")
        result = update_product(product_id, data)
        return result
    except Exception as e:
        print(f"ERROR in api_update_product: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{product_id}")
def api_delete_product(product_id: str):
    try:
        delete_product(product_id)
        return {"status": "deleted", "id": product_id}
    except Exception as e:
        error_str = str(e)
        if "foreign key constraint" in error_str or "23503" in error_str:
            raise HTTPException(
                status_code=409, 
                detail="Cannot delete product because it is used in existing videos. Please delete the videos first."
            )
        print(f"ERROR in api_delete_product: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import UploadFile, File


@app.post("/api/products/upload")
async def api_product_upload(file: UploadFile = File(...)):
    try:
        import uuid
        contents = await file.read()
        max_bytes = 50 * 1024 * 1024
        if len(contents) > max_bytes:
            raise HTTPException(status_code=413, detail="File too large (max 50 MB).")

        content_type = (file.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail=f"Expected image upload, got {content_type!r}")

        from ugc_db.image_normalize import normalize_image_bytes
        png_bytes = normalize_image_bytes(contents)
        unique_name = f"{uuid.uuid4()}.png"

        sb = get_supabase()
        bucket = "product-images"
        sb.storage.from_(bucket).upload(
            unique_name, png_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
        public_url = sb.storage.from_(bucket).get_public_url(unique_name)
        print(f"[Product Upload] {file.filename!r} ({len(contents)} B) -> {unique_name} ({len(png_bytes)} B PNG)")
        return {"public_url": public_url, "path": unique_name}

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in api_product_upload: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)[:200]}")


class ProductAnalyzeRequest(BaseModel):
    product_id: str

@app.post("/api/products/analyze")
def api_analyze_product(data: ProductAnalyzeRequest):
    try:
        from ugc_backend.llm_vision_client import LLMVisionClient
        from ugc_db.db_manager import get_product, update_product
        
        print(f"DEBUG: Analyzing product {data.product_id}")
        
        # 1. Fetch Product
        product = get_product(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
            
        if not product.get("image_url"):
            raise HTTPException(status_code=400, detail="Product has no image URL")
            
        # 2. Analyze
        client = LLMVisionClient()
        analysis = client.describe_product_image(product["image_url"])
        
        if not analysis:
            raise HTTPException(status_code=500, detail="Vision analysis failed or returned empty")
            
        print(f"DEBUG: Analysis result: {analysis}")
        
        # 3. Update DB
        # Note: Using visual_description column as per Directive, mapping analysis result to it.
        # Ensure the column used matches DB schema. 
        # The prompt requested 'visual_description' JSONB. 
        # If migration 005 used 'visual_analysis', we should align. 
        # I will use 'visual_description' here and ensure migration 006 adds it.
        update_product(data.product_id, {"visual_description": analysis})
        
        return analysis
        
    except Exception as e:
        print(f"ERROR in api_analyze_product: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class ProductAnalyzeImageRequest(BaseModel):
    image_url: str
    product_id: Optional[str] = None  # If provided, saves result to product

@app.post("/api/products/analyze-image")
def api_analyze_product_image(data: ProductAnalyzeImageRequest):
    """Analyze a product image directly — no saved product required.

    If product_id is provided, also persists the result to the product record.
    """
    try:
        from ugc_backend.llm_vision_client import LLMVisionClient

        if not data.image_url:
            raise HTTPException(status_code=400, detail="image_url is required")

        print(f"DEBUG: Analyzing product image directly: {data.image_url[:80]}...")

        client = LLMVisionClient()
        analysis = client.describe_product_image(data.image_url)

        if not analysis:
            raise HTTPException(status_code=500, detail="Vision analysis failed or returned empty")

        print(f"DEBUG: Analysis result: {analysis}")

        # Persist to product if product_id is provided
        if data.product_id:
            from ugc_db.db_manager import update_product
            update_product(data.product_id, {"visual_description": analysis})
            print(f"DEBUG: Saved analysis to product {data.product_id}")

        return analysis

    except Exception as e:
        print(f"ERROR in api_analyze_product_image: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id}/analyze-digital")
def api_analyze_digital_product(product_id: str):
    """
    Scrapes the product website and uses GPT to extract structured product
    insights (description, benefits, audience, USPs) for script generation.
    """
    try:
        from ugc_backend.web_scraper import WebScraperClient
        import openai, json as _json

        product = get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        analysis = {}

        # Step 1: Scrape the website
        website_text = None
        if product.get("website_url"):
            try:
                scraper = WebScraperClient()
                website_text = scraper.scrape(product["website_url"])
                print(f"      [OK] Website scraping complete for product {product_id} ({len(website_text or '')} chars)")
            except Exception as e:
                print(f"      !! Website scraping failed (non-fatal): {e}")

        if not website_text:
            raise HTTPException(status_code=422, detail="Could not scrape website content. Check the URL.")

        # Step 2: Send scraped text to GPT for intelligent analysis
        try:
            client = openai.OpenAI()
            resp = client.chat.completions.create(
                model="gpt-4.1-mini",
                temperature=0.3,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": (
                        "You are a product analyst. Given raw website text from a digital product/app, "
                        "extract structured insights in JSON format. Return ONLY a JSON object with these keys:\n"
                        "- product_summary: A 2-3 sentence description of what the product is and does.\n"
                        "- key_benefits: An array of 3-5 main benefits for users (short, punchy phrases).\n"
                        "- target_audience: Who this product is for (1-2 sentences).\n"
                        "- unique_selling_points: An array of 2-4 things that make it stand out from competitors.\n"
                        "- tone_and_personality: The brand's voice/tone in 2-3 words (e.g. 'Friendly, Professional, Bold').\n"
                        "- category: The product category (e.g. 'Productivity', 'Health & Fitness', 'Finance', etc.).\n"
                        "Be concise and direct. Focus on what matters for creating compelling UGC video scripts."
                    )},
                    {"role": "user", "content": f"Product name: {product.get('name', 'Unknown')}\n\nWebsite content:\n{website_text[:2500]}"}
                ]
            )
            raw = resp.choices[0].message.content
            analysis = _json.loads(raw)
            print(f"      [OK] GPT analysis complete for product {product_id}")
        except Exception as e:
            print(f"      !! GPT analysis failed: {e}")
            # Fallback: store raw text summary if GPT fails
            analysis["website_content_summary"] = website_text[:1000]

        if analysis:
            update_product(product_id, {"visual_description": analysis})
            return {"status": "analyzed", "product_id": product_id, "analysis": analysis}
        else:
            raise HTTPException(status_code=422, detail="Analysis returned no data.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in api_analyze_digital_product: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class ScriptGenerateRequest(BaseModel):
    product_id: str
    duration: int = 15
    influencer_id: Optional[str] = None
    product_type: str = "physical"         # "digital" or "physical"
    output_format: str = "json"            # "json" (new) or "legacy" (||| string)
    methodology: Optional[str] = None      # Force a specific methodology
    context: Optional[str] = None          # Additional user instructions
    video_language: str = "en"             # 'en' or 'es' — defaults to English
    model_api: str = ""                    # AI model (e.g. "seedance-2.0") for adapted word counts

@app.post("/api/scripts/generate")
def api_generate_script(data: ScriptGenerateRequest):
    """
    Generates a UGC script for a product.

    output_format="json" -> Uses three-call prompt chain, returns script_json.
    output_format="legacy" -> Uses the original single-call method, returns ||| string.
    """
    try:
        from ugc_backend.ai_script_client import AIScriptClient

        print(f"DEBUG: Generating {data.product_type} script for product {data.product_id} ({data.duration}s, format={data.output_format})")

        product = get_product(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        client = AIScriptClient()

        # Build influencer data dict (used by both paths)
        influencer_data = None
        if data.influencer_id:
            influencer = get_influencer(data.influencer_id)
            if influencer:
                influencer_data = {
                    "name": influencer.get("name", ""),
                    "personality": influencer.get("personality", ""),
                    "style": influencer.get("style", ""),
                    "gender": influencer.get("gender", "Female"),
                    "age": influencer.get("age", "25-year-old"),
                    "accent": influencer.get("accent", "neutral English"),
                    "tone": influencer.get("tone", "Enthusiastic"),
                    "energy_level": influencer.get("energy_level", "High"),
                }

        # === NEW: Structured JSON output via three-call prompt chain ===
        if data.output_format == "json":
            product_data = {
                "name": product.get("name", "Product"),
                "brand_name": product.get("name", "Product"),
                "category": product.get("category", data.product_type),
                **(product.get("visual_description") or {}),
            }
            script_json = client.generate_structured_script(
                product_data=product_data,
                influencer_data=influencer_data or {"name": "Creator"},
                video_length=data.duration,
                methodology=data.methodology,
                context=data.context,
                video_language=data.video_language,
                model_api=data.model_api,
                product_type=data.product_type,
            )
            return {"script_json": script_json, "product_id": data.product_id}

        # === LEGACY FALLBACK: ||| delimited string ===
        if data.product_type == "physical":
            visuals = product.get("visual_description") or {}
            script = client.generate_physical_product_script(
                product_analysis=visuals,
                duration=data.duration,
                product_name=product.get("name", "Product"),
                influencer_data=influencer_data,
                model_api=data.model_api,
                video_language=data.video_language,
                context=data.context or "",
            )
        else:
            visuals = product.get("visual_description") or {}
            website_content = None

            if product.get("website_url"):
                try:
                    from ugc_backend.web_scraper import WebScraperClient
                    scraper = WebScraperClient()
                    website_content = scraper.scrape(product["website_url"])
                    print(f"      [OK] Scraped {len(website_content or '')} chars from {product['website_url']}")
                except Exception as e:
                    print(f"      !! Website scraping failed (non-fatal): {e}")

            script = client.generate_digital_product_script(
                product_name=product.get("name", "App"),
                product_analysis=visuals,
                website_content=website_content,
                duration=data.duration,
                video_language=data.video_language,
            )

        return {"script": script, "product_id": data.product_id}

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in api_generate_script: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.post("/jobs")
def api_create_job(
    request: Request,
    data: JobCreate,
    user: dict = Depends(get_optional_user),
    skip_dispatch: bool = False,
):
    """
    Creates a new video generation job.
    Supports both digital (app demo) and physical product flows.
    """
    try:
        # 0. Credit Gate (only for authenticated users)
        if user:
            try:
                credit_cost = get_video_credit_cost(data.product_type, data.length)
                wallet = get_wallet(user["id"])
                if not wallet:
                    raise HTTPException(status_code=402, detail="Credit wallet not found. Please contact support.")
                if wallet["balance"] < credit_cost:
                    raise HTTPException(
                        status_code=402,
                        detail=f"Insufficient credits. Current balance: {wallet['balance']}. Required: {credit_cost}."
                    )
            except HTTPException:
                raise
            except Exception as e:
                print(f"      [Credit] Warning: credit check failed ({e}), proceeding anyway")
                credit_cost = None
        else:
            credit_cost = None

        # 1. Validate Influencer (optional — Seedance product-only modes skip this)
        inf = None
        if data.influencer_id:
            inf = get_influencer(data.influencer_id)
            if not inf:
                raise HTTPException(status_code=404, detail="Influencer not found")

        # 2. Flow-specific Validation
        if data.product_type == "physical" and not data.product_id:
            raise HTTPException(status_code=400, detail="product_id required for physical products")

        # 3. Resolve script text from explicit script_id or hook
        # NOTE: Random script auto-selection was removed — it was a deprecated
        # bulk campaign behavior that overrode agent-provided scripts. The agent
        # now handles script generation via generate_scripts() or passes the
        # user's script directly as `hook`. If neither is provided, the worker
        # falls back to a generic line ("Check this out!") which is intentional.
        script_text = ""
        if data.script_id:
            s = get_script(data.script_id)
            if s: script_text = s.get("text", "")
        elif data.hook:
            script_text = data.hook

        # 4. App clip selection / validation
        # If the agent passes an app_clip_id that doesn't belong to the product, or
        # omits it for a digital product, auto-select a valid one to prevent hallucinations.
        selected_clip_id = data.app_clip_id
        if data.product_type == "digital" and data.product_id:
            product_clips = list_app_clips_by_product(data.product_id)
            if product_clips:
                valid_clip_ids = {c["id"] for c in product_clips}
                if not selected_clip_id or selected_clip_id not in valid_clip_ids:
                    # Auto-select the first available clip for this product
                    selected_clip_id = product_clips[0]["id"]
                    print(f"      [Validation] Overrode app_clip_id to valid clip for product: {selected_clip_id}")

        # 5. Calculate Cost Estimate
        costs = cost_service.estimate_total_cost(
            script_text=script_text,
            duration=data.length,
            model=data.model_api,
            product_type=data.product_type,
            music_enabled=data.music_enabled if data.music_enabled is not None else True,
        )

        # 6. Prepare Job Data — dynamically detect actual DB columns
        # Query one row to discover real column names (empty table → fallback list)
        try:
            _probe = get_supabase().table("video_jobs").select("*").limit(1).execute()
            db_columns = set(_probe.data[0].keys()) if _probe.data else set()
        except Exception:
            db_columns = set()

        # Fallback: known safe columns if table is empty or query fails
        if not db_columns:
            db_columns = {
                "id", "user_id", "influencer_id", "app_clip_id", "script_id",
                "status", "progress", "final_video_url", "created_at", "updated_at",
                "product_type", "product_id", "project_id", "cost_image",
                "hook", "model_api", "assistant_type", "length", "campaign_name",
                "cost_video", "cost_voice", "cost_music", "cost_processing", "total_cost",
                "cinematic_shot_ids", "error_message",
                "subtitles_enabled", "subtitle_style", "subtitle_placement",
                "video_language", "music_enabled",
                "preview_url", "preview_type", "status_message",
            }

        job_data = data.model_dump(exclude_none=True)
        job_data.update(costs)
        job_data["status"] = "pending"
        job_data["progress"] = 0
        if selected_clip_id:
            job_data["app_clip_id"] = selected_clip_id

        # Inject user_id and project_id if authenticated
        if user:
            job_data["user_id"] = user["id"]
            pid = _resolve_project_id(request, user)
            if pid and "project_id" in db_columns:
                job_data["project_id"] = pid

        # Extract transition info for the worker (stored in job_data if column exists)
        auto_trans = job_data.pop("auto_transition_type", None)
        if auto_trans and "auto_transition_type" in db_columns:
            job_data["auto_transition_type"] = auto_trans

        # Store metadata if the column exists, otherwise just log it
        if "metadata" in db_columns:
            metadata = {}
            if auto_trans:
                metadata["auto_transition_type"] = auto_trans
            if job_data.get("cinematic_shot_ids"):
                metadata["cinematic_shot_ids"] = job_data["cinematic_shot_ids"]
            if data.hook:
                metadata["hook"] = data.hook
            if metadata:
                job_data["metadata"] = metadata

        # Strip any fields that don't exist as actual DB columns
        unknown_keys = [k for k in list(job_data.keys()) if k not in db_columns]
        for k in unknown_keys:
            val = job_data.pop(k)
            try:
                safe_val = str(val).encode('ascii', 'ignore').decode('ascii')[:80]
                print(f"   !! Stripped unknown column '{k}' (value: {safe_val})")
            except:
                pass

        print(f"DEBUG api_create_job: inserting keys={list(job_data.keys())}")
        # ── Trace hook for script-passthrough debugging ──
        _hook_val = job_data.get("hook", "")
        print(f"DEBUG api_create_job: hook={'YES (' + str(len(_hook_val)) + ' chars)' if _hook_val else 'NONE'}")
        if _hook_val:
            print(f"DEBUG api_create_job: hook_preview={repr(_hook_val[:120])}")
        print(f"DEBUG api_create_job: video_language={job_data.get('video_language', 'NOT SET')}")

        # 7. Deduct credits (before creating job, so failed creation doesn't lose credits)
        deduction_result = None
        if user and credit_cost:
            try:
                deduction_result = deduct_credits(user["id"], credit_cost, {
                    "product_type": data.product_type,
                    "length": data.length,
                })
                print(f"      [Credit] Deducted {credit_cost} credits. New balance: {deduction_result['balance']}")
            except ValueError as e:
                raise HTTPException(status_code=402, detail=str(e))

        # 8. Create in DB
        job = create_job(job_data)
        if not job:
            # Refund if job creation failed
            if deduction_result and user:
                refund_credits(user["id"], credit_cost, {"reason": "job_creation_failed"})
            raise HTTPException(status_code=500, detail="Job creation returned empty result")

        # 9. Dispatch to Worker (non-blocking) — skip when caller handles its own pipeline
        if skip_dispatch:
            print(f"[Creative OS] Job {job['id']} created (skip_dispatch=True — no worker)")
            worker_dispatched = False
        else:
            worker_dispatched = _dispatch_worker(job["id"])

        return {**job, "worker_dispatched": worker_dispatched, "credits_deducted": credit_cost}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Job creation failed: {str(e)}")




# ---------------------------------------------------------------------------
# Product Shots API (Cinematic Product Shots)
# ---------------------------------------------------------------------------

@app.get("/api/products/{product_id}/shots")
def api_list_product_shots(product_id: str):
    """List all cinematic shots for a product."""
    try:
        return list_product_shots(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _dispatch_shot_task(task_func, shot_id: str, task_name: str):
    """Dispatch a cinematic shot task — tries Celery, falls back to in-process thread."""
    import socket, threading
    from urllib.parse import urlparse

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    parsed = urlparse(broker_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    redis_available = False
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        redis_available = True
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass

    if redis_available:
        try:
            task_func.delay(shot_id)
            print(f"[OK] Shot task '{task_name}' dispatched to Celery for {shot_id}")
            return
        except Exception as e:
            print(f"!! Celery dispatch failed: {e}, falling back to in-process")

    # Fallback: run directly in a background thread (no Redis needed)
    def _run():
        try:
            print(f"[RUN] Running shot task '{task_name}' in-process for {shot_id}...")
            task_func(shot_id)
        except Exception as e:
            print(f"[FAIL] Shot task '{task_name}' failed: {e}")
            update_product_shot(shot_id, {"status": "failed", "error_message": str(e)})

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f"[START] Shot task '{task_name}' started in background thread for {shot_id}")


@app.post("/api/products/{product_id}/shots")
def api_generate_shot_image(product_id: str, data: ShotGenerateRequest):
    """Creates records and dispatches tasks to generate still images."""
    from ugc_worker.tasks import generate_product_shot_image
    try:
        created_shots = []
        for _ in range(data.variations):
            shot_data = {
                "product_id": product_id,
                "shot_type": data.shot_type,
                "status": "image_pending"
            }
            if data.prompt:
                shot_data["prompt"] = data.prompt
            if data.influencer_image_url:
                shot_data["analysis_json"] = {"influencer_image_url": data.influencer_image_url}
            shot = create_product_shot(shot_data)
            _dispatch_shot_task(generate_product_shot_image, shot["id"], "generate_product_shot_image")
            created_shots.append(shot)
        return created_shots
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}/shots")
def api_get_product_shots(product_id: str):
    """Get all existing shots for a specific product."""
    from ugc_db.db_manager import list_product_shots
    try:
        return list_product_shots(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shots/{shot_id}/animate")
def api_animate_shot(shot_id: str):
    """Dispatches a task to animate a still image into a video."""
    from ugc_worker.tasks import animate_product_shot_video
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise HTTPException(status_code=404, detail="Product shot not found")
        if not shot.get("image_url"):
            raise HTTPException(status_code=400, detail="Shot has no image yet")
        _dispatch_shot_task(animate_product_shot_video, shot_id, "animate_product_shot_video")
        return {"status": "animation_queued", "shot_id": shot_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/shots/costs")
def api_get_shot_costs():
    """Return cost estimates for cinematic shot generation."""
    return {
        "image_generation_cost": cost_service.estimate_shot_image_cost(),
        "animation_cost": cost_service.estimate_shot_animation_cost(),
    }

@app.delete("/api/shots/{shot_id}")
def api_delete_shot(shot_id: str):
    """Delete a product shot from the database."""
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise HTTPException(status_code=404, detail="Product shot not found")
        delete_product_shot(shot_id)
        return {"status": "deleted", "shot_id": shot_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id}/transition-shot")
def api_create_transition_shot(product_id: str, data: TransitionShotRequest):
    """
    Creates a transition shot that seamlessly blends with the preceding UGC scene.
    Pipeline: extract last frame → analyze → generate context-aware image → animate → stitch.
    """
    from ugc_worker.tasks import generate_transition_shot
    from ugc_db.db_manager import get_product

    valid_transitions = {"match_cut", "whip_pan", "focus_pull"}
    if data.transition_type not in valid_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition_type. Must be one of: {valid_transitions}",
        )

    try:
        product = get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Create a product_shot record with transition metadata
        shot = create_product_shot({
            "product_id": product_id,
            "shot_type": "hero",  # Default base shot type for transitions
            "status": "image_pending",
            "transition_type": data.transition_type,
            "preceding_video_url": data.preceding_scene_video_url,
        })

        _dispatch_shot_task(
            generate_transition_shot,
            shot["id"],
            "generate_transition_shot",
        )

        return {
            "status": "transition_shot_queued",
            "shot_id": shot["id"],
            "transition_type": data.transition_type,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# ENDPOINTS
# =========================================================================

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0", "database": "supabase-rest"}


# ---------------------------------------------------------------------------
# Influencers CRUD
# ---------------------------------------------------------------------------

@app.get("/influencers")
def api_list_influencers(request: Request, user: dict = Depends(get_optional_user)):
    if user:
        pid = _resolve_project_id(request, user)
        if pid:
            return list_influencers_scoped(user["id"], pid)
        # Skip-scope: list influencers across ALL of the user's projects
        sb = get_supabase()
        return sb.table("influencers").select("*").eq("user_id", user["id"]).execute().data or []
    return list_influencers()

@app.get("/influencers/{influencer_id}")
def api_get_influencer(influencer_id: str):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    return inf

@app.post("/influencers")
def api_create_influencer(data: InfluencerCreate, request: Request, user: dict = Depends(get_optional_user)):
    try:
        payload = data.model_dump(exclude_none=True)
        # Inject ownership so the influencer appears in scoped queries
        if user:
            payload["user_id"] = user["id"]
            pid = _resolve_project_id(request, user)
            if pid:
                payload["project_id"] = pid
            print(f"  [DEBUG] CREATE INFLUENCER: user={user['id']}, project_id={pid}, payload_keys={list(payload.keys())}")
        else:
            print(f"  [DEBUG] CREATE INFLUENCER: NO USER (unauthenticated)")
        result = create_influencer(payload)
        print(f"  [DEBUG] CREATED: id={result.get('id')}, user_id={result.get('user_id')}, project_id={result.get('project_id')}")

        # Auto-analyze background setting from reference image (non-blocking)
        if result and result.get("image_url") and not result.get("setting"):
            import threading
            def _analyze_setting():
                try:
                    from ugc_backend.llm_vision_client import LLMVisionClient
                    client = LLMVisionClient()
                    setting = client.analyze_influencer_setting(result["image_url"])
                    if setting:
                        update_influencer(result["id"], {"setting": setting})
                        print(f"      [OK] Auto-analyzed setting for {result.get('name')}: {setting}")
                except Exception as e:
                    print(f"      !! Setting analysis failed for {result.get('name')}: {e}")
            threading.Thread(target=_analyze_setting, daemon=True).start()

        return result
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Influencer '{data.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/influencers/{influencer_id}")
def api_update_influencer(influencer_id: str, data: InfluencerCreate):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    update_data = data.model_dump(exclude_none=True)
    result = update_influencer(influencer_id, update_data)

    # Re-analyze setting if image_url changed and no explicit setting was provided
    image_changed = update_data.get("image_url") and update_data["image_url"] != inf.get("image_url")
    if image_changed and "setting" not in update_data:
        import threading
        def _analyze_setting():
            try:
                from ugc_backend.llm_vision_client import LLMVisionClient
                client = LLMVisionClient()
                setting = client.analyze_influencer_setting(update_data["image_url"])
                if setting:
                    update_influencer(influencer_id, {"setting": setting})
                    print(f"      [OK] Re-analyzed setting for {inf.get('name')}: {setting}")
            except Exception as e:
                print(f"      !! Setting re-analysis failed for {inf.get('name')}: {e}")
        threading.Thread(target=_analyze_setting, daemon=True).start()

    return result

@app.delete("/influencers/{influencer_id}")
def api_delete_influencer(influencer_id: str):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    delete_influencer(influencer_id)
    return {"status": "deleted", "id": influencer_id}


@app.post("/influencers/analyze-settings")
def api_analyze_all_influencer_settings():
    """Batch-analyze background/environment settings for all influencers that have an image but no setting."""
    from ugc_backend.llm_vision_client import LLMVisionClient

    all_influencers = list_influencers()
    if not all_influencers:
        return {"status": "no_influencers", "updated": 0, "skipped": 0, "failed": 0}

    client = LLMVisionClient()
    updated, skipped, failed = 0, 0, 0
    results = []

    for inf in all_influencers:
        name = inf.get("name", "Unknown")
        image_url = inf.get("image_url") or inf.get("reference_image_url")

        if not image_url:
            skipped += 1
            results.append({"name": name, "status": "skipped", "reason": "no image_url"})
            continue

        try:
            setting = client.analyze_influencer_setting(image_url)
            if setting:
                update_influencer(inf["id"], {"setting": setting})
                updated += 1
                results.append({"name": name, "status": "updated", "setting": setting})
                print(f"      [OK] Setting for {name}: {setting}")
            else:
                failed += 1
                results.append({"name": name, "status": "failed", "reason": "empty response"})
        except Exception as e:
            failed += 1
            results.append({"name": name, "status": "failed", "reason": str(e)})
            print(f"      !! Setting analysis failed for {name}: {e}")

    return {"status": "done", "updated": updated, "skipped": skipped, "failed": failed, "details": results}


# ---------------------------------------------------------------------------
# Scripts CRUD (v2 with structured JSON support)
# Legacy routes (/scripts) kept for backward compatibility.
# New routes (/api/scripts/*) for the new frontend.
# ---------------------------------------------------------------------------

@app.get("/scripts")
@app.get("/api/scripts")
def api_list_scripts(
    request: Request,
    category: Optional[str] = None,
    methodology: Optional[str] = None,
    video_length: Optional[int] = None,
    influencer_id: Optional[str] = None,
    product_id: Optional[str] = None,
    source: Optional[str] = None,
    is_trending: Optional[bool] = None,
    sort_by: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_optional_user),
):
    filters = {}
    if methodology: filters["methodology"] = methodology
    if video_length: filters["video_length"] = video_length
    if influencer_id: filters["influencer_id"] = influencer_id
    if product_id: filters["product_id"] = product_id
    if source: filters["source"] = source
    if is_trending is not None: filters["is_trending"] = is_trending
    if sort_by: filters["sort_by"] = sort_by
    if search: filters["search"] = search
    if user:
        pid = _resolve_project_id(request, user)
        if pid:
            return list_scripts_scoped(user["id"], pid, **filters)
        return []
    return list_scripts(category, **filters)

@app.post("/scripts")
@app.post("/api/scripts")
def api_create_script(data: ScriptCreate):
    payload = data.model_dump(exclude_none=True)
    # Auto-generate name from hook if not provided
    if not payload.get("name"):
        if payload.get("script_json") and payload["script_json"].get("hook"):
            payload["name"] = payload["script_json"]["hook"][:80]
        elif payload.get("text"):
            payload["name"] = payload["text"][:80]
    return create_script(payload)

@app.put("/scripts/{script_id}")
@app.put("/api/scripts/{script_id}")
def api_update_script(script_id: str, data: ScriptUpdate):
    payload = data.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update.")
    result = update_script(script_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Script not found.")
    return result

@app.delete("/scripts/{script_id}")
@app.delete("/api/scripts/{script_id}")
def api_delete_script(script_id: str):
    delete_script(script_id)
    return {"status": "deleted", "id": script_id}

@app.post("/api/scripts/bulk")
def api_bulk_create_scripts(items: List[ScriptBulkItem]):
    """Insert multiple scripts at once (for CSV upload)."""
    scripts_data = []
    for item in items:
        d = item.model_dump(exclude_none=True)
        # Auto-generate name from hook
        if not d.get("name") and d.get("script_json", {}).get("hook"):
            d["name"] = d["script_json"]["hook"][:80]
        scripts_data.append(d)
    result = bulk_create_scripts(scripts_data)
    return {"imported": len(result), "scripts": result}

@app.post("/api/scripts/{script_id}/use")
def api_use_script(script_id: str):
    """Increment the times_used counter for a script."""
    new_count = increment_script_usage(script_id)
    return {"script_id": script_id, "times_used": new_count}

class FindTrendingRequest(BaseModel):
    topic: str = "UGC ads"
    max_scripts: int = 5
    sources: list[str] | None = None

@app.post("/api/scripts/find-trending")
def api_find_trending(
    data: FindTrendingRequest,
    request: Request,
    user: dict = Depends(get_optional_user),
):
    """Trigger trending script discovery in the background."""
    import threading

    # Capture user/project context for the background thread
    user_id = user["id"] if user else None
    project_id = _resolve_project_id(request, user) if user else None

    def _run_scraper():
        try:
            from ugc_backend.trending_scraper import scrape_trending_scripts
            scripts_data = scrape_trending_scripts(
                topic=data.topic,
                sources=data.sources,
                max_scripts=data.max_scripts,
            )
            # Save each extracted script — scoped to user + project
            for s in scripts_data:
                script_payload = {
                    "name": s.get("name", "Trending Script"),
                    "script_json": s,
                    "category": data.topic if data.topic != "UGC ads" else "General",
                    "methodology": s.get("methodology", "Hook/Benefit/CTA"),
                    "video_length": s.get("target_duration_sec", 15),
                    "source": "web_scraped",
                    "is_trending": True,
                }
                if user_id:
                    script_payload["user_id"] = user_id
                if project_id:
                    script_payload["project_id"] = project_id
                create_script(script_payload)
            print(f"      [Trending] Saved {len(scripts_data)} scripts to database (user={user_id}, project={project_id}).")
        except Exception as e:
            import traceback
            print(f"      [Trending] Background job failed: {e}")
            traceback.print_exc()

    threading.Thread(target=_run_scraper, daemon=True).start()
    return {"status": "started", "message": f"Finding trending scripts for '{data.topic}'. Check back in a few seconds."}


# ---------------------------------------------------------------------------
# App Clips CRUD
# ---------------------------------------------------------------------------

@app.get("/app-clips")
def api_list_app_clips(request: Request, user: dict = Depends(get_optional_user)):
    if user:
        pid = _resolve_project_id(request, user)
        if pid:
            return list_app_clips_scoped(user["id"], pid)
        return []
    return list_app_clips()

@app.post("/app-clips")
def api_create_app_clip(data: AppClipCreate, request: Request, user: dict = Depends(get_optional_user)):
    """
    Creates a new app clip. If video_url is provided, automatically
    triggers first-frame extraction in a background thread.
    """
    try:
        clip_data = data.model_dump(exclude_none=True)
        if user:
            clip_data["user_id"] = user["id"]
            pid = _resolve_project_id(request, user)
            if pid:
                clip_data["project_id"] = pid
        new_clip = create_app_clip(clip_data)
        if not new_clip:
            raise HTTPException(status_code=500, detail="Failed to create app clip")

        # Auto-create a linked digital product ONLY when no product_id was provided.
        # If the user already selected or created a product in the modal,
        # skip auto-creation to avoid duplicates.
        if not new_clip.get("product_id"):
            product_data = {"name": new_clip["name"], "type": "digital", "image_url": ""}
            if new_clip.get("user_id"):
                product_data["user_id"] = new_clip["user_id"]
            if new_clip.get("project_id"):
                product_data["project_id"] = new_clip["project_id"]
            new_product = create_product(product_data)
            if new_product:
                update_app_clip(new_clip["id"], {"product_id": new_product["id"]})
                new_clip["product_id"] = new_product["id"]
                print(f"      [OK] Auto-created digital product {new_product['id']} for clip {new_clip['id']}")
        else:
            new_product = None  # Product already linked — skip auto-creation
            print(f"      [OK] Clip {new_clip['id']} already linked to product {new_clip['product_id']}")
        # Extract first frame in background, then update clip + product image
        if new_clip.get("video_url") and not new_clip.get("first_frame_url"):
            import threading
            def _extract_in_background():
                try:
                    from ugc_backend.frame_extractor import extract_first_frame
                    frame_url = extract_first_frame(new_clip["video_url"])
                    if frame_url:
                        update_app_clip(new_clip["id"], {"first_frame_url": frame_url})
                        # Update the linked product's image if it has none yet
                        linked_pid = new_clip.get("product_id")
                        if linked_pid:
                            linked_prod = get_product(linked_pid)
                            if linked_prod and not linked_prod.get("image_url"):
                                update_product(linked_pid, {"image_url": frame_url})
                                print(f"      [OK] Updated product {linked_pid} image from clip first frame")
                        print(f"      [OK] Auto-extracted first frame for clip {new_clip['id']}")
                except Exception as e:
                    print(f"      !! Auto frame extraction failed for clip {new_clip['id']}: {e}")
            threading.Thread(target=_extract_in_background, daemon=True).start()

        return new_clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/app-clips/{clip_id}")
def api_delete_app_clip(clip_id: str):
    delete_app_clip(clip_id)
    return {"status": "deleted", "id": clip_id}


@app.get("/api/app-clips")
def api_list_app_clips_filtered(product_id: Optional[str] = None):
    """
    List app clips, optionally filtered by product_id.
    GET /api/app-clips                    -> all clips (backwards compatible)
    GET /api/app-clips?product_id={id}    -> clips linked to a specific product
    """
    try:
        if product_id:
            return list_app_clips_by_product(product_id)
        return list_app_clips()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/app-clips/{clip_id}")
def api_update_app_clip(clip_id: str, data: AppClipUpdate):
    """Update an app clip's product_id or other fields."""
    try:
        result = update_app_clip(clip_id, data.model_dump(exclude_none=True))
        if not result:
            raise HTTPException(status_code=404, detail="App clip not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/app-clips/{clip_id}/extract-frame")
def api_extract_frame(clip_id: str):
    """
    Manually trigger first-frame extraction for an existing app clip.
    Also called automatically on clip creation if video_url is present.
    """
    try:
        sb = get_supabase()
        result = sb.table("app_clips").select("*").eq("id", clip_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="App clip not found")
        clip = result.data[0]
        if not clip.get("video_url"):
            raise HTTPException(status_code=400, detail="App clip has no video_url")

        from ugc_backend.frame_extractor import extract_first_frame
        frame_url = extract_first_frame(clip["video_url"])
        if not frame_url:
            raise HTTPException(status_code=500, detail="Frame extraction failed")

        update_app_clip(clip_id, {"first_frame_url": frame_url})
        return {"status": "success", "first_frame_url": frame_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Storage: Signed URL for Direct Upload
# ---------------------------------------------------------------------------

@app.post("/assets/signed-url")
def create_signed_url(data: SignedUrlRequest):
    sb = get_supabase()
    allowed_buckets = {"influencer-images", "app-clips", "generated-videos", "clone-looks"}
    if data.bucket not in allowed_buckets:
        raise HTTPException(status_code=400, detail=f"Invalid bucket. Allowed: {allowed_buckets}")
    try:
        result = sb.storage.from_(data.bucket).create_signed_upload_url(data.file_name)
        return {"signed_url": result.get("signedURL") or result.get("signed_url"), "path": data.file_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create signed URL: {str(e)}")


# ---------------------------------------------------------------------------
# Jobs: Single + Bulk
# ---------------------------------------------------------------------------




@app.post("/jobs/bulk")
def api_create_bulk_jobs(data: BulkJobCreate, request: Request, user: dict = Depends(get_optional_user)):
    try:
        inf = get_influencer(data.influencer_id)
        if not inf:
            raise HTTPException(status_code=404, detail="Influencer not found")

        # ---------------------------------------------------------------
        # Build script & clip pools — product-scoped for digital campaigns
        # ---------------------------------------------------------------
        is_digital_product = (data.product_type == "digital" and data.product_id)

        if is_digital_product:
            # Product-scoped clips: only clips belonging to this product
            product_clips = list_app_clips_by_product(data.product_id)
            clip_pool = product_clips if product_clips else list_app_clips()  # fallback
            if not clip_pool:
                clip_pool = []  # safe empty — jobs will have no clip

            # Product-scoped scripts: only scripts linked to this product
            product_scripts = list_scripts(product_id=data.product_id)
            scripts = product_scripts if product_scripts else list_scripts()  # fallback
        else:
            # Legacy path: global pools + category matching (unchanged)
            scripts = list_scripts()
            clips = list_app_clips()
            inf_style = (inf.get("style") or "").lower().strip()
            matching_clips = [
                c for c in clips
                if inf_style and (
                    inf_style in (c.get("category") or "").lower()
                    or inf_style in (c.get("description") or "").lower()
                    or inf_style in (c.get("name") or "").lower()
                )
            ] if clips else []
            clip_pool = matching_clips if matching_clips else clips

        if not scripts:
            raise HTTPException(status_code=400, detail="No scripts available. Add scripts first.")

        # Detect actual DB columns dynamically (same approach as single job)
        try:
            _probe = get_supabase().table("video_jobs").select("*").limit(1).execute()
            db_columns = set(_probe.data[0].keys()) if _probe.data else set()
        except Exception:
            db_columns = set()

        if not db_columns:
            db_columns = {
                "id", "user_id", "influencer_id", "app_clip_id", "script_id",
                "status", "progress", "final_video_url", "created_at", "updated_at",
                "product_type", "product_id", "cost_image",
                "hook", "model_api", "assistant_type", "length", "campaign_name",
                "cost_video", "cost_voice", "cost_music", "cost_processing", "total_cost",
                "cinematic_shot_ids", "error_message", "variation_prompt",
                "subtitles_enabled", "subtitle_style", "subtitle_placement",
                "video_language", "music_enabled",
                "preview_url", "preview_type", "status_message",
            }

        created_jobs = []
        for i in range(data.count):
            # ----- Clip selection: round-robin for digital, random for physical -----
            if is_digital_product and clip_pool:
                selected_clip = clip_pool[i % len(clip_pool)]
            elif clip_pool:
                selected_clip = random.choice(clip_pool)
            else:
                selected_clip = None

            selected_script = random.choice(scripts)

            # ----- 70/30 Influencer Setting Variation (digital only) -----
            variation_prompt = None
            if is_digital_product and random.random() < 0.70:
                try:
                    from prompts.digital_prompts import generate_variation_prompt
                    default_setting = (inf.get("setting") or "").strip()
                    variation_prompt = generate_variation_prompt(
                        influencer_name=inf.get("name", "Influencer"),
                        default_setting=default_setting or "natural environment",
                    )
                except Exception as e:
                    print(f"   !! Variation prompt failed for job {i}: {e}")
                    variation_prompt = None  # safe fallback

            # ----- Script: generate unique per-video script for digital -----
            if is_digital_product and not data.hook:
                # Generate a fresh, unique script for each video
                try:
                    from ugc_backend.ai_script_client import AIScriptClient
                    product = get_product(data.product_id)
                    visuals = product.get("visual_description") or {} if product else {}
                    client = AIScriptClient()
                    script_text = client.generate_digital_product_script(
                        product_name=product.get("name", "App") if product else "App",
                        product_analysis=visuals,
                        duration=data.duration,
                        video_language=data.video_language,
                    )
                    print(f"   [Bulk] Job {i+1}: Generated unique script ({len(script_text)} chars)")
                except Exception as e:
                    print(f"   !! Per-video script generation failed for job {i}: {e}")
                    script_text = selected_script.get("text", "")
            else:
                script_text = data.hook if data.hook else selected_script.get("text", "")
            costs = cost_service.estimate_total_cost(
                script_text=script_text,
                duration=data.duration,
                model=data.model_api,
                product_type=data.product_type,
                music_enabled=data.music_enabled if hasattr(data, 'music_enabled') and data.music_enabled is not None else True,
            )

            job_data = {
                "influencer_id": data.influencer_id,
                "script_id": selected_script["id"] if not data.hook else None,
                "app_clip_id": selected_clip["id"] if selected_clip else None,
                "product_type": data.product_type,
                "product_id": data.product_id,
                "model_api": data.model_api,
                "campaign_name": data.campaign_name,
                "length": data.duration,
                "status": "pending",
                "progress": 0,
                "variation_prompt": variation_prompt,  # None = use default setting
                "video_language": data.video_language,
                **costs,
            }

            # Inject user_id and project_id if authenticated
            if user:
                job_data["user_id"] = user["id"]
                pid = _resolve_project_id(request, user)
                if pid and "project_id" in db_columns:
                    job_data["project_id"] = pid

            if data.hook:
                job_data["hook"] = data.hook
            elif is_digital_product and script_text:
                # Store the uniquely generated script in the hook field
                job_data["hook"] = script_text
                job_data["script_id"] = None  # no static script reference
            if data.cinematic_shot_ids:
                job_data["cinematic_shot_ids"] = data.cinematic_shot_ids

            # Store auto_transition_type directly if column exists
            if data.auto_transition_type and "auto_transition_type" in db_columns:
                job_data["auto_transition_type"] = data.auto_transition_type

            # Store metadata if the column exists
            if "metadata" in db_columns:
                metadata = {}
                if data.auto_transition_type:
                    metadata["auto_transition_type"] = data.auto_transition_type
                if job_data.get("cinematic_shot_ids"):
                    metadata["cinematic_shot_ids"] = job_data["cinematic_shot_ids"]
                if data.hook:
                    metadata["hook"] = data.hook
                if metadata:
                    job_data["metadata"] = metadata

            # Strip unknown columns
            unknown_keys = [k for k in list(job_data.keys()) if k not in db_columns]
            for k in unknown_keys:
                val = job_data.pop(k)
                try:
                    safe_val = str(val).encode('ascii', 'ignore').decode('ascii')[:80]
                    print(f"   !! [Bulk] Stripped unknown column '{k}' (value: {safe_val})")
                except:
                    pass

            job = create_job(job_data)
            if not job:
                print(f"WARNING: create_job returned None for bulk job")
                continue
            _dispatch_worker(job["id"])
            created_jobs.append(job["id"])

        return {"status": "dispatched", "count": len(created_jobs), "job_ids": created_jobs}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bulk job creation failed: {str(e)}")


# ---------------------------------------------------------------------------
# Jobs: Status + History
# ---------------------------------------------------------------------------

@app.get("/jobs")
def api_list_jobs(request: Request, status: Optional[str] = None, limit: int = Query(default=50, le=200), include_clones: bool = Query(default=False), user: dict = Depends(get_optional_user)):
    if user:
        pid = _resolve_project_id(request, user)
        regular_jobs = list_jobs_scoped(user["id"], project_id=pid, status=status, limit=limit)
    else:
        regular_jobs = list_jobs(status, limit)

    if not include_clones or not user:
        return regular_jobs

    # Also fetch clone video jobs and normalize them to match the VideoJob shape
    sb = get_supabase()
    try:
        q = (
            sb.table("clone_video_jobs")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(limit)
        )
        if pid:
            q = q.eq("project_id", pid)
        if status:
            q = q.eq("status", status)
        clone_jobs_raw = q.execute().data or []
    except Exception:
        # Fallback: project_id column may not exist yet (pre-migration)
        q = (
            sb.table("clone_video_jobs")
            .select("*")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .limit(limit)
        )
        if status:
            q = q.eq("status", status)
        clone_jobs_raw = q.execute().data or []

    if not clone_jobs_raw:
        return regular_jobs

    # Look up clone names for display
    clone_ids = list({j["clone_id"] for j in clone_jobs_raw if j.get("clone_id")})
    clone_map = {}
    if clone_ids:
        clones_data = sb.table("user_ai_clones").select("id,name").in_("id", clone_ids).execute().data or []
        clone_map = {c["id"]: c["name"] for c in clones_data}

    # Also look up look image URLs for thumbnails
    look_ids = list({j["look_id"] for j in clone_jobs_raw if j.get("look_id")})
    look_map = {}
    if look_ids:
        looks_data = sb.table("user_ai_clone_looks").select("id,image_url").in_("id", look_ids).execute().data or []
        look_map = {l["id"]: l["image_url"] for l in looks_data}

    # Normalize clone jobs to look like regular VideoJob
    for cj in clone_jobs_raw:
        cj["_source"] = "clone"
        cj["clone_name"] = clone_map.get(cj.get("clone_id", ""), "AI Clone")
        cj["look_image_url"] = look_map.get(cj.get("look_id", ""), "")
        # Normalize status: clone uses 'complete', regular uses 'success'
        if cj.get("status") == "complete":
            cj["status"] = "success"
            cj["progress"] = 100
        # Map clone fields to regular VideoJob fields the frontend expects
        cj["campaign_name"] = "AI Clone"
        cj["influencer_id"] = f"clone_{cj.get('clone_id', '')}"  # Prefixed ID for filtering

    # Merge and sort by created_at desc
    for rj in regular_jobs:
        rj["_source"] = "influencer"

    all_jobs = regular_jobs + clone_jobs_raw
    all_jobs.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    return all_jobs[:limit]

@app.get("/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.delete("/jobs/{job_id}")
def api_delete_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    delete_job(job_id)
    return {"status": "deleted", "id": job_id}

@app.get("/jobs/{job_id}/status")
def api_get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "final_video_url": job.get("final_video_url"),
        "error_message": job.get("error_message"),
    }


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

@app.get("/stats")
def api_get_stats(user: dict = Depends(get_optional_user)):
    if user:
        stats = get_stats_scoped(user["id"])
        # Add projects count for the dashboard KPI
        user_projects = list_projects(user["id"])
        stats["projects"] = len(user_projects or [])
        return stats
    return get_stats()


@app.post("/estimate")
def api_estimate_cost(data: CostEstimateRequest):
    """Real-time cost estimation for the Create page."""
    return cost_service.estimate_total_cost(
        script_text=data.script_text,
        duration=data.duration,
        model=data.model,
        music_enabled=data.music_enabled if data.music_enabled is not None else True,
    )


@app.get("/stats/costs")
def api_get_cost_stats(request: Request, user: dict = Depends(get_optional_user)):
    """Aggregate spend stats for the Activity page — scoped per user and project."""
    sb = get_supabase()
    # Build query — scope by user if authenticated
    q = sb.table("video_jobs").select("total_cost,created_at,status,product_type").not_.is_("total_cost", "null")
    if user:
        q = q.eq("user_id", user["id"])
        pid = _resolve_project_id(request, user)
        if pid:
            q = q.eq("project_id", pid)
    all_jobs = q.execute()
    rows = all_jobs.data or []

    total_credits = 0
    for r in rows:
        if r.get("status") == "success":
            cost = float(r.get("total_cost", 0) or 0)
            ptype = r.get("product_type")
            is_digital = ptype != "physical"
            is_30s = cost > 0.75
            
            if is_digital:
                total_credits += (77 if is_30s else 39)
            else:
                total_credits += (199 if is_30s else 100)

    return {
        "total_spend_all": total_credits,
    }


# ---------------------------------------------------------------------------
# AI Hook Generation (template-based, no external API needed)
# ---------------------------------------------------------------------------

class HookRequest(BaseModel):
    category: str = "General"
    influencer_id: Optional[str] = None

HOOK_TEMPLATES: dict[str, list[str]] = {
    "Travel": [
        "I found the most insane hidden spot and nobody's talking about it...",
        "This place literally broke my brain. You NEED to see this.",
        "POV: You just discovered your new favourite destination.",
        "Stop scrolling. This view is about to change your whole mood.",
        "I wasn't supposed to share this location, but...",
        "If this doesn't make you want to book a flight, nothing will.",
    ],
    "Fashion": [
        "This outfit hack is about to save you hundreds of dollars.",
        "Everyone's wearing this wrong. Here's how it's actually done.",
        "The fashion industry doesn't want you to know this trick.",
        "I found the exact dupe and it's even better than the original.",
        "Stop buying fast fashion. Try this instead.",
        "This one styling trick makes any outfit look 10x more expensive.",
    ],
    "Tech": [
        "This app just changed everything for me.",
        "Your phone can do this and you had NO idea.",
        "Delete that app. Use this instead.",
        "I've been using this wrong my entire life.",
        "This feature is hidden and nobody talks about it.",
        "The one setting you need to change right now.",
    ],
    "Fitness": [
        "I tried this for 30 days and the results are insane.",
        "Your trainer doesn't want you to know this.",
        "This one exercise replaces your entire workout.",
        "Stop doing crunches. Do this instead.",
        "The workout that actually transformed my body.",
        "3 minutes. That's all it takes. Watch this.",
    ],
    "Food": [
        "This recipe broke the internet and I had to try it.",
        "You've been making this wrong your entire life.",
        "The secret ingredient that changes everything.",
        "This 5-minute meal tastes like it took 2 hours.",
        "I can't believe this actually works.",
        "Chefs don't want you to know this simple trick.",
    ],
    "General": [
        "Wait for it... this is going to blow your mind.",
        "I need to tell you something nobody's talking about.",
        "This changed my entire perspective. Seriously.",
        "You're going to want to save this one.",
        "I wasn't going to post this, but you need to see it.",
        "If you only watch one video today, make it this one.",
        "POV: You just discovered something game-changing.",
        "Stop what you're doing. You need to hear this.",
    ],
}

@app.post("/ai/hook")
def api_generate_hook(data: HookRequest):
    category = data.category
    # Find the best matching template category
    templates = HOOK_TEMPLATES.get(category, None)
    if not templates:
        # Try case-insensitive match
        for key, val in HOOK_TEMPLATES.items():
            if key.lower() == category.lower():
                templates = val
                break
    if not templates:
        templates = HOOK_TEMPLATES["General"]

    hook = random.choice(templates)
    return {"hook": hook, "category": category}


# ===========================================================================
# SaaS ENDPOINTS — Authentication, Projects, Subscriptions, Credits
# ===========================================================================


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def api_get_profile(user: dict = Depends(get_current_user)):
    profile = get_profile(user["id"])
    if not profile:
        return {"id": user["id"], "email": user["email"], "name": None, "avatar_url": None}
    return profile

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None

@app.put("/api/profile")
def api_update_profile(data: ProfileUpdateRequest, user: dict = Depends(get_current_user)):
    payload = data.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = update_profile(user["id"], payload)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result


# ---------------------------------------------------------------------------
# Projects CRUD
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
    name: str

@app.get("/api/projects")
def api_list_projects(user: dict = Depends(get_current_user)):
    return list_projects(user["id"])

@app.post("/api/projects")
def api_create_project(data: ProjectCreate, user: dict = Depends(get_current_user)):
    result = db_create_project(user["id"], data.name)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create project")
    return result

@app.put("/api/projects/{project_id}")
def api_update_project(project_id: str, data: ProjectUpdate, user: dict = Depends(get_current_user)):
    result = db_update_project(project_id, user["id"], {"name": data.name})
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@app.delete("/api/projects/{project_id}")
def api_delete_project_endpoint(project_id: str, user: dict = Depends(get_current_user)):
    try:
        db_delete_project(project_id, user["id"])
        return {"status": "deleted", "id": project_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

@app.get("/api/plans")
def api_list_plans():
    """Return all active subscription plans from the database."""
    sb = get_supabase()
    result = sb.table("subscription_plans").select("*").eq("is_active", True).order("price_monthly", desc=False).execute()
    return result.data or []

@app.get("/api/subscription")
def api_get_subscription(user: dict = Depends(get_current_user)):
    sub = get_subscription(user["id"])
    if not sub:
        return {"status": "none", "plan": {"name": "Free", "credits_monthly": 0}}
    return sub


# ---------------------------------------------------------------------------
# Credit Wallet & Transactions
# ---------------------------------------------------------------------------

@app.get("/api/wallet")
def api_get_wallet(user: dict = Depends(get_current_user)):
    wallet = get_wallet(user["id"])
    if not wallet:
        # User has no wallet row yet. Supabase trigger handle_new_user failed or is missing.
        # Lazily initialize their wallet with 100 free credits.
        sb = get_supabase()
        
        # Ensure profile exists
        existing_profile = sb.table("profiles").select("id").eq("id", user["id"]).execute()
        if not existing_profile.data:
            sb.table("profiles").insert({"id": user["id"]}).execute()
            
        # Create wallet with 100 credits
        result = sb.table("credit_wallets").insert({
            "user_id": user["id"],
            "balance": 100
        }).execute()
        
        wallet_id = result.data[0]["id"]
        
        # Log the 100 credits as a Welcome Bonus
        sb.table("credit_transactions").insert({
            "wallet_id": wallet_id,
            "amount": 100,
            "type": "welcome_bonus",
            "description": "100 Free Credits on Sign-up",
            "metadata": {}
        }).execute()
        
        return {"balance": 100, "user_id": user["id"]}
    return wallet

@app.get("/api/wallet/transactions")
def api_get_transactions(user: dict = Depends(get_current_user), limit: int = Query(default=50, le=200)):
    return list_transactions(user["id"], limit)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

@app.get("/api/notifications")
def api_get_notifications(limit: int = Query(default=20, le=50), user: dict = Depends(get_current_user)):
    """Return recent activity notifications for the authenticated user."""
    return get_notifications(user["id"], limit)


# ---------------------------------------------------------------------------
# Credit Costs Reference
# ---------------------------------------------------------------------------

@app.get("/api/credits/costs")
def api_get_credit_costs():
    """Return the full credit cost table for frontend display."""
    return {
        "digital_15s": 39,
        "digital_30s": 77,
        "physical_15s": 100,
        "physical_30s": 199,
        "cinematic_image_1k": 13,
        "cinematic_image_2k": 13,
        "cinematic_image_4k": 16,
        "cinematic_video_8s": 51,
    }


# ---------------------------------------------------------------------------
# Stripe Billing
# ---------------------------------------------------------------------------

# Top-up package definitions (server-side source of truth)
TOPUP_PACKAGES = {
    "small":  {"credits": 250,  "stripe_price_id": os.getenv("STRIPE_TOPUP_SMALL_PRICE_ID", "")},
    "medium": {"credits": 750,  "stripe_price_id": os.getenv("STRIPE_TOPUP_MEDIUM_PRICE_ID", "")},
    "large":  {"credits": 2000, "stripe_price_id": os.getenv("STRIPE_TOPUP_LARGE_PRICE_ID", "")},
    "xl":     {"credits": 5000, "stripe_price_id": os.getenv("STRIPE_TOPUP_XL_PRICE_ID", "")},
}

class CheckoutSubscriptionRequest(BaseModel):
    plan_id: str

class CheckoutTopUpRequest(BaseModel):
    package: str  # "small", "medium", "large", "xl"


@app.post("/api/stripe/checkout/subscription")
def api_stripe_checkout_subscription(
    body: CheckoutSubscriptionRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for a subscription plan."""
    plan = get_plan_by_id(body.plan_id)
    if not plan or not plan.get("stripe_price_id"):
        raise HTTPException(status_code=400, detail="Invalid plan or plan not configured for Stripe")

    # Get or lazily create Stripe Customer
    customer_id = get_stripe_customer_id(user["id"])
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.get("email", ""),
            metadata={"supabase_user_id": user["id"]},
        )
        customer_id = customer.id
        save_stripe_customer_id(user["id"], customer_id)

    origin = request.headers.get("origin", os.getenv("FRONTEND_URL", "http://localhost:3000"))

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": plan["stripe_price_id"], "quantity": 1}],
        success_url=f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/upgrade",
        metadata={
            "supabase_user_id": user["id"],
            "plan_id": plan["id"],
        },
        subscription_data={
            "metadata": {
                "supabase_user_id": user["id"],
                "plan_id": plan["id"],
            },
        },
    )

    return {"checkout_url": session.url}


@app.post("/api/stripe/checkout/topup")
def api_stripe_checkout_topup(
    body: CheckoutTopUpRequest,
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe Checkout Session for a one-time credit top-up."""
    pkg = TOPUP_PACKAGES.get(body.package)
    if not pkg or not pkg["stripe_price_id"]:
        raise HTTPException(status_code=400, detail="Invalid top-up package")

    # Get or lazily create Stripe Customer
    customer_id = get_stripe_customer_id(user["id"])
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.get("email", ""),
            metadata={"supabase_user_id": user["id"]},
        )
        customer_id = customer.id
        save_stripe_customer_id(user["id"], customer_id)

    origin = request.headers.get("origin", os.getenv("FRONTEND_URL", "http://localhost:3000"))

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="payment",
        line_items=[{"price": pkg["stripe_price_id"], "quantity": 1}],
        success_url=f"{origin}/checkout/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin}/manage?topup=1",
        metadata={
            "supabase_user_id": user["id"],
            "topup_package": body.package,
            "topup_credits": str(pkg["credits"]),
        },
    )

    return {"checkout_url": session.url}


@app.post("/api/stripe/portal")
def api_stripe_portal(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Create a Stripe Customer Portal session for self-service billing management."""
    customer_id = get_stripe_customer_id(user["id"])
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.get("email", ""),
            metadata={"supabase_user_id": user["id"]},
        )
        customer_id = customer.id
        save_stripe_customer_id(user["id"], customer_id)

    origin = request.headers.get("origin", os.getenv("FRONTEND_URL", "http://localhost:3000"))

    portal_session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=f"{origin}/manage",
    )

    return {"portal_url": portal_session.url}


@app.post("/api/stripe/webhook")
async def api_stripe_webhook(request: Request):
    """Handle Stripe webhook events. Unauthenticated — verified via signature."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header or not STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=400, detail="Missing Stripe signature or webhook secret")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {str(e)}")

    event_type = event["type"]
    data = event["data"]["object"]

    print(f"[Stripe] Received event: {event_type} (id: {event['id']})")

    # ── checkout.session.completed ─────────────────────────────────────
    if event_type == "checkout.session.completed":
        metadata = data.get("metadata", {})
        mode = data.get("mode")

        if mode == "payment":
            # One-time top-up payment completed
            user_id = metadata.get("supabase_user_id")
            credits = int(metadata.get("topup_credits", "0"))
            package = metadata.get("topup_package", "unknown")

            if user_id and credits > 0:
                add_credits(
                    user_id=user_id,
                    amount=credits,
                    tx_type="top_up",
                    description=f"Credit top-up: {package} ({credits} credits)",
                    metadata={
                        "stripe_session_id": data.get("id"),
                        "package": package,
                    },
                )
                print(f"[Stripe] Added {credits} credits to user {user_id} (top-up: {package})")

    # ── invoice.paid ───────────────────────────────────────────────────
    elif event_type == "invoice.paid":
        subscription_id = data.get("subscription")
        customer_id = data.get("customer")

        if subscription_id:
            sub = stripe.Subscription.retrieve(subscription_id)
            user_id = sub.metadata.get("supabase_user_id")
            plan_id = sub.metadata.get("plan_id")

            if not user_id:
                user_id = get_user_id_by_stripe_customer(customer_id)

            if user_id and plan_id:
                plan = get_plan_by_id(plan_id)
                if plan:
                    period_start = datetime.fromtimestamp(
                        sub["current_period_start"], tz=timezone.utc
                    ).isoformat()
                    period_end = datetime.fromtimestamp(
                        sub["current_period_end"], tz=timezone.utc
                    ).isoformat()

                    upsert_subscription(
                        user_id=user_id,
                        plan_id=plan_id,
                        stripe_subscription_id=subscription_id,
                        status="active",
                        period_start=period_start,
                        period_end=period_end,
                    )

                    add_credits(
                        user_id=user_id,
                        amount=plan["credits_monthly"],
                        tx_type="monthly_allotment",
                        description=f"{plan['name']} plan: {plan['credits_monthly']} monthly credits",
                        metadata={
                            "stripe_invoice_id": data.get("id"),
                            "stripe_subscription_id": subscription_id,
                            "period_start": period_start,
                            "period_end": period_end,
                        },
                    )
                    print(f"[Stripe] Replenished {plan['credits_monthly']} credits for user {user_id} ({plan['name']})")

    # ── customer.subscription.updated ──────────────────────────────────
    elif event_type == "customer.subscription.updated":
        subscription_id = data.get("id")
        user_id = data.get("metadata", {}).get("supabase_user_id")
        customer_id = data.get("customer")
        status = data.get("status")

        if not user_id:
            user_id = get_user_id_by_stripe_customer(customer_id)

        if user_id:
            items = data.get("items", {}).get("data", [])
            if items:
                new_price_id = items[0].get("price", {}).get("id")
                new_plan = get_plan_by_stripe_price_id(new_price_id) if new_price_id else None

                if new_plan:
                    period_start = datetime.fromtimestamp(
                        data["current_period_start"], tz=timezone.utc
                    ).isoformat()
                    period_end = datetime.fromtimestamp(
                        data["current_period_end"], tz=timezone.utc
                    ).isoformat()

                    upsert_subscription(
                        user_id=user_id,
                        plan_id=new_plan["id"],
                        stripe_subscription_id=subscription_id,
                        status=status if status in ("active", "past_due", "canceled") else "active",
                        period_start=period_start,
                        period_end=period_end,
                    )
                    print(f"[Stripe] Subscription updated for user {user_id}: {new_plan['name']} ({status})")

    # ── customer.subscription.deleted ──────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")
        cancel_subscription(subscription_id)
        print(f"[Stripe] Subscription {subscription_id} canceled/deleted")

    return {"status": "ok"}


# ─────────────────────────────────────────────────────────────────────────────
# AI Clone Job Endpoints (new — completely separate from /jobs)
# ─────────────────────────────────────────────────────────────────────────────

class CloneJobCreate(BaseModel):
    clone_id: str
    look_id: Optional[str] = None
    product_id: Optional[str] = None
    product_type: str = "physical"
    script_text: str
    duration: int = 15
    subtitles_enabled: bool = True
    subtitle_style: str = "hormozi"
    subtitle_placement: str = "middle"
    video_language: str = "en"             # 'en' or 'es' — defaults to English
    project_id: Optional[str] = None       # Project this clone video belongs to


@app.post("/api/clone-jobs")
def create_clone_job(data: CloneJobCreate, request: Request, user: dict = Depends(get_optional_user)):
    """
    Create a new AI Clone video job and dispatch it to the clone worker.
    This endpoint is completely separate from POST /jobs (standard pipeline).
    """
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    sb = get_supabase()

    # Verify the clone belongs to this user
    clone_check = (
        sb.table("user_ai_clones")
        .select("id")
        .eq("id", data.clone_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not clone_check.data:
        raise HTTPException(status_code=404, detail="Clone not found")

    # Create the job record
    # Resolve project_id from request header or payload
    pid = data.project_id or _resolve_project_id(request, user)
    row = {
        "user_id": user["id"],
        "clone_id": data.clone_id,
        "look_id": data.look_id,
        "product_id": data.product_id,
        "product_type": data.product_type,
        "script_text": data.script_text,
        "duration": data.duration,
        "subtitles_enabled": data.subtitles_enabled,
        "subtitle_style": data.subtitle_style,
        "subtitle_placement": data.subtitle_placement,
        "video_language": data.video_language,
        "status": "pending",
        "progress": 0,
    }
    if pid:
        row["project_id"] = pid
    try:
        result = sb.table("clone_video_jobs").insert(row).execute()
    except Exception:
        # project_id column may not exist yet — retry without it
        row.pop("project_id", None)
        result = sb.table("clone_video_jobs").insert(row).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create clone job")

    job = result.data[0]
    job_id = job["id"]

    # Dispatch to the isolated clone worker (Modal or in-process)
    _dispatch_clone_worker(job_id)

    return {"job_id": job_id, "status": "pending"}


@app.get("/api/clone-jobs/{job_id}")
def get_clone_job_status(job_id: str, user: dict = Depends(get_optional_user)):
    """Poll the status of a clone video job."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    result = (
        sb.table("clone_video_jobs")
        .select("*")
        .eq("id", job_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Job not found")
    return result.data[0]


@app.get("/api/clone-jobs")
def list_clone_jobs(user: dict = Depends(get_optional_user)):
    """List all clone video jobs for the current user."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    result = (
        sb.table("clone_video_jobs")
        .select("*")
        .eq("user_id", user["id"])
        .order("created_at", desc=True)
        .limit(50)
        .execute()
    )
    return result.data or []


@app.delete("/api/clone-jobs/{job_id}")
def delete_clone_job(job_id: str, user: dict = Depends(get_optional_user)):
    """Delete a clone video job."""
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    sb = get_supabase()
    sb.table("clone_video_jobs").delete().eq("id", job_id).eq("user_id", user["id"]).execute()
    return {"status": "deleted", "id": job_id}

# ---------------------------------------------------------------------------
# Job Refund (for failed generations)
# ---------------------------------------------------------------------------

@app.post("/jobs/{job_id}/refund")
def api_refund_job(job_id: str, user: dict = Depends(get_current_user)):
    """Refund credits for a failed generation job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only refund failed jobs
    if job.get("status") not in ("failed",):
        raise HTTPException(status_code=400, detail="Can only refund failed jobs")

    # Determine the credit cost to refund
    try:
        credit_cost = get_video_credit_cost(
            job.get("product_type", "digital"),
            job.get("length", 15)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Cannot determine credit cost for this job type")

    try:
        result = refund_credits(user["id"], credit_cost, {
            "job_id": job_id,
            "reason": "failed_generation",
        })
        return {"status": "refunded", "amount": credit_cost, "new_balance": result["balance"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ===========================================================================
# Schedule & Post (Ayrshare) — Social Media Scheduling
# ===========================================================================

import hashlib
import hmac
from ugc_backend import ayrshare_client


# ---------------------------------------------------------------------------
# JWT — Generate Ayrshare OAuth popup URL
# ---------------------------------------------------------------------------

@app.post("/api/ayrshare/jwt")
async def api_ayrshare_jwt(user: dict = Depends(get_current_user)):
    """Generate a JWT URL to open the Ayrshare social-account linking popup."""
    sb = get_supabase()
    user_id = user["id"]

    # Check if user already has an Ayrshare profile
    row = sb.table("ayrshare_profiles").select("ayrshare_profile_key").eq("user_id", user_id).execute()

    if row.data:
        profile_key = row.data[0]["ayrshare_profile_key"]
        print(f"[Ayrshare] Found existing profile key: {profile_key[:20]}...")
    else:
        # Create a new Ayrshare sub-profile
        try:
            print(f"[Ayrshare] Creating new profile for user {user_id}")
            profile_resp = await ayrshare_client.create_profile(user_id)
            print(f"[Ayrshare] create_profile response: {profile_resp}")
            profile_key = profile_resp.get("profileKey")
            if not profile_key:
                raise HTTPException(status_code=502, detail=f"Ayrshare did not return a profileKey. Response: {profile_resp}")
            sb.table("ayrshare_profiles").insert({
                "user_id": user_id,
                "ayrshare_profile_key": profile_key,
            }).execute()
            print(f"[Ayrshare] Saved profile key: {profile_key}")
        except HTTPException:
            raise
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=502, detail=f"Failed to create Ayrshare profile: {e}")

    # Generate JWT URL
    try:
        print(f"[Ayrshare] Generating JWT for profile_key: {profile_key[:20]}...")
        jwt_resp = await ayrshare_client.generate_jwt(profile_key)
        print(f"[Ayrshare] generate_jwt response: {jwt_resp}")
        url = jwt_resp.get("url")
        if not url:
            raise HTTPException(status_code=502, detail=f"Ayrshare did not return a JWT URL. Response: {jwt_resp}")
        return {"url": url}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"Failed to generate JWT: {e}")


# ---------------------------------------------------------------------------
# Connections — List connected social accounts
# ---------------------------------------------------------------------------

@app.get("/api/connections")
async def api_get_connections(user: dict = Depends(get_current_user)):
    """Return the user's connected social media accounts."""
    sb = get_supabase()
    row = sb.table("ayrshare_profiles").select("ayrshare_profile_key").eq("user_id", user["id"]).execute()

    if not row.data:
        return {"socials": []}

    profile_key = row.data[0]["ayrshare_profile_key"]

    # Fetch live from Ayrshare
    try:
        socials = await ayrshare_client.get_user_socials(profile_key)
        return {"socials": socials}
    except Exception as e:
        print(f"[Ayrshare] Failed to fetch socials: {e}")
        return {"socials": []}


# ---------------------------------------------------------------------------
# Bulk Schedule — Create scheduled posts
# ---------------------------------------------------------------------------

class SchedulePostItem(BaseModel):
    video_job_id: str
    platforms: List[str]
    caption: Optional[str] = None
    hashtags: Optional[List[str]] = None
    scheduled_at: str  # ISO 8601 UTC

class BulkScheduleRequest(BaseModel):
    posts: List[SchedulePostItem]

@app.post("/api/schedule/bulk")
async def api_schedule_bulk(data: BulkScheduleRequest, user: dict = Depends(get_current_user)):
    """Schedule one or more videos for social media posting."""
    sb = get_supabase()
    user_id = user["id"]

    # Get the user's Ayrshare profile key
    profile_row = sb.table("ayrshare_profiles").select("ayrshare_profile_key").eq("user_id", user_id).execute()
    if not profile_row.data:
        raise HTTPException(status_code=400, detail="No social accounts connected. Visit Connections page first.")
    profile_key = profile_row.data[0]["ayrshare_profile_key"]

    results = []
    scheduled_count = 0
    failed_count = 0

    for post in data.posts:
        # Validate the video job belongs to this user and has a video URL
        job = get_job(post.video_job_id)
        if not job or job.get("user_id") != user_id:
            results.append({"video_job_id": post.video_job_id, "status": "failed", "error": "Video not found"})
            failed_count += 1
            continue
        if not job.get("final_video_url"):
            results.append({"video_job_id": post.video_job_id, "status": "failed", "error": "Video not ready"})
            failed_count += 1
            continue

        # Create one social_posts record per platform
        for platform in post.platforms:
            try:
                post_record = sb.table("social_posts").insert({
                    "user_id": user_id,
                    "video_job_id": post.video_job_id,
                    "status": "scheduled",
                    "platform": platform,
                    "caption": post.caption,
                    "hashtags": post.hashtags,
                    "scheduled_at": post.scheduled_at,
                }).execute()

                social_post_id = post_record.data[0]["id"] if post_record.data else None

                # Send to Ayrshare
                ayrshare_data = {
                    "post": post.caption or "",
                    "platforms": [platform],
                    "mediaUrls": [job["final_video_url"]],
                    "scheduleDate": post.scheduled_at,
                }
                if post.hashtags:
                    ayrshare_data["hashTags"] = post.hashtags

                ayrshare_resp = await ayrshare_client.create_post(profile_key, ayrshare_data)
                ayrshare_post_id = ayrshare_resp.get("id")

                if social_post_id and ayrshare_post_id:
                    sb.table("social_posts").update({
                        "ayrshare_post_id": ayrshare_post_id,
                    }).eq("id", social_post_id).execute()

                results.append({"video_job_id": post.video_job_id, "platform": platform, "social_post_id": social_post_id, "status": "scheduled"})
                scheduled_count += 1

            except Exception as e:
                if social_post_id:
                    sb.table("social_posts").update({
                        "status": "failed",
                        "error_message": str(e),
                    }).eq("id", social_post_id).execute()
                results.append({"video_job_id": post.video_job_id, "platform": platform, "status": "failed", "error": str(e)})
                failed_count += 1

    return {"status": "success", "scheduled": scheduled_count, "failed": failed_count, "results": results}


# ---------------------------------------------------------------------------
# Schedule List — Get posts for calendar view
# ---------------------------------------------------------------------------

@app.get("/api/schedule")
def api_get_schedule(
    start_date: str = Query(...),
    end_date: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Return all social posts for the user within the given date range."""
    sb = get_supabase()
    rows = (
        sb.table("social_posts")
        .select("*")
        .eq("user_id", user["id"])
        .gte("scheduled_at", start_date)
        .lte("scheduled_at", end_date)
        .order("scheduled_at", desc=False)
        .execute()
    )
    return rows.data or []


# ---------------------------------------------------------------------------
# Cancel a scheduled post
# ---------------------------------------------------------------------------

@app.delete("/api/schedule/{post_id}")
async def api_cancel_schedule(post_id: str, user: dict = Depends(get_current_user)):
    """Cancel a scheduled post (only permitted for status='scheduled')."""
    sb = get_supabase()
    row = sb.table("social_posts").select("*").eq("id", post_id).eq("user_id", user["id"]).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Post not found")

    post = row.data[0]
    if post["status"] != "scheduled":
        raise HTTPException(status_code=400, detail="Can only cancel scheduled posts")

    # Cancel in Ayrshare
    if post.get("ayrshare_post_id"):
        profile_row = sb.table("ayrshare_profiles").select("ayrshare_profile_key").eq("user_id", user["id"]).execute()
        if profile_row.data:
            try:
                await ayrshare_client.delete_post(profile_row.data[0]["ayrshare_profile_key"], post["ayrshare_post_id"])
            except Exception:
                pass  # Best effort — still cancel locally

    sb.table("social_posts").update({
        "status": "cancelled",
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", post_id).execute()

    return {"status": "cancelled", "id": post_id}


# ---------------------------------------------------------------------------
# AI Caption Generation for Social Posts
# ---------------------------------------------------------------------------

class CaptionRequest(BaseModel):
    video_job_id: str
    platform: str = "instagram"

@app.post("/api/schedule/generate-caption")
async def api_generate_caption(data: CaptionRequest, user: dict = Depends(get_current_user)):
    """Generate 3 AI caption suggestions for a video, optimised for the target platform."""
    job = get_job(data.video_job_id)
    if not job or job.get("user_id") != user["id"]:
        raise HTTPException(status_code=404, detail="Video not found")

    # Gather context from job metadata
    product_name = ""
    product_desc = ""
    influencer_name = ""
    if job.get("product_id"):
        product = get_product(job["product_id"])
        if product:
            product_name = product.get("name", "")
            product_desc = product.get("description", "")
    if job.get("influencer_id"):
        inf = get_influencer(job["influencer_id"])
        if inf:
            influencer_name = inf.get("name", "")

    platform = data.platform.capitalize()
    prompt = f"""Generate exactly 3 distinct, engaging social media captions for {platform}.

Context:
- Product: {product_name or 'Unknown product'}
- Description: {product_desc or 'AI-generated UGC video'}
- Influencer: {influencer_name or 'AI creator'}

Requirements:
- Each caption should have a different angle (e.g. storytelling, CTA, question)
- Include relevant emojis
- Keep under 200 characters for TikTok, 2200 for Instagram, 500 for YouTube
- Include 3-5 relevant hashtags at the end
- Sound natural and authentic, not salesy

Return ONLY a JSON array of 3 strings, nothing else."""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
        )
        import json
        raw = response.choices[0].message.content.strip()
        # Strip markdown code fence if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        captions = json.loads(raw)
        if not isinstance(captions, list):
            captions = [raw]
        return {"captions": captions[:3]}
    except Exception as e:
        return {"captions": [
            f"Check out this amazing {product_name or 'product'}! 🔥 #ugc #ai",
            f"You need to see this! {product_name or 'This product'} is incredible ✨ #viral",
            f"POV: You just found your new favourite {product_name or 'thing'} 👀 #trending",
        ]}


# ---------------------------------------------------------------------------
# Ayrshare Webhook Handler (publicly accessible — no auth)
# ---------------------------------------------------------------------------

@app.post("/api/webhooks/ayrshare")
async def api_ayrshare_webhook(request: Request):
    """Handle incoming Ayrshare webhook events (post status, social account changes)."""
    webhook_secret = os.getenv("AYRSHARE_WEBHOOK_SECRET", "")

    # Validate HMAC signature
    body = await request.body()
    if webhook_secret:
        expected_sig = request.headers.get("X-Authorization-Content-SHA256", "")
        computed_sig = hmac.new(webhook_secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(computed_sig, expected_sig):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    import json
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    sb = get_supabase()
    action = payload.get("action", "")

    # ── Post status update ──────────────────────────────────────────────
    if action == "post":
        ayrshare_id = payload.get("id")
        status = payload.get("status", "")
        if ayrshare_id:
            update_data = {"updated_at": datetime.now(timezone.utc).isoformat()}
            if status == "success":
                update_data["status"] = "posted"
                update_data["posted_at"] = datetime.now(timezone.utc).isoformat()
            elif status == "error":
                update_data["status"] = "failed"
                update_data["error_message"] = payload.get("errorMessage", "Unknown error")
            if "status" in update_data:
                sb.table("social_posts").update(update_data).eq("ayrshare_post_id", ayrshare_id).execute()

    # ── Social account change ───────────────────────────────────────────
    elif action == "social":
        profile_key = payload.get("profileKey")
        accounts = payload.get("activeSocialAccounts", [])
        if profile_key:
            sb.table("ayrshare_profiles").update({
                "connected_accounts": accounts,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("ayrshare_profile_key", profile_key).execute()

    return {"status": "ok"}

