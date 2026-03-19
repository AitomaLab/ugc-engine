"""
Naiara Content Distribution Engine — Video Assembler

Uses FFmpeg to:
1. Trim each scene clip to its target duration
2. Concatenate all scenes in order
3. Burn in Hormozi-style subtitles (ASS)
4. Overlay background music with fade-out
5. Enforce 9:16 aspect ratio and max duration

Output: final MP4 ready for upload.
"""
import subprocess
import shutil
import uuid
from pathlib import Path
import config
from subtitle_engine import extract_transcription_with_whisper, generate_subtitles_from_whisper


def get_video_duration(video_path):
    """Get the duration of a video file in seconds using FFprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return 0.0


def trim_video(input_path, output_path, duration, mode="start"):
    """
    Trim a video to the specified duration using various modes.
    Modes:
      - start: Take the first X seconds (standard)
      - end: Take the last X seconds (good for showing results)
      - center: Take the middle segment
    """
    actual = get_video_duration(input_path)
    if actual <= duration:
        # No trimming needed
        shutil.copy2(input_path, output_path)
        return str(output_path)

    start_time = 0
    if mode == "end":
        start_time = actual - duration
    elif mode == "center":
        start_time = (actual - duration) / 2

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start_time:.3f}",
        "-i", str(input_path),
        "-t", str(duration),
        "-c:v", "libx264", "-c:a", "aac",
        "-preset", "veryfast",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(output_path)


def normalize_video(input_path, output_path, target_width=1080, target_height=1920):
    """
    Normalize a video to 9:16 aspect ratio with consistent encoding.
    Handles videos that may have different resolutions or codecs.
    """
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", (
            f"scale={target_width}:{target_height}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
        ),
        "-c:v", "libx264",
        "-c:a", "aac",
        "-ar", "44100",
        "-preset", "veryfast",
        "-r", "30",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(output_path)


# ---------------------------------------------------------------------------
# Scene Transition Generator
# ---------------------------------------------------------------------------

TRANSITION_DURATION = 0.5  # seconds — cross-dissolve between Veo scenes


def _has_audio_stream(video_path):
    """Check if a video file has an audio stream using FFprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "a",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return bool(result.stdout.strip())
    except subprocess.CalledProcessError:
        return False


def ensure_audio_stream(video_path, work_dir):
    """Add a silent audio track to a video if it doesn't have one.
    Returns the path to the video with guaranteed audio stream."""
    if _has_audio_stream(video_path):
        return str(video_path)

    output = Path(work_dir) / f"audio_padded_{Path(video_path).stem}.mp4"
    dur = get_video_duration(video_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-f", "lavfi", "-i", f"anullsrc=channel_layout=stereo:sample_rate=44100",
        "-c:v", "copy",
        "-c:a", "aac",
        "-t", f"{dur:.3f}",
        "-shortest",
        str(output),
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        print(f"      [+] Added silent audio track to {Path(video_path).name}")
        return str(output)
    return str(video_path)


def apply_transitions_between_veo_scenes(video_paths, scene_types, work_dir):
    """
    Applies a cross-dissolve transition between consecutive scenes.

    A transition is applied between scene[i] and scene[i+1] when scene[i]
    is AI-generated (type in {'veo', 'physical_product_scene', 'digital_ugc'})
    and scene[i+1] is AI-generated OR a clip (type 'clip').
    This covers both AI↔AI transitions and the digital pipeline's UGC→app_clip
    transition. Cinematic shots are never transitioned.

    Args:
        video_paths:  Ordered list of local file paths to the scene videos.
        scene_types:  Ordered list of scene type strings (one per video).
        work_dir:     Temporary directory for intermediate files.

    Returns:
        New ordered list of file paths with transitions baked in.
        If no transitions are needed, returns the original list unchanged.
    """
    AI_SCENE_TYPES = {"veo", "physical_product_scene", "digital_ugc"}
    # Scenes eligible to RECEIVE a transition from a preceding AI scene
    TRANSITION_ELIGIBLE = AI_SCENE_TYPES | {"clip"}
    td = TRANSITION_DURATION

    # Check if any transitions are needed:
    # Transition applies when an AI scene is followed by another AI scene OR a clip
    needs_transition = any(
        scene_types[i] in AI_SCENE_TYPES and scene_types[i + 1] in TRANSITION_ELIGIBLE
        for i in range(len(scene_types) - 1)
    )

    if not needs_transition:
        return video_paths

    print(f"   [TRANS] Applying cross-dissolve transitions between scenes...")

    result_paths = list(video_paths)

    i = 0
    while i < len(result_paths) - 1:
        if scene_types[i] not in AI_SCENE_TYPES or scene_types[i + 1] not in TRANSITION_ELIGIBLE:
            i += 1
            continue

        clip_a = result_paths[i]
        clip_b = result_paths[i + 1]
        output = work_dir / f"transition_{i}_{i+1}.mp4"

        # Get duration of clip A to calculate xfade offset
        dur_a = get_video_duration(clip_a)
        if dur_a <= td:
            print(f"   !! Clip {i} too short for transition ({dur_a:.1f}s). Skipping.")
            i += 1
            continue

        offset = dur_a - td

        # Probe which clips have audio streams
        has_audio_a = _has_audio_stream(clip_a)
        has_audio_b = _has_audio_stream(clip_b)

        if has_audio_a and has_audio_b:
            # Both have audio — full video + audio crossfade
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip_a),
                "-i", str(clip_b),
                "-filter_complex",
                (
                    f"[0:v][1:v]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv];"
                    f"[0:a][1:a]acrossfade=d={td}[xa]"
                ),
                "-map", "[xv]",
                "-map", "[xa]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k",
                str(output),
            ]
        elif has_audio_a:
            # Only clip_a has audio — visual crossfade + keep clip_a's audio
            print(f"      Clip {i+2} has no audio — preserving audio from clip {i+1}")
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip_a),
                "-i", str(clip_b),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv]",
                "-map", "[xv]",
                "-map", "0:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k",
                str(output),
            ]
        elif has_audio_b:
            # Only clip_b has audio — visual crossfade + keep clip_b's audio
            print(f"      Clip {i+1} has no audio — preserving audio from clip {i+2}")
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip_a),
                "-i", str(clip_b),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv]",
                "-map", "[xv]",
                "-map", "1:a",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-c:a", "aac", "-b:a", "128k",
                str(output),
            ]
        else:
            # Neither has audio — video-only crossfade
            cmd = [
                "ffmpeg", "-y",
                "-i", str(clip_a),
                "-i", str(clip_b),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv]",
                "-map", "[xv]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-an",
                str(output),
            ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            # Last resort fallback: video-only (no audio)
            print(f"      !! Transition audio failed for clips {i+1}-{i+2}, trying video-only")
            cmd_vo = [
                "ffmpeg", "-y",
                "-i", str(clip_a),
                "-i", str(clip_b),
                "-filter_complex",
                f"[0:v][1:v]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv]",
                "-map", "[xv]",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
                "-an",
                str(output),
            ]
            result = subprocess.run(cmd_vo, capture_output=True)
            if result.returncode != 0:
                print(f"      !! Transition FFmpeg failed for clips {i+1}-{i+2}. Using hard cut.")
                i += 1
                continue

        # Replace both clips with the merged transition output
        result_paths[i] = str(output)
        result_paths.pop(i + 1)
        scene_types.pop(i + 1)

        print(f"   [OK] Transition applied between scene {i+1} and scene {i+2}")
        # Don't increment i — check merged clip against next

    return result_paths


def assemble_video(video_paths, output_path, music_path=None, max_duration=None, scene_types=None, brand_names=None):
    """Assembles the final UGC video with word-perfect, transcription-based subtitles.
    
    Args:
        brand_names: Optional list of brand/product names to ensure correct spelling in subtitles.
    """
    if output_path is None:
        output_path = config.OUTPUT_DIR / "final_ugc.mp4"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    assembly_id = uuid.uuid4().hex[:8]
    work_dir = config.TEMP_DIR / f"assembly_{assembly_id}"
    work_dir.mkdir(parents=True, exist_ok=True)

    print("\n[BUILD] Assembling final video...")

    # Step 1: Normalize all clips to same resolution/codec (No Trimming)
    print("   [NORM] Normalizing to 9:16...")
    normalized_paths = []
    scene_metadata = []  # Track which scenes are UGC vs cinematic
    
    for i, scene_data in enumerate(video_paths):
        # Extract path from scene dict or use raw path
        if isinstance(scene_data, dict):
            path = scene_data["path"]
            scene_type = scene_data.get("type", "veo")
        else:
            path = scene_data
            scene_type = "veo"

        # [*] FIX: For physical product scenes, use their actual duration and do not trim
        if scene_type == "physical_product_scene":
            # For physical scenes, we want the full generated output (usually ~7.5s - 8s)
            # Trimming it to a default "hook" duration (like 4s) ruins the video.
            normalized = work_dir / f"normalized_{i}.mp4"
            normalize_video(path, normalized)
            normalized_paths.append(str(normalized))
            scene_metadata.append({"index": i, "type": scene_type, "path": str(normalized)})
            
            actual_dur = get_video_duration(normalized)
            print(f"      Scene {i+1} ({scene_type}): Using full duration {actual_dur:.1f}s (no trim)")
            continue

        # Normal normalization for digital app / cinematic videos
        normalized = work_dir / f"normalized_{i}.mp4"
        normalize_video(path, normalized)
        normalized_paths.append(str(normalized))
        scene_metadata.append({"index": i, "type": scene_type, "path": str(normalized)})
        
        actual_dur = get_video_duration(normalized)
        print(f"      Scene {i+1} ({scene_type}): {actual_dur:.1f}s")

    # Ensure ALL clips have an audio stream BEFORE transitions.
    # Without this, xfade between an audio clip (Veo) and a silent clip (app recording)
    # maps only the first clip's audio, creating a mismatch (8s audio vs 14.5s video)
    # that later gets truncated by the music-mixing step.
    for idx in range(len(normalized_paths)):
        normalized_paths[idx] = ensure_audio_stream(normalized_paths[idx], work_dir)

    # Apply cross-dissolve transitions between consecutive AI-generated scenes
    if scene_types:
        types_list = list(scene_types)
        normalized_paths = apply_transitions_between_veo_scenes(
            normalized_paths, types_list, work_dir,
        )
        # Rebuild scene_metadata to match the potentially reduced list
        scene_metadata = [
            {"index": i, "type": types_list[i] if i < len(types_list) else "clip", "path": p}
            for i, p in enumerate(normalized_paths)
        ]

    # Check if we have a mix of UGC and cinematic scenes
    has_cinematic = any(s["type"] == "cinematic_shot" for s in scene_metadata)
    ugc_types = {"veo", "physical_product_scene", "clip"}
    ugc_scenes = [s for s in scene_metadata if s["type"] in ugc_types]
    cinematic_scenes_meta = [s for s in scene_metadata if s["type"] == "cinematic_shot"]

    if has_cinematic and ugc_scenes:
        # [*] SUBTITLE-SAFE ASSEMBLY: Burn subtitles on UGC portion only
        print("   [CIN] Cinematic mode: subtitles will only appear on UGC scenes")

        # Step 2a: Concatenate only UGC scenes for transcription
        ugc_concat_list = work_dir / "ugc_concat.txt"
        with open(ugc_concat_list, "w") as f:
            for s in ugc_scenes:
                safe_path = str(Path(s["path"]).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        ugc_combined = work_dir / "ugc_combined.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(ugc_concat_list),
            "-c", "copy",
            str(ugc_combined),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        ugc_dur = get_video_duration(ugc_combined)
        print(f"      UGC portion: {ugc_dur:.1f}s")

        # Step 2b: Transcribe and burn subtitles on UGC portion only
        ugc_input = str(ugc_combined)
        transcription = extract_transcription_with_whisper(ugc_input, brand_names=brand_names)
        if transcription:
            subtitle_path = work_dir / "subtitles_synced.ass"
            generate_subtitles_from_whisper(transcription, subtitle_path, brand_names=brand_names)
            
            if Path(subtitle_path).exists() and Path(subtitle_path).stat().st_size > 250:
                print("   [SUB] Burning subtitles on UGC portion only...")
                ugc_subtitled = work_dir / "ugc_subtitled.mp4"
                sub_path_safe = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
                cmd = ["ffmpeg", "-y", "-i", ugc_input, "-vf", f"ass=\\'{sub_path_safe}\\'", "-c:v", "libx264", "-c:a", "copy", "-preset", "veryfast", str(ugc_subtitled)]
                subprocess.run(cmd, capture_output=True, check=True)
                ugc_input = str(ugc_subtitled)

        # Step 2c: Re-normalize the subtitled UGC (codec may have changed)
        ugc_final = work_dir / "ugc_final.mp4"
        normalize_video(ugc_input, ugc_final)

        # Step 2d: Concatenate UGC-with-subtitles + cinematic clips in original order
        print("   [LINK] Concatenating UGC (with subs) + cinematic (no subs)...")
        final_concat_list = work_dir / "final_concat.txt"
        with open(final_concat_list, "w") as f:
            for s in scene_metadata:
                if s["type"] in ugc_types:
                    safe_path = str(Path(ugc_final).resolve()).replace("\\", "/")
                else:
                    # Cinematic — use original normalized (no subtitles)
                    norm_path = work_dir / f"cin_renorm_{s['index']}.mp4"
                    normalize_video(s["path"], norm_path)
                    safe_path = str(Path(norm_path).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        combined = work_dir / "combined.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(final_concat_list),
            "-c", "copy",
            str(combined),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        current_input = str(combined)

        total_dur = get_video_duration(combined)
        print(f"      Combined: {total_dur:.1f}s (UGC subtitled, cinematic clean)")

    else:
        # Standard path: no cinematic scenes — concatenate and subtitle everything
        # (Audio streams already ensured before transitions above)

        print("   [LINK] Concatenating scenes...")
        concat_list = work_dir / "concat.txt"
        with open(concat_list, "w") as f:
            for path in normalized_paths:
                safe_path = str(Path(path).resolve()).replace("\\", "/")
                f.write(f"file '{safe_path}'\n")

        combined = work_dir / "combined.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c", "copy",
            str(combined),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        total_dur = get_video_duration(combined)
        print(f"      Combined: {total_dur:.1f}s")

        # Step 3: Generate and Burn Synchronized Subtitles
        current_input = str(combined)
        transcription = extract_transcription_with_whisper(current_input, brand_names=brand_names)
        if transcription:
            subtitle_path = work_dir / "subtitles_synced.ass"
            generate_subtitles_from_whisper(transcription, subtitle_path, brand_names=brand_names)
            
            if Path(subtitle_path).exists() and Path(subtitle_path).stat().st_size > 250:
                print("   [SUB] Burning in subtitles...")
                subtitled = work_dir / "subtitled.mp4"
                sub_path_safe = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
                cmd = ["ffmpeg", "-y", "-i", current_input, "-vf", f"ass=\\'{sub_path_safe}\\'", "-c:v", "libx264", "-c:a", "copy", "-preset", "veryfast", str(subtitled)]
                subprocess.run(cmd, capture_output=True, check=True)
                current_input = str(subtitled)

    # Step 4: Add background music (if provided)
    if music_path and Path(music_path).exists():
        print("   [MUSIC] Adding background music...")
        final_dur = get_video_duration(current_input)
        fade_start = max(0, final_dur - 2)  # 2-second fade-out

        # Probe if the video has an audio stream
        probe_cmd = [
            "ffprobe", "-v", "quiet",
            "-select_streams", "a",
            "-show_entries", "stream=codec_type",
            "-of", "default=noprint_wrappers=1:nokey=1",
            current_input,
        ]
        try:
            probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
            has_audio = bool(probe_result.stdout.strip())
        except subprocess.CalledProcessError:
            has_audio = False

        with_music = work_dir / "with_music.mp4"

        if has_audio:
            # Video HAS audio → mix video audio + background music
            # Use duration=longest so audio isn't truncated if video audio
            # is shorter than the video stream (e.g. after xfade transitions).
            cmd = [
                "ffmpeg", "-y",
                "-i", current_input,
                "-i", str(music_path),
                "-filter_complex", (
                    f"[1:a]atrim=0:{final_dur},"
                    f"afade=t=out:st={fade_start}:d=2,"
                    f"volume=0.25[bg];"
                    f"[0:a][bg]amix=inputs=2:duration=longest:dropout_transition=2[a]"
                ),
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                str(with_music),
            ]
        else:
            # Video has NO audio → just overlay music as the only audio track
            print("      [i] Video has no audio stream, adding music as sole audio track")
            cmd = [
                "ffmpeg", "-y",
                "-i", current_input,
                "-i", str(music_path),
                "-filter_complex", (
                    f"[1:a]atrim=0:{final_dur},"
                    f"afade=t=out:st={fade_start}:d=2,"
                    f"volume=0.25[a]"
                ),
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "copy",
                "-c:a", "aac",
                str(with_music),
            ]

        subprocess.run(cmd, capture_output=True, check=True)
        current_input = str(with_music)

    # Step 5: Enforce max duration and copy to final output
    print(f"   [FINAL] Finalizing...")
    final_dur = get_video_duration(current_input)

    limit = max_duration or config.VIDEO_MAX_DURATION
    if final_dur > limit:
        cmd = [
            "ffmpeg", "-y",
            "-i", current_input,
            "-t", str(limit),
            "-c", "copy",
            str(output_path),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
    else:
        shutil.copy2(current_input, output_path)

    final_dur = get_video_duration(output_path)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\n[OK] Final video: {output_path}")
    print(f"   Duration: {final_dur:.1f}s | Size: {size_mb:.1f} MB")

    # Clean up this specific job's assembly folder
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
    except Exception:
        pass

    return str(output_path)


def cleanup_temp(project_name=None):
    """Remove temporary files."""
    if project_name:
        temp = config.TEMP_DIR / project_name
        if temp.exists():
            shutil.rmtree(temp, ignore_errors=True)
    print("   [CLEAN] Temp files cleaned up (assembly dirs are self-cleaning)")


if __name__ == "__main__":
    print("This module is imported by pipeline.py")
    print("Functions: assemble_video(), get_video_duration(), cleanup_temp()")
