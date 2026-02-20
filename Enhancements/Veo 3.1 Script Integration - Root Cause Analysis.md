# Veo 3.1 Script Integration - Root Cause Analysis

## The Critical Mistake

**The system separates visual description from dialogue, but Veo 3.1 needs BOTH in the same prompt.**

### Current (Broken) Architecture:

```python
scenes.append({
    "video_animation_prompt": visual_animation_prompt,  # ← Visual only
    "subtitle_text": scene_script,                      # ← Script only
})
```

**Result:**
- Veo 3.1 receives: "A person holding a product..."
- Veo 3.1 does NOT receive: "The person says: 'Check out this amazing conditioner!'"
- Veo 3.1 generates: Silent video or generic background audio
- Subtitles show: The actual script (but no audio matches it)

### Why This Happened:

The original system was designed for **digital app videos** where:
1. Seedance generates the video with lip-sync
2. ElevenLabs generates a separate voiceover
3. The voiceover is overlaid on the video during assembly

For **physical product videos**, the system is using Veo 3.1, which:
1. Generates video AND audio together
2. Needs the dialogue in the prompt to generate matching audio
3. Does NOT use a separate voiceover overlay

**The architecture assumes separate audio generation, but Veo 3.1 does integrated audio generation.**

---

## Root Cause Summary

| Issue | Current Behavior | Correct Behavior |
|-------|-----------------|------------------|
| **Script Storage** | Stored in `subtitle_text` only | Must be in `video_animation_prompt` |
| **Veo 3.1 Prompt** | Visual description only | Visual description + dialogue |
| **Audio Generation** | Veo 3.1 has no script → no speech | Veo 3.1 has script → generates speech |
| **Subtitle Sync** | Subtitles don't match audio | Subtitles match generated audio |

---

## The Fix

**Modify `_build_scene_1_veo_prompt` and `_build_scene_2_veo_prompt` to accept the script as a parameter and include it in the prompt.**

### Before:
```python
def _build_scene_1_veo_prompt(ctx):
    return (
        f"A realistic, high-quality, authentic UGC video selfie..."
        # NO SCRIPT
    )
```

### After:
```python
def _build_scene_1_veo_prompt(ctx, script_part):
    return (
        f"A realistic, high-quality, authentic UGC video selfie..."
        f"The person says: \"{script_part}\" "
        # SCRIPT INCLUDED
    )
```

### In `_build_physical_product_scenes`:
```python
# Before:
visual_animation_prompt = _build_scene_1_veo_prompt(ctx)

# After:
scene_script = script_parts[i] if i < len(script_parts) else ""
visual_animation_prompt = _build_scene_1_veo_prompt(ctx, scene_script)
```

This ensures the script is passed to the prompt builder and included in the final Veo 3.1 prompt.
