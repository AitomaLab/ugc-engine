# Veo 3.1 Prompt Enhancement - Temporal Consistency Design

## **Objective**

Design a new prompt structure for Veo 3.1 that eliminates mid-video character hallucinations by enforcing strict temporal consistency and anchoring the character identity to the reference image.

---

## **Problem Analysis**

**Root Cause:** The current Veo 3.1 prompts lack explicit instructions for temporal consistency, allowing the model to morph the character's identity during the animation process.

**Current Prompt Weaknesses:**
1.  **Generic Character Description:** Describes a generic person ("a 25-year-old female influencer") instead of referencing the specific person in the input image.
2.  **No Temporal Enforcement:** Does not instruct the model to maintain the same person throughout the video.
3.  **No Identity Anchoring:** Fails to anchor the character's identity to the reference image.
4.  **Incomplete Negative Prompt:** Prohibits anatomical errors but not identity-related errors (character morphing, face changes).

---

## **Design Principles**

### **1. Extreme Specificity**
Leave no room for ambiguity. Use strong, direct language to constrain the model's behavior.

### **2. Reference Image is Ground Truth**
The reference image is the single source of truth for the character's identity. The prompt should reinforce this, not compete with it.

### **3. Redundancy and Reinforcement**
Repeat critical instructions in different ways to ensure the model understands and prioritizes them.

### **4. Comprehensive Negative Prompts**
Explicitly prohibit all forms of character inconsistency, not just anatomical errors.

---

## **Enhanced Prompt Architecture**

### **Part 1: The Positive Prompt (Enforcement)**

#### **1.1. The Opening Anchor**
Start the prompt with an immediate, unambiguous instruction to use the person from the reference image.

**Example:**
```
A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image.
```

#### **1.2. The Critical Consistency Command**
Follow the anchor with a critical, all-caps instruction that defines the temporal consistency requirement.

**Example:**
```
CRITICAL: The person's identity, facial features, skin tone, hair, and body remain COMPLETELY IDENTICAL and CONSISTENT throughout the ENTIRE video from the first frame to the last frame.
```

#### **1.3. The Action Description**
Describe the action the person is performing, but do NOT describe the person's appearance.

**Example:**
```
The person is holding exactly one product bottle in their right hand, positioned at chest level between their face and the camera.
```

#### **1.4. The Reinforcement Clause**
End the prompt with a final reinforcement of the consistency requirement.

**Example:**
```
The person remains THE SAME INDIVIDUAL with NO CHANGES to their face, identity, or appearance at any point in the video.
```

---

### **Part 2: The Negative Prompt (Prohibition)**

#### **2.1. Anatomical Errors (Existing)**
Keep the existing negative prompts for anatomical errors.

**Example:**
```
extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, anatomical errors, multiple arms, distorted body, unnatural proportions, floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, artificial, CGI-looking, unnatural movements
```

#### **2.2. Identity Errors (New)**
Add a comprehensive list of negative prompts that prohibit all forms of character inconsistency.

**Example:**
```
character morphing, face morphing, different person, facial feature changes, identity switching, person changing, character inconsistency, multiple people, appearance changes, face changes, different face, changing identity, morphing person, switching characters
```

---

## **Complete Enhanced Prompt Template**

```python
def _build_scene_1_veo_prompt_enhanced(ctx):
    return (
        # 1.1. The Opening Anchor
        f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "
        
        # 1.2. The Critical Consistency Command
        f"CRITICAL: The person's identity, facial features, skin tone, hair, and body remain COMPLETELY IDENTICAL and CONSISTENT throughout the ENTIRE video from the first frame to the last frame. "
        
        # 1.3. The Action Description
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
        
        # 1.4. The Reinforcement Clause
        f"The person remains THE SAME INDIVIDUAL with NO CHANGES to their face, identity, or appearance at any point in the video. "
        
        # 2. The Negative Prompt
        f"NEGATIVE PROMPT: "
        # 2.1. Anatomical Errors
        f"extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements, "
        # 2.2. Identity Errors
        f"character morphing, face morphing, different person, facial feature changes, identity switching, "
        f"person changing, character inconsistency, multiple people, appearance changes, face changes, "
        f"different face, changing identity, morphing person, switching characters."
    )
```

---

## **Implementation**

This enhanced prompt structure should be implemented in `scene_builder.py` for all Veo 3.1 prompt generation functions (`_build_scene_1_veo_prompt`, `_build_scene_2_veo_prompt`, etc.).

### **Key Changes to Implement:**

1.  **Replace generic descriptions** with the new anchor and consistency commands.
2.  **Use gender-neutral pronouns** ("they", "their") to avoid conflicts.
3.  **Append the new identity-related negative prompts** to the existing negative prompt string.
4.  **Apply this structure to all scene-specific prompts** to ensure consistency across the entire video.

---

## **Expected Outcome**

By implementing this enhanced prompt design, Veo 3.1 will be forced to:

- ✅ **Prioritize the reference image** for character identity.
- ✅ **Maintain the same person** throughout the entire video.
- ✅ **Prevent character morphing** and identity switching.
- ✅ **Produce temporally consistent videos** with a single, stable character.

This design directly addresses the root cause of the mid-video hallucinations and is expected to resolve the issue with a high degree of confidence.
