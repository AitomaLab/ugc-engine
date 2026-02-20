# Veo 3.1 Correct Prompt Structure with Script Integration

## Design Principles

1. **Include the script/dialogue in the Veo 3.1 prompt** - This is how Veo 3.1 knows what audio to generate
2. **Keep visual descriptions clear and specific** - Prevent hallucinations
3. **Maintain temporal consistency instructions** - Prevent character morphing
4. **Use natural language format** - Compatible with Veo 3.1 API

---

## Prompt Template Structure

```
[VISUAL DESCRIPTION] + [DIALOGUE] + [CONSTRAINTS] + [NEGATIVE PROMPT]
```

### Example for Scene 1:

```
A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. The person's identity, facial features, skin tone, hair, and body remain completely identical and consistent throughout the entire video. Upper body shot from chest up, filmed in a well-lit, casual home environment. The person is holding exactly one product bottle in their right hand at chest level, with the product label facing the camera. They are looking directly at the camera with an enthusiastic expression. The person says: "Okay, you guys have to try this Flakes moisturizing conditioner! It's seriously a game changer for dry hair." Natural, authentic UGC-style movements. Professional quality with realistic human proportions. NEGATIVE PROMPT: extra limbs, extra hands, floating objects, character morphing, different person.
```

---

## Implementation

### Step 1: Modify Function Signatures

**Add `script_part` parameter to both prompt builders:**

```python
def _build_scene_1_veo_prompt(ctx, script_part):
    """Scene 1: Holding product up close to camera"""
    
def _build_scene_2_veo_prompt(ctx, script_part):
    """Scene 2: Demonstrating product texture on hand"""
```

### Step 2: Include Script in Prompt

**Add the dialogue section to the prompt:**

```python
def _build_scene_1_veo_prompt(ctx, script_part):
    return (
        # VISUAL DESCRIPTION
        f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "
        f"The person's identity, facial features, skin tone, hair, and body remain completely identical and consistent throughout the entire video. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The person is holding exactly one product bottle in their right hand at chest level, with the product label facing the camera. "
        f"They are looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
        
        # DIALOGUE (THE CRITICAL ADDITION)
        f"The person says: \"{script_part}\" "
        
        # CONSTRAINTS
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"The person remains the same individual with no changes to their face or appearance. "
        
        # NEGATIVE PROMPT
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, floating objects, duplicate products, "
        f"character morphing, face morphing, different person, facial feature changes."
    )
```

### Step 3: Pass Script to Prompt Builders

**In `_build_physical_product_scenes`, pass the script part when calling the prompt builders:**

```python
# BEFORE (line 237-243):
if i == 0:
    visual_animation_prompt = _build_scene_1_veo_prompt(ctx)
elif i == 1:
    visual_animation_prompt = _build_scene_2_veo_prompt(ctx)

# AFTER:
scene_script = script_parts[i] if i < len(script_parts) else ""

if i == 0:
    visual_animation_prompt = _build_scene_1_veo_prompt(ctx, scene_script)
elif i == 1:
    visual_animation_prompt = _build_scene_2_veo_prompt(ctx, scene_script)
```

---

## Expected Behavior After Fix

### Veo 3.1 Prompt Will Contain:

```json
{
  "prompt": "A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image... The person says: \"Okay, you guys have to try this Flakes moisturizing conditioner!\" ...",
  "imageUrls": ["https://..."],
  "model": "veo3_fast",
  "aspect_ratio": "9:16",
  "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO"
}
```

### Veo 3.1 Will Generate:

1. ✅ **Visual animation** matching the description
2. ✅ **Audio/speech** saying the script dialogue
3. ✅ **Lip movements** synchronized with the audio
4. ✅ **Character consistency** throughout the video

### Subtitle System Will:

1. ✅ Transcribe the generated audio using OpenAI Whisper
2. ✅ Generate word-level timestamps
3. ✅ Burn subtitles that match the actual spoken dialogue

---

## Why This Works

**Veo 3.1 is a multimodal model that generates video + audio together.** When you include dialogue in the prompt:

- The visual description tells it what to show
- The dialogue tells it what audio to generate
- The model creates a cohesive video where the person appears to be speaking the dialogue

This is fundamentally different from the digital app flow where audio is generated separately and overlaid.
