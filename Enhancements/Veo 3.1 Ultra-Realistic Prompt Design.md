# Veo 3.1 Ultra-Realistic Prompt Design

## **Objective**

Create Veo 3.1 prompts that generate **100% realistic, hallucination-free UGC videos** by adding strict physical, anatomical, and object constraints.

## **Current Prompt Analysis (Lines 157-168 in scene_builder.py)**

```python
visual_animation_prompt = (
    f"A realistic, high-quality, cinematic video of a {ctx['age']} {ctx['visuals']} "
    f"{ctx['gender'].lower()} influencer named {ctx['name']}. "
    f"The scene shows the upper body from the chest up. "
    f"{ctx['p']['subj']} is {desc}. "  # desc = "holding the product up close to the camera"
    f"The shot must be anatomically correct with exactly two arms and two hands visible. "
    f"The style is a natural, authentic, UGC-style shot in a well-lit, casual environment. "
    f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
    f"Ensure the product is clearly visible and held naturally. "
    f"High-fidelity, professional quality with realistic human proportions. "
    f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, deformed hands, mutated hands, anatomical errors, multiple arms, distorted body, unnatural proportions, blurry, low quality."
)
```

## **Identified Gaps**

### **1. No Product Constraints**
- ❌ Doesn't specify "exactly one product"
- ❌ No constraint on product duplication or merging
- ❌ No constraint on product position (can float)

### **2. No Physics Constraints**
- ❌ Doesn't prohibit floating objects
- ❌ No gravity constraints
- ❌ No hand-product interaction rules

### **3. Generic Scene Description**
- ❌ `{desc}` is too vague ("holding the product up close to the camera")
- ❌ Doesn't specify starting position
- ❌ Doesn't specify which hand holds the product
- ❌ Doesn't specify what the other hand is doing

### **4. Weak Negative Prompt**
- ❌ Focuses only on anatomical errors
- ❌ Doesn't mention object hallucinations
- ❌ Doesn't prohibit floating objects or duplicate products

## **Enhanced Prompt Architecture**

### **Core Principles:**

1. **Explicit Object Counting:** "exactly one product bottle"
2. **Physics Constraints:** "all objects obey gravity", "no floating objects"
3. **Hand-Product Binding:** "the product is held firmly in the [hand]"
4. **Temporal Consistency:** "the product remains in the same hand throughout"
5. **Scene-Specific Actions:** Detailed description of starting position and movement
6. **Comprehensive Negative Prompts:** Cover all hallucination types

### **Scene-Specific Prompt Templates:**

---

## **Scene 1: "Holding the Product Up Close to the Camera"**

### **Enhanced Prompt:**

```python
visual_animation_prompt = (
    f"A realistic, high-quality, authentic UGC video selfie of a {ctx['age']} {ctx['visuals']} "
    f"{ctx['gender'].lower()} influencer. "
    f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
    
    # EXACT STARTING POSITION
    f"The influencer is holding exactly one product bottle in her right hand, "
    f"positioned at chest level between her face and the camera. "
    f"The product label is facing the camera and clearly visible. "
    f"Her left hand is relaxed at her side or near her shoulder. "
    
    # ANATOMICAL CONSTRAINTS
    f"The shot shows exactly two arms and exactly two hands. "
    f"Both hands are anatomically correct with five fingers each. "
    
    # PRODUCT CONSTRAINTS
    f"There is exactly one product bottle in the scene. "
    f"The product is held firmly in the influencer's right hand throughout the entire video. "
    f"The product does not float, duplicate, merge, or change position unnaturally. "
    
    # PHYSICS CONSTRAINTS
    f"All objects obey gravity. No objects are floating in mid-air. "
    f"Natural hand-product interaction with realistic grip. "
    
    # EXPRESSION AND STYLE
    f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
    f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
    
    # COMPREHENSIVE NEGATIVE PROMPT
    f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
    f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
    f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
    f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
    f"artificial, CGI-looking, unnatural movements."
)
```

---

## **Scene 2: "Demonstrating the Product's Texture on Her Hand"**

### **Enhanced Prompt:**

```python
visual_animation_prompt = (
    f"A realistic, high-quality, authentic UGC video selfie of a {ctx['age']} {ctx['visuals']} "
    f"{ctx['gender'].lower()} influencer. "
    f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
    
    # EXACT STARTING POSITION
    f"The influencer is holding exactly one product bottle in her left hand at chest level. "
    f"She is using her right hand to apply product from the bottle, demonstrating the texture. "
    f"Her right hand shows a small amount of product (cream/conditioner) on the palm or fingers. "
    f"Both hands are clearly visible in the frame throughout the scene. "
    
    # ANATOMICAL CONSTRAINTS
    f"The shot shows exactly two arms and exactly two hands. "
    f"Both hands are anatomically correct with five fingers each. "
    f"The left hand holds the bottle, the right hand demonstrates the product. "
    
    # PRODUCT CONSTRAINTS
    f"There is exactly one product bottle in the scene, held in the left hand. "
    f"The product bottle remains in the left hand throughout the entire video and does not move, float, duplicate, or merge. "
    f"A small amount of product is visible on the right hand, applied naturally from the bottle. "
    
    # PHYSICS CONSTRAINTS
    f"All objects obey gravity. No objects are floating in mid-air. "
    f"Natural hand movements with realistic product application. "
    f"The product on the hand behaves like a real cream/conditioner texture. "
    
    # EXPRESSION AND STYLE
    f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
    f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
    
    # COMPREHENSIVE NEGATIVE PROMPT
    f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
    f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
    f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
    f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
    f"artificial, CGI-looking, unnatural movements, product floating, hands not holding product."
)
```

---

## **Implementation Strategy**

### **Step 1: Create Scene-Specific Prompt Functions**

Instead of using a generic `desc` variable, create dedicated prompt builders for each scene type:

```python
def _build_scene_1_veo_prompt(ctx):
    """Scene 1: Holding product up close to camera"""
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

def _build_scene_2_veo_prompt(ctx):
    """Scene 2: Demonstrating product texture on hand"""
    return (
        f"A realistic, high-quality, authentic UGC video selfie of a {ctx['age']} {ctx['visuals']} "
        f"{ctx['gender'].lower()} influencer. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The influencer is holding exactly one product bottle in her left hand at chest level. "
        f"She is using her right hand to apply product from the bottle, demonstrating the texture. "
        f"Her right hand shows a small amount of product (cream/conditioner) on the palm or fingers. "
        f"Both hands are clearly visible in the frame throughout the scene. "
        f"The shot shows exactly two arms and exactly two hands. "
        f"Both hands are anatomically correct with five fingers each. "
        f"The left hand holds the bottle, the right hand demonstrates the product. "
        f"There is exactly one product bottle in the scene, held in the left hand. "
        f"The product bottle remains in the left hand throughout the entire video and does not move, float, duplicate, or merge. "
        f"A small amount of product is visible on the right hand, applied naturally from the bottle. "
        f"All objects obey gravity. No objects are floating in mid-air. "
        f"Natural hand movements with realistic product application. "
        f"The product on the hand behaves like a real cream/conditioner texture. "
        f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements, product floating, hands not holding product."
    )
```

### **Step 2: Update _build_physical_product_scenes Function**

```python
# Replace the generic loop with scene-specific prompt generation
for i, desc in enumerate(scene_descriptions):
    # ... (nano_banana_prompt remains the same)
    
    # ✨ NEW: Use scene-specific prompt builders
    if i == 0:
        visual_animation_prompt = _build_scene_1_veo_prompt(ctx)
    elif i == 1:
        visual_animation_prompt = _build_scene_2_veo_prompt(ctx)
    else:
        # Fallback for additional scenes (if needed)
        visual_animation_prompt = _build_scene_1_veo_prompt(ctx)
    
    # ... (rest of the scene building logic)
```

## **Expected Results**

After implementing these ultra-realistic prompts:

✅ **No Floating Objects:** All objects obey gravity and are held by hands
✅ **No Extra Limbs:** Exactly two hands, two arms, anatomically correct
✅ **No Duplicate Products:** Exactly one product bottle per scene
✅ **No Merged Objects:** Products maintain consistency throughout
✅ **Ultra-Realistic:** Videos look like authentic, professional UGC content
✅ **Natural Movements:** Smooth, realistic hand-product interactions

## **Key Improvements Over Current Prompt**

| **Aspect** | **Current Prompt** | **Enhanced Prompt** |
|------------|-------------------|---------------------|
| Product Count | ❌ Not specified | ✅ "exactly one product bottle" |
| Product Position | ❌ "held naturally" (vague) | ✅ "held firmly in right/left hand" |
| Physics | ❌ Not mentioned | ✅ "all objects obey gravity, no floating" |
| Hand Specification | ❌ "two hands visible" | ✅ "right hand holds bottle, left hand at side" |
| Temporal Consistency | ❌ Not mentioned | ✅ "remains in same hand throughout" |
| Negative Prompt | ❌ Only anatomical errors | ✅ Anatomical + object + physics errors |
| Scene Description | ❌ Generic `{desc}` | ✅ Detailed starting position and action |

## **Summary**

The key to preventing hallucinations is **extreme specificity**:

1. **Count everything:** "exactly one", "exactly two"
2. **Specify positions:** "in the right hand", "at chest level"
3. **Add physics:** "obey gravity", "no floating"
4. **Bind objects to hands:** "held firmly", "remains in hand"
5. **Prohibit everything bad:** Comprehensive negative prompts

This approach leaves **zero room for the model to hallucinate** extra objects, limbs, or impossible physics.
