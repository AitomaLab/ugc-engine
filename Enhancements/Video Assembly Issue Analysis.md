# Video Assembly Issue Analysis

## **Terminal Log Analysis**

### **Issue 1: Unwanted Voiceover Added**

**Lines 3-8:**
```
[Job d556c2ce-39ed-4b91-a1c5-410b03cbceab] Voiceover: Physical_Scene_2
🎙️ Adding Voiceover...
🎙️ Generating ElevenLabs voiceover...
Voice: hpp4J3VqNfWAUOO0d1Us
Text: this out!...
✅ Voiceover saved: C:\Users\dedam\.antigravity\UGC Engine SaaS\temp\vo_2_physical_scene_2.mp3
```

**Problem:** The system is generating an ElevenLabs voiceover for Scene 2 and adding it to the video, even though Veo 3.1 already generated the video with native audio.

**Location:** This happens in `core_engine.py` around lines 119-145, where it checks:
```python
if scene.get("subtitle_text"):
    # Generate voiceover
```

The issue is that this logic doesn't check whether the video model already has audio.

### **Issue 2: Videos Trimmed to ~1 Second**

**Lines 80-84:**
```
📐 Normalizing to 9:16...
   Scene 1: 0.7s
   Scene 2: 0.9s
📐 Normalizing to 9:16...
🔗 Concatenating scenes...
   Combined: 1.6s
```

**Problem:** The original Veo 3.1 videos are likely 8-15 seconds long, but they're being trimmed to 0.7s and 0.9s during the "Normalizing to 9:16" step.

**Location:** This happens in `assemble_video.py` during the normalization or trimming phase.

## **Root Causes**

### **Root Cause 1: No Check for Native Audio**

In `core_engine.py`, the voiceover logic is:

```python
# Veo is silent, so generates voiceover if needed
if scene.get("subtitle_text"):
    # Generate and add voiceover
```

The comment says "Veo is silent", but **Veo 3.1 is NOT silent** - it generates videos with native speech when given a prompt with dialogue.

The fix is to **skip voiceover for Veo 3.1** videos.

### **Root Cause 2: Aggressive Trimming**

In `assemble_video.py`, there's likely a trimming loop that cuts videos to default durations from `config.SCENE_DURATIONS`:

```python
# Pseudocode of what's probably happening
for scene in scenes:
    target_duration = config.SCENE_DURATIONS[scene['type']]  # e.g., 4s
    trim_video(scene, target_duration)  # Cuts 15s video to 4s
```

The problem is that `config.SCENE_DURATIONS` was designed for **digital app videos** where:
- Hook = 4s
- App Demo = 4s
- etc.

But for **physical product videos**, the Veo 3.1 scenes are **8-15 seconds long** and should NOT be trimmed.

## **The Fixes Needed**

### **Fix 1: Skip Voiceover for Veo 3.1**

**File:** `C:\Users\dedam\.antigravity\UGC Engine SaaS\core_engine.py`

Add a check to skip voiceover for models with native audio:

```python
# Define models that generate audio natively
MODELS_WITH_NATIVE_AUDIO = {"veo-3.1-fast", "veo-3.1", "seedance-1.5-pro", "seedance-2.0"}

# In the physical_product_scene handling
if scene["type"] == "physical_product_scene":
    # ... Nano Banana + Veo generation ...
    
    # ✅ FIX: Only add voiceover if the model doesn't have native audio
    model_used = "veo-3.1-fast"  # or extract from scene/config
    if scene.get("subtitle_text") and model_used not in MODELS_WITH_NATIVE_AUDIO:
        # Generate and add voiceover
```

### **Fix 2: Don't Trim Physical Product Videos**

**File:** `C:\Users\dedam\.antigravity\UGC Engine SaaS\assemble_video.py`

Remove or skip the trimming loop for physical product scenes:

```python
# Before trimming
for scene in scenes:
    if scene.get("type") == "physical_product_scene":
        # ✅ FIX: Use actual video duration, don't trim
        continue
    else:
        # Trim digital app videos as before
        target_duration = config.SCENE_DURATIONS.get(scene['name'], 4)
        trim_video(scene, target_duration)
```

Or better yet, **remove the trimming entirely** and use the actual duration of each generated video.

## **Expected Results After Fix**

- ✅ Veo 3.1 videos retain their native audio (no duplicate voiceover)
- ✅ Videos are not trimmed (full 8-15 second scenes preserved)
- ✅ Final video is 15-30 seconds long (sum of all scenes)
- ✅ Subtitles and music are added correctly
