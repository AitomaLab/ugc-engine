"""
editor_api.py — Remotion Editor API Router

This module provides all backend API routes for the Remotion Editor integration.
It is completely isolated from the existing video generation pipeline.
If this module fails, the existing SaaS continues to function normally.
"""

import os
import re
import uuid
import shutil
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


def _probe_video_dimensions(video_url: str) -> Optional[tuple]:
    """
    Probe a remote (or local) video URL with ffprobe and return (width, height)
    in *display* orientation — i.e. axes are swapped when the stream carries a
    ±90° rotation via the `displaymatrix` side-data or the legacy `rotate` tag.
    This matches what a browser's HTML5 `<video>` `videoWidth`/`videoHeight`
    reports after applying rotation metadata.

    Returns None if probing fails or ffprobe is unavailable. Bounded by a short
    timeout so the state endpoint stays responsive.
    """
    import json as _json

    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_streams",
                "-print_format", "json",
                video_url,
            ],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if result.returncode != 0:
            return None
        data = _json.loads(result.stdout or "{}")
        streams = data.get("streams") or []
        if not streams:
            return None
        s = streams[0]
        w = int(s.get("width") or 0)
        h = int(s.get("height") or 0)
        if w <= 0 or h <= 0:
            return None

        rotation = 0
        tags = s.get("tags") or {}
        if tags.get("rotate"):
            try:
                rotation = int(tags["rotate"])
            except (TypeError, ValueError):
                rotation = 0
        for sd in s.get("side_data_list") or []:
            if "rotation" in sd:
                try:
                    rotation = int(sd["rotation"])
                except (TypeError, ValueError):
                    pass

        if abs(rotation) % 180 == 90:
            w, h = h, w
        return (w, h)
    except Exception:
        return None


# ============================================================================
# ADAPTER: Build UndoableState from video_jobs row
# ============================================================================

def _primary_video_bounds(items: dict, composition_w: int, composition_h: int) -> tuple:
    """Return (left, top, width, height) covering all video items, or full canvas.

    For single-video jobs this collapses to the one video item's bounds. For
    combined videos with multiple video items side-by-side, we use the UNION
    bounding box so captions center over the combined visible area instead of
    just the first clip.
    """
    video_items = [i for i in items.values() if i.get("type") == "video"]
    if not video_items:
        return (0, 0, composition_w, composition_h)

    lefts = [int(i.get("left", 0)) for i in video_items]
    tops = [int(i.get("top", 0)) for i in video_items]
    rights = [int(i.get("left", 0)) + int(i.get("width", composition_w)) for i in video_items]
    bottoms = [int(i.get("top", 0)) + int(i.get("height", composition_h)) for i in video_items]

    min_left = min(lefts)
    min_top = min(tops)
    union_w = max(rights) - min_left
    union_h = max(bottoms) - min_top
    return (min_left, min_top, union_w, union_h)


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
    duration_seconds = job.get("video_duration_seconds") or job.get("duration") or job.get("length") or 30.0
    if isinstance(duration_seconds, str):
        try:
            duration_seconds = float(duration_seconds)
        except ValueError:
            duration_seconds = 30.0
    # Always probe the source so we get display-correct (rotation-aware)
    # dimensions. The DB's `video_width`/`video_height` columns were populated
    # before rotation handling existed, so they can be axis-swapped on iPhone
    # footage. Probe result wins; fall back to stored columns only if probe
    # fails; final fallback is portrait 1080x1920 to match the prior default.
    probed = _probe_video_dimensions(video_url)
    if probed:
        width, height = probed
    else:
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
                "text": " " + word,
                "startMs": round(start * 1000),
                "endMs": round(end * 1000),
                "timestampMs": round(start * 1000),
                "confidence": None,
            })

        placement = job.get("subtitle_placement", "middle")
        vx, vy, vw, vh = _primary_video_bounds(items, width, height)
        caption_top_map = {
            "top": vy + round(vh * 0.10),
            "middle": vy + round(vh * 0.45),
            "bottom": vy + round(vh * 0.75),
        }
        caption_top = caption_top_map.get(placement, vy + round(vh * 0.45))
        caption_box_width = round(vw * 0.90)
        caption_box_left = vx + round(vw * 0.05)

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
            "left": caption_box_left,
            "width": caption_box_width,
            "height": round(vh * 0.20),
            "opacity": 1,
            "isDraggingInTimeline": False,
            "rotation": 0,
            "fontFamily": "Anton",
            "fontStyle": {"variant": "normal", "weight": 400},
            "lineHeight": 1.2,
            "letterSpacing": 0,
            "fontSize": 72,
            "align": "center",
            "color": "#FFFFFF",
            "highlightColor": "#FFFF00",
            "strokeWidth": 8,
            "strokeColor": "#000000",
            "direction": "ltr",
            "pageDurationInMilliseconds": 800,
            "captionStartInSeconds": 0,
            "maxLines": 2,
            "fadeInDurationInSeconds": 0,
            "fadeOutDurationInSeconds": 0,
        }

        assets[caption_asset_id] = caption_asset
        items[caption_item_id] = caption_item
        # Frontend renders tracks reversed (canvas/layers.tsx), so index 0 is
        # rendered on top. Prepend the caption track so captions sit above the
        # video instead of behind it.
        tracks.insert(0, {
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
def get_editor_state(job_id: str, force_rebuild: bool = False, user: dict = Depends(get_current_user)):
    """
    Returns the UndoableState JSON for a given job.
    The frontend base64-encodes this and appends it to the editor URL as #state=<encoded>.
    Pass ?force_rebuild=true to discard the cached state and rebuild from the job row.
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

        # Return saved editor state if it exists (from a previous edit session).
        # Cached state represents user intent — never mutate it here. To pick up
        # newer dimension/probe logic, clients must request ?force_rebuild=true
        # which discards the cached state and rebuilds via _build_editor_state.
        if job.get("editor_state") and not force_rebuild:
            return job["editor_state"]

        # If no transcription data, auto-transcribe the video so captions are editable
        if not job.get("transcription") and job.get("final_video_url"):
            try:
                metadata = job.get("metadata") or {}
                if not isinstance(metadata, dict):
                    metadata = {}
                script_prompt = _script_prompt_from_job(job, metadata)
                caption_lang = _resolve_caption_language(job, metadata, script_prompt)
                transcription = _auto_transcribe_video(
                    job["final_video_url"],
                    script_prompt=script_prompt,
                    language=caption_lang,
                )
                if transcription and transcription.get("words"):
                    job["transcription"] = transcription
                    # Persist transcription so we don't re-run Whisper next time
                    _save_transcription(job_id, table, transcription, language=caption_lang)
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

def _auto_transcribe_video(
    video_url: str,
    script_prompt: Optional[str] = None,
    language: Optional[str] = None,
) -> dict:
    """
    Download a video from URL, extract audio, and transcribe with Whisper.
    Returns {"words": [...], "text": "..."} or None.

    When `script_prompt` is provided (e.g. the full VO script from
    metadata.voiceover_script), Whisper biases decoding toward those words —
    closes gaps in word timestamps that otherwise appear when audio is ducked
    or noisy.
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
        transcription = client.transcribe_audio(
            str(audio_path),
            script_prompt=script_prompt,
            language=language,
        )

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


_SPANISH_SCRIPT_HINT = re.compile(
    r"[ñáéíóúü¿¡]|\b(el|la|los|las|de|que|con|para|por|esta|este|es|son|muy|más|sin|como|cuando|qué|cómo)\b",
    re.IGNORECASE,
)


def _script_prompt_from_job(job: dict, metadata: dict) -> Optional[str]:
    """Collect known dialogue text to guide Whisper decoding."""
    vo_script = metadata.get("voiceover_script")
    if vo_script:
        return str(vo_script).strip() or None
    for key in ("script", "hook"):
        val = job.get(key) or metadata.get(key)
        if val:
            return str(val).strip()
    scenes = metadata.get("scenes") or job.get("scenes")
    if isinstance(scenes, list):
        parts: list[str] = []
        for scene in scenes:
            if not isinstance(scene, dict):
                continue
            dialogue = scene.get("dialogue") or scene.get("text") or ""
            if dialogue:
                parts.append(str(dialogue).strip())
        if parts:
            return " ".join(parts)
    return None


def _resolve_caption_language(job: dict, metadata: dict, script_prompt: Optional[str]) -> str:
    """Resolve Whisper ISO-639-1 language for caption transcription."""
    for source in (job.get("video_language"), metadata.get("video_language")):
        lang = (source or "").strip().lower()
        if lang in ("en", "es"):
            return lang
    if script_prompt and _SPANISH_SCRIPT_HINT.search(script_prompt):
        return "es"
    return "en"


def _should_reuse_transcription(
    transcription: Optional[dict],
    stored_lang: Optional[str],
    desired_lang: str,
) -> bool:
    if not transcription or not transcription.get("words"):
        return False
    if stored_lang:
        return stored_lang == desired_lang
    # Legacy rows: only trust cached transcription for English jobs.
    return desired_lang == "en"


def _save_transcription(
    job_id: str,
    table: str,
    transcription: dict,
    language: Optional[str] = None,
):
    """Persist transcription data to the correct table."""
    try:
        metadata_patch: Optional[dict] = None
        if language:
            job, _ = _get_job_any(job_id)
            metadata = (job or {}).get("metadata") or {}
            if not isinstance(metadata, dict):
                metadata = {}
            metadata = dict(metadata)
            metadata["transcription_language"] = language
            metadata_patch = metadata

        if table == "clone_video_jobs":
            try:
                sb = get_supabase()
                payload: dict = {"transcription": transcription}
                if metadata_patch is not None:
                    payload["metadata"] = metadata_patch
                sb.table("clone_video_jobs").update(payload).eq("id", job_id).execute()
            except Exception:
                pass  # transcription column may not exist yet
        else:
            payload = {"transcription": transcription}
            if metadata_patch is not None:
                payload["metadata"] = metadata_patch
            update_job(job_id, payload)
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

                stripped = word.strip()
                if not stripped:
                    continue
                captions.append({
                    "text": stripped + " ",
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
# ROUTE: POST /api/editor/caption-video/{job_id}
# Server-side captioning: transcribes video audio with Whisper and injects
# a proper captions track into the editor state. This is the same pipeline
# the frontend "Caption video" button uses, but driven entirely server-side
# so the Creative Agent can trigger it without a browser.
# ============================================================================

# Caption style presets — matches the Remotion editor's CaptionsItem schema.
# "hormozi" mirrors the frontend default in caption-section.tsx.
CAPTION_STYLES = {
    "hormozi": {
        "fontFamily": "Anton", "fontSize": 72, "color": "#FFFFFF",
        "highlightColor": "#FFFF00", "strokeWidth": 8, "strokeColor": "#000000",
        "maxLines": 2, "pageDurationInMilliseconds": 800,
    },
    "minimal": {
        "fontFamily": "Inter", "fontSize": 48, "color": "#FFFFFF",
        "highlightColor": "#FFFF00", "strokeWidth": 4, "strokeColor": "#000000",
        "maxLines": 1, "pageDurationInMilliseconds": 800,
    },
    "bold": {
        "fontFamily": "Bebas Neue", "fontSize": 84, "color": "#FFFFFF",
        "highlightColor": "#FF3366", "strokeWidth": 10, "strokeColor": "#000000",
        "maxLines": 2, "pageDurationInMilliseconds": 800,
    },
    "karaoke": {
        "fontFamily": "Anton", "fontSize": 64, "color": "#FFFFFF",
        "highlightColor": "#337AFF", "strokeWidth": 6, "strokeColor": "#000000",
        "maxLines": 1, "pageDurationInMilliseconds": 800,
    },
}

# Valid values for the caption_video `stroke_mode` input — mirrors
# `StrokeMode` in frontend/src/editor/items/captions/captions-item-type.ts.
STROKE_MODES = {"solid", "shadow", "glow"}


# ============================================================================
# HELPER: ffmpeg-based caption burn-in (fast alternative to Remotion render)
# ============================================================================

def _hex_to_ass_color(hex_color: str) -> str:
    """Convert #RRGGBB to ASS &HAABBGGRR& format (BGR, alpha=00=opaque)."""
    h = hex_color.lstrip("#")
    if len(h) == 6:
        r, g, b = h[0:2], h[2:4], h[4:6]
        return f"&H00{b}{g}{r}&"
    return "&H00FFFFFF&"


def _group_captions_into_pages(
    captions: list[dict],
    max_words_per_page: int = 5,
) -> list[list[dict]]:
    """Group word-level captions into display pages."""
    pages = []
    current_page: list[dict] = []
    for cap in captions:
        current_page.append(cap)
        if len(current_page) >= max_words_per_page:
            pages.append(current_page)
            current_page = []
    if current_page:
        pages.append(current_page)
    return pages


def _generate_ass_subtitles(
    captions: list[dict],
    style_props: dict,
    placement: str,
    width: int = 1080,
    height: int = 1920,
    stroke_mode: str = "solid",
    shadow_color: Optional[str] = None,
    shadow_blur: int = 8,
) -> str:
    """Generate ASS subtitle content from word-level caption data with
    word-level highlighting (current word in highlight color).

    PlayResX/PlayResY are set to the real video dimensions and
    ScaledBorderAndShadow is on, so fontSize/strokeWidth are applied in source
    pixels — no manual scaling needed.
    """

    # fontFamily is a CSS stack ("Anton, Impact, sans-serif"); libass matches a
    # single family name, so take the first and let fontsdir resolve it.
    font_family = str(style_props.get("fontFamily", "Anton")).split(",")[0].strip().strip("'\"")
    font_size = style_props.get("fontSize", 72)
    primary_color = _hex_to_ass_color(style_props.get("color", "#FFFFFF"))
    highlight_color = _hex_to_ass_color(style_props.get("highlightColor", "#FFFF00"))
    outline_color = _hex_to_ass_color(style_props.get("strokeColor", "#000000"))
    outline_width = style_props.get("strokeWidth", 8)
    max_lines = style_props.get("maxLines", 2)

    # stroke_mode -> ASS border/shadow. "solid" is a plain outline; "shadow"
    # drops an offset shadow in shadow_color; "glow" blurs the outline out into
    # a halo (inline \blur, since the Style block has no blur column).
    back_color = _hex_to_ass_color(shadow_color or style_props.get("strokeColor", "#000000"))
    shadow_depth = 0
    inline_prefix = ""
    if stroke_mode == "shadow":
        shadow_depth = max(1, int(shadow_blur / 2))
    elif stroke_mode == "glow":
        outline_color = back_color
        inline_prefix = f"{{\\blur{max(1, int(shadow_blur))}}}"

    # Placement -> ASS alignment (numpad: 2=bottom, 5=middle, 8=top)
    alignment_map = {"bottom": 2, "middle": 5, "top": 8}
    alignment = alignment_map.get(placement, 5)

    # Vertical margin based on placement
    margin_v_map = {"bottom": int(height * 0.12), "middle": int(height * 0.02), "top": int(height * 0.10)}
    margin_v = margin_v_map.get(placement, int(height * 0.02))

    # Words per page: ~max_lines * 2-3 words per line
    words_per_page = max(max_lines * 3, 3)
    pages = _group_captions_into_pages(captions, max_words_per_page=words_per_page)

    def _ms_to_ass_time(ms: int) -> str:
        """Convert milliseconds to ASS time format H:MM:SS.CC"""
        total_cs = ms // 10
        cs = total_cs % 100
        total_s = total_cs // 100
        s = total_s % 60
        m = (total_s // 60) % 60
        h = total_s // 3600
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\n"
        f"PlayResY: {height}\n"
        "WrapStyle: 0\n"
        "ScaledBorderAndShadow: yes\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{font_family},{font_size},{primary_color},"
        f"{highlight_color},{outline_color},{back_color},"
        f"1,0,0,0,100,100,0,0,1,{outline_width},{shadow_depth},"
        f"{alignment},40,40,{margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    events = []
    for page in pages:
        if not page:
            continue
        page_start_ms = page[0]["startMs"]
        page_end_ms = page[-1]["endMs"]

        # For each word's time slice in this page, generate an event
        # showing all page words with the current word highlighted
        for i, word_cap in enumerate(page):
            word_start = word_cap["startMs"]
            # Word end = next word's start (or page end for last word)
            word_end = page[i + 1]["startMs"] if i + 1 < len(page) else page_end_ms

            if word_end <= word_start:
                word_end = word_start + 100  # minimum 100ms

            # Build text with current word highlighted
            parts = []
            for j, w in enumerate(page):
                word_text = w["text"].strip()
                if not word_text:
                    continue
                if j == i:
                    # Highlight current word
                    parts.append(f"{{\\1c{highlight_color}}}{word_text.upper()}{{\\1c{primary_color}}}")
                else:
                    parts.append(word_text.upper())

            line_text = " ".join(parts)
            # Insert line break at midpoint for multi-line display
            if max_lines >= 2 and len(page) >= 4:
                mid = len(parts) // 2
                words_list = line_text.split(" ")
                # Find approximate midpoint
                if len(words_list) >= 4:
                    mid_idx = len(words_list) // 2
                    line_text = " ".join(words_list[:mid_idx]) + "\\N" + " ".join(words_list[mid_idx:])

            start_t = _ms_to_ass_time(word_start)
            end_t = _ms_to_ass_time(word_end)
            events.append(
                f"Dialogue: 0,{start_t},{end_t},Default,,0,0,0,,{inline_prefix}{line_text}"
            )

    return header + "\n".join(events) + "\n"


def _ffmpeg_binary() -> Optional[str]:
    """System ffmpeg first, then imageio-ffmpeg bundled binary."""
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _probe_local_video_dimensions(video_path: Path, ffmpeg_path: str) -> tuple[int, int]:
    """Return (width, height) for a local file, defaulting to 1080x1920."""
    width, height = 1080, 1920
    ffprobe = shutil.which("ffprobe")
    if ffprobe:
        try:
            probe = subprocess.run(
                [ffprobe, "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height",
                 "-of", "csv=s=x:p=0", str(video_path)],
                capture_output=True, text=True, timeout=10,
            )
            if probe.returncode == 0 and "x" in probe.stdout.strip():
                dims = probe.stdout.strip().split("x")
                width, height = int(dims[0]), int(dims[1])
                return width, height
        except Exception:
            pass
    try:
        probe = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-i", str(video_path)],
            capture_output=True, text=True, timeout=15,
        )
        match = re.search(r"(\d{2,5})x(\d{2,5})", probe.stderr or "")
        if match:
            width, height = int(match.group(1)), int(match.group(2))
    except Exception:
        pass
    return width, height


def _subtitles_filter_available(ffmpeg_path: str) -> bool:
    """True if this ffmpeg build has libass (the `subtitles` filter).

    imageio-ffmpeg's bundled binaries ship without libass, so the burn has to
    check rather than assume — otherwise it shells out to a command that can
    never work and the caller silently falls back to a slow Remotion render.
    """
    try:
        probe = subprocess.run(
            [ffmpeg_path, "-hide_banner", "-filters"],
            capture_output=True, text=True, timeout=15,
        )
        return re.search(r"^\s*\S*\s+subtitles\s", probe.stdout or "", re.MULTILINE) is not None
    except Exception:
        return False


def _ffmpeg_burn_captions(
    video_url: str,
    captions: list[dict],
    style_props: dict,
    placement: str,
    job_id: str,
    stroke_mode: str = "solid",
    shadow_color: Optional[str] = None,
    shadow_blur: int = 8,
) -> tuple[Optional[str], Optional[str]]:
    """Download video, burn word-timed captions with libass, upload the result.

    Returns (public_url, error_message). A None url means "fall back to the
    Remotion render", so every failure path returns an error string rather
    than raising.
    """
    import requests as req_lib
    from datetime import datetime as _dt

    ffmpeg_path = _ffmpeg_binary()
    if not ffmpeg_path:
        print("[CAPTION BURN] ffmpeg not found — skipping ffmpeg burn")
        return None, "ffmpeg not found (install ffmpeg or imageio-ffmpeg)"

    if not _subtitles_filter_available(ffmpeg_path):
        print("[CAPTION BURN] ffmpeg has no libass/subtitles filter — skipping ffmpeg burn")
        return None, "libass unavailable (ffmpeg built without the subtitles filter)"

    if not captions:
        return None, "No captions to burn"

    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            # 1. Download video
            video_path = Path(tmpdir) / "input.mp4"
            print(f"[CAPTION BURN] Downloading video...")
            resp = req_lib.get(video_url, timeout=120)
            resp.raise_for_status()
            video_path.write_bytes(resp.content)

            # 2. Probe dimensions — ASS PlayResX/Y must match the real frame so
            #    fontSize/strokeWidth land at their intended pixel size.
            probe_width, probe_height = _probe_local_video_dimensions(video_path, ffmpeg_path)
            print(f"[CAPTION BURN] Video: {probe_width}x{probe_height}")

            # 3. Build the ASS subtitle file
            ass_content = _generate_ass_subtitles(
                captions=captions,
                style_props=style_props,
                placement=placement,
                width=probe_width,
                height=probe_height,
                stroke_mode=stroke_mode,
                shadow_color=shadow_color,
                shadow_blur=shadow_blur,
            )
            ass_path = Path(tmpdir) / "captions.ass"
            ass_path.write_text(ass_content, encoding="utf-8")
            print(f"[CAPTION BURN] ASS written ({len(ass_content)} bytes, {len(captions)} words)")

            # 4. libass resolves fonts by family name via fontconfig, which does
            #    not know about our bundled .ttf files. Copy them next to the
            #    .ass and point fontsdir at them, or every style silently renders
            #    in a fallback font.
            bundled_fonts = Path(__file__).parent / "fonts"
            local_fonts = Path(tmpdir) / "fonts"
            try:
                shutil.copytree(str(bundled_fonts), str(local_fonts))
            except Exception as font_err:
                local_fonts.mkdir(exist_ok=True)
                print(f"[CAPTION BURN] WARNING: bundled fonts unavailable ({font_err}) — "
                      f"libass will fall back to a system font")

            # 5. Burn. Run from tmpdir and reference everything by bare relative
            #    name — the subtitles filter parses ':' and '\' as syntax, which
            #    every absolute Windows path would break.
            output_path = Path(tmpdir) / "output.mp4"
            cmd = [
                ffmpeg_path,
                "-i", "input.mp4",
                "-vf", "subtitles=captions.ass:fontsdir=fonts",
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-pix_fmt", "yuv420p",
                "-c:a", "copy",
                "-y", "output.mp4",
            ]
            print(f"[CAPTION BURN] Running ffmpeg (libass)...")
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, cwd=tmpdir,
            )
            if result.returncode != 0:
                err_tail = (result.stderr or result.stdout or "")[-800:]
                print(f"[CAPTION BURN] ffmpeg failed: {err_tail}")
                return None, f"ffmpeg failed: {err_tail}"

            if not output_path.exists() or output_path.stat().st_size == 0:
                return None, "ffmpeg produced no output"

            print(f"[CAPTION BURN] ffmpeg done, output {output_path.stat().st_size} bytes")

            # 6. Upload to Supabase
            timestamp = _dt.now().strftime("%Y%m%d_%H%M%S")
            storage_filename = f"captioned_{job_id[:8]}_{timestamp}.mp4"
            try:
                sb = get_supabase()
                with open(output_path, "rb") as f:
                    sb.storage.from_("generated-videos").upload(
                        storage_filename, f,
                        file_options={"content-type": "video/mp4"},
                    )
                public_url = sb.storage.from_("generated-videos").get_public_url(storage_filename)
                print(f"[CAPTION BURN] Uploaded: {public_url}")
                return public_url, None
            except Exception as upload_err:
                print(f"[CAPTION BURN] Upload failed: {upload_err}")
                return None, f"Upload failed: {upload_err}"

        except Exception as e:
            print(f"[CAPTION BURN] Error: {e}")
            import traceback
            traceback.print_exc()
            return None, str(e)


class CaptionVideoRequest(BaseModel):
    style: Optional[str] = "hormozi"
    placement: Optional[str] = "middle"
    stroke_mode: Optional[str] = "solid"
    shadow_color: Optional[str] = None
    shadow_blur: Optional[int] = 8
    shadow_offset_x: Optional[int] = 0
    shadow_offset_y: Optional[int] = 4


@router.post("/caption-video/{job_id}")
def caption_video(job_id: str, body: CaptionVideoRequest = CaptionVideoRequest(), user: dict = Depends(get_current_user)):
    """
    Server-side captioning endpoint. Reuses the same Whisper transcription
    pipeline as the frontend 'Caption video' button.

    Flow:
    1. Load job → get final_video_url + existing transcription
    2. If no transcription yet, run _auto_transcribe_video (Whisper)
    3. Load or build the editor state
    4. Inject caption asset + item into the state (same schema as caption-section.tsx)
    5. Save updated state to DB
    6. Return summary
    """
    try:
        job, table = _get_job_any(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # ── Always use the ORIGINAL (pre-caption) video URL ──
        # This prevents double-captioning when users re-caption.
        metadata = job.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        current_url = job.get("final_video_url")
        if not current_url:
            raise HTTPException(status_code=400, detail="Job has no final video URL")

        # Strategy: find the true original URL from multiple sources
        video_url = None

        # Source 1: Editor state → video asset remoteUrl (always the original)
        editor_state_raw = job.get("editor_state")
        if editor_state_raw:
            es = editor_state_raw if isinstance(editor_state_raw, dict) else json.loads(editor_state_raw)
            for _aid, asset in (es.get("assets") or {}).items():
                if asset.get("type") == "video" and asset.get("remoteUrl"):
                    candidate = asset["remoteUrl"]
                    if "captioned_" not in candidate:
                        video_url = candidate
                        print(f"[CAPTION] Using original video from editor state asset")
                        break

        # Source 2: metadata.original_video_url (if not a captioned URL)
        if not video_url:
            stored_original = metadata.get("original_video_url")
            if stored_original and "captioned_" not in stored_original:
                video_url = stored_original
                print(f"[CAPTION] Using original_video_url from metadata")

        # Source 3: current final_video_url (only if it's not a captioned URL)
        if not video_url:
            if "captioned_" not in current_url:
                video_url = current_url
                print(f"[CAPTION] Using current final_video_url (not yet captioned)")

        if not video_url:
            # All URLs are captioned — this shouldn't happen, but fall back
            video_url = metadata.get("original_video_url") or current_url
            print(f"[CAPTION] WARNING: Could not find original uncaptioned video, using: {video_url[:80]}")

        # Persist the original URL for future re-captioning
        if "original_video_url" not in metadata or "captioned_" in (metadata.get("original_video_url") or ""):
            metadata["original_video_url"] = video_url
            if table == "clone_video_jobs":
                try:
                    sb = get_supabase()
                    sb.table("clone_video_jobs").update(
                        {"metadata": metadata}
                    ).eq("id", job_id).execute()
                except Exception:
                    pass
            else:
                update_job(job_id, {"metadata": metadata})
            print(f"[CAPTION] Saved clean original_video_url to metadata")

        # ── Step 1: Get or create transcription ──────────────────────
        # For voiceover_on_video jobs the mix drops source audio volume which
        # confuses Whisper — prefer the clean TTS mp3 saved in metadata.
        vo_audio_url = metadata.get("voiceover_audio_url")
        script_prompt = _script_prompt_from_job(job, metadata)
        caption_lang = _resolve_caption_language(job, metadata, script_prompt)
        stored_transcription_lang = metadata.get("transcription_language")
        transcription_source = vo_audio_url or video_url

        transcription = job.get("transcription")
        if _should_reuse_transcription(transcription, stored_transcription_lang, caption_lang):
            print(
                f"[CAPTION] Reusing existing transcription for {job_id} "
                f"({len(transcription['words'])} words, lang={stored_transcription_lang or caption_lang})"
            )
        else:
            if transcription and transcription.get("words"):
                print(
                    f"[CAPTION] Discarding stale transcription for {job_id} "
                    f"(stored_lang={stored_transcription_lang!r}, need={caption_lang})"
                )
            transcription = None

        if not transcription or not transcription.get("words"):
            if vo_audio_url:
                print(f"[CAPTION] Using VO audio from metadata for {job_id}: {vo_audio_url}")
            else:
                print(f"[CAPTION] Transcribing final_video_url for {job_id}: {video_url}")
            if script_prompt:
                print(f"[CAPTION] Seeding Whisper with {len(str(script_prompt).split())}-word script prompt")
            print(f"[CAPTION] Whisper language={caption_lang}")
            transcription = _auto_transcribe_video(
                transcription_source,
                script_prompt=script_prompt,
                language=caption_lang,
            )
            if not transcription or not transcription.get("words"):
                raise HTTPException(
                    status_code=500,
                    detail=f"Whisper transcription returned no words (source={transcription_source})",
                )
            # Persist so we don't re-transcribe next time
            _save_transcription(job_id, table, transcription, language=caption_lang)

        # ── Step 2: Build captions array (Remotion Caption format) ───
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
            word = word.strip()
            if not word:
                continue
            captions.append({
                "text": " " + word,
                "startMs": round(start * 1000),
                "endMs": round(end * 1000),
                "timestampMs": round(start * 1000),
                "confidence": None,
            })

        if not captions:
            raise HTTPException(status_code=500, detail="Transcription produced no usable words")

        # ── Step 3: Load or build editor state ───────────────────────
        editor_state = job.get("editor_state")
        if not editor_state:
            editor_state = _build_editor_state(job)

        undoable = editor_state.get("undoableState", editor_state)
        fps = editor_state.get("fps", 24)
        width = undoable.get("compositionWidth", 1080)
        height = undoable.get("compositionHeight", 1920)

        # Duration from the existing state
        existing_tracks = undoable.get("tracks", [])
        existing_items = undoable.get("items", {})
        existing_assets = undoable.get("assets", {})

        # Remove any existing caption tracks/items/assets before adding new ones
        caption_item_ids = set()
        caption_asset_ids = set()
        for item_id, item in list(existing_items.items()):
            if item.get("type") == "captions":
                caption_item_ids.add(item_id)
                caption_asset_ids.add(item.get("assetId", ""))
        for item_id in caption_item_ids:
            existing_items.pop(item_id, None)
        for asset_id in caption_asset_ids:
            existing_assets.pop(asset_id, None)
        existing_tracks = [
            t for t in existing_tracks
            if not all(i in caption_item_ids for i in t.get("items", []))
        ]

        # ── Step 4: Build caption asset + item ───────────────────────
        style_name = (body.style or "hormozi").lower()
        style_props = CAPTION_STYLES.get(style_name, CAPTION_STYLES["hormozi"])

        placement = (body.placement or "middle").lower()
        vx, vy, vw, vh = _primary_video_bounds(existing_items, width, height)
        caption_top_map = {
            "top": vy + round(vh * 0.10),
            "middle": vy + round(vh * 0.45),
            "bottom": vy + round(vh * 0.75),
        }
        caption_top = caption_top_map.get(placement, vy + round(vh * 0.45))

        caption_asset_id = str(uuid.uuid4())
        caption_item_id = str(uuid.uuid4())
        caption_track_id = str(uuid.uuid4())

        # Compute duration from the last caption word
        last_end_ms = max(c["endMs"] for c in captions)
        duration_frames = round((last_end_ms / 1000) * fps)

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

        caption_width = min(vw, 900) - 40
        stroke_mode = (body.stroke_mode or "solid").lower()
        if stroke_mode not in STROKE_MODES:
            stroke_mode = "solid"
        shadow_color = body.shadow_color or style_props["strokeColor"]
        shadow_blur = int(body.shadow_blur) if body.shadow_blur is not None else 8
        shadow_offset_x = int(body.shadow_offset_x) if body.shadow_offset_x is not None else 0
        shadow_offset_y = int(body.shadow_offset_y) if body.shadow_offset_y is not None else 4

        caption_item = {
            "id": caption_item_id,
            "type": "captions",
            "assetId": caption_asset_id,
            "durationInFrames": duration_frames,
            "from": 0,
            "top": caption_top,
            "left": vx + round((vw - caption_width) / 2),
            "width": caption_width,
            "height": round(style_props["fontSize"] * 1.2 * style_props["maxLines"]),
            "opacity": 1,
            "isDraggingInTimeline": False,
            "rotation": 0,
            "fontFamily": style_props["fontFamily"],
            "fontStyle": {"variant": "normal", "weight": 400},
            "lineHeight": 1.2,
            "letterSpacing": 0,
            "fontSize": style_props["fontSize"],
            "align": "center",
            "color": style_props["color"],
            "highlightColor": style_props["highlightColor"],
            "strokeWidth": style_props["strokeWidth"],
            "strokeColor": style_props["strokeColor"],
            "strokeMode": stroke_mode,
            "shadowColor": shadow_color,
            "shadowBlur": shadow_blur,
            "shadowOffsetX": shadow_offset_x,
            "shadowOffsetY": shadow_offset_y,
            "direction": "ltr",
            "pageDurationInMilliseconds": style_props["pageDurationInMilliseconds"],
            "captionStartInSeconds": 0,
            "maxLines": style_props["maxLines"],
            "fadeInDurationInSeconds": 0,
            "fadeOutDurationInSeconds": 0,
        }

        # ── Step 5: Inject into state and save ───────────────────────
        existing_assets[caption_asset_id] = caption_asset
        existing_items[caption_item_id] = caption_item

        caption_track = {
            "id": caption_track_id,
            "items": [caption_item_id],
            "hidden": False,
            "muted": False,
        }
        # Frontend renders tracks with `.slice().reverse()` in canvas/layers.tsx,
        # so lower index = rendered on top. Captions must always be ON TOP of
        # the video, so insert at index 0.
        existing_tracks.insert(0, caption_track)

        undoable["tracks"] = existing_tracks
        undoable["items"] = existing_items
        undoable["assets"] = existing_assets

        # Write back
        if "undoableState" in editor_state:
            editor_state["undoableState"] = undoable
        else:
            editor_state = undoable

        # Persist to DB
        if table == "clone_video_jobs":
            try:
                sb = get_supabase()
                sb.table("clone_video_jobs").update(
                    {"editor_state": editor_state}
                ).eq("id", job_id).execute()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to save editor state: {e}")
        else:
            update_job(job_id, {"editor_state": editor_state})

        print(f"[CAPTION] Editor state saved: {len(captions)} words, style={style_name}, placement={placement}")

        # ── ffmpeg burn-in: produce a fast captioned video for Videos tab ──
        burned_url = None
        burn_error = None
        try:
            burned_url, burn_error = _ffmpeg_burn_captions(
                video_url=video_url,
                captions=captions,
                style_props=style_props,
                placement=placement,
                job_id=job_id,
                stroke_mode=stroke_mode,
                shadow_color=shadow_color,
                shadow_blur=shadow_blur,
            )
            if burned_url:
                # Persist as final_video_url so Videos tab shows captioned version
                if table == "clone_video_jobs":
                    try:
                        sb = get_supabase()
                        sb.table("clone_video_jobs").update(
                            {"final_video_url": burned_url}
                        ).eq("id", job_id).execute()
                    except Exception:
                        pass
                else:
                    update_job(job_id, {"final_video_url": burned_url})
                print(f"[CAPTION] ffmpeg burn complete — final_video_url updated")
            else:
                print(f"[CAPTION] ffmpeg burn failed — video URL not updated (editor captions still work): {burn_error}")
        except Exception as burn_err:
            burn_error = str(burn_err)
            print(f"[CAPTION] ffmpeg burn error (non-fatal): {burn_err}")

        return {
            "status": "ok",
            "word_count": len(captions),
            "duration_seconds": round(last_end_ms / 1000, 1),
            "style": style_name,
            "placement": placement,
            "stroke_mode": stroke_mode,
            "burned_video_url": burned_url,
            "burn_error": burn_error,
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[CAPTION] Error: {e}")
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
        if not signed_url:
            raise HTTPException(
                status_code=500,
                detail="Failed to create signed upload URL: no URL returned from storage",
            )
        public_url = sb.storage.from_("editor-assets").get_public_url(file_key)

        return {
            "presignedUrl": signed_url,
            "readUrl": public_url,
            "fileKey": file_key,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ROUTE: POST /api/editor/music
# Generates an instrumental music track for use in the editor.
# Wraps generate_scenes.generate_music (the same Suno-backed helper used by
# the studio pipeline).
# ============================================================================

class MusicRequest(BaseModel):
    prompt: str
    duration: Optional[float] = None


@router.post("/music")
def generate_editor_music(req: MusicRequest, user: dict = Depends(get_current_user)):
    """
    Generates background music from a text prompt. Returns {url, duration}.
    Falls back to 502 if the upstream provider fails.
    """
    try:
        from generate_scenes import generate_music

        prompt = (req.prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="prompt is required")

        result = generate_music(prompt=prompt, instrumental=True)
        if not result:
            raise HTTPException(status_code=502, detail="Music generation failed")

        if isinstance(result, dict):
            url = result.get("url") or result.get("audio_url") or result.get("remoteUrl")
            duration = result.get("duration") or result.get("durationInSeconds")
        else:
            url = str(result)
            duration = None

        if not url:
            raise HTTPException(status_code=502, detail="Music generation returned no URL")

        return {"url": url, "duration": duration}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


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
    Background thread: renders the editor state via the Remotion renderer
    service. Uses the direct Remotion renderer (synchronous) so the
    in-memory progress dict is updated immediately when the render finishes.

    Priority:
      1. REMOTION_RENDERER_URL (Railway-hosted Remotion service) — preferred,
         synchronous, reliable.
      2. MODAL_EDITOR_RENDER_URL — fallback, dispatches to Modal and polls
         for completion via a Supabase marker row.

    The old Modal-only approach relied on HTTP callbacks which were unreliable
    (wrong instance, network issues). The direct renderer avoids this.
    """
    import requests as _req
    import tempfile
    from datetime import datetime as _dt

    def _update(data: dict):
        if render_id not in _editor_renders:
            _editor_renders[render_id] = {}
        _editor_renders[render_id].update(data)

    try:
        _update({"status": "processing", "progress": 5})

        remotion_url = os.environ.get("REMOTION_RENDERER_URL", "")
        modal_url = os.environ.get("MODAL_EDITOR_RENDER_URL", "")

        # ── Decide which renderer to use ──
        renderer_base_url = None

        if remotion_url:
            # Prefer the direct Remotion renderer — it's synchronous
            # and doesn't rely on callbacks.
            try:
                health = _req.get(f"{remotion_url}/health", timeout=5)
                if health.status_code == 200:
                    renderer_base_url = remotion_url
                    print(f"[EDITOR RENDER] Using Remotion renderer: {remotion_url}")
            except Exception as health_err:
                print(f"[EDITOR RENDER] Remotion renderer unreachable ({health_err}), trying Modal...")

        if not renderer_base_url and modal_url:
            # Fallback: dispatch to Modal and wait for callback.
            # Modal's trigger_editor_render uses .spawn() and calls back.
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
            print(f"[EDITOR RENDER] ✓ Dispatched to Modal — callback will update progress")
            # Modal will call POST /api/editor/render/{render_id}/callback
            # when done, which updates _editor_renders.
            return

        if not renderer_base_url:
            raise RuntimeError(
                "No renderer available. Set REMOTION_RENDERER_URL or "
                "MODAL_EDITOR_RENDER_URL in the environment."
            )

        # ── Direct render via Remotion service ──
        print(f"[EDITOR RENDER] Starting render {render_id} via {renderer_base_url}")
        response = _req.post(
            f"{renderer_base_url}/render-editor",
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

        # Auto-persist final_video_url on the job row so the Videos tab
        # shows the captioned version even if the agent's poll loop timed out.
        if job_id and job_id != "standalone" and output_url and not output_url.startswith("file://"):
            try:
                from ugc_db.db_manager import update_job as _update_job
                _update_job(job_id, {"final_video_url": output_url})
                print(f"[EDITOR RENDER] ✓ Persisted final_video_url on job {job_id[:8]}")
            except Exception as persist_err:
                print(f"[EDITOR RENDER] ⚠ final_video_url persist failed (non-fatal): {persist_err}")

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
