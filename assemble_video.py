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
from pathlib import Path
import config


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
        "-preset", "fast",
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
        "-preset", "fast",
        "-r", "30",
        str(output_path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return str(output_path)


def assemble_video(video_paths, subtitle_path=None, music_path=None,
                   output_path=None, scene_durations=None, max_duration=None):
    """
    Assemble the final UGC video.

    Args:
        video_paths: List of video file paths in scene order
        subtitle_path: Path to ASS subtitle file (optional)
        music_path: Path to background music file (optional)
        output_path: Where to save the final video
        scene_durations: List of target durations per scene (optional)

    Returns:
        Path to the final assembled video
    """
    if output_path is None:
        output_path = config.OUTPUT_DIR / "final_ugc.mp4"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    work_dir = config.TEMP_DIR / "assembly"
    work_dir.mkdir(parents=True, exist_ok=True)

    print("\n🔧 Assembling final video...")

    # Step 1: Trim each scene to target duration
    print("   ✂️  Trimming scenes...")
    trimmed_paths = []
    durations = scene_durations or [config.SCENE_DURATIONS.get(n, 4)
                                    for n in ["hook", "app_demo", "reaction", "cta"]]

    for i, (scene, dur) in enumerate(zip(video_paths, durations)):
        # scenes is a list of dicts, but video_paths is just paths. 
        # Wait, the interface here is a bit mixed. Let's fix it.
        # Check if we have the full scene objects or just paths
        mode = "start"
        if isinstance(scene, dict):
            path = scene["path"]
            mode = scene.get("trim_mode", "start")
        else:
            path = scene

        trimmed = work_dir / f"trimmed_{i}.mp4"
        trim_video(path, trimmed, dur, mode=mode)
        trimmed_paths.append(str(trimmed))
        actual_dur = get_video_duration(trimmed)
        print(f"      Scene {i+1}: {actual_dur:.1f}s (target {dur}s, mode {mode})")

    # Step 2: Normalize all clips to same resolution/codec
    print("   📐 Normalizing to 9:16...")
    normalized_paths = []
    for i, path in enumerate(trimmed_paths):
        normalized = work_dir / f"normalized_{i}.mp4"
        normalize_video(path, normalized)
        normalized_paths.append(str(normalized))

    # Step 3: Concatenate
    print("   🔗 Concatenating scenes...")
    concat_list = work_dir / "concat.txt"
    with open(concat_list, "w") as f:
        for path in normalized_paths:
            # Use forward slashes for FFmpeg compatibility
            safe_path = str(Path(path).resolve()).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    combined = work_dir / "combined.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(combined),
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    total_dur = get_video_duration(combined)
    print(f"      Combined: {total_dur:.1f}s")

    # Step 4: Burn subtitles (if provided)
    current_input = str(combined)
    if subtitle_path and Path(subtitle_path).exists():
        print("   🔤 Burning in subtitles...")
        subtitled = work_dir / "subtitled.mp4"
        sub_path_safe = str(Path(subtitle_path).resolve()).replace("\\", "/").replace(":", "\\:")
        cmd = [
            "ffmpeg", "-y",
            "-i", current_input,
            "-vf", f"ass='{sub_path_safe}'",
            "-c:v", "libx264",
            "-c:a", "copy",
            "-preset", "fast",
            str(subtitled),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        current_input = str(subtitled)

    # Step 5: Add background music (if provided)
    if music_path and Path(music_path).exists():
        print("   🎵 Adding background music...")
        final_dur = get_video_duration(current_input)
        fade_start = max(0, final_dur - 2)  # 2-second fade-out

        with_music = work_dir / "with_music.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-i", current_input,
            "-i", str(music_path),
            "-filter_complex", (
                f"[1:a]atrim=0:{final_dur},"
                f"afade=t=out:st={fade_start}:d=2,"
                f"volume=0.15[bg];"
                f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=2[a]"
            ),
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(with_music),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        current_input = str(with_music)

    # Step 6: Enforce max duration and copy to final output
    print(f"   📦 Finalizing...")
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
    print(f"\n✅ Final video: {output_path}")
    print(f"   Duration: {final_dur:.1f}s | Size: {size_mb:.1f} MB")

    return str(output_path)


def cleanup_temp(project_name=None):
    """Remove temporary files."""
    if project_name:
        temp = config.TEMP_DIR / project_name
        if temp.exists():
            shutil.rmtree(temp)
    assembly = config.TEMP_DIR / "assembly"
    if assembly.exists():
        shutil.rmtree(assembly)
    print("   🧹 Temp files cleaned up")


if __name__ == "__main__":
    print("This module is imported by pipeline.py")
    print("Functions: assemble_video(), get_video_duration(), cleanup_temp()")
