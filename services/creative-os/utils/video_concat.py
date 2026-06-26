"""Shared ffmpeg helpers for video concatenation + aspect probing.

Extracted from ugc_backend/main.py so the creative-os video pipeline can reuse
the same "B-roll conforms to primary clip dimensions via scale+pad" logic the
clone thread already uses.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple


def _probe_duration(path: Path) -> float:
    """Return clip duration in seconds via ffprobe. Falls back to 5.0 on failure."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 5.0


def _has_audio_stream(path: Path) -> bool:
    """Check whether the file has an audio stream (xfade+acrossfade needs one)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_type",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        return "audio" in (result.stdout or "").lower()
    except Exception:
        return False


def probe_video_dimensions(path_or_url: str) -> Tuple[int, int]:
    """Return (width, height) for a local path OR remote URL via ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet", "-print_format", "json",
        "-show_streams", str(path_or_url),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout or "{}")
    vid = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
    return int(vid.get("width", 0)), int(vid.get("height", 0))


def classify_orientation(width: int, height: int) -> str:
    """'phone' if ratio <= 1.0 (portrait/square), else 'laptop'."""
    if width <= 0 or height <= 0:
        return "phone"
    return "phone" if (width / height) <= 1.0 else "laptop"


def probe_orientation(url: str) -> str:
    """Convenience: probe URL → classify. Falls back to 'phone' on failure."""
    try:
        w, h = probe_video_dimensions(url)
        return classify_orientation(w, h)
    except Exception:
        return "phone"


def _download(url: str, dest: Path) -> Path:
    from utils.persist_media import download_url_to_file

    return download_url_to_file(url, dest)


def probe_duration(path_or_url: str) -> float:
    """Public duration probe for a local path OR remote URL. 0.0 on failure
    (callers should treat 0.0 as 'unknown' rather than a real 5s default)."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path_or_url),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def trim_segment(
    src_path_or_url: str,
    start: float,
    end: float,
    out_path: Optional[Path] = None,
) -> Path:
    """Cut [start, end] seconds out of a source clip, re-encoding for an
    accurate, keyframe-independent cut. Accepts a local path or remote URL.
    Returns the local output path. Used to carve the pre/post segments that
    bracket a Gemini Omni edit window so the untouched footage is preserved.
    """
    work = Path(tempfile.mkdtemp(prefix="trim_"))
    src = Path(str(src_path_or_url))
    if src.exists():
        local = src
    else:
        local = _download(src_path_or_url, work / "src.mp4")

    out = out_path or (work / f"seg_{uuid.uuid4().hex}.mp4")
    has_audio = _has_audio_stream(local)
    cmd = ["ffmpeg", "-y", "-ss", f"{max(0.0, float(start)):.3f}", "-to", f"{float(end):.3f}", "-i", str(local)]
    if not has_audio:
        cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest"]
    cmd += [
        "-r", "30", "-pix_fmt", "yuv420p",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-movflags", "+faststart",
        str(out),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return out


def concat_segments(
    segment_paths_or_urls: list[str],
    out_path: Optional[Path] = None,
) -> Path:
    """Hard-cut concatenate N segments (in order) into one MP4.

    Unlike concat_videos_matched (which dissolves a seam between two
    semantically distinct clips), this joins segments that were originally
    contiguous — pre | edited-window | post — so a clean butt-join with no
    transition is correct. All segments are first normalized to the FIRST
    segment's dimensions / fps / codec so the concat demuxer accepts them.
    Returns the local output path.
    """
    if not segment_paths_or_urls:
        raise ValueError("concat_segments requires at least one segment")

    work = Path(tempfile.mkdtemp(prefix="stitch_"))

    # Materialize all segments locally.
    locals_: list[Path] = []
    for i, seg in enumerate(segment_paths_or_urls):
        p = Path(str(seg))
        if p.exists():
            locals_.append(p)
        else:
            locals_.append(_download(seg, work / f"in_{i}.mp4"))

    if len(locals_) == 1:
        return locals_[0]

    # Target dims/fps come from the first segment (the original clip's head).
    tw, th = probe_video_dimensions(locals_[0])
    if tw <= 0 or th <= 0:
        tw, th = 720, 1280

    norm_paths: list[Path] = []
    for i, src in enumerate(locals_):
        dest = work / f"norm_{i}.mp4"
        has_audio = _has_audio_stream(src)
        cmd = ["ffmpeg", "-y", "-i", str(src)]
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest"]
        cmd += [
            "-vf", f"scale={tw}:{th}:force_original_aspect_ratio=decrease,"
                   f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(dest),
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        norm_paths.append(dest)

    out = out_path or (work / f"stitch_{uuid.uuid4().hex}.mp4")
    concat_list = work / "concat.txt"
    concat_list.write_text("".join(f"file '{p.as_posix()}'\n" for p in norm_paths))
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
            "-movflags", "+faststart",
            str(out),
        ],
        capture_output=True, check=True,
    )
    return out


def concat_videos_matched(
    primary_url: str,
    broll_url: str,
    out_path: Optional[Path] = None,
    transition_dur: float = 0.6,
) -> Path:
    """Concat primary + broll into one MP4 with a short dissolve.

    B-roll is rescaled+padded to match the primary clip's dimensions so
    mismatched aspect ratios letterbox/pillarbox cleanly instead of skewing.
    A ~0.6s xfade dissolve (+ acrossfade on audio) covers the seam so the
    handoff doesn't read as a freeze.
    Returns the local output path.
    """
    work = Path(tempfile.mkdtemp(prefix="concat_"))
    primary_local = _download(primary_url, work / "primary.mp4")
    broll_local = _download(broll_url, work / "broll.mp4")

    pw, ph = probe_video_dimensions(primary_local)
    if pw <= 0 or ph <= 0:
        pw, ph = 720, 1280

    # Normalize both clips to identical res/fps/codec/audio. xfade+acrossfade
    # requires matching streams AND both inputs must carry audio — synthesize
    # silence if the source is muted.
    def _normalize(src: Path, dest: Path) -> None:
        has_audio = _has_audio_stream(src)
        cmd = ["ffmpeg", "-y", "-i", str(src)]
        if not has_audio:
            cmd += ["-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100", "-shortest"]
        cmd += [
            "-vf", f"scale={pw}:{ph}:force_original_aspect_ratio=decrease,"
                   f"pad={pw}:{ph}:(ow-iw)/2:(oh-ih)/2,setsar=1",
            "-r", "30", "-pix_fmt", "yuv420p",
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
            "-movflags", "+faststart",
            str(dest),
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    primary_norm = work / "primary_norm.mp4"
    broll_norm = work / "broll_norm.mp4"
    _normalize(primary_local, primary_norm)
    _normalize(broll_local, broll_norm)

    out = out_path or (work / f"concat_{uuid.uuid4().hex}.mp4")

    primary_dur = _probe_duration(primary_norm)
    broll_dur = _probe_duration(broll_norm)

    # Only use xfade when both clips are long enough to absorb the transition.
    use_xfade = (
        transition_dur > 0
        and primary_dur > transition_dur * 2
        and broll_dur > transition_dur * 2
    )

    if use_xfade:
        offset = max(0.1, primary_dur - transition_dur)
        filter_complex = (
            f"[0:v][1:v]xfade=transition=dissolve:duration={transition_dur}:offset={offset:.3f}[v];"
            f"[0:a][1:a]acrossfade=d={transition_dur}[a]"
        )
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(primary_norm),
                    "-i", str(broll_norm),
                    "-filter_complex", filter_complex,
                    "-map", "[v]", "-map", "[a]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                    "-movflags", "+faststart",
                    str(out),
                ],
                capture_output=True, check=True,
            )
            return out
        except subprocess.CalledProcessError as e:
            # Fall through to simple concat on xfade failure (e.g. weird input).
            err_tail = (e.stderr or b"")[-600:].decode("utf-8", errors="ignore")
            print(f"[concat_videos_matched] xfade failed, falling back to hard cut: {err_tail}")

    concat_list = work / "concat.txt"
    concat_list.write_text(
        f"file '{primary_norm.as_posix()}'\nfile '{broll_norm.as_posix()}'\n"
    )
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_list),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-movflags", "+faststart",
            str(out),
        ],
        capture_output=True, check=True,
    )
    return out
