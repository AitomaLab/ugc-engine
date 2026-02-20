# Implementation Review Findings

## What Was Actually Implemented

### ✅ CORRECT: Physical Product Scenes

The code shows that `_build_physical_product_scenes` (lines 182-260) is correctly using the new simplified prompts:

```python
# Line 238-244: Correct implementation
if i == 0:
    visual_animation_prompt = _build_scene_1_veo_prompt(ctx, scene_script)
elif i == 1:
    visual_animation_prompt = _build_scene_2_veo_prompt(ctx, scene_script)
```

And the prompt builders (lines 102-178) are correctly implemented with script integration.

### ❌ PROBLEM: Digital Product Scenes Still Use Old Format

The markdown-formatted prompt comes from `_generate_ultra_prompt` (lines 298-349), which is used for **digital product videos** (15s and 30s flows).

**This function is called in:**
- `_build_15s` (line 360) - For digital app videos
- `_build_30s` (lines 412, 453, 467) - For digital app videos

---

## Root Cause Identified

**The error you're seeing is NOT from physical product videos - it's from digital product videos!**

Looking at the prompt you provided:

```json
{
  "prompt": "## 1. Core Concept\nAn authentic, high-energy, handheld smartphone selfie video...",
  "imageUrls": ["https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/influencer-images/naiara_reference.jpeg"]
}
```

This is the `_generate_ultra_prompt` format, which means:
1. You're testing with a **digital product** (not physical product)
2. OR the frontend is sending `product_type="digital"` instead of `product_type="physical"`
3. OR there's a routing issue in the backend

---

## The Issue

**The markdown-formatted prompt includes person-identifying information:**

```
{ctx['name']}, a {ctx['age']} {ctx['gender'].lower()} with {ctx['visuals']}
```

Example: "Naiara, a 25-year-old female with casual style"

**This triggers Veo 3.1's content moderation** because:
- It describes a specific person by name and demographics
- Combined with the reference image, Veo 3.1 thinks you're trying to generate a video of a real public figure
- The system blocks the request

---

## Solutions

### Option 1: Fix the Digital Product Prompt (Recommended)

Update `_generate_ultra_prompt` to remove person-identifying information and use the same approach as physical products.

### Option 2: Ensure Physical Product Flow is Used

Make sure the frontend is sending `product_type="physical"` for physical product videos, not `product_type="digital"`.

### Option 3: Check Routing Logic

Verify that `build_scenes` is correctly routing to `_build_physical_product_scenes` when `product_type="physical"`.

---

## Next Steps

1. Confirm whether you're testing with physical or digital products
2. If physical: Check why it's using the digital flow
3. If digital: Fix `_generate_ultra_prompt` to remove person-identifying information
