# UGC Engine: Subtitle Synchronisation & Configuration — Complete Implementation Blueprint

**Document Version:** 2.0 (Definitive)
**Date:** 2026-03-30
**Author:** Manus AI
**Status:** This is the sole source of truth. No prior documents exist or should be referenced.

---

## 1. Purpose and Mandate

This document provides the complete, exhaustive, and definitive technical blueprint for overhauling the UGC Engine's subtitle generation system. It contains every SQL statement, every full code block, every file path, and every step-by-step instruction required. There are no placeholders, no "copy from original" notes, and no ambiguity.

**Antigravity must read this document in its entirety before writing a single line of code.**

The work has two objectives:

1. **Fix subtitle desynchronisation** — Eradicate the root causes of subtitles appearing out of sync with speech in Veo 3.1 videos.
2. **Add subtitle configuration** — Allow users to enable/disable subtitles, choose a visual style, and choose an on-screen placement from the `/create` page, with a live preview.

**The Paramount Constraint:** Every change is additive and corrective. No existing, working functionality may be broken. All existing API endpoints, response shapes, database columns, and video generation workflows must continue to function exactly as they do today.

---

## 2. Mandatory Pre-Implementation Audit

Before touching any file, Antigravity must open the codebase and confirm the following facts. If any finding differs from what is described here, Antigravity must stop and report the discrepancy before proceeding.

| # | File | What to Confirm |
|---|------|----------------|
| 1 | `core_engine.py` | The `elif scene["type"] == "veo":` block does NOT contain any `TranscriptionClient` call or `scene["transcription"] =` assignment after the `generate_scenes.download_video` call. |
| 2 | `assemble_video.py` | The `assemble_video` function signature is `def assemble_video(video_paths, output_path, music_path=None, max_duration=None, scene_types=None, brand_names=None):` with no `subtitle_config` parameter. |
| 3 | `assemble_video.py` | The cinematic path (the `if has_cinematic and ugc_scenes:` block) concatenates only UGC scenes, runs `extract_transcription_with_whisper` on that partial video, burns subtitles, and then re-concatenates with cinematic clips. |
| 4 | `subtitle_engine.py` | The `generate_subtitles_from_whisper` function signature is `def generate_subtitles_from_whisper(transcription, output_path, max_words=3, brand_names=None):` with no `style` or `placement` parameters. |
| 5 | `subtitle_engine.py` | The `_build_ass_header` function is `def _build_ass_header():` with no parameters. |
| 6 | `ugc_backend/main.py` | The `JobCreate` and `BulkJobCreate` models do NOT contain `subtitles_enabled`, `subtitle_style`, or `subtitle_placement` fields. |
| 7 | `ugc_db/migrations/` | The latest migration file is `012_add_social_scheduling.sql`. The next migration must be numbered `013`. |
| 8 | `ugc_worker/tasks.py` | The `fields` dictionary does NOT contain any subtitle configuration keys. |
| 9 | `frontend/src/app/create/page.tsx` | The `modelApi` state defaults to `'seedance-1.5-pro'`. The AI model selector UI block is rendered and visible. There are no `subtitlesEnabled`, `subtitleStyle`, or `subtitlePlacement` state variables. |

---

## 3. Root Cause Analysis

### Bug #1 — The Fragile Cinematic Assembly Path (`assemble_video.py`)

When a video contains a mix of AI influencer scenes and cinematic product shots, the `assemble_video` function takes a special path. It concatenates only the influencer clips into a temporary file (`ugc_combined.mp4`), runs Whisper on this partial video, burns subtitles, and then re-concatenates with the cinematic clips. The timestamps from Whisper are correct for the partial video, but after re-concatenation with cinematic clips, the final video has a different total duration and scene ordering. This makes the subtitle timestamps wrong for the final output. This path must be removed entirely.

### Bug #2 — Missing Per-Scene Transcription for the Standard `veo` Path (`core_engine.py`)

The `physical_product_scene` path (lines ~353–400 in `core_engine.py`) correctly extracts audio from each individual Veo 3.1 clip and runs Whisper on it, storing the result in `scene["transcription"]`. The `veo-extend` pipeline (lines ~265–310) does the same for the extended chain. However, the standard `elif scene["type"] == "veo":` path — the default for all digital product videos — has no such transcription step. After downloading the video, it proceeds directly to the next scene with no transcription data attached. This means the standard path relies entirely on the fragile post-assembly transcription.

### Bug #3 — Per-Scene Transcription Data Is Ignored (`assemble_video.py`)

This is the architectural root cause. Even when `core_engine.py` correctly generates `scene["transcription"]` data (as it does for `physical_product_scene`), the `assemble_video` function completely ignores it. The `video_paths` list passed to `assemble_video` contains scene dicts with `transcription` keys, but the function never reads them. Instead, it always discards this data and runs a fresh Whisper call on the final combined video. The fix is to invert this: burn subtitles per-scene using the attached transcription data, then concatenate.

---

## 4. Implementation — Phase 1: Fix Subtitle Synchronisation

This phase fixes all three bugs. It must be completed and tested before Phase 2 begins.

### 4.1 — Add Per-Scene Transcription to the Standard `veo` Path

**File:** `core_engine.py`

Locate the `elif scene["type"] == "veo":` block inside the main scene generation loop. Find the `else:` sub-block for pure AI model generation. After the line `generate_scenes.download_video(video_url, output_path)`, add the following block. This is the only addition to this file in Phase 1.

```python
# --- ADD THIS BLOCK after `generate_scenes.download_video(video_url, output_path)` ---
# Per-scene transcription for native audio models (Veo 3.1)
MODELS_WITH_NATIVE_AUDIO = {"veo-3.1-fast", "veo-3.1"}
if model_api in MODELS_WITH_NATIVE_AUDIO:
    print(f"      [MIC] Veo 3.1 native audio — extracting per-scene transcription...")
    try:
        audio_extract_path = output_dir / f"scene_{i}_{scene['name']}.mp3"
        cmd = [
            "ffmpeg", "-y", "-v", "quiet",
            "-i", str(output_path),
            "-vn", "-acodec", "libmp3lame", "-q:a", "2",
            str(audio_extract_path)
        ]
        subprocess.run(cmd, check=True)
        transcription_client = TranscriptionClient()
        transcription = transcription_client.transcribe_audio(
            str(audio_extract_path),
            brand_names=brand_names if 'brand_names' in dir() else None
        )
        if transcription:
            scene["transcription"] = transcription
            print(f"      [OK] Per-scene transcription attached: {len(transcription.get('words', []))} words")
        try:
            os.remove(audio_extract_path)
        except Exception:
            pass
    except Exception as e:
        print(f"      !! Per-scene transcription failed for scene {scene['name']}: {e}. Subtitles may be affected.")
# --- END OF ADDED BLOCK ---
```

**Important:** The `brand_names` variable is built later in `core_engine.py` (after the scene loop, before the `assemble_video` call). To make it available inside the loop, move the brand_names construction to **before** the scene generation loop. Find this block:

```python
# Build brand names list for subtitle correction
brand_names = []
if product:
    if product.get("name"):
        brand_names.append(product["name"])
    visuals = product.get("visual_description") or {}
    if visuals.get("brand_name") and visuals["brand_name"] not in brand_names:
        brand_names.append(visuals["brand_name"])
if brand_names:
    print(f"      [BRAND] Brand names for subtitle correction: {brand_names}")
```

Move this entire block to just **before** the `for i, scene in enumerate(scenes):` loop begins.

### 4.2 — Refactor `assemble_video` to Use Per-Scene Transcription

**File:** `assemble_video.py`

The `assemble_video` function must be replaced. The rest of the file (helper functions: `get_video_duration`, `normalize_video`, `_has_audio_stream`, `ensure_audio_stream`, `apply_transitions_between_veo_scenes`, `cleanup_temp`, and the `if __name__ == "__main__":` block) must remain **completely unchanged**. Only the `assemble_video` function itself is replaced.

Replace the entire `assemble_video` function — from `def assemble_video(...)` to the closing `return str(final_path)` — with the following:

```python
def assemble_video(video_paths, output_path, music_path=None, max_duration=None, scene_types=None, brand_names=None, subtitle_config=None):
    """Assembles the final UGC video.

    Subtitle strategy: burn subtitles per-scene using Whisper transcription data
    already attached to each scene dict by core_engine.py. This is the most
    accurate method because timestamps are relative to each individual clip.
    Falls back gracefully to no subtitles if transcription data is absent.

    Args:
        video_paths:    List of scene dicts (each has 'path', 'type', optionally 'transcription').
        output_path:    Final output file path.
        music_path:     Optional path to background music file.
        max_duration:   Optional maximum duration cap in seconds.
        scene_types:    List of scene type strings (one per scene). Used for transitions.
        brand_names:    Optional list of brand/product names for subtitle spelling correction.
        subtitle_config: Optional dict with keys: 'enabled' (bool), 'style' (str), 'placement' (str).
    """
    if output_path is None:
        output_path = config.OUTPUT_DIR / "final_ugc.mp4"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    assembly_id = uuid.uuid4().hex[:8]
    work_dir = config.TEMP_DIR / f"assembly_{assembly_id}"
    work_dir.mkdir(parents=True, exist_ok=True)
    print("\n[BUILD] Assembling final video...")

    # Parse subtitle configuration
    sub_cfg = subtitle_config or {}
    subtitles_enabled = sub_cfg.get("enabled", True)
    subtitle_style = sub_cfg.get("style", "hormozi")
    subtitle_placement = sub_cfg.get("placement", "middle")

    # -------------------------------------------------------------------------
    # Step 1: Normalize all clips to same resolution/codec
    # -------------------------------------------------------------------------
    print("   [NORM] Normalizing to 9:16...")
    normalized_paths = []
    scene_metadata = []

    for i, scene_data in enumerate(video_paths):
        if isinstance(scene_data, dict):
            path = scene_data["path"]
            scene_type = scene_data.get("type", "clip")
        else:
            path = scene_data
            scene_type = (scene_types[i] if scene_types and i < len(scene_types) else "clip")

        normalized = work_dir / f"normalized_{i}.mp4"
        normalize_video(path, normalized)
        normalized_paths.append(str(normalized))
        scene_metadata.append({
            "index": i,
            "type": scene_type,
            "path": str(normalized),
            "transcription": scene_data.get("transcription") if isinstance(scene_data, dict) else None,
            "name": scene_data.get("name", f"scene_{i}") if isinstance(scene_data, dict) else f"scene_{i}",
        })
        actual_dur = get_video_duration(normalized)
        print(f"      Scene {i+1} ({scene_type}): {actual_dur:.1f}s | has_transcription={bool(scene_metadata[-1]['transcription'])}")

    # -------------------------------------------------------------------------
    # Step 2: Ensure all clips have an audio stream (required for transitions)
    # -------------------------------------------------------------------------
    for idx in range(len(normalized_paths)):
        normalized_paths[idx] = ensure_audio_stream(normalized_paths[idx], work_dir)
        scene_metadata[idx]["path"] = normalized_paths[idx]

    # -------------------------------------------------------------------------
    # Step 3: Apply cross-dissolve transitions between consecutive AI scenes
    # -------------------------------------------------------------------------
    if scene_types:
        types_list = list(scene_types)
        normalized_paths = apply_transitions_between_veo_scenes(
            normalized_paths, types_list, work_dir,
        )
        scene_metadata = [
            {**scene_metadata[i], "path": normalized_paths[i]}
            for i in range(len(normalized_paths))
        ]

    # -------------------------------------------------------------------------
    # Step 4: Burn subtitles per-scene (using pre-attached transcription data)
    # -------------------------------------------------------------------------
    subtitled_paths = []
    for scene in scene_metadata:
        scene_path = Path(scene["path"])
        transcription = scene.get("transcription")

        if subtitles_enabled and transcription and transcription.get("words"):
            print(f"   [SUB] Burning subtitles for scene {scene['index']} ({scene['name']})...")
            subtitle_ass_path = work_dir / f"scene_{scene['index']}.ass"

            from .subtitle_engine import generate_subtitles_from_whisper
            generate_subtitles_from_whisper(
                transcription=transcription,
                output_path=subtitle_ass_path,
                brand_names=brand_names,
                style=subtitle_style,
                placement=subtitle_placement,
            )

            if subtitle_ass_path.exists() and subtitle_ass_path.stat().st_size > 250:
                subtitled_path = work_dir / f"scene_{scene['index']}_subtitled.mp4"
                sub_path_safe = str(subtitle_ass_path.resolve()).replace("\\", "/").replace(":", "\\:")
                cmd = [
                    "ffmpeg", "-y",
                    "-i", str(scene_path),
                    "-vf", f"ass=\\'{sub_path_safe}\\'",
                    "-c:v", "libx264", "-crf", "18", "-preset", "veryfast",
                    "-c:a", "copy",
                    str(subtitled_path),
                ]
                result = subprocess.run(cmd, capture_output=True)
                if result.returncode == 0:
                    subtitled_paths.append(str(subtitled_path))
                    print(f"      [OK] Subtitles burned for scene {scene['index']}.")
                else:
                    print(f"      !! Subtitle burn failed for scene {scene['index']}. Using original.")
                    subtitled_paths.append(str(scene_path))
            else:
                print(f"      [WARN] Subtitle file for scene {scene['index']} was empty. Using original.")
                subtitled_paths.append(str(scene_path))
        else:
            if subtitles_enabled and not transcription:
                print(f"   [INFO] No transcription data for scene {scene['index']} ({scene['name']}). Skipping subtitles.")
            subtitled_paths.append(str(scene_path))

    # -------------------------------------------------------------------------
    # Step 5: Final concatenation of all (subtitled) scenes
    # -------------------------------------------------------------------------
    print("   [LINK] Concatenating all scenes...")
    concat_list_path = work_dir / "final_concat.txt"
    with open(concat_list_path, "w") as f:
        for path in subtitled_paths:
            safe_path = str(Path(path).resolve()).replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    combined = work_dir / "combined.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        str(combined),
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    total_dur = get_video_duration(combined)
    print(f"      Combined: {total_dur:.1f}s")
    current_input = str(combined)

    # -------------------------------------------------------------------------
    # Step 6: Add background music (if provided)
    # -------------------------------------------------------------------------
    if music_path and Path(music_path).exists():
        print("   [MUSIC] Adding background music...")
        final_dur = get_video_duration(current_input)
        fade_start = max(0, final_dur - 2)
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

    # -------------------------------------------------------------------------
    # Step 7: Enforce max duration and copy to final output
    # -------------------------------------------------------------------------
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
    try:
        shutil.rmtree(work_dir, ignore_errors=True)
    except Exception:
        pass
    return str(output_path)
```

### 4.3 — Update the `assemble_video` Call in `core_engine.py`

**File:** `core_engine.py`

The existing call to `assemble_video.assemble_video` at the end of `run_generation_pipeline` must be updated to pass the new `subtitle_config` parameter. First, add `subtitle_config: dict = None` to the `run_generation_pipeline` function signature. Then update the call:

```python
# EXISTING call (find this):
final_path = assemble_video.assemble_video(
    video_paths=video_paths,
    output_path=output_path,
    music_path=music_path,
    max_duration=config.get_max_duration(length),
    scene_types=[s.get("type", "clip") for s in video_paths],
    brand_names=brand_names or None,
)

# REPLACE WITH:
final_path = assemble_video.assemble_video(
    video_paths=video_paths,
    output_path=output_path,
    music_path=music_path,
    max_duration=config.get_max_duration(length),
    scene_types=[s.get("type", "clip") for s in video_paths],
    brand_names=brand_names or None,
    subtitle_config=subtitle_config,
)
```

---

## 5. Implementation — Phase 2: Subtitle Configuration

This phase introduces the database columns, API fields, and engine changes to support user-controlled subtitle configuration. All new fields default to current behaviour, so any existing job that does not include these fields will continue to work exactly as before.

### 5.1 — Database Migration

Create the following file. Run this SQL in the Supabase SQL Editor after the code changes are deployed.

**File:** `ugc_db/migrations/013_add_subtitle_config.sql`

```sql
-- Migration 013: Add Subtitle Configuration to Video Jobs
-- Adds three nullable columns with safe defaults to the video_jobs table.
-- Safe to run multiple times (ADD COLUMN IF NOT EXISTS).

ALTER TABLE public.video_jobs
  ADD COLUMN IF NOT EXISTS subtitles_enabled  BOOLEAN DEFAULT true,
  ADD COLUMN IF NOT EXISTS subtitle_style     TEXT    DEFAULT 'hormozi',
  ADD COLUMN IF NOT EXISTS subtitle_placement TEXT    DEFAULT 'middle';

COMMENT ON COLUMN public.video_jobs.subtitles_enabled  IS 'Whether to burn subtitles into the final video. Defaults to true.';
COMMENT ON COLUMN public.video_jobs.subtitle_style     IS 'Visual style preset: hormozi | mrbeast. Defaults to hormozi.';
COMMENT ON COLUMN public.video_jobs.subtitle_placement IS 'Vertical placement: top | middle | bottom. Defaults to middle.';
```

### 5.2 — Update API Models in `ugc_backend/main.py`

Add the three new optional fields to both `JobCreate` and `BulkJobCreate`.

```python
# FIND JobCreate and add these three fields:
class JobCreate(BaseModel):
    influencer_id: str
    script_id: Optional[str] = None
    app_clip_id: Optional[str] = None
    product_id: Optional[str] = None
    product_type: str = "digital"
    hook: Optional[str] = None
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    length: int = 15
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None
    cinematic_shot_ids: Optional[List[str]] = None
    auto_transition_type: Optional[str] = None
    # NEW FIELDS — subtitle configuration
    subtitles_enabled: Optional[bool] = True
    subtitle_style: Optional[str] = "hormozi"
    subtitle_placement: Optional[str] = "middle"

# FIND BulkJobCreate and add these three fields:
class BulkJobCreate(BaseModel):
    influencer_id: str
    count: int = 1
    duration: int = 15
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    product_type: str = "digital"
    product_id: Optional[str] = None
    hook: Optional[str] = None
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None
    cinematic_shot_ids: Optional[List[str]] = None
    auto_transition_type: Optional[str] = None
    # NEW FIELDS — subtitle configuration
    subtitles_enabled: Optional[bool] = True
    subtitle_style: Optional[str] = "hormozi"
    subtitle_placement: Optional[str] = "middle"
```

The existing `db_columns` probe logic in `api_create_job` and `api_create_bulk_jobs` will automatically handle these new columns once the migration has been run — the new fields will be present in the probed column set and will be included in `job_data` via `data.model_dump(exclude_none=True)`.

### 5.3 — Pass Subtitle Config Through the Worker

**File:** `ugc_worker/tasks.py`

In the `generate_video_job` function, after the `fields` dictionary is constructed, add the following block to build the `subtitle_config` dictionary and pass it to the pipeline:

```python
# ADD THIS after the `fields = { ... }` block:
subtitle_config = {
    "enabled": job.get("subtitles_enabled", True),
    "style": job.get("subtitle_style", "hormozi"),
    "placement": job.get("subtitle_placement", "middle"),
}

# THEN update the run_generation_pipeline call to include it:
# FIND:
final_video_path = core_engine.run_generation_pipeline(
    project_name=project_name,
    influencer=influencer_dict,
    app_clip=app_clip_dict,
    product=product_dict,
    product_type=job.get("product_type", "digital"),
    fields=fields,
    status_callback=status_callback,
    skip_music=False,
)

# REPLACE WITH:
final_video_path = core_engine.run_generation_pipeline(
    project_name=project_name,
    influencer=influencer_dict,
    app_clip=app_clip_dict,
    product=product_dict,
    product_type=job.get("product_type", "digital"),
    fields=fields,
    status_callback=status_callback,
    skip_music=False,
    subtitle_config=subtitle_config,
)
```

### 5.4 — Refactor `subtitle_engine.py` for Configuration

Replace the `_build_ass_header` and `generate_subtitles_from_whisper` functions in `subtitle_engine.py`. All other functions (`extract_transcription_with_whisper`, `generate_subtitles`, `generate_synced_subtitles`, `_format_ass_time`, `_split_into_chunks`, `_highlight_power_words`, `_correct_brand_in_text`, `_correct_brand_in_words`, and the `if __name__ == "__main__":` block) must remain **completely unchanged**.

**Add these style constants** near the top of the file, after the existing constants:

```python
# --- Configurable Style Presets ---
SUBTITLE_STYLES = {
    "hormozi": {
        "font_name": "Impact",
        "font_size": 140,
        "primary_color": "&H00FFFFFF",   # White text
        "outline_color": "&H00000000",   # Black outline
        "back_color": "&H80000000",      # Semi-transparent shadow
        "bold": -1,
        "outline_width": 8,
        "shadow_depth": 5,
        "highlight_color": "&H0000FFFF", # Yellow for power words
    },
    "mrbeast": {
        "font_name": "Impact",
        "font_size": 130,
        "primary_color": "&H0000FFFF",   # Yellow text
        "outline_color": "&H00000000",   # Black outline
        "back_color": "&H80000000",
        "bold": -1,
        "outline_width": 6,
        "shadow_depth": 4,
        "highlight_color": "&H00FFFFFF", # White for power words
    },
}

# ASS Alignment values: 2=bottom-center, 5=middle-center, 8=top-center
SUBTITLE_PLACEMENTS = {
    "bottom": 2,
    "middle": 5,
    "top": 8,
}
```

**Replace `_build_ass_header`** with this parameterised version:

```python
def _build_ass_header(style_name="hormozi", placement_name="middle"):
    """Build the ASS file header with configurable style and placement."""
    style = SUBTITLE_STYLES.get(style_name, SUBTITLE_STYLES["hormozi"])
    alignment = SUBTITLE_PLACEMENTS.get(placement_name, SUBTITLE_PLACEMENTS["middle"])
    style_line = (
        f"Style: {style_name.title()},"
        f"{style['font_name']},"
        f"{style['font_size']},"
        f"{style['primary_color']},"
        f"&H000000FF,"
        f"{style['outline_color']},"
        f"{style['back_color']},"
        f"{style['bold']},"
        f"0,0,0,100,100,0,0,1,"
        f"{style['outline_width']},"
        f"{style['shadow_depth']},"
        f"{alignment},"
        f"40,40,40,1"
    )
    return f"""[Script Info]
Title: UGC Engine Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
{style_line}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
```

**Replace `generate_subtitles_from_whisper`** with this parameterised version:

```python
def generate_subtitles_from_whisper(transcription, output_path, max_words=3, brand_names=None, style="hormozi", placement="middle"):
    """Generates a configured ASS subtitle file from a Whisper API verbose_json response."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_content = _build_ass_header(style_name=style, placement_name=placement)

    if not transcription or "words" not in transcription or not transcription["words"]:
        print("   ⚠️ No words found in transcription. Skipping subtitle generation.")
        with open(output_path, "w") as f:
            f.write(ass_content)
        return None

    all_words = transcription["words"]

    # Apply brand name corrections if not already done during extraction
    if brand_names:
        _correct_brand_in_words(all_words, brand_names)

    MAX_CHUNK_DURATION = 2.5  # seconds — Hormozi-style subtitles should flash quickly
    style_name_title = style.title()
    chunks = []
    for i in range(0, len(all_words), max_words):
        chunk_words = all_words[i:i + max_words]
        text = " ".join([word["word"].strip() for word in chunk_words])
        start_time = chunk_words[0]["start"]
        end_time = chunk_words[-1]["end"]
        # Cap duration to prevent long-lingering subtitles
        if end_time - start_time > MAX_CHUNK_DURATION:
            end_time = start_time + MAX_CHUNK_DURATION
        chunks.append({"text": text, "start": start_time, "end": end_time})

    # Shift first subtitle to start at 0.0s if it begins within 1.5s
    if chunks and chunks[0]["start"] > 0 and chunks[0]["start"] < 2.0:
        chunks[0]["start"] = 0.0

    for chunk in chunks:
        start = _format_ass_time(chunk["start"])
        end = _format_ass_time(chunk["end"])
        styled_chunk = _highlight_power_words(chunk["text"])
        ass_content += f"Dialogue: 0,{start},{end},{style_name_title},,0,0,0,,{styled_chunk}\n"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"   🔤 Synchronized subtitles saved: {output_path} [style={style}, placement={placement}]")
    return str(output_path)
```

**Important:** The existing `generate_subtitles` function calls `_build_ass_header()` with no arguments. After the refactor, `_build_ass_header()` still accepts no arguments (they are optional with defaults), so this call continues to work without any changes.

---

## 6. Implementation — Phase 3: Frontend UI

This phase adds the subtitle controls and live preview to the `/create` page, and hides the AI model selector.

### 6.1 — Hide the AI Model Selector

**File:** `frontend/src/app/create/page.tsx`

Change the default value of `modelApi`:

```typescript
// FIND:
const [modelApi, setModelApi] = useState('seedance-1.5-pro');
// REPLACE WITH:
const [modelApi, setModelApi] = useState('veo-3.1-fast');
```

Comment out the entire AI Model config section JSX. Find the block that starts with `{/* STEP 3 — AI Model */}` and wrap the entire `<div className="config-section">` block in a comment:

```jsx
{/* AI Model selector hidden — Veo 3.1 Fast is used by default
<div className="config-section">
    <div className="config-step">
        <div className="step-num">3</div>
        <div className="step-text">AI Model</div>
    </div>
    <div className="pill-group">
        {AI_MODELS.map(model => (
            <button key={model.value} className={`btn-secondary ${modelApi === model.value ? 'active' : ''}`} onClick={() => setModelApi(model.value)} style={{padding:'8px 16px'}}>
                {model.label}
            </button>
        ))}
    </div>
</div>
*/}
```

### 6.2 — Add Subtitle State Variables

**File:** `frontend/src/app/create/page.tsx`

Add these three state variables alongside the existing state declarations (after the `enableAutoTransitions` and `autoTransitionType` lines):

```typescript
// Subtitle configuration
const [subtitlesEnabled, setSubtitlesEnabled] = useState(true);
const [subtitleStyle, setSubtitleStyle] = useState<'hormozi' | 'mrbeast'>('hormozi');
const [subtitlePlacement, setSubtitlePlacement] = useState<'top' | 'middle' | 'bottom'>('middle');
```

### 6.3 — Create the `SubtitlePreview` Component

Create this new file:

**File:** `frontend/src/components/SubtitlePreview.tsx`

```tsx
'use client';
import React from 'react';

interface SubtitlePreviewProps {
    enabled: boolean;
    style: 'hormozi' | 'mrbeast';
    placement: 'top' | 'middle' | 'bottom';
}

const STYLE_CONFIG = {
    hormozi: {
        color: '#FFFFFF',
        fontFamily: 'Impact, "Arial Narrow", sans-serif',
        fontSize: '13px',
        textShadow: '2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 0 3px 0 #000',
        fontWeight: 'bold',
        letterSpacing: '0.5px',
    },
    mrbeast: {
        color: '#FFE000',
        fontFamily: 'Impact, "Arial Narrow", sans-serif',
        fontSize: '12px',
        textShadow: '2px 2px 0 #000, -2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000',
        fontWeight: 'bold',
        letterSpacing: '0.5px',
    },
};

const PLACEMENT_CONFIG = {
    top: { top: '12%', bottom: 'auto', transform: 'translateX(-50%)' },
    middle: { top: '50%', bottom: 'auto', transform: 'translate(-50%, -50%)' },
    bottom: { top: 'auto', bottom: '12%', transform: 'translateX(-50%)' },
};

export const SubtitlePreview: React.FC<SubtitlePreviewProps> = ({ enabled, style, placement }) => {
    const styleConfig = STYLE_CONFIG[style];
    const placementConfig = PLACEMENT_CONFIG[placement];

    return (
        <div style={{
            position: 'relative',
            width: '90px',
            height: '160px',
            borderRadius: '8px',
            overflow: 'hidden',
            background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
            border: '1px solid var(--border)',
            flexShrink: 0,
        }}>
            {/* Simulated video frame content */}
            <div style={{
                position: 'absolute', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
                <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'rgba(255,255,255,0.15)' }} />
            </div>

            {/* Subtitle overlay */}
            {enabled && (
                <div style={{
                    position: 'absolute',
                    left: '50%',
                    width: '85%',
                    textAlign: 'center',
                    ...placementConfig,
                    ...styleConfig,
                    lineHeight: 1.2,
                    padding: '2px 4px',
                    pointerEvents: 'none',
                }}>
                    AMAZING
                </div>
            )}

            {/* Label */}
            <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                background: 'rgba(0,0,0,0.5)',
                fontSize: '8px', color: 'rgba(255,255,255,0.6)',
                textAlign: 'center', padding: '2px',
            }}>
                Preview
            </div>
        </div>
    );
};
```

### 6.4 — Add Subtitle Controls to the Create Page

**File:** `frontend/src/app/create/page.tsx`

First, import the new component at the top of the file:

```typescript
import { SubtitlePreview } from '@/components/SubtitlePreview';
```

Then, add the subtitle configuration section. Place it in the JSX immediately after the (now commented-out) AI Model section, and before the Duration section. The step number should be renumbered to 3 (since AI Model is now hidden):

```jsx
{/* STEP 3 — Subtitles */}
<div className="config-section">
    <div className="config-step">
        <div className="step-num">3</div>
        <div className="step-text">Subtitles</div>
    </div>
    <div style={{ display: 'flex', gap: '20px', alignItems: 'flex-start' }}>
        <div style={{ flex: 1 }}>
            {/* Enable/Disable Toggle */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '14px' }}>
                <button
                    onClick={() => setSubtitlesEnabled(!subtitlesEnabled)}
                    style={{
                        width: 40, height: 22, borderRadius: 11,
                        background: subtitlesEnabled ? 'var(--blue)' : 'var(--border)',
                        position: 'relative', cursor: 'pointer', border: 'none', padding: 0,
                        transition: 'background 0.2s',
                    }}
                >
                    <span style={{
                        position: 'absolute', left: 3, top: 3,
                        width: 16, height: 16, borderRadius: '50%',
                        background: 'white', transition: 'transform 0.15s',
                        transform: subtitlesEnabled ? 'translateX(18px)' : 'translateX(0)',
                    }} />
                </button>
                <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
                    {subtitlesEnabled ? 'Subtitles On' : 'Subtitles Off'}
                </span>
            </div>

            {subtitlesEnabled && (
                <>
                    {/* Style Selector */}
                    <div className="config-label" style={{ marginBottom: '6px' }}>Style</div>
                    <div className="pill-group" style={{ marginBottom: '12px' }}>
                        {([
                            { value: 'hormozi', label: 'Hormozi' },
                            { value: 'mrbeast', label: 'Mr Beast' },
                        ] as const).map(s => (
                            <button
                                key={s.value}
                                className={`btn-secondary ${subtitleStyle === s.value ? 'active' : ''}`}
                                onClick={() => setSubtitleStyle(s.value)}
                            >
                                {s.label}
                            </button>
                        ))}
                    </div>

                    {/* Placement Selector */}
                    <div className="config-label" style={{ marginBottom: '6px' }}>Placement</div>
                    <div className="pill-group">
                        {([
                            { value: 'top', label: 'Top' },
                            { value: 'middle', label: 'Middle' },
                            { value: 'bottom', label: 'Bottom' },
                        ] as const).map(p => (
                            <button
                                key={p.value}
                                className={`btn-secondary ${subtitlePlacement === p.value ? 'active' : ''}`}
                                onClick={() => setSubtitlePlacement(p.value)}
                            >
                                {p.label}
                            </button>
                        ))}
                    </div>
                </>
            )}
        </div>

        {/* Live Preview */}
        <SubtitlePreview
            enabled={subtitlesEnabled}
            style={subtitleStyle}
            placement={subtitlePlacement}
        />
    </div>
</div>
```

### 6.5 — Add Subtitle Config to API Calls

**File:** `frontend/src/app/create/page.tsx`

In the `handleCreateVideo` function, add the three new fields to both API request bodies.

For the bulk campaign request (`/jobs/bulk`):

```typescript
body: JSON.stringify({
    influencer_id: selectedInfluencer,
    count: quantity,
    duration,
    model_api: modelApi,
    campaign_name: campaignName || undefined,
    assistant_type: selectedInf?.style || 'Travel',
    product_type: productType,
    product_id: productId || undefined,
    hook: bulkHook,
    cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
    auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
    // NEW
    subtitles_enabled: subtitlesEnabled,
    subtitle_style: subtitleStyle,
    subtitle_placement: subtitlePlacement,
}),
```

For the single video request (`/jobs`):

```typescript
body: JSON.stringify({
    influencer_id: selectedInfluencer,
    script_id: scriptSource === 'specific' ? selectedScript : undefined,
    app_clip_id: (productType === 'digital' && appClipId !== 'auto') ? appClipId : undefined,
    product_id: productId || undefined,
    product_type: productType,
    hook: effectiveHook,
    model_api: modelApi,
    assistant_type: selectedInf?.style || 'Travel',
    length: duration,
    cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
    auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
    // NEW
    subtitles_enabled: subtitlesEnabled,
    subtitle_style: subtitleStyle,
    subtitle_placement: subtitlePlacement,
}),
```

---

## 7. Deployment Sequence

The following sequence must be followed exactly:

1. Complete all Phase 1 code changes and commit.
2. Complete all Phase 2 code changes (backend only — `main.py`, `tasks.py`, `core_engine.py`, `subtitle_engine.py`) and commit.
3. Complete all Phase 3 frontend changes and commit.
4. Push to GitHub. Railway/Render will auto-deploy.
5. After the deployment is live and healthy, run the SQL from `013_add_subtitle_config.sql` in the Supabase SQL Editor.
6. The new columns will now be present in the `video_jobs` table. The `db_columns` probe in `api_create_job` and `api_create_bulk_jobs` will detect them automatically on the next request.

---

## 8. Non-Breaking Guarantee

The following existing behaviours are explicitly preserved:

| Concern | How It Is Preserved |
|---------|-------------------|
| Jobs created before migration 013 | The new columns have `DEFAULT true / 'hormozi' / 'middle'`, so existing rows are unaffected. |
| API calls that do not include subtitle fields | All three new Pydantic fields have defaults, so existing callers receive the current default behaviour. |
| The `generate_subtitles` function | Unchanged. It calls `_build_ass_header()` with no arguments, which still works because the new parameters are optional with defaults. |
| The `generate_synced_subtitles` function | Unchanged. |
| The `extract_transcription_with_whisper` function | Unchanged. |
| The `physical_product_scene` transcription path | Unchanged. It already correctly attaches `scene["transcription"]`, which the new `assemble_video` will now correctly use. |
| The `veo-extend` pipeline | Unchanged. It already correctly attaches `scene["transcription"]` to the extended chain scene, which the new `assemble_video` will now correctly use. |
| All non-Veo models (Seedance, Kling, InfiniteTalk) | Unchanged. These scenes will have no `transcription` key; the new `assemble_video` gracefully skips subtitle burning for them. |
| All helper functions in `assemble_video.py` | Unchanged. Only the `assemble_video` function itself is replaced. |
| All existing API endpoints and response shapes | No endpoint signatures, response schemas, or status codes are changed. |

---

## 9. Definition of Done

The implementation is complete when all of the following are true:

- A Veo 3.1 Fast single video is generated with subtitles enabled. Every word in the subtitles matches the spoken audio at the correct moment.
- A Veo 3.1 Fast campaign (3+ videos) is generated. All videos have correctly synced subtitles.
- A physical product video with cinematic shots is generated. Subtitles appear only on the influencer scenes and are correctly synced.
- On the `/create` page, the AI model selector is no longer visible.
- On the `/create` page, the Subtitles section shows a toggle, style pills, placement pills, and a live preview that updates in real time.
- Generating a video with `subtitles_enabled: false` produces a video with no subtitles burned in.
- Generating a video with `subtitle_style: 'mrbeast'` produces yellow-text subtitles.
- Generating a video with `subtitle_placement: 'top'` produces subtitles at the top of the frame.
- All existing Seedance and other non-Veo video generation workflows continue to function without errors.
- Migration `013_add_subtitle_config.sql` has been run in Supabase with no errors.
