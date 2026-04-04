"""
editor_api.py — Remotion Editor API Router

This module provides all backend API routes for the Remotion Editor integration.
It is completely isolated from the existing video generation pipeline.
If this module fails, the existing SaaS continues to function normally.
"""

import os
import uuid
import tempfile
import subprocess
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Body
from pydantic import BaseModel
from typing import Optional

from ugc_backend.auth import get_current_user
from ugc_db.db_manager import get_job, update_job, get_supabase

router = APIRouter(prefix="/api/editor", tags=["editor"])


def _get_job_any(job_id: str) -> tuple:
    """
    Look up a job in both video_jobs and clone_video_jobs.
    Returns (job_dict, table_name) or (None, None).
    """
    job = get_job(job_id)
    if job:
        return job, "video_jobs"

    # Also check clone_video_jobs (select * minus editor_state which may not exist yet)
    try:
        sb = get_supabase()
        result = sb.table("clone_video_jobs").select("*").eq("id", job_id).execute()
        if result.data:
            return result.data[0], "clone_video_jobs"
    except Exception:
        # If column doesn't exist, try without editor_state
        try:
            sb = get_supabase()
            result = sb.table("clone_video_jobs").select(
                "id,user_id,status,final_video_url,duration,subtitle_placement,"
                "subtitle_style,subtitles_enabled,video_language,created_at"
            ).eq("id", job_id).execute()
            if result.data:
                return result.data[0], "clone_video_jobs"
        except Exception:
            pass

    return None, None


# ============================================================================
# ADAPTER: Build UndoableState from video_jobs row
# ============================================================================

def _build_editor_state(job: dict) -> dict:
    """
    Convert a video_jobs or clone_video_jobs row into a Remotion Editor Starter UndoableState.
    See Section 6.2 of the blueprint for the full specification.
    """
    fps = 24
    video_url = job.get("final_video_url")
    if not video_url:
        raise ValueError("Job has no final_video_url")

    # Handle different column naming: video_jobs uses video_duration_seconds, clone_video_jobs uses duration
    duration_seconds = job.get("video_duration_seconds") or job.get("duration") or 30.0
    if isinstance(duration_seconds, str):
        try:
            duration_seconds = float(duration_seconds)
        except ValueError:
            duration_seconds = 30.0
    width = job.get("video_width") or 1080
    height = job.get("video_height") or 1920
    transcription = job.get("transcription")
    duration_frames = round(duration_seconds * fps)

    video_asset_id = str(uuid.uuid4())
    caption_asset_id = str(uuid.uuid4())
    video_item_id = str(uuid.uuid4())
    caption_item_id = str(uuid.uuid4())
    video_track_id = str(uuid.uuid4())
    caption_track_id = str(uuid.uuid4())

    video_asset = {
        "id": video_asset_id,
        "type": "video",
        "filename": "generated_video.mp4",
        "size": 0,
        "mimeType": "video/mp4",
        "remoteUrl": video_url,
        "remoteFileKey": None,
        "durationInSeconds": duration_seconds,
        "hasAudioTrack": True,
        "width": width,
        "height": height,
    }

    video_item = {
        "id": video_item_id,
        "type": "video",
        "assetId": video_asset_id,
        "durationInFrames": duration_frames,
        "from": 0,
        "top": 0,
        "left": 0,
        "width": width,
        "height": height,
        "opacity": 1,
        "isDraggingInTimeline": False,
        "videoStartFromInSeconds": 0,
        "decibelAdjustment": 0,
        "playbackRate": 1,
        "audioFadeInDurationInSeconds": 0,
        "audioFadeOutDurationInSeconds": 0,
        "fadeInDurationInSeconds": 0,
        "fadeOutDurationInSeconds": 0,
        "keepAspectRatio": True,
        "borderRadius": 0,
        "rotation": 0,
        "cropLeft": 0,
        "cropTop": 0,
        "cropRight": 0,
        "cropBottom": 0,
    }

    assets = {video_asset_id: video_asset}
    items = {video_item_id: video_item}
    tracks = [{"id": video_track_id, "items": [video_item_id], "hidden": False, "muted": False}]

    if transcription and transcription.get("words") and job.get("subtitles_enabled", True):
        captions = []
        for word_data in transcription["words"]:
            if isinstance(word_data, dict):
                word = word_data.get("word", "")
                start = float(word_data.get("start", 0))
                end = float(word_data.get("end", 0))
            else:
                word = getattr(word_data, "word", "")
                start = float(getattr(word_data, "start", 0))
                end = float(getattr(word_data, "end", 0))

            # Ensure each word has proper spacing (Whisper includes leading space)
            # Strip and re-add a single trailing space for clean rendering
            word = word.strip()
            if not word:
                continue

            captions.append({
                "text": word + " ",
                "startMs": round(start * 1000),
                "endMs": round(end * 1000),
                "timestampMs": round(start * 1000),
                "confidence": None,
            })

        placement = job.get("subtitle_placement", "middle")
        caption_top_map = {
            "top": round(height * 0.10),
            "middle": round(height * 0.45),
            "bottom": round(height * 0.75),
        }
        caption_top = caption_top_map.get(placement, round(height * 0.45))

        # Read the subtitle style from the job to match the original rendering
        style = job.get("subtitle_style", "hormozi")

        caption_asset = {
            "id": caption_asset_id,
            "type": "caption",
            "filename": "captions.json",
            "size": 0,
            "mimeType": "application/json",
            "remoteUrl": None,
            "remoteFileKey": None,
            "captions": captions,
        }

        caption_item = {
            "id": caption_item_id,
            "type": "captions",
            "assetId": caption_asset_id,
            "durationInFrames": duration_frames,
            "from": 0,
            "top": caption_top,
            "left": round(width * 0.05),
            "width": round(width * 0.90),
            "height": round(height * 0.20),
            # opacity=0: captions are already burned into the video pixels.
            # The track exists in the timeline so users can view/edit the text,
            # but it doesn't render a duplicate overlay on the canvas.
            "opacity": 0,
            "isDraggingInTimeline": False,
            "rotation": 0,
            "fontFamily": "Montserrat",
            "fontStyle": {"variant": "normal", "weight": 800},
            "lineHeight": 1.2,
            "letterSpacing": 0,
            "fontSize": 72,
            "align": "center",
            "color": "#FFFFFF",
            "highlightColor": "#FFFF00",
            "strokeWidth": 3,
            "strokeColor": "#000000",
            "direction": "ltr",
            "pageDurationInMilliseconds": 1200,
            "captionStartInSeconds": 0,
            "maxLines": 2,
            "fadeInDurationInSeconds": 0,
            "fadeOutDurationInSeconds": 0,
        }

        assets[caption_asset_id] = caption_asset
        items[caption_item_id] = caption_item
        tracks.append({
            "id": caption_track_id,
            "items": [caption_item_id],
            "hidden": False,
            "muted": False,
        })

    return {
        "fps": fps,
        "compositionWidth": width,
        "compositionHeight": height,
        "tracks": tracks,
        "items": items,
        "assets": assets,
        "deletedAssets": [],
    }


# ============================================================================
# ROUTE: GET /api/editor/jobs
# Returns a lightweight list of the user's videos eligible for editing.
# ============================================================================

@router.get("/jobs")
def list_editor_jobs(user: dict = Depends(get_current_user)):
    """
    Returns completed video jobs for the current user that are eligible
    for editing. Merges results from video_jobs and clone_video_jobs.
    Sorted by most recently updated first.
    """
    user_id = str(user["id"])
    sb = get_supabase()
    jobs = []

    # 1. video_jobs
    try:
        result = sb.table("video_jobs").select(
            "id,campaign_name,final_video_url,status,created_at,updated_at,editor_state"
        ).eq("user_id", user_id).in_(
            "status", ["success"]
        ).not_.is_("final_video_url", "null").order(
            "updated_at", desc=True
        ).limit(50).execute()

        for row in result.data or []:
            jobs.append({
                "id": row["id"],
                "name": row.get("campaign_name") or "Untitled Video",
                "final_video_url": row["final_video_url"],
                "status": row["status"],
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "has_editor_state": row.get("editor_state") is not None,
                "source": "video_jobs",
            })
    except Exception as e:
        print(f"[EDITOR JOBS] Error fetching video_jobs: {e}")

    # 2. clone_video_jobs
    try:
        result = sb.table("clone_video_jobs").select(
            "id,status,final_video_url,created_at,updated_at"
        ).eq("user_id", user_id).in_(
            "status", ["complete"]
        ).not_.is_("final_video_url", "null").order(
            "updated_at", desc=True
        ).limit(50).execute()

        for row in result.data or []:
            jobs.append({
                "id": row["id"],
                "name": "Clone Video",
                "final_video_url": row["final_video_url"],
                "status": row["status"],
                "created_at": row.get("created_at"),
                "updated_at": row.get("updated_at"),
                "has_editor_state": False,  # clone jobs may not have editor_state column
                "source": "clone_video_jobs",
            })
    except Exception as e:
        print(f"[EDITOR JOBS] Error fetching clone_video_jobs: {e}")

    # Sort merged list by updated_at DESC
    jobs.sort(key=lambda j: j.get("updated_at") or j.get("created_at") or "", reverse=True)

    return {"jobs": jobs[:50]}


# ============================================================================
# ROUTE: GET /api/editor/state/{job_id}

# Returns the UndoableState JSON for a given job.
# ============================================================================

@router.get("/state/{job_id}")
def get_editor_state(job_id: str, user: dict = Depends(get_current_user)):
    """
    Returns the UndoableState JSON for a given job.
    The frontend base64-encodes this and appends it to the editor URL as #state=<encoded>.
    """
    try:
        job, table = _get_job_any(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if str(job.get("user_id")) != str(user["id"]):
            raise HTTPException(status_code=403, detail="Access denied")

        # Clone jobs use status='complete', video_jobs use status='success'
        done_statuses = {"success", "complete"}
        if job.get("status") not in done_statuses:
            raise HTTPException(status_code=400, detail="Job is not complete")
        if not job.get("final_video_url"):
            raise HTTPException(status_code=400, detail="Job has no final video")

        # Return saved editor state if it exists (from a previous edit session)
        if job.get("editor_state"):
            return job["editor_state"]

        # If no transcription data, auto-transcribe the video so captions are editable
        if not job.get("transcription") and job.get("final_video_url"):
            try:
                transcription = _auto_transcribe_video(job["final_video_url"])
                if transcription and transcription.get("words"):
                    job["transcription"] = transcription
                    # Persist transcription so we don't re-run Whisper next time
                    _save_transcription(job_id, table, transcription)
            except Exception as e:
                print(f"[EDITOR] Auto-transcription failed (non-fatal): {e}")

        # Build fresh state from job metadata
        return _build_editor_state(job)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE: POST /api/editor/state/{job_id}
# Saves the current editor state to the DB for resuming later.
# ============================================================================

@router.post("/state/{job_id}")
def save_editor_state(job_id: str, state: dict = Body(...), user: dict = Depends(get_current_user)):
    """Saves the current editor state to the DB so the user can resume editing later."""
    try:
        job, table = _get_job_any(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        if str(job.get("user_id")) != str(user["id"]):
            raise HTTPException(status_code=403, detail="Access denied")

        # Save to the correct table
        if table == "clone_video_jobs":
            try:
                sb = get_supabase()
                sb.table("clone_video_jobs").update({"editor_state": state}).eq("id", job_id).execute()
            except Exception:
                pass  # Column may not exist yet — state not persisted for clones
        else:
            update_job(job_id, {"editor_state": state})
        return {"status": "saved"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HELPER: Auto-transcribe video using Whisper
# ============================================================================

def _auto_transcribe_video(video_url: str) -> dict:
    """
    Download a video from URL, extract audio, and transcribe with Whisper.
    Returns {"words": [...], "text": "..."} or None.
    """
    import requests as req_lib
    from ugc_backend.transcription_client import TranscriptionClient

    with tempfile.TemporaryDirectory() as tmpdir:
        # Download video
        video_path = Path(tmpdir) / "video.mp4"
        print(f"[EDITOR] Downloading video for transcription...")
        response = req_lib.get(video_url, timeout=120)
        response.raise_for_status()
        video_path.write_bytes(response.content)

        # Extract audio with ffmpeg
        audio_path = Path(tmpdir) / "audio.wav"
        result = subprocess.run(
            ["ffmpeg", "-i", str(video_path), "-vn", "-acodec", "pcm_s16le",
             "-ar", "16000", "-ac", "1", str(audio_path), "-y"],
            capture_output=True, timeout=60
        )
        if result.returncode != 0 or not audio_path.exists():
            print(f"[EDITOR] ffmpeg audio extraction failed")
            return None

        # Transcribe with Whisper
        print(f"[EDITOR] Transcribing with Whisper...")
        client = TranscriptionClient()
        transcription = client.transcribe_audio(str(audio_path))

        if transcription and transcription.get("words"):
            # Normalize word objects to plain dicts
            words = []
            for w in transcription["words"]:
                if isinstance(w, dict):
                    words.append(w)
                else:
                    words.append({
                        "word": getattr(w, "word", ""),
                        "start": getattr(w, "start", 0),
                        "end": getattr(w, "end", 0),
                    })
            transcription["words"] = words
            print(f"[EDITOR] Transcription complete: {len(words)} words")

        return transcription


def _save_transcription(job_id: str, table: str, transcription: dict):
    """Persist transcription data to the correct table."""
    try:
        if table == "clone_video_jobs":
            try:
                sb = get_supabase()
                sb.table("clone_video_jobs").update(
                    {"transcription": transcription}
                ).eq("id", job_id).execute()
            except Exception:
                pass  # transcription column may not exist yet
        else:
            update_job(job_id, {"transcription": transcription})
    except Exception as e:
        print(f"[EDITOR] Failed to save transcription (non-fatal): {e}")


# ============================================================================
# ROUTE: POST /api/editor/captions
# Transcribes audio from an uploaded file and returns word-level captions.
# Used by the Remotion Editor's captioning feature.
# ============================================================================

class CaptionsRequest(BaseModel):
    fileKey: str

@router.post("/captions")
def generate_captions(req: CaptionsRequest, user: dict = Depends(get_current_user)):
    """
    Downloads the audio from Supabase storage (uploaded by the editor),
    transcribes it with Whisper, and returns word-level captions in the
    format the Remotion Editor expects.
    """
    try:
        import requests as req_lib
        from ugc_backend.transcription_client import TranscriptionClient

        sb = get_supabase()

        # Get the public URL for the uploaded audio
        public_url = sb.storage.from_("editor-assets").get_public_url(req.fileKey)

        with tempfile.TemporaryDirectory() as tmpdir:
            # Download the audio file
            audio_path = Path(tmpdir) / "audio.wav"
            response = req_lib.get(public_url, timeout=120)
            response.raise_for_status()
            audio_path.write_bytes(response.content)

            # Transcribe with Whisper
            client = TranscriptionClient()
            transcription = client.transcribe_audio(str(audio_path))

            if not transcription or not transcription.get("words"):
                return {"captions": []}

            # Convert Whisper output to the format the editor expects
            captions = []
            for w in transcription["words"]:
                if isinstance(w, dict):
                    word = w.get("word", "")
                    start = float(w.get("start", 0))
                    end = float(w.get("end", 0))
                else:
                    word = getattr(w, "word", "")
                    start = float(getattr(w, "start", 0))
                    end = float(getattr(w, "end", 0))

                captions.append({
                    "text": word,
                    "startMs": round(start * 1000),
                    "endMs": round(end * 1000),
                    "timestampMs": round(start * 1000),
                    "confidence": None,
                })

            return {"captions": captions}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE: POST /api/editor/upload-url
# Returns a Supabase Storage upload URL for editor asset uploads.
# Replaces the Editor Starter's AWS S3 presign route.
# ============================================================================

class UploadUrlRequest(BaseModel):
    filename: str
    contentType: str
    size: Optional[int] = 0


@router.post("/upload-url")
def get_upload_url(req: UploadUrlRequest, user: dict = Depends(get_current_user)):
    """Returns a Supabase Storage signed upload URL for editor asset uploads."""
    try:
        ext = req.filename.rsplit(".", 1)[-1] if "." in req.filename else "bin"
        file_key = f"{user['id']}/{uuid.uuid4()}.{ext}"

        sb = get_supabase()
        result = sb.storage.from_("editor-assets").create_signed_upload_url(file_key)
        signed_url = result.get("signedURL") or result.get("signed_url") or result.get("signedUrl")
        public_url = sb.storage.from_("editor-assets").get_public_url(file_key)

        return {
            "presignedUrl": signed_url,
            "readUrl": public_url,
            "fileKey": file_key,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE: POST /api/editor/render
# Triggers a server-side render of the edited video.
# Uses a background thread to call the Remotion renderer directly (no Celery/Redis).
# ============================================================================

class EditorRenderRequest(BaseModel):
    job_id: Optional[str] = ""
    editor_state: dict
    codec: Optional[str] = "h264"


# In-memory render status store
_editor_renders: dict = {}


def _run_editor_render(
    render_id: str,
    job_id: str,
    user_id: str,
    editor_state: dict,
    codec: str,
):
    """
    Background thread: dispatches render to Modal (production) or calls
    Remotion renderer directly (local dev fallback).
    """
    import requests as _req

    def _update(data: dict):
        if render_id not in _editor_renders:
            _editor_renders[render_id] = {}
        _editor_renders[render_id].update(data)

    try:
        _update({"status": "processing", "progress": 5})

        modal_url = os.environ.get("MODAL_EDITOR_RENDER_URL")

        if modal_url:
            # ── Production: dispatch to Modal ──
            print(f"[EDITOR RENDER] Dispatching {render_id} to Modal: {modal_url}")
            resp = _req.post(
                modal_url,
                json={
                    "render_id": render_id,
                    "editor_state": editor_state,
                    "codec": codec,
                },
                timeout=15,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Modal dispatch failed ({resp.status_code}): {resp.text[:500]}"
                )
            _update({"status": "processing", "progress": 10})
            print(f"[EDITOR RENDER] ✓ Dispatched to Modal — waiting for callback")
            # Modal will call POST /api/editor/render/{render_id}/callback
            # when done, which updates _editor_renders.

        else:
            # ── Local dev: call Remotion renderer directly ──
            import tempfile
            from datetime import datetime as _dt

            remotion_url = os.environ.get(
                "REMOTION_RENDERER_URL", "http://localhost:8090"
            )

            print(f"[EDITOR RENDER] Starting render {render_id} via {remotion_url}")
            response = _req.post(
                f"{remotion_url}/render-editor",
                json={"editorState": editor_state, "codec": codec},
                timeout=600,
                stream=True,
            )

            if response.status_code != 200:
                raise RuntimeError(
                    f"Remotion renderer returned {response.status_code}: "
                    f"{response.text[:500]}"
                )

            _update({"progress": 50})

            timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
            storage_filename = f"edited_{job_id[:8]}_{timestamp}.mp4"

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        tmp.write(chunk)
                tmp_path = tmp.name

            _update({"progress": 80})

            try:
                from ugc_db.db_manager import get_supabase
                sb = get_supabase()
                with open(tmp_path, "rb") as f:
                    sb.storage.from_("generated-videos").upload(
                        storage_filename, f,
                        file_options={"content-type": "video/mp4"},
                    )
                output_url = sb.storage.from_("generated-videos").get_public_url(
                    storage_filename
                )
            except Exception as upload_err:
                print(f"[EDITOR RENDER] Upload failed: {upload_err}")
                output_url = f"file:///{tmp_path}"

            output_size = os.path.getsize(tmp_path)
            os.unlink(tmp_path)

            _update({
                "status": "done",
                "progress": 100,
                "output_url": output_url,
                "output_size": output_size,
            })
            print(f"[EDITOR RENDER] ✓ Render {render_id} done: {output_url}")

    except Exception as e:
        print(f"[EDITOR RENDER] ✗ Render {render_id} failed: {e}")
        _update({"status": "failed", "error": str(e)})


@router.post("/render")
def trigger_editor_render(
    body: EditorRenderRequest,
    user: dict = Depends(get_current_user),
):
    """
    Triggers a server-side render of the edited video.
    Uses a background thread to call the Remotion renderer directly.
    Returns a render_id for polling via GET /api/editor/render/{render_id}/progress.
    """
    try:
        # Job validation is best-effort: render works even if job is not in DB
        # (e.g. standalone editor sessions or cleaned-up jobs)
        if body.job_id:
            job = get_job(body.job_id)
            if job and str(job.get("user_id")) != str(user["id"]):
                raise HTTPException(status_code=403, detail="Access denied")

        render_id = str(uuid.uuid4())
        _editor_renders[render_id] = {"status": "processing", "progress": 0}

        # Launch render in a background thread (no Celery/Redis needed)
        import threading
        thread = threading.Thread(
            target=_run_editor_render,
            args=(render_id, body.job_id or "standalone", str(user["id"]),
                  body.editor_state, body.codec or "h264"),
            daemon=True,
        )
        thread.start()

        return {
            "type": "success",
            "renderId": render_id,
            "bucketName": "aitoma",  # Not used — render is server-side
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ROUTE: GET /api/editor/render/{render_id}/progress
# Returns the progress of an editor render job.
# ============================================================================

@router.get("/render/{render_id}/progress")
def get_render_progress(render_id: str, user: dict = Depends(get_current_user)):
    """Returns the progress of an editor render job."""
    render = _editor_renders.get(render_id)
    if not render:
        return {"type": "in-progress", "overallProgress": 0.0}

    if render.get("status") == "done":
        return {
            "type": "done",
            "outputFile": render["output_url"],
            "outputSizeInBytes": render.get("output_size", 0),
            "outputName": "edited_video.mp4",
        }
    if render.get("status") == "failed":
        return {"type": "error", "error": render.get("error", "Render failed")}

    return {"type": "in-progress", "overallProgress": render.get("progress", 0) / 100}


# ============================================================================
# ROUTE: POST /api/editor/render/{render_id}/callback
# Called by Modal when a render job completes (success or failure).
# ============================================================================

@router.post("/render/{render_id}/callback")
def render_callback(render_id: str, body: dict = Body(...)):
    """
    Callback endpoint for Modal to report render completion.
    Expects: {"status": "done", "output_url": "...", "output_size": 123}
    Or:      {"status": "failed", "error": "..."}
    """
    if body.get("status") == "done":
        _editor_renders[render_id] = {
            "status": "done",
            "progress": 100,
            "output_url": body["output_url"],
            "output_size": body.get("output_size", 0),
        }
    elif body.get("status") == "failed":
        _editor_renders[render_id] = {
            "status": "failed",
            "error": body.get("error", "Render failed"),
        }
    else:
        # Progress update
        _editor_renders[render_id] = {
            "status": "processing",
            "progress": body.get("progress", 0),
        }
    return {"ok": True}

# ============================================================================
# ROUTE: GET /api/editor/assets
# Returns all SaaS assets available for use in the editor.
# Powers the "My Assets" panel in the Editor.
# ============================================================================

@router.get("/assets")
def get_editor_assets(user: dict = Depends(get_current_user)):
    """
    Returns all SaaS assets available for use in the editor:
    app clips, product shots, and previously generated videos.
    """
    try:
        from ugc_db.db_manager import list_app_clips, list_jobs_scoped

        # App clips
        app_clips = list_app_clips() or []
        clip_assets = [
            {
                "id": clip["id"],
                "type": "video",
                "name": clip.get("name", "App Clip"),
                "url": clip.get("video_url"),
                "duration": clip.get("duration"),
                "category": "app_clip",
                "source": "app_clips",
            }
            for clip in app_clips
            if clip.get("video_url")
        ]

        # User's generated videos
        jobs = list_jobs_scoped(user_id=str(user["id"]), status="success", limit=50) or []
        video_assets = [
            {
                "id": job["id"],
                "type": "video",
                "name": job.get("campaign_name") or "Generated Video",
                "url": job.get("final_video_url"),
                "duration": job.get("video_duration_seconds"),
                "category": "generated_video",
                "source": "video_jobs",
            }
            for job in jobs
            if job.get("final_video_url")
        ]

        return {"clips": clip_assets, "videos": video_assets}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
