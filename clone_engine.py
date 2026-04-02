"""
clone_engine.py

Isolated AI Clone video generation engine.

Pipeline:
  1. Fetch clone profile (ElevenLabs Voice ID) from Supabase
  2. Generate TTS audio via ElevenLabs using the user's Voice ID
  3. Split audio into ≤15s chunks (InfiniteTalk hard limit)
  4. For each chunk: upload audio → submit InfiniteTalk → poll → download video
  5. Concatenate all chunk videos into a single seamless video
  6. Optionally burn subtitles via subtitle_engine
  7. Upload final video to Supabase Storage
  8. Return the final public video URL

This module imports ONLY:
  - config (for API keys and model IDs)
  - elevenlabs_client (shared utility — never modified)
  - storage_helper (shared utility — never modified)
  - subtitle_engine (shared utility — never modified)
  - Standard library: os, time, json, shutil, subprocess, requests, pathlib, logging
"""
import os
import io
import sys
import time
import json
import shutil
import subprocess
import logging
import requests
from PIL import Image
from pathlib import Path

import config
import elevenlabs_client
import storage_helper
import subtitle_engine

# ── Logging setup — force flush so background-thread output is always visible ─
logger = logging.getLogger("clone_engine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[CLONE] %(message)s"))
    handler.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

# InfiniteTalk hard limit
MAX_CHUNK_SECONDS = 12.0  # safe limit to avoid 15s timeout edge cases


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_format", audio_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {result.stderr[:200]}")
    info = json.loads(result.stdout)
    return float(info["format"]["duration"])


def _split_audio(audio_path: str, output_dir: Path) -> list[Path]:
    """
    Split an audio file into ≤MAX_CHUNK_SECONDS segments.
    Returns a list of chunk file paths in order.
    """
    duration = _get_audio_duration(audio_path)
    logger.info(f"Audio duration: {duration:.1f}s (limit per chunk: {MAX_CHUNK_SECONDS}s)")

    if duration <= MAX_CHUNK_SECONDS:
        logger.info("Audio fits in a single chunk — no splitting needed")
        return [Path(audio_path)]

    # Use ffmpeg segment muxer for clean splits at silence boundaries
    chunk_pattern = str(output_dir / "chunk_%03d.mp3")
    cmd = [
        "ffmpeg", "-y", "-i", audio_path,
        "-f", "segment",
        "-segment_time", str(MAX_CHUNK_SECONDS),
        "-reset_timestamps", "1",
        "-c", "copy",
        chunk_pattern,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Audio splitting failed: {result.stderr[:300]}")

    chunks = sorted(output_dir.glob("chunk_*.mp3"))
    logger.info(f"Split audio into {len(chunks)} chunks")
    for i, c in enumerate(chunks):
        cdur = _get_audio_duration(str(c))
        logger.info(f"  Chunk {i}: {cdur:.1f}s")
    return chunks


def generate_clone_video(
    job_id: str,
    clone_image_url: str,
    elevenlabs_voice_id: str,
    script_text: str,
    subtitles_enabled: bool = True,
    subtitle_style: str = "hormozi",
    subtitle_placement: str = "middle",
    product_name: str = "",
    product_image_url: str = None,
    avatar_duration: float = None,
    skip_subtitles: bool = False,
    gender: str = "male",
    progress_callback=None,
) -> str:
    """
    Generate an AI Clone video.

    Parameters
    ----------
    job_id : str
        UUID of the clone_video_jobs row. Used for temp directory naming only.
    clone_image_url : str
        Public URL of the portrait photo (Look) to animate.
    elevenlabs_voice_id : str
        The user's ElevenLabs Voice ID for TTS generation.
    script_text : str
        The script the AI clone will speak.
    subtitles_enabled : bool
        Whether to burn subtitles onto the final video.
    subtitle_style : str
        One of: "hormozi", "mrbeast", "plain".
    subtitle_placement : str
        One of: "top", "middle", "bottom".
    product_name : str
        Used as a brand name hint for subtitle_engine. Can be empty string.
    product_image_url : str
        URL of the product image. If provided, triggers Nano Banana Pro composite.
    avatar_duration : float
        If set, caps TTS audio to this length (for B-roll stitching).
    skip_subtitles : bool
        If True, skip subtitle burning (caller handles subtitles after B-roll assembly).

    Returns
    -------
    str
        Public URL of the final video in Supabase Storage.
    """
    output_dir = Path(f"/tmp/clone_{job_id}")
    output_dir.mkdir(parents=True, exist_ok=True)

    def _progress(pct: int, msg: str):
        if progress_callback:
            progress_callback(pct, msg)

    try:
        # ── Step 1 & 2: Generate TTS audio logically per script part ───────────
        logger.info("Steps 1-2 — Generating ElevenLabs audio logically per chunk...")
        _progress(25, "Generating speech audio...")
        
        # Split script explicitly on ||| to prevent blind audio-truncation issues later
        raw_parts = [p.strip() for p in script_text.split("|||") if p.strip()]
        if not raw_parts:
            # Fallback if empty script
            raw_parts = ["I love this product."]
            
        audio_chunks = []
        cumulative_duration = 0.0
        for i, part_text in enumerate(raw_parts):
            safe_text = part_text.replace("  ", " ").strip()
            if not safe_text:
                continue
                
            chunk_filename = f"clone_{job_id}_chunk_{i}.mp3"
            returned_path = elevenlabs_client.generate_voiceover(
                text=safe_text,
                voice_id=elevenlabs_voice_id,
                filename=chunk_filename,
            )
            chunk_path = output_dir / f"voiceover_chunk_{i}.mp3"
            shutil.copy2(returned_path, str(chunk_path))
            
            dur = _get_audio_duration(str(chunk_path))
            logger.info(f"Chunk {i} audio: {chunk_path.stat().st_size / 1024:.1f} KB, {dur:.1f}s")
            
            # Sub-split only if a singular semantic part somehow exceeds WaveSpeed limits
            if dur > MAX_CHUNK_SECONDS:
                logger.warning(f"Chunk {i} exceeded {MAX_CHUNK_SECONDS}s. Force-splitting audio.")
                sub_dir = output_dir / f"subchunk_{i}"
                sub_dir.mkdir(exist_ok=True)
                sub_chunks = _split_audio(str(chunk_path), sub_dir)
                audio_chunks.extend(sub_chunks)
                cumulative_duration += dur
            else:
                audio_chunks.append(chunk_path)
                cumulative_duration += dur
            
            # If avatar_duration is set (B-roll/app clip follows), stop generating
            # audio beyond the allotted avatar speaking time
            if avatar_duration and cumulative_duration >= avatar_duration:
                remaining = len(raw_parts) - (i + 1)
                if remaining > 0:
                    logger.info(
                        f"Avatar duration cap reached ({cumulative_duration:.1f}s >= {avatar_duration:.1f}s). "
                        f"Skipping remaining {remaining} script part(s) — B-roll will fill the rest."
                    )
                break
                
        total_chunks = len(audio_chunks)
        logger.info(f"Total audio chunks for InfiniteTalk: {total_chunks} ({cumulative_duration:.1f}s total)")

        # ── Step 2.5: Mirror Clone Image & Wait for CDN ───────────────────────
        logger.info("Step 2.5 — Mirroring & Resizing clone image for API accessibility...")
        _progress(30, "Preparing clone image...")
        mirrored_image_url = clone_image_url
        try:
            download_url = clone_image_url
            if "cloudflarestorage.com" in clone_image_url or "r2.dev" in clone_image_url:
                clean_url = clone_image_url.replace("https://", "")
                download_url = f"https://images.weserv.nl/?url={clean_url}"

            img_resp = requests.get(download_url, timeout=10)
            if img_resp.status_code == 200:
                try:
                    img_content = img_resp.content
                    with Image.open(io.BytesIO(img_content)) as pil_img:
                        pil_img = pil_img.convert("RGB")
                        
                        # Enforce max 1080px resolution and even dimensions (fix for InfiniteTalk 524 timeouts)
                        MAX_DIM = 1080
                        w, h = pil_img.size
                        if max(w, h) > MAX_DIM:
                            scale = MAX_DIM / float(max(w, h))
                            w, h = int(w * scale), int(h * scale)
                        # Ensure even dimensions (required by some FFmpeg/AI workflows)
                        w = w - (w % 2)
                        h = h - (h % 2)
                        if (w, h) != pil_img.size:
                            logger.info(f"Resizing image to {w}x{h}")
                            pil_img = pil_img.resize((w, h), Image.Resampling.LANCZOS)
                            
                        temp_img_path = output_dir / f"mirror_{int(time.time())}.jpg"
                        pil_img.save(temp_img_path, format="JPEG", quality=95)
                except Exception as e:
                    logger.warning(f"Image conversion failed: {e}, falling back to raw write")
                    temp_img_path = output_dir / f"mirror_{int(time.time())}.jpg"
                    with open(temp_img_path, "wb") as f:
                        f.write(img_resp.content)

                mirrored_image_url = storage_helper.upload_temporary_file(temp_img_path)
                logger.info(f"Asset mirrored successfully: {mirrored_image_url}")

                try:
                    os.remove(temp_img_path)
                except:
                    pass
            else:
                logger.warning(f"Mirror download failed ({img_resp.status_code}), reverting to raw URL")
        except Exception as e:
            logger.warning(f"Mirroring failed: {e}, reverting to raw URL")

        # ── Step 2.6: Composite product into clone image (if product provided) ─
        composite_image_url = mirrored_image_url  # default: use plain clone photo
        if product_image_url:
            logger.info("Step 2.6 — Compositing product into clone image via Nano Banana Pro...")
            try:
                composite_image_url = _generate_product_composite(
                    product_image_url=product_image_url,
                    influencer_image_url=mirrored_image_url,
                    output_dir=output_dir,
                    product_name=product_name,
                    gender=gender,
                )
                logger.info(f"Composite image generated: {composite_image_url}")
            except Exception as comp_err:
                logger.warning(f"Product composite failed ({comp_err}). Falling back to plain clone image.")
                composite_image_url = mirrored_image_url

        # ── Step 3: Generate a lipsync video for each chunk ───────────────────
        _progress(35, "Starting lip sync generation...")
        chunk_videos: list[Path] = []

        animation_prompt = (
            "A person speaking very calmly, professionally, and softly to the camera. "
            "Absolutely NO exaggerated expressions, NO wide mouth movements, "
            "restrained neutral face, extremely subtle micro-expressions. "
            "Natural eyes, occasional gentle blink, minimal head movement."
        )

        # WaveSpeed API config (used for AI Clone videos only)
        WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY", "")
        WAVESPEED_API_URL = "https://api.wavespeed.ai/api/v3/wavespeed-ai/infinitetalk"
        WAVESPEED_HEADERS = {
            "Authorization": f"Bearer {WAVESPEED_API_KEY}",
            "Content-Type": "application/json",
        }

        if not WAVESPEED_API_KEY:
            raise RuntimeError("WAVESPEED_API_KEY not set in environment")

        for ci, chunk_audio in enumerate(audio_chunks):
            logger.info(f"Step 3.{ci+1}/{total_chunks} — Processing audio chunk {ci+1}...")
            # Distribute progress 35-85% across chunks
            chunk_base = 35 + int(50 * ci / max(total_chunks, 1))
            _progress(chunk_base, f"Lip sync: scene {ci+1}/{total_chunks}...")

            # 3a. Upload chunk audio to temporary public URL
            chunk_public_url = storage_helper.upload_temporary_file(str(chunk_audio))
            
            # Use ffprobe to log duration
            try:
                probe = subprocess.check_output(f"ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {chunk_audio}", shell=True)
                dur = float(probe.decode().strip())
            except:
                dur = 0.0
            logger.info(f"  Chunk {ci+1} audio URL: {chunk_public_url} (Duration: {dur:.1f}s)")

            if dur == 0.0:
                logger.warning(f"  Chunk {ci+1} has 0.0 duration! Passing this to API could fail.")

            # 3a-bis. Determine the input image for this chunk
            # Chunk 0: use the original composite image (from Nano Banana Pro)
            # Chunk 1+: extract the LAST FRAME from the previous chunk's video
            #           so facial expressions flow naturally (like Veo Extend)
            if ci == 0:
                chunk_image_url = composite_image_url
                logger.info("  Waiting 10s for asset CDN propagation...")
                time.sleep(10)
            else:
                prev_video = chunk_videos[-1]  # last downloaded chunk video
                last_frame_path = output_dir / f"last_frame_chunk_{ci-1}.jpg"
                try:
                    # Extract the very last frame from the previous chunk video
                    cmd_frame = [
                        "ffmpeg", "-y",
                        "-sseof", "-0.1",       # seek to 0.1s before end
                        "-i", str(prev_video),
                        "-frames:v", "1",         # grab exactly 1 frame
                        "-q:v", "2",              # high-quality JPEG
                        str(last_frame_path),
                    ]
                    subprocess.run(cmd_frame, capture_output=True, check=True)
                    
                    if last_frame_path.exists() and last_frame_path.stat().st_size > 0:
                        # Upload the last frame as a temporary public URL
                        chunk_image_url = storage_helper.upload_temporary_file(str(last_frame_path))
                        logger.info(f"  Using last frame from chunk {ci} for visual continuity: {chunk_image_url[:60]}...")
                    else:
                        logger.warning(f"  Last frame extraction produced empty file. Falling back to original composite.")
                        chunk_image_url = composite_image_url
                except Exception as frame_err:
                    logger.warning(f"  Last frame extraction failed ({frame_err}). Falling back to original composite.")
                    chunk_image_url = composite_image_url

            # 3b. Submit InfiniteTalk job via WaveSpeed API
            lipsync_payload = {
                "image": chunk_image_url,
                "audio": chunk_public_url,
                "prompt": animation_prompt,
                "resolution": config.LIPSYNC_QUALITY,  # "480p" or "720p"
                "audio_scale": 0.8,  # Reduce expression/mouth intensity
            }

            logger.info(f"  Submitting to WaveSpeed InfiniteTalk...")
            resp = requests.post(
                WAVESPEED_API_URL,
                headers=WAVESPEED_HEADERS,
                json=lipsync_payload,
                timeout=60,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"WaveSpeed submit error ({resp.status_code}): {resp.text[:300]}"
                )

            api_result = resp.json()
            # WaveSpeed wraps response in {code, message, data: {...}}
            result_data = api_result.get("data", api_result)
            prediction_id = result_data.get("id")
            if not prediction_id:
                raise RuntimeError(
                    f"WaveSpeed API error — no prediction ID returned: {str(api_result)[:300]}"
                )

            # Extract the status polling URL from response
            status_url = result_data.get("urls", {}).get("get", "")
            if not status_url:
                # Fallback to standard WaveSpeed polling pattern
                status_url = f"https://api.wavespeed.ai/api/v3/predictions/{prediction_id}/result"

            logger.info(f"  Chunk {ci+1} — WaveSpeed task: {prediction_id}")
            logger.info(f"  Status URL: {status_url}")

            # 3c. Poll until complete
            animated_video_url = None
            for i in range(120):
                wait_secs = 10 if i < 30 else 20
                time.sleep(wait_secs)

                try:
                    poll_resp = requests.get(
                        status_url,
                        headers=WAVESPEED_HEADERS,
                        timeout=30,
                    )
                    poll_data = poll_resp.json()
                except Exception as poll_err:
                    elapsed = sum(10 if j < 30 else 20 for j in range(i + 1))
                    logger.warning(f"  Poll warning at ~{elapsed}s: {poll_err}")
                    continue

                # WaveSpeed wraps response in {code, data: {...}}
                poll_inner = poll_data.get("data", poll_data)
                status = poll_inner.get("status", "processing").lower()

                if status == "completed":
                    outputs = poll_inner.get("outputs", [])
                    if outputs:
                        animated_video_url = outputs[0]
                        elapsed = sum(10 if j < 30 else 20 for j in range(i + 1))
                        logger.info(f"  Chunk {ci+1} complete after ~{elapsed}s — URL: {animated_video_url[:80]}...")
                        break
                    logger.info(f"  Chunk {ci+1} completed state but no outputs — retrying...")
                elif status == "failed":
                    error_msg = poll_inner.get("error", "Unknown error")
                    raise RuntimeError(
                        f"WaveSpeed InfiniteTalk failed (chunk {ci+1}): {error_msg}"
                    )
                else:
                    if i % 6 == 0:  # Log every ~60s
                        elapsed = sum(10 if j < 30 else 20 for j in range(i + 1))
                        logger.info(f"  Chunk {ci+1} still generating... (~{elapsed}s, status={status})")

            if not animated_video_url:
                raise RuntimeError(f"WaveSpeed InfiniteTalk timed out on chunk {ci+1} after 20 minutes")

            # 3d. Download chunk video
            chunk_video_path = output_dir / f"chunk_video_{ci:03d}.mp4"
            _download_file(animated_video_url, chunk_video_path)
            chunk_videos.append(chunk_video_path)
            logger.info(f"  Chunk {ci+1} video saved: {chunk_video_path.stat().st_size / (1024*1024):.1f} MB")

        # ── Step 4: Concatenate chunk videos ──────────────────────────────────
        _progress(85, "Assembling final video...")
        if len(chunk_videos) == 1:
            raw_video_path = chunk_videos[0]
            logger.info("Step 4 — Single chunk, no concatenation needed")
        else:
            logger.info(f"Step 4 — Concatenating {len(chunk_videos)} chunk videos...")
            raw_video_path = output_dir / "raw_clone.mp4"

            # Re-encode each chunk for consistent format before concat
            encoded_chunks: list[Path] = []
            for ci, cv in enumerate(chunk_videos):
                encoded_path = output_dir / f"chunk_encoded_{ci:03d}.mp4"
                cmd = [
                    "ffmpeg", "-y", "-i", str(cv),
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k",
                    "-g", "30", "-keyint_min", "1",
                    "-movflags", "+faststart",
                    str(encoded_path),
                ]
                subprocess.run(cmd, capture_output=True, check=True)
                encoded_chunks.append(encoded_path)

            # Concat via file list
            concat_list = output_dir / "concat.txt"
            with open(concat_list, "w") as f:
                for ec in encoded_chunks:
                    f.write(f"file '{ec.as_posix()}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(raw_video_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            logger.info(f"Concatenated video: {raw_video_path} ({raw_video_path.stat().st_size / (1024*1024):.1f} MB)")

        # ── Step 5: Subtitles now handled globally in main.py ───────────────────
        final_video_path = output_dir / "final_clone.mp4"
        logger.info("Step 5 — Subtitles skipped (main.py will handle Remotion subtitles and Music externally)")
        shutil.copy(str(raw_video_path), str(final_video_path))

        # ── Step 6: Upload to Supabase Storage ────────────────────────────────
        logger.info("Step 6 — Uploading final video to Supabase Storage...")
        _progress(90, "Uploading video...")
        destination = f"clone-videos/{job_id}/final.mp4"
        final_url = storage_helper.upload_to_supabase_storage(
            file_path=str(final_video_path),
            bucket="generated-videos",
            destination_path=destination,
        )
        logger.info(f"✓ Final video URL: {final_url}")
        return final_url

    finally:
        # Always clean up temp files, even on failure
        try:
            shutil.rmtree(output_dir, ignore_errors=True)
            logger.info(f"Temp directory cleaned up: {output_dir}")
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
# Private helpers — local to this module only
# ─────────────────────────────────────────────────────────────────────────────

def _extract_video_url(data: dict) -> str | None:
    """Extract video URL from a Kie.ai poll response data dict."""
    response_obj = data.get("response", {})
    if isinstance(response_obj, str):
        try:
            response_obj = json.loads(response_obj)
        except Exception:
            response_obj = {}
    if response_obj.get("resultUrls"):
        return response_obj["resultUrls"][0]
    if response_obj.get("videoUrl"):
        return response_obj["videoUrl"]

    result_json = data.get("resultJson", "{}")
    if isinstance(result_json, str):
        try:
            result_json = json.loads(result_json)
        except Exception:
            result_json = {}
    if result_json.get("resultUrls"):
        return result_json["resultUrls"][0]
    return result_json.get("videoUrl")


def _download_file(url: str, output_path: Path, max_retries: int = 5):
    """Download a file from URL to a local path with exponential-backoff retries."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, stream=True, timeout=120)
            resp.raise_for_status()
            with open(output_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            return
        except Exception as e:
            if attempt < max_retries - 1:
                wait = (2 ** attempt) * 5
                logger.warning(f"Download attempt {attempt + 1} failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise RuntimeError(
                    f"Download failed after {max_retries} attempts: {e}"
                )


def _generate_product_composite(
    product_image_url: str,
    influencer_image_url: str,
    output_dir: Path,
    product_name: str = "the product",
    gender: str = "male",
) -> str:
    """
    Generate a composite image of the clone holding the product.

    Uses the same structured prompt format as the AI Influencer pipeline
    (physical_prompts.py / digital_prompts.py) for consistent results.

    Makes DIRECT API calls to Kie.ai (not through the shared NanoBananaClient,
    which hardcodes 'woman' in the prompt).

    Tries Kie.ai Nano Banana Pro first, then falls back to WaveSpeed.

    Returns:
        str: Public URL of the composite image on Supabase.
    """
    person_word = "man" if gender == "male" else "woman"

    # Build the structured prompt — matching the physical product format from
    # physical_prompts.py build_physical_product_scenes() (lines 344-360)
    composite_prompt = (
        f"action: character holding {product_name} up close to the camera with an excited expression, "
        f"casually presenting the product\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"one hand explicitly holds the product, other arm rests naturally TO THE PERSON'S SIDE\n"
        f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
        f"natural skin texture with visible pores and subtle grain, fine lines, skin imperfections, "
        f"unretouched complexion, not airbrushed\n"
        f"product: the product from the product image is clearly visible in the person's hand, "
        f"preserve all visible text and logos exactly as in product image\n"
        f"setting: natural environment matching the background visible in the reference image, natural lighting\n"
        f"camera: amateur iPhone selfie, slightly uneven framing\n"
        f"style: candid UGC look, no filters, realism, high detail, skin texture, visible pores, "
        f"micro skin texture, raw unedited photo quality\n"
        f"negative: no smooth skin, no poreless skin, no beauty filter, no skin retouching, "
        f"no third arm, no third hand, no extra limbs, no extra fingers, "
        f"no airbrushed skin, no studio backdrop, no geometric distortion, "
        f"no mutated hands, no floating limbs, no disconnected limbs, "
        f"no arm crossing screen, no unnatural arm position, no multiple people, no different person"
    )

    # Enhanced final prompt with correct gender (NOT using NanoBananaClient which hardcodes 'woman')
    final_prompt = (
        f"photorealistic, professional UGC, 8k, sharp focus, {composite_prompt}, "
        f"featuring the specific {person_word} from the reference image, (face consistency:1.5)"
    )

    negative_prompt = (
        "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, "
        "wrong anatomy, mutation, mutated, ugly, disgusting, blurry, amputation, "
        "multiple people, different person"
    )

    # ── Method 1: Direct Kie.ai Nano Banana Pro API call ───────────────────
    # We call Kie.ai directly (not through NanoBananaClient) because the shared
    # client hardcodes "featuring the specific woman" which causes gender mismatch.
    try:
        logger.info(f"  Trying Kie.ai Nano Banana Pro (direct call, gender={gender})...")
        import config as _cfg

        kie_payload = {
            "model": "nano-banana-pro",
            "input": {
                "prompt": final_prompt,
                "negative_prompt": negative_prompt,
                "image_input": [
                    influencer_image_url,   # reference image (clone avatar) first
                    product_image_url,      # product image second
                ],
                "aspect_ratio": "9:16",
                "resolution": "2K",
            },
        }

        kie_headers = {
            "Authorization": f"Bearer {_cfg.KIE_API_KEY}",
            "Content-Type": "application/json",
        }

        resp = requests.post(
            f"{_cfg.KIE_API_URL}/api/v1/jobs/createTask",
            headers=kie_headers,
            json=kie_payload,
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") != 200:
            raise RuntimeError(f"Kie.ai API error: {data.get('msg', str(data))}")

        task_id = data["data"]["taskId"]
        logger.info(f"  Kie.ai task: {task_id}")

        # Poll for result
        for i in range(120):
            time.sleep(5)
            try:
                poll_resp = requests.get(
                    f"{_cfg.KIE_API_URL}/api/v1/jobs/recordInfo",
                    headers=kie_headers,
                    params={"taskId": task_id},
                    timeout=30,
                )
                poll_data = poll_resp.json()
                if poll_data.get("code") != 200:
                    continue
                state = poll_data["data"].get("state", "processing")
                if state == "success":
                    result_json = poll_data["data"].get("resultJson")
                    if isinstance(result_json, str):
                        result_data = json.loads(result_json)
                    else:
                        result_data = result_json or {}
                    image_urls = result_data.get("resultUrls") or result_data.get("images")
                    if image_urls and len(image_urls) > 0:
                        kie_image_url = image_urls[0]
                        composite_url = _rehost_image_on_supabase(kie_image_url, output_dir)
                        logger.info(f"  Kie.ai composite success: {composite_url}")
                        return composite_url
                elif state == "fail":
                    raise RuntimeError(f"Kie.ai failed: {poll_data['data'].get('failMsg', 'Unknown')}")
                if i % 6 == 0:
                    logger.info(f"  Kie.ai generating composite... ({i*5}s)")
            except RuntimeError:
                raise
            except Exception as poll_err:
                logger.warning(f"  Kie.ai poll error: {poll_err}")
        raise RuntimeError("Kie.ai Nano Banana Pro timed out (10 min)")
    except Exception as kie_err:
        logger.warning(f"  Kie.ai composite failed: {kie_err}")

    # ── Method 2: WaveSpeed Nano Banana Pro Edit (fallback) ────────────────
    logger.info("  Falling back to WaveSpeed Nano Banana Pro Edit...")
    WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY", "")
    if not WAVESPEED_API_KEY:
        raise RuntimeError("Both Kie.ai and WaveSpeed failed — no API key for fallback")

    ws_headers = {
        "Authorization": f"Bearer {WAVESPEED_API_KEY}",
        "Content-Type": "application/json",
    }

    # WaveSpeed edit endpoint takes the clone image + a text prompt to add the product
    ws_payload = {
        "prompt": (
            f"Edit this image: make the person hold a product in their hand. "
            f"The product looks like the item at this URL. "
            f"{composite_prompt}"
        ),
        "image": influencer_image_url,
        "seed": int(time.time()) % 999999,
    }

    resp = requests.post(
        "https://api.wavespeed.ai/api/v3/google/nano-banana-pro/edit",
        headers=ws_headers,
        json=ws_payload,
        timeout=60,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"WaveSpeed edit submit failed ({resp.status_code}): {resp.text[:200]}")

    api_result = resp.json()
    result_data = api_result.get("data", api_result)
    prediction_id = result_data.get("id")
    if not prediction_id:
        raise RuntimeError(f"WaveSpeed edit — no prediction ID: {str(api_result)[:200]}")

    status_url = result_data.get("urls", {}).get("get", "")
    if not status_url:
        status_url = f"https://api.wavespeed.ai/api/v3/predictions/{prediction_id}/result"

    logger.info(f"  WaveSpeed edit task: {prediction_id}")

    # Poll for result (images are fast, typically <30s)
    for i in range(60):
        time.sleep(5)
        try:
            poll_resp = requests.get(status_url, headers=ws_headers, timeout=30)
            poll_data = poll_resp.json()
            poll_inner = poll_data.get("data", poll_data)
            status = poll_inner.get("status", "processing").lower()

            if status == "completed":
                outputs = poll_inner.get("outputs", [])
                if outputs:
                    ws_image_url = outputs[0]
                    composite_url = _rehost_image_on_supabase(ws_image_url, output_dir)
                    logger.info(f"  WaveSpeed composite success: {composite_url}")
                    return composite_url
            elif status == "failed":
                raise RuntimeError(f"WaveSpeed edit failed: {poll_inner.get('error', 'unknown')}")
        except RuntimeError:
            raise
        except Exception as poll_err:
            logger.warning(f"  WaveSpeed edit poll error: {poll_err}")

    raise RuntimeError("WaveSpeed Nano Banana Pro Edit timed out (5 min)")


def _rehost_image_on_supabase(image_url: str, output_dir: Path) -> str:
    """
    Download an image from any URL and re-upload to Supabase temporary storage.
    Ensures the image is accessible to downstream APIs (InfiniteTalk etc.).
    """
    resp = requests.get(image_url, timeout=60)
    resp.raise_for_status()
    temp_path = output_dir / f"composite_{int(time.time())}.jpg"

    # Convert to JPEG with proper dimensions
    with Image.open(io.BytesIO(resp.content)) as img:
        img = img.convert("RGB")
        # Enforce even dimensions
        w, h = img.size
        w = w - (w % 2)
        h = h - (h % 2)
        if (w, h) != img.size:
            img = img.resize((w, h), Image.Resampling.LANCZOS)
        img.save(temp_path, format="JPEG", quality=95)

    public_url = storage_helper.upload_temporary_file(str(temp_path))
    try:
        os.remove(temp_path)
    except:
        pass
    return public_url
