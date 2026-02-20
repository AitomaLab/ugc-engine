# Veo 3.1 Prompt Enhancement Strategy

## **Current Issue: Anatomical Hallucinations**

The user reports that Veo 3.1 is generating extra limbs/hands in the second scene. This is a common issue with video generation models when prompts don't explicitly constrain anatomical features.

## **Current Veo 3.1 Prompt (Line 155-161 in scene_builder.py):**

```python
visual_animation_prompt = (
    f"A realistic, high-quality video of a {ctx['age']} {ctx['visuals']} "
    f"{ctx['gender'].lower()} influencer named {ctx['name']}. "
    f"{ctx['p']['subj']} is {desc}. The style is a natural, authentic, UGC-style shot in a "
    f"well-lit, casual environment. The influencer is looking directly at the camera with a positive, "
    f"{ctx['energy'].lower()} expression. Ensure the product is clearly visible and held naturally."
)
```

**Problems:**
1. No anatomical constraints
2. No negative prompt to prevent extra limbs
3. No quality/fidelity parameters
4. Too generic - doesn't specify exact body parts visible

## **Solution: Enhanced Prompt with Anatomical Constraints**

Similar to what we did for Nano Banana Pro, we need to add:

1. **Explicit Anatomical Constraints:**
   - "exactly two hands visible"
   - "exactly two arms"
   - "anatomically correct human body"
   
2. **Negative Prompt:**
   - "no extra limbs"
   - "no extra hands"
   - "no extra fingers"
   - "no deformed hands"
   - "no mutated hands"
   
3. **Quality Parameters:**
   - "high-quality"
   - "professional"
   - "realistic proportions"
   
4. **Specific Body Part Visibility:**
   - "upper body visible from chest up"
   - "both hands clearly visible holding the product"

## **Enhanced Prompt Template:**

```python
visual_animation_prompt = (
    f"A realistic, high-quality video of a {ctx['age']} {ctx['visuals']} "
    f"{ctx['gender'].lower()} influencer named {ctx['name']}. "
    f"{ctx['p']['subj']} is {desc}, with exactly two hands visible, exactly two arms, "
    f"and anatomically correct human body proportions. "
    f"Upper body visible from chest up. Both hands are clearly visible holding the product naturally. "
    f"The style is a natural, authentic, UGC-style shot in a well-lit, casual environment. "
    f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
    f"Professional quality with realistic human proportions. "
    f"NEGATIVE: no extra limbs, no extra hands, no extra fingers, no deformed hands, no mutated hands, "
    f"no anatomical errors, no multiple arms."
)
```

## **Additional Parameters to Pass to Veo 3.1 API:**

If the Veo 3.1 API supports negative prompts or quality parameters, we should also add:

```python
{
    "prompt": visual_animation_prompt,
    "negative_prompt": "extra limbs, extra hands, extra fingers, deformed hands, mutated hands, anatomical errors, multiple arms, distorted body, unnatural proportions",
    "quality": "high",
    "guidance_scale": 7.5,  # Higher guidance for better prompt adherence
}
```

## **Scene-Specific Enhancements:**

### **Scene 1: "holding the product up close to the camera"**
```python
"Upper body selfie shot showing the influencer's face and upper torso. "
"She is holding the product bottle with her right hand, positioned between her face and the camera. "
"Her left hand is visible at her side or near her shoulder. "
"Exactly two hands visible, exactly two arms. "
"The product label is clearly readable and facing the camera."
```

### **Scene 2: "demonstrating the product's texture on her hand"**
```python
"Upper body shot showing the influencer's face and both hands. "
"She is holding the product bottle in her left hand while applying product to her right hand. "
"Exactly two hands visible, exactly two arms. "
"Both hands are in frame, one holding the bottle, one showing the product texture. "
"Natural hand movements, anatomically correct fingers and palms."
```

## **Implementation:**

Update `scene_builder.py` line 155-161 with the enhanced prompt template, ensuring:
1. Explicit anatomical constraints for each scene
2. Scene-specific body part descriptions
3. Negative prompt elements embedded in the main prompt
4. Quality and realism keywords
