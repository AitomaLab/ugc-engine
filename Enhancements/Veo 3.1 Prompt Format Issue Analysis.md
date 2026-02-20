# Veo 3.1 Prompt Format Issue Analysis

## The Problem

**Veo 3.1 is receiving the OLD markdown-formatted prompt instead of the NEW simplified prompt.**

### Prompt Sent to Veo 3.1:

```
## 1. Core Concept
An authentic, high-energy, handheld smartphone selfie video...

## 2. Visual Style
- **Camera**: Close-up shot...

## 3. Performance - Visual
- **Eye Contact**: CRITICAL: The person MUST maintain...

## 4. Performance - Vocal
- **Language**: Natural, conversational...

## 5. Script
"Check this out!"

## 6. Technical Specifications
Vertical 9:16, handheld (fixed_lens: false).
```

### Expected Prompt (What We Implemented):

```
A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. The person's identity, facial features, skin tone, hair, and body remain completely identical and consistent throughout the entire video. Upper body shot from chest up, filmed in a well-lit, casual home environment. The person is holding exactly one product bottle in their right hand at chest level... The person says: "Check this out!" Natural, authentic UGC-style movements...
```

---

## Why This Is Happening

**Possible Causes:**

1. **Antigravity did NOT implement the fix** - The code changes were not applied
2. **Wrong function is being called** - There's another prompt builder that's being used
3. **Cache issue** - Old code is still running
4. **Different code path** - Physical product scenes are using a different flow

---

## The "Prominent Public Figure" Error

**Error:** `Request blocked: The input content was flagged for containing a prominent public figure.`

**Why This Happens:**

The markdown-formatted prompt includes phrases like:
- "The person, a 25-year-old female with casual style"
- "Castilian Spanish (Spain)"
- Detailed performance instructions

These descriptions, combined with the reference image, may trigger Veo 3.1's content moderation system to think you're trying to generate a video of a real public figure.

**The Fix:**

The simplified prompt avoids this by:
- NOT describing the person's demographics
- Anchoring to "THE EXACT SAME PERSON from the reference image"
- Focusing on actions, not identity

---

## Next Steps

1. Pull the latest code from the repository
2. Check if `_build_scene_1_veo_prompt` and `_build_scene_2_veo_prompt` were actually updated
3. Identify where the markdown-formatted prompt is coming from
4. Provide corrected implementation instructions
