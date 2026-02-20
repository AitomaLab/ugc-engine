# Veo 3.1 Mid-Video Hallucination Analysis - CORRECTED

## **Critical Correction**

**Previous Misdiagnosis:** Nano Banana Pro was generating wrong characters  
**Actual Issue:** Nano Banana Pro generates CORRECT images, but Veo 3.1 introduces different people MID-VIDEO during animation

---

## **The Real Problem**

### **What's Happening:**

1. ✅ **Nano Banana Pro** generates composite image with **correct influencer**
2. ✅ **Veo 3.1** receives the correct composite image as reference
3. ❌ **Veo 3.1** starts animation with correct person
4. ❌ **Veo 3.1** HALLUCINATES and introduces **different people mid-video**
5. ❌ **Final video** shows character morphing/switching during the animation

---

## **Evidence from Videos**

### **Pattern Analysis:**

Looking at the 6 videos with this corrected understanding:

**Video 1:** 
- Starts with one person
- Mid-video: Character features change or different person appears
- Product handling becomes inconsistent

**Video 2:**
- Similar pattern of character morphing
- Facial features shift during animation
- Body proportions change mid-scene

**Video 3-6:**
- Consistent pattern across all videos
- Veo 3.1 is not maintaining temporal consistency
- The reference image is used at the start but not enforced throughout

---

## **Root Cause: Veo 3.1 Temporal Consistency Failure**

### **Why This Happens:**

Veo 3.1 uses **image-to-video** generation with **FIRST_AND_LAST_FRAMES_2_VIDEO** mode:

```python
"generationType": "FIRST_AND_LAST_FRAMES_2_VIDEO"
```

**The Problem:**

1. Veo 3.1 receives **only the first frame** (Nano Banana Pro output)
2. The model generates **intermediate frames** based on:
   - The reference image (first frame)
   - The text prompt (video_animation_prompt)
3. If the text prompt is too generic or doesn't enforce character consistency, Veo 3.1 will:
   - Start with the reference image
   - Gradually introduce hallucinations mid-video
   - Morph the character into a different person

### **Current Veo 3.1 Prompt Structure:**

**File:** `scene_builder.py` (Lines 102-154)

```python
def _build_scene_1_veo_prompt(ctx):
    return (
        f"A realistic, high-quality, authentic UGC video selfie of a {ctx['age']} {ctx['visuals']} "
        f"{ctx['gender'].lower()} influencer. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The influencer is holding exactly one product bottle in her right hand, "
        ...
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, ..."
    )
```

**The Problem with This Prompt:**

1. ❌ Describes a **generic person** ("25-year-old casual style female influencer")
2. ❌ Does NOT reference the **specific person in the input image**
3. ❌ Does NOT enforce **temporal consistency** (same person throughout)
4. ❌ Does NOT prohibit **character morphing or switching**

**Result:** Veo 3.1 starts with the reference image but gradually morphs the character based on the generic text description.

---

## **Why the Negative Prompt Isn't Enough**

The current negative prompt focuses on **anatomical errors**:
```
"extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, 
anatomical errors, multiple arms, distorted body, unnatural proportions, 
floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, 
merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, 
artificial, CGI-looking, unnatural movements."
```

**What's Missing:**
- ❌ No mention of "character consistency"
- ❌ No mention of "same person throughout"
- ❌ No mention of "no character morphing"
- ❌ No mention of "no face changes"
- ❌ No mention of "maintain facial features"

---

## **The Solution**

### **1. Add Temporal Consistency to Positive Prompt**

The prompt must explicitly tell Veo 3.1 to:
- Use the **exact person from the reference image**
- Maintain **the same person throughout the entire video**
- Keep **facial features, skin tone, and appearance consistent**
- Prevent **character morphing or switching**

### **2. Add Character Consistency to Negative Prompt**

The negative prompt must explicitly prohibit:
- Character morphing
- Face changes
- Different person appearing
- Facial feature changes
- Identity switching

### **3. Use More Specific Character Anchoring**

Instead of describing a generic person, the prompt should:
- Reference the input image directly
- Describe the action, not the person
- Let the reference image define the character

---

## **Recommended Prompt Structure**

### **Enhanced Positive Prompt:**

```python
def _build_scene_1_veo_prompt(ctx):
    return (
        f"A realistic, high-quality, authentic UGC video selfie using the EXACT SAME PERSON from the reference image. "
        f"The person in the reference image remains the SAME PERSON throughout the entire video with consistent facial features, skin tone, hair, and appearance. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The person is holding exactly one product bottle in their right hand, positioned at chest level between their face and the camera. "
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
        f"CRITICAL: The person's identity, facial features, and appearance remain COMPLETELY CONSISTENT from the first frame to the last frame. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements, "
        f"character morphing, face changes, different person, facial feature changes, identity switching, "
        f"person changing, character inconsistency, multiple people, face morphing, appearance changes."
    )
```

### **Key Changes:**

1. ✅ **"using the EXACT SAME PERSON from the reference image"** - Anchors to reference
2. ✅ **"remains the SAME PERSON throughout the entire video"** - Enforces temporal consistency
3. ✅ **"consistent facial features, skin tone, hair, and appearance"** - Specifies what to maintain
4. ✅ **"CRITICAL: The person's identity...remain COMPLETELY CONSISTENT"** - Strong emphasis
5. ✅ **Negative prompt additions:** "character morphing, face changes, different person, facial feature changes, identity switching, person changing, character inconsistency, multiple people, face morphing, appearance changes"

---

## **Additional Recommendations**

### **1. Increase Veo 3.1 Inference Steps (If Available)**

If the Veo 3.1 API supports inference steps or quality settings, increase them to improve temporal consistency.

### **2. Use Shorter Video Durations**

Longer videos (8-15 seconds) give Veo 3.1 more opportunity to hallucinate. Consider:
- Splitting into shorter clips (4-6 seconds each)
- Stitching them together in post-processing

### **3. Add Frame Consistency Checks (Advanced)**

If possible, extract frames from the generated video and verify that the person remains consistent using face recognition.

---

## **Conclusion**

The character consistency issue is caused by **Veo 3.1 mid-video hallucinations**, not Nano Banana Pro. The fix requires:

1. **Enhanced prompts** with explicit temporal consistency instructions
2. **Expanded negative prompts** to prohibit character morphing
3. **Character anchoring** to the reference image throughout the video

This is a prompt engineering fix, not a code architecture change.
