"""
Video Tools for Cinematic Transition Shots.

Provides FFmpeg-based stitching with cross-fade transitions (xfade)
to seamlessly blend influencer clips with cinematic product shots.
"""

import subprocess
from pathlib import Path
from assemble_video import get_video_duration, normalize_video


def stitch_with_transition(
    influencer_clip: str,
    cinematic_clip: str,
    transition_type: str,
    output_path: str,
) -> str:
    """
    Stitches an influencer clip and a cinematic clip using an FFmpeg xfade
    transition, producing a single seamless video.

    Args:
        influencer_clip: Path to the influencer scene video.
        cinematic_clip: Path to the cinematic product shot video.
        transition_type: One of 'match_cut', 'whip_pan', 'focus_pull'.
        output_path: Path for the merged output video.

    Returns:
        The output_path of the stitched video.
    """
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    work_dir = output.parent / f"_stitch_{output.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)

    # Normalize both clips to consistent resolution/codec
    norm_inf = work_dir / "norm_influencer.mp4"
    norm_cin = work_dir / "norm_cinematic.mp4"
    normalize_video(influencer_clip, str(norm_inf))
    normalize_video(cinematic_clip, str(norm_cin))

    inf_dur = get_video_duration(str(norm_inf))
    cin_dur = get_video_duration(str(norm_cin))

    if inf_dur <= 0 or cin_dur <= 0:
        raise RuntimeError(
            f"Invalid clip durations: influencer={inf_dur:.1f}s, cinematic={cin_dur:.1f}s"
        )

    # Select xfade parameters based on transition type
    xfade_transition, xfade_duration = _get_xfade_params(transition_type)
    offset = max(0, inf_dur - xfade_duration)

    # Build FFmpeg xfade filter
    filter_complex = (
        f"[0:v][1:v]xfade=transition={xfade_transition}"
        f":duration={xfade_duration}:offset={offset:.3f}[v]"
    )

    # Handle audio: cross-fade audio streams as well
    audio_filter = (
        f"[0:a][1:a]acrossfade=d={xfade_duration}:c1=tri:c2=tri[a]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", str(norm_inf),
        "-i", str(norm_cin),
        "-filter_complex", f"{filter_complex};{audio_filter}",
        "-map", "[v]",
        "-map", "[a]",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-preset", "fast",
        str(output),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        # Retry without audio cross-fade (one or both clips may lack audio)
        print(f"   Audio xfade failed, retrying video-only: {result.stderr[:200]}")
        cmd_fallback = [
            "ffmpeg", "-y",
            "-i", str(norm_inf),
            "-i", str(norm_cin),
            "-filter_complex", f"{filter_complex}",
            "-map", "[v]",
            "-an",
            "-c:v", "libx264",
            "-preset", "fast",
            str(output),
        ]
        result2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
        if result2.returncode != 0:
            raise RuntimeError(f"FFmpeg stitch failed: {result2.stderr[:300]}")

    # Cleanup work dir
    import shutil
    shutil.rmtree(work_dir, ignore_errors=True)

    return str(output)


def _get_xfade_params(transition_type: str) -> tuple:
    """
    Returns (xfade_transition_name, duration_seconds) for the given type.
    """
    params = {
        "match_cut": ("dissolve", 0.5),
        "whip_pan": ("wipeleft", 0.3),
        "focus_pull": ("dissolve", 0.8),
    }
    return params.get(transition_type, ("dissolve", 0.5))
