# Veo 3.1 Script Flow Analysis

## Current Flow (BROKEN)

### 1. Frontend → Backend
- User provides script in the frontend SaaS
- Script is sent to backend in the job creation request

### 2. Backend → scene_builder.py
```python
# Line 190: Tries to get the script from multiple keys
script = fields.get("Hook") or fields.get("Script") or fields.get("caption") or "Check this out!"
```

**Problem:** If the frontend sends the script under a different key (e.g., "script" lowercase), it falls back to "Check this out!"

### 3. scene_builder.py → Script Splitting
```python
# Lines 207-222: Splits the script into 2 parts for 2 scenes
sentences = re.split(r'(?<=[.!?])\s+', script)
if len(sentences) < 2:
    words = script.split()
    mid = len(words) // 2
    part1 = " ".join(words[:mid])
    part2 = " ".join(words[mid:])
else:
    mid = len(sentences) // 2
    part1 = " ".join(sentences[:mid])
    part2 = " ".join(sentences[mid:])
    
script_parts = [part1, part2]
```

**Result:** The script is split into `part1` and `part2`.

### 4. scene_builder.py → Scene Creation
```python
# Line 245: Assigns script part to scene
scene_script = script_parts[i] if i < len(script_parts) else ""

# Line 252: Stores in scene dict
scenes.append({
    "video_animation_prompt": visual_animation_prompt,  # ← VISUAL DESCRIPTION ONLY
    "subtitle_text": scene_script,                      # ← SCRIPT PART
    ...
})
```

**Critical Issue:** The script is stored in `subtitle_text`, but the Veo 3.1 prompt uses `video_animation_prompt`, which contains ONLY visual description, NOT the script!

### 5. generate_scenes.py → Veo 3.1 Call
```python
# Line 629: Gets the prompt
prompt = scene.get("video_animation_prompt") or scene.get("prompt")

# Line 631-635: Calls Veo 3.1
return generate_video_with_retry(
    prompt=prompt,  # ← VISUAL DESCRIPTION ONLY, NO SCRIPT!
    reference_image_url=image_url,
    model_api="veo-3.1-fast"
)
```

**Result:** Veo 3.1 receives ONLY the visual description, not the script. It cannot generate speech because it doesn't know what to say.

### 6. generate_video → Veo 3.1 API
```python
# Lines 105-112: Constructs Veo 3.1 payload
payload = {
    "prompt": prompt,  # ← VISUAL DESCRIPTION ONLY
    "model": model_api,
    "aspect_ratio": config.VIDEO_ASPECT_RATIO,
}
if reference_image_url:
    payload["imageUrls"] = [reference_image_url]
    payload["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"
```

**Final Result:** Veo 3.1 API receives a prompt with NO script, so it cannot generate audio/speech.

---

## Root Cause

**The `video_animation_prompt` contains ONLY visual description, NOT the script.**

The script is stored in `subtitle_text`, which is used for subtitle generation, but is NEVER passed to Veo 3.1.

---

## Solution

**The `video_animation_prompt` must include BOTH:**
1. Visual description (what the person is doing)
2. Script (what the person is saying)

Veo 3.1 needs to know what dialogue to generate audio for.

---

## Correct Prompt Structure

```python
def _build_scene_1_veo_prompt(ctx, script_part):
    """Scene 1: Holding product up close to camera"""
    return (
        # VISUAL DESCRIPTION
        f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The person is holding exactly one product bottle in their right hand at chest level. "
        f"They are looking directly at the camera with an enthusiastic expression. "
        
        # SCRIPT / DIALOGUE
        f"The person says: \"{script_part}\" "
        
        # CONSTRAINTS
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"NEGATIVE PROMPT: extra limbs, floating objects, character morphing, different person."
    )
```

This gives Veo 3.1 both the visual context AND the dialogue to generate.
