## UGC Engine: Nano Banana Pro Prompt Generation Fix

## 1. Executive Summary

The UGC Engine is currently sending the wrong prompt format to the Nano Banana Pro API. It is sending a complex, multi-section video generation prompt (designed for Veo 3.1) instead of a simple, descriptive image composition prompt. This results in random, incorrect image outputs that do not use the provided influencer or product references.

This document provides a complete, standalone implementation plan to fix this critical issue. The fix involves creating a dedicated prompt generation function for Nano Banana Pro and modifying the core engine to use it for physical product video scenes.

---

## 2. Root Cause Analysis

The core problem lies in `scene_builder.py`. The `_generate_ultra_prompt` function creates a detailed video script prompt, which is then incorrectly passed to Nano Banana Pro. The system lacks a separate logic path for generating image composition prompts.

**Incorrect Prompt Sent:**
```json
{
  "prompt": "## 1. Core Concept\nAn authentic, high-energy, handheld smartphone selfie video..."
}
```

**Correct Prompt Required:**
```json
{
  "prompt": "A realistic photo of influencer Naiara holding a white bottle of conditioner in a cozy bedroom, looking at the camera."
}
```

Nano Banana Pro is an **image generation model**, not a video model. It requires a simple, descriptive prompt telling it *what image to create*, not a script telling it *what video to animate*.

---

## 3. Solution Architecture

The solution involves creating a new, dedicated prompt generation system for Nano Banana Pro and integrating it into the physical product workflow.

### System Components

1.  **New Prompt Generation Function (`_generate_nano_banana_prompt`):** A new function within `scene_builder.py` that creates a simple, descriptive prompt specifically for Nano Banana Pro.
2.  **Modified Core Engine (`core_engine.py`):** The main pipeline will be updated to differentiate between physical and digital products and call the correct prompt generation function.
3.  **Modified Worker (`ugc_worker/tasks.py`):** The Celery task will be updated to pass the `product_type` to the core engine.

### Data Flow

1.  The `generate_ugc_video` task in `ugc_worker/tasks.py` fetches the `product_type` from the job details.
2.  It passes the `product_type` and `product` details to `core_engine.run_generation_pipeline`.
3.  Inside `core_engine`, when generating scenes for a **physical product**, it calls the new `scene_builder._generate_nano_banana_prompt` function.
4.  This generates a simple, descriptive prompt.
5.  The correct prompt, along with the influencer and product image URLs, is sent to the `generate_scenes.generate_composite_image` function, which calls the Nano Banana Pro API.
6.  The correctly generated composite image is then passed to the Veo 3.1 API for animation.

---

## 4. Implementation Details

### Phase 1: Backend - New Prompt Generation Logic

#### 4.1 Create Nano Banana Pro Prompt Function

**File:** `scene_builder.py` (Add this new function)

```python
def _generate_nano_banana_prompt(influencer_name: str, product_description: str, scene_description: str) -> str:
    """
    Generates a simple, descriptive prompt for Nano Banana Pro image composition.

    Args:
        influencer_name (str): The name of the influencer.
        product_description (str): The visual description of the product.
        scene_description (str): A brief description of the scene (e.g., 'holding the product in a bedroom').

    Returns:
        str: A concise prompt for Nano Banana Pro.
    """
    prompt = (
        f"A realistic, high-quality photo of a female influencer named {influencer_name} {scene_description}. "
        f"She is holding a {product_description}. "
        f"The style is a natural, authentic, UGC-style selfie shot in a well-lit, casual environment. "
        f"The influencer is looking directly at the camera with a positive expression. "
        f"Ensure the product is clearly visible and held naturally."
    )
    return prompt
```

### Phase 2: Backend - Core Engine & Worker Integration

#### 4.2 Update Worker Task

**File:** `ugc_worker/tasks.py` (Modify `generate_ugc_video` function)

```python
# Inside generate_ugc_video, after fetching job data:

# ... existing code to fetch job, influencer, script ...

# NEW: Fetch product data if it's a physical product job
product_dict = None
product_type = job.get("product_type", "digital") # Default to digital

if product_type == "physical" and job.get("product_id"):
    product_result = sb.table("products").select("*").eq("id", job["product_id"]).execute()
    if product_result.data:
        product_dict = product_result.data[0]
        print(f"      📦 Physical Product found: {product_dict['name']}")
    else:
        print(f"      ⚠️ Physical Product ID {job['product_id']} not found!")

# ... existing code ...

# In the call to core_engine.run_generation_pipeline:
final_video_path = core_engine.run_generation_pipeline(
    project_name=project_name,
    influencer=influencer_dict,
    app_clip=app_clip_dict, # This will be None for physical products
    product=product_dict, # NEW: Pass the product dictionary
    product_type=product_type, # NEW: Pass the product type
    fields=fields,
    status_callback=status_callback,
    skip_music=False,
)
```

#### 4.3 Update Core Engine Pipeline

**File:** `core_engine.py` (Modify `run_generation_pipeline`)

```python
# Update function signature
def run_generation_pipeline(
    project_name: str,
    influencer: dict,
    fields: dict,
    product_type: str = "digital", # NEW
    app_clip: dict = None, # Optional
    product: dict = None, # NEW, Optional
    status_callback=None,
    skip_music: bool = False
):
    # ...
    # 1. Build scene structure
    scenes = scene_builder.build_scenes(fields, influencer, app_clip, product, product_type) # Pass new args

    # ...
    # 2. Generate all scene videos
    for i, scene in enumerate(scenes, 1):
        # ...
        if scene["type"] == "physical_product_scene": # NEW SCENE TYPE
            # This is the new two-step process for physical products
            composite_image_url = generate_scenes.generate_composite_image(
                scene=scene,
                influencer=influencer,
                product=product
            )
            
            # Now animate the composite image
            video_paths.append(generate_scenes.animate_image(
                image_url=composite_image_url,
                scene=scene
            ))
        elif scene["type"] == "veo":
            # Existing digital product logic
            # ...
```

#### 4.4 Update Scene Builder

**File:** `scene_builder.py` (Modify `build_scenes` and add new logic)

```python
# Update function signature
def build_scenes(fields, influencer, app_clip, product, product_type):
    # ...
    if product_type == "physical":
        return _build_physical_product_scenes(fields, influencer, product)
    else:
        # Existing digital product logic
        # ...

def _build_physical_product_scenes(fields, influencer, product):
    """Builds scenes for a physical product video."""
    scenes = []
    script = fields.get("Hook", "Check this out!")
    # For a 15s video, we might have 2-3 scenes
    scene_descriptions = [
        "holding the product up close to the camera with an excited expression",
        "demonstrating the product's texture on her hand",
        "smiling and giving a thumbs-up with the product in the foreground"
    ]

    for i, desc in enumerate(scene_descriptions):
        # Generate the CORRECT prompt for Nano Banana
        nano_banana_prompt = _generate_nano_banana_prompt(
            influencer_name=influencer["name"],
            product_description=product["visual_description"].get("visual_description", "the product"),
            scene_description=desc
        )

        scenes.append({
            "name": f"physical_scene_{i+1}",
            "type": "physical_product_scene", # NEW TYPE
            "nano_banana_prompt": nano_banana_prompt, # CORRECT PROMPT
            "video_animation_prompt": script, # The script is for the video animation part
            "reference_image_url": influencer["reference_image_url"],
            "product_image_url": product["image_url"],
            "target_duration": 5, # Each scene is 5s for a 15s total
            "subtitle_text": script.split('.')[i] if len(script.split('.')) > i else script,
            "voice_id": influencer["elevenlabs_voice_id"],
        })
    return scenes
```

#### 4.5 Update Scene Generation Logic

**File:** `generate_scenes.py` (Add new functions)

```python
def generate_composite_image(scene: dict, influencer: dict, product: dict) -> str:
    """Calls Nano Banana Pro to generate a composite image."""
    print("   🖼️ Generating composite image with Nano Banana Pro...")
    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": scene["nano_banana_prompt"],
            "image_input": [
                scene["reference_image_url"],
                scene["product_image_url"]
            ],
            "aspect_ratio": "9:16",
            "resolution": "1K"
        }
    }
    # ... [API call and polling logic similar to generate_video]
    # This function should return the URL of the generated image
    generated_image_url = poll_for_result(task_id)
    return generated_image_url

def animate_image(image_url: str, scene: dict) -> str:
    """Calls Veo 3.1 to animate a composite image."""
    print("   🎞️ Animating composite image with Veo 3.1...")
    # This will be similar to the existing generate_video function,
    # but it will use the composite image as the reference and the
    # 'video_animation_prompt' (the script) as the prompt.
    video_path = generate_video(
        prompt=scene["video_animation_prompt"],
        reference_image_url=image_url,
        model_api="veo-3.1-fast"
    )
    return video_path
```

---

## 5. Conclusion

This implementation introduces a clear distinction in the generation pipeline between digital and physical products. By creating a dedicated prompt generation function for Nano Banana Pro and a two-step (image composition -> video animation) workflow for physical products, the system will now correctly utilize the Nano Banana Pro API, resulting in accurate and high-quality composite images. This fix is essential for making the physical product feature functional and reliable.
