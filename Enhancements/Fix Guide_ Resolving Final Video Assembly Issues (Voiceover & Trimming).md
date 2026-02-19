# **Fix Guide: Resolving Final Video Assembly Issues (Voiceover & Trimming)**

**Author:** Manus AI
**Date:** 2026-02-19

---

## **1. Overview**

This document provides the definitive fix for two critical errors in the final video assembly stage:

1.  **Unwanted Voiceover:** An ElevenLabs voiceover is being added on top of Veo 3.1 videos, which already have native audio.
2.  **Aggressive Trimming:** Full-length scenes are being cut down to less than 1 second, resulting in a final video that is too short.

Both issues stem from logic that was designed for digital app videos and is being incorrectly applied to the new physical product video pipeline.

---

## **2. Root Cause Analysis**

### **Issue 1: Unwanted Voiceover**

**File:** `C:\Users\dedam\.antigravity\UGC Engine SaaS\core_engine.py` (Lines 119-145)

**Problem:** The code unconditionally adds a voiceover if `subtitle_text` exists, based on the incorrect assumption that "Veo is silent".

```python
# The comment is wrong - Veo 3.1 is NOT silent
# Veo is silent, so generates voiceover if needed
if scene.get("subtitle_text"):
    # This block always runs for physical product scenes
    print(f"      🎙️ Adding Voiceover...")
    # ... (ElevenLabs generation and FFmpeg overlay)
```

### **Issue 2: Aggressive Trimming**

**File:** `C:\Users\dedam\.antigravity\UGC Engine SaaS\assemble_video.py` (Lines 117-138)

**Problem:** The code iterates through each video and trims it to a default duration (e.g., 4 seconds) from `config.SCENE_DURATIONS`. This was designed for short app demo clips, not for the longer, dynamically generated Veo 3.1 scenes.

```python
# This loop incorrectly trims all videos to a short, fixed duration
for i, (scene, dur) in enumerate(zip(video_paths, durations)):
    trimmed = work_dir / f"trimmed_{i}.mp4"
    # This function cuts the video down to `dur` (e.g., 4s)
    trim_video(path, trimmed, dur, mode=mode)
    trimmed_paths.append(str(trimmed))
```

---

## **3. The Solution: Conditional Logic & Smarter Assembly**

### **Part 1: Fix Unwanted Voiceover**

**File to Modify:** `C:\Users\dedam\.antigravity\UGC Engine SaaS\core_engine.py`

**Action:** We will introduce a list of models that have native audio and check against it before attempting to add a voiceover.

**Find this code block (around line 119):**

```python
# C:\Users\dedam\.antigravity\UGC Engine SaaS\core_engine.py (BEFORE)

# Veo is silent, so generates voiceover if needed
if scene.get("subtitle_text"):
    if status_callback: status_callback(f"Voiceover: {scene["name"].title()}")
    # ... (voiceover generation and overlay)
```

**Replace it with this new, smarter logic:**

```python
# C:\Users\dedam\.antigravity\UGC Engine SaaS\core_engine.py (AFTER)

# ✨ FIX: Define models that generate their own audio
MODELS_WITH_NATIVE_AUDIO = {"veo-3.1-fast", "veo-3.1", "seedance-1.5-pro", "seedance-2.0"}

# For physical product scenes, the model is hardcoded to veo-3.1-fast
model_used = "veo-3.1-fast"

# Only add a voiceover if the model is NOT in the native audio list
if scene.get("subtitle_text") and model_used not in MODELS_WITH_NATIVE_AUDIO:
    if status_callback: status_callback(f"Voiceover: {scene["name"].title()}")
    print(f"      🎙️ Adding Voiceover (model {model_used} has no native audio)...")
    
    voice_id = scene.get("voice_id", config.VOICE_MAP.get(influencer["name"], "pNInz6obpgDQGcFmaJgB"))
    audio_file = elevenlabs_client.generate_voiceover(
        text=scene["subtitle_text"],
        voice_id=voice_id,
        filename=f"vo_{i}_{scene["name"]}.mp3"
    )
    
    # Overlay voiceover (FFmpeg command)
    # ... (rest of the original ffmpeg block)
else:
    print(f"      ✅ Skipping voiceover: Model '{model_used}' has native audio.")
```

### **Part 2: Fix Aggressive Trimming**

**File to Modify:** `C:\Users\dedam\.antigravity\UGC Engine SaaS\assemble_video.py`

**Action:** We will modify the trimming loop to **skip trimming** for `physical_product_scene` types, thereby preserving their full, original duration.

**Find this code block (around line 122):**

```python
# C:\Users\dedam\.antigravity\UGC Engine SaaS\assemble_video.py (BEFORE)

for i, (scene, dur) in enumerate(zip(video_paths, durations)):
    # ... (logic to get path and mode)
    trimmed = work_dir / f"trimmed_{i}.mp4"
    trim_video(path, trimmed, dur, mode=mode)
    trimmed_paths.append(str(trimmed))
    # ...
```

**Replace it with this corrected logic:**

```python
# C:\Users\dedam\.antigravity\UGC Engine SaaS\assemble_video.py (AFTER)

for i, scene_data in enumerate(video_paths):
    path = scene_data["path"]
    scene_type = scene_data.get("type", "veo") # Default to veo if type is missing

    # ✨ FIX: For physical product scenes, use their actual duration and do not trim
    if scene_type == "physical_product_scene":
        actual_dur = get_video_duration(path)
        print(f"      Scene {i+1} ({scene_type}): Using full duration {actual_dur:.1f}s (no trim)")
        trimmed_paths.append(path) # Add original path, no trimming
        continue # Skip to the next scene

    # --- Original logic for digital app videos ---
    dur = durations[i] if i < len(durations) else 4 # Fallback duration
    mode = scene_data.get("trim_mode", "start")
    
    trimmed = work_dir / f"trimmed_{i}.mp4"
    trim_video(path, trimmed, dur, mode=mode)
    trimmed_paths.append(str(trimmed))
    actual_dur = get_video_duration(trimmed)
    print(f"      Scene {i+1}: {actual_dur:.1f}s (target {dur}s, mode {mode})")
```

**Note:** This fix assumes that `video_paths` is a list of dictionaries, each containing the `path` and `type`. You may need to adjust `core_engine.py` to pass this structured data to `assemble_video` instead of just a list of paths.

---

## **4. Expected Outcome**

-   **No Unwanted Voiceover:** The system will correctly identify that Veo 3.1 provides its own audio and will skip the ElevenLabs voiceover step.
-   **Full Scene Duration:** The final video will be composed of the full-length Veo 3.1 scenes, not trimmed-down versions.
-   **Correct Final Video:** The output will be a 15-30 second video with two distinct scenes, native audio from Veo 3.1, background music, and subtitles, all assembled correctly.
