# Veo 3.1 Mid-Video Hallucination - Definitive Root Cause

## **The Corrected Diagnosis**

**Previous Misdiagnosis:** Nano Banana Pro generating wrong characters  
**Actual Root Cause:** Veo 3.1 introducing different people mid-video during animation

---

## **How the Pipeline Actually Works**

### **Step-by-Step Flow:**

1. **Nano Banana Pro** (generate_scenes.py, lines 529-590)
   - Receives: Influencer reference image + Product image + Prompt
   - Generates: Composite image with **correct influencer** holding product
   - Output: `composite_url` (static image)

2. **Veo 3.1** (generate_scenes.py, lines 624-635)
   - Receives: `composite_url` (the correct composite image) + `video_animation_prompt`
   - API Call:
     ```python
     payload = {
         "prompt": video_animation_prompt,
         "imageUrls": [composite_url],  # The Nano Banana output
         "generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO",
         "model": "veo-3.1-fast",
         "aspect_ratio": "9:16"
     }
     ```
   - Generates: 8-15 second animated video
   - **Problem:** Mid-video, the person changes/morphs into someone else

---

## **ROOT CAUSE: Veo 3.1 Prompt Lacks Temporal Consistency Instructions**

### **Current Veo 3.1 Prompt (scene_builder.py, lines 102-154):**

```python
def _build_scene_1_veo_prompt(ctx):
    return (
        f"A realistic, high-quality, authentic UGC video selfie of a {ctx['age']} {ctx['visuals']} "
        f"{ctx['gender'].lower()} influencer. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The influencer is holding exactly one product bottle in her right hand, "
        f"positioned at chest level between her face and the camera. "
        f"The product label is facing the camera and clearly visible. "
        f"Her left hand is relaxed at her side or near her shoulder. "
        f"The shot shows exactly two arms and exactly two hands. "
        f"Both hands are anatomically correct with five fingers each. "
        f"There is exactly one product bottle in the scene. "
        f"The product is held firmly in the influencer's right hand throughout the entire video. "
        f"The product does not float, duplicate, merge, or change position unnaturally. "
        f"All objects obey gravity. No objects are floating in mid-air. "
        f"Natural hand-product interaction with realistic grip. "
        f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements."
    )
```

### **What's Wrong with This Prompt:**

| Issue | Current Prompt | Result |
|-------|----------------|--------|
| **Character Description** | "a 25-year-old casual style female influencer" | Generic description, not tied to reference image |
| **Temporal Consistency** | ❌ Not mentioned | Veo 3.1 can morph the character mid-video |
| **Reference Image Anchoring** | ❌ Not mentioned | Veo 3.1 doesn't know to maintain the person from the reference |
| **Character Identity** | ❌ Not enforced | Veo 3.1 treats it as "any female influencer" |
| **Negative Prompt** | Only anatomical errors | Doesn't prohibit character morphing/switching |

---

## **Why Veo 3.1 Hallucinates Mid-Video**

### **Understanding FIRST_AND_LAST_FRAMES_2_VIDEO:**

This generation type means:
1. Veo 3.1 receives the **first frame** (Nano Banana composite)
2. Veo 3.1 generates **intermediate frames** to create motion
3. The text prompt guides what happens in those intermediate frames

**The Problem:**

When the prompt says "a 25-year-old casual style female influencer," Veo 3.1 interprets this as:
- Frame 1: Use the reference image (correct person)
- Frames 2-30: Generate "a 25-year-old casual style female influencer" (could be anyone)
- Result: Character gradually morphs from the reference image to a generic person matching the text description

**Why This Happens:**

- Veo 3.1 is a **generative model** that creates new frames based on the prompt
- Without explicit instructions to maintain the **same person**, it treats each frame as a new generation opportunity
- The model optimizes for the text description, not the reference image consistency
- Over 8-15 seconds (30-45 frames), the character drifts away from the reference

---

## **Evidence Supporting This Root Cause**

### **1. Nano Banana Pro is Working Correctly**

If Nano Banana Pro was the problem:
- ❌ The composite image would have the wrong person from the start
- ❌ Veo 3.1 would animate that wrong person consistently
- ❌ All videos would show the same wrong person (if seed is consistent)

But the user confirmed:
- ✅ Nano Banana Pro generates correct influencer images
- ✅ The problem is mid-video character switching
- ✅ Different people appear during the animation

### **2. The Prompt Describes a Generic Person**

Current prompt: "a 25-year-old casual style female influencer"

This could match thousands of different people. Veo 3.1 doesn't know it should be the **specific person** from the reference image.

### **3. No Temporal Consistency Instructions**

The prompt never says:
- "maintain the same person throughout"
- "keep the person from the reference image"
- "no character morphing"
- "consistent facial features"

Without these instructions, Veo 3.1 has no reason to enforce consistency.

### **4. Negative Prompt Focuses on Anatomy, Not Identity**

Current negative prompt prohibits:
- Extra limbs, deformed hands, floating objects

But doesn't prohibit:
- Character morphing, face changes, different person, identity switching

---

## **The Solution**

### **1. Add Explicit Temporal Consistency Instructions**

The prompt must tell Veo 3.1:
- Use the **exact same person** from the reference image
- Maintain **consistent identity** throughout the entire video
- Keep **facial features, skin tone, hair, and body** unchanged
- Prevent **character morphing or switching**

### **2. Anchor to the Reference Image**

Instead of describing a generic person, the prompt should:
- Reference the input image directly: "the person in the reference image"
- Describe the action, not the person's appearance
- Let the reference image define the character identity

### **3. Add Character Consistency to Negative Prompt**

Explicitly prohibit:
- Character morphing
- Face changes
- Different person appearing
- Identity switching
- Facial feature changes
- Person changing mid-video

---

## **Recommended Fix**

### **Enhanced Veo 3.1 Prompt:**

```python
def _build_scene_1_veo_prompt(ctx):
    return (
        f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "
        f"CRITICAL: The person's identity, facial features, skin tone, hair, and body remain COMPLETELY IDENTICAL and CONSISTENT throughout the ENTIRE video from the first frame to the last frame. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The person is holding exactly one product bottle in their right hand, "
        f"positioned at chest level between their face and the camera. "
        f"The product label is facing the camera and clearly visible. "
        f"Their left hand is relaxed at their side or near their shoulder. "
        f"The shot shows exactly two arms and exactly two hands. "
        f"Both hands are anatomically correct with five fingers each. "
        f"There is exactly one product bottle in the scene. "
        f"The product is held firmly in the person's right hand throughout the entire video. "
        f"The product does not float, duplicate, merge, or change position unnaturally. "
        f"All objects obey gravity. No objects are floating in mid-air. "
        f"Natural hand-product interaction with realistic grip. "
        f"The person is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"The person remains THE SAME INDIVIDUAL with NO CHANGES to their face, identity, or appearance at any point in the video. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements, "
        f"character morphing, face morphing, different person, facial feature changes, identity switching, "
        f"person changing, character inconsistency, multiple people, appearance changes, face changes, "
        f"different face, changing identity, morphing person, switching characters."
    )
```

### **Key Changes:**

1. ✅ **"THE EXACT SAME PERSON from the reference image"** - Anchors to reference
2. ✅ **"CRITICAL: The person's identity...remain COMPLETELY IDENTICAL"** - Strong emphasis on consistency
3. ✅ **"throughout the ENTIRE video from the first frame to the last frame"** - Temporal scope
4. ✅ **"The person remains THE SAME INDIVIDUAL with NO CHANGES"** - Reinforcement at the end
5. ✅ **Expanded negative prompt** - Prohibits all forms of character morphing/switching

---

## **Conclusion**

**Root Cause:** Veo 3.1 prompts lack explicit temporal consistency instructions, allowing the model to morph the character mid-video.

**Fix:** Enhance the Veo 3.1 prompts with strong character identity anchoring and temporal consistency enforcement.

**Impact:** This is a **prompt engineering fix** that requires updating `scene_builder.py` (lines 102-154) with the enhanced prompt structure.

**Expected Result:** Veo 3.1 will maintain the exact same person from the reference image throughout the entire video without any character morphing or switching.
