# Digital Product Prompt Fix Design

## Objective

Update `_generate_ultra_prompt` to remove person-identifying information that triggers Veo 3.1's content moderation system.

---

## Current Problem

**Current Prompt Structure:**

```python
f"## 1. Core Concept\n"
f"An authentic, high-energy, handheld smartphone selfie video. {ctx['name']}, a {ctx['age']} {ctx['gender'].lower()} with {ctx['visuals']}, is excitedly sharing an amazing discovery.\n\n"
```

**Issues:**
1. Includes person's name: `{ctx['name']}`
2. Includes demographics: `{ctx['age']} {ctx['gender'].lower()} with {ctx['visuals']}`
3. Triggers content moderation: "prominent public figure" error

---

## Solution Design

### Approach 1: Remove Person-Identifying Information (Recommended)

**Replace:**
```python
f"{ctx['name']}, a {ctx['age']} {ctx['gender'].lower()} with {ctx['visuals']}, is excitedly sharing an amazing discovery.\n\n"
```

**With:**
```python
f"THE EXACT SAME PERSON from the reference image is excitedly sharing an amazing discovery.\n\n"
```

**Benefits:**
- Anchors to the reference image (like physical product prompts)
- Removes all person-identifying information
- Avoids content moderation flags
- Maintains temporal consistency

### Approach 2: Simplify to Natural Language (More Radical)

Replace the entire markdown structure with a simplified, natural language prompt similar to physical products.

**Benefits:**
- Consistent with physical product prompts
- More compatible with Veo 3.1 API
- Removes all structured formatting

**Drawbacks:**
- Requires more extensive changes
- May affect digital product video quality

---

## Recommended Fix

**Update `_generate_ultra_prompt` (lines 298-349) to remove person-identifying information while keeping the rest of the structure intact.**

### Changes:

**Line 329 - Remove person identification:**

```python
# BEFORE:
f"An authentic, high-energy, handheld smartphone selfie video. {ctx['name']}, a {ctx['age']} {ctx['gender'].lower()} with {ctx['visuals']}, is excitedly sharing an amazing discovery.\n\n"

# AFTER:
f"An authentic, high-energy, handheld smartphone selfie video. THE EXACT SAME PERSON from the reference image is excitedly sharing an amazing discovery.\n\n"
```

**Line 336 - Remove person's name:**

```python
# BEFORE:
f"- **Eye Contact**: CRITICAL: {ctx['name']} MUST maintain direct eye contact with the lens throughout.\n"

# AFTER:
f"- **Eye Contact**: CRITICAL: The person MUST maintain direct eye contact with the lens throughout.\n"
```

---

## Expected Results

After this fix:
- ✅ Veo 3.1 will not flag the content for "prominent public figure"
- ✅ The prompt will anchor to the reference image
- ✅ Digital product videos will generate successfully
- ✅ Character consistency will be maintained

---

## Alternative: Check Product Type Routing

If you're testing physical products, ensure the frontend is sending `product_type="physical"` so the correct flow is used.
