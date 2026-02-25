# Antigravity Implementation Guide: Cinematic Product Shots (v2)

**Author:** Manus AI
**Date:** February 25, 2026
**Version:** 2.0

**Feature Summary:** This guide details a revised, two-phase architecture for integrating cinematic product shots into the UGC Engine. The user first generates still product images in the Library, then selectively animates them into video clips. These final video clips can then be included as scenes in the main UGC video creation pipeline on the Create page.

This new architecture decouples image generation from video animation and integrates the final cinematic shots into the existing `core_engine.py` pipeline, a significant change from the v1 proposal.

---

## Table of Contents

1.  [Revised Architecture Overview](#1-revised-architecture-overview)
2.  [Database: New Table & Migration](#2-database-new-table--migration)
3.  [Backend: New Prompts Module](#3-backend-new-prompts-module)
4.  [Backend: New Generation Functions](#4-backend-new-generation-functions)
5.  [Backend: New Celery Worker Tasks](#5-backend-new-celery-worker-tasks)
6.  [Backend: New API Endpoints](#6-backend-new-api-endpoints)
7.  [Backend: Core Engine Integration](#7-backend-core-engine-integration)
8.  [Backend: Cost Service Update](#8-backend-cost-service-update)
9.  [Frontend: Types & API Hooks](#9-frontend-types--api-hooks)
10. [Frontend: Library UI Overhaul](#10-frontend-library-ui-overhaul)
11. [Frontend: Create Page Integration](#11-frontend-create-page-integration)
12. [SEALCaM Prompt Engineering Reference](#12-sealcam-prompt-engineering-reference)
13. [Cinematic Shot Type Catalog](#13-cinematic-shot-type-catalog)
14. [End-to-End Flow Summary](#14-end-to-end-flow-summary)

---

## 1. Revised Architecture Overview

This feature is now broken into two distinct user-facing phases, which requires a more integrated but flexible backend architecture.

**Phase 1: Asset Generation (Library)**

1.  **Generate Stills:** From the Library Products tab, the user clicks a new "Generate Shots" button on a product card. A modal appears, allowing them to select a *Shot Type* (e.g., Hero, Macro) and number of variations.
2.  **Image Generation Task:** This triggers a new API endpoint that dispatches a Celery task (`generate_product_shot_image`). The task uses the SEALCaM framework to generate a still image with Nano Banana Pro.
3.  **Animate Stills:** The generated still images appear in a new gallery section under the product. Each still image has an "Animate" button.
4.  **Video Animation Task:** Clicking "Animate" triggers another new API endpoint that dispatches a second Celery task (`animate_product_shot`). This task takes the still image and uses Veo 3.1 to generate a short, animated video clip.

**Phase 2: Video Composition (Create Page)**

1.  **Select Product:** On the `/create` page, when the user selects a Physical Product, a new UI section appears below the product selector.
2.  **Include Cinematic Shots:** This new section displays the *animated* cinematic shots available for the selected product. The user can select one or more of these shots to include in their final video.
3.  **Scene Building:** The IDs of the selected cinematic shots are passed to the `/jobs` endpoint. The `scene_builder.py` module is modified to fetch these video URLs and insert them as a new scene type (`cinematic_shot`) into the scene list, alongside the standard influencer-holding-product scenes.
4.  **Final Assembly:** The `core_engine.py` pipeline processes this mixed list of scenes, assembling a final video that combines both AI influencer footage and the pre-rendered cinematic product shots.

### File Impact Summary

| File | Action | Purpose |
|:---|:---:|:---|
| `ugc_db/migrations/007_add_product_shots.sql` | **NEW** | Creates the `product_shots` table with status tracking. |
| `ugc_db/db_manager.py` | **MODIFY** | Add CRUD functions for the new `product_shots` table. |
| `prompts/cinematic_shots.py` | **NEW** | Contains SEALCaM prompt builders for Nano Banana Pro (stills). |
| `generate_scenes.py` | **MODIFY** | Add `generate_cinematic_product_image` and `animate_product_shot` functions. |
| `ugc_worker/tasks.py` | **MODIFY** | Add two new Celery tasks: `generate_product_shot_image` and `animate_product_shot`. |
| `ugc_backend/main.py` | **MODIFY** | Add new API endpoints for generating, animating, and listing shots. Modify `/jobs` endpoint. |
| `scene_builder.py` | **MODIFY** | Integrate cinematic shots into the main scene building logic. |
| `core_engine.py` | **MODIFY** | Handle the new `cinematic_shot` scene type during assembly. |
| `ugc_backend/cost_service.py` | **MODIFY** | Add separate cost estimations for image generation and animation. |
| `frontend/src/lib/types.ts` | **MODIFY** | Add `ProductShot` interface. |
| `frontend/src/app/library/page.tsx` | **MODIFY** | Major overhaul to include shot generation modal and gallery. |
| `frontend/src/app/create/page.tsx` | **MODIFY** | Add UI for selecting and including cinematic shots in the final video. |

---

## 2. Database: New Table & Migration

A new table, `product_shots`, is required to store the generated assets and track their state.

**File:** `/home/ubuntu/ugc-engine/ugc_db/migrations/007_add_product_shots.sql`

```sql
-- 007_add_product_shots.sql
CREATE TABLE public.product_shots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES public.products(id) ON DELETE CASCADE,
    shot_type TEXT NOT NULL, -- e.g., 'hero', 'macro_detail', 'pedestal'
    status TEXT NOT NULL DEFAULT 'image_pending', -- image_pending, image_completed, animation_pending, animation_completed, failed
    image_url TEXT, -- URL of the still image from Nano Banana Pro
    video_url TEXT, -- URL of the animated video from Veo 3.1
    prompt TEXT, -- The SEALCaM prompt used for image generation
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE public.product_shots ENABLE ROW LEVEL SECURITY;

-- Create Policies
CREATE POLICY "Allow all for authenticated users" ON public.product_shots
    FOR ALL
    USING (auth.role() = 'authenticated');

-- Trigger to update 'updated_at' timestamp
CREATE TRIGGER handle_updated_at
    BEFORE UPDATE ON public.product_shots
    FOR EACH ROW
    EXECUTE PROCEDURE moddatetime (updated_at);
```

### DB Manager Updates

Add the corresponding CRUD functions to `db_manager.py`.

**File:** `/home/ubuntu/ugc-engine/ugc_db/db_manager.py`

```python
# Add after delete_product function

# ---------------------------------------------------------------------------
# CRUD Helpers — Product Shots
# ---------------------------------------------------------------------------

def list_product_shots(product_id: str):
    sb = get_supabase()
    result = sb.table("product_shots").select("*").eq("product_id", product_id).order("created_at", desc=True).execute()
    return result.data

def get_product_shot(shot_id: str):
    sb = get_supabase()
    result = sb.table("product_shots").select("*").eq("id", shot_id).execute()
    return result.data[0] if result.data else None

def create_product_shot(data: dict):
    sb = get_supabase()
    result = sb.table("product_shots").insert(data).execute()
    return result.data[0] if result.data else None

def update_product_shot(shot_id: str, data: dict):
    sb = get_supabase()
    result = sb.table("product_shots").update(data).eq("id", shot_id).execute()
    return result.data[0] if result.data else None
```

---

## 3. Backend: New Prompts Module

Create a new, dedicated prompts module for generating the SEALCaM prompts for still images.

**File:** `/home/ubuntu/ugc-engine/prompts/cinematic_shots.py`

```python
"""
SEALCaM Prompt builder for Cinematic Product Shots (Still Images).
Generates structured prompts for Nano Banana Pro.
"""

SHOT_TYPE_PROMPTS = {
    "hero": {
        "E": "a clean, minimalist studio setting with a single soft light source from the side",
        "A": "The product sits centered on a slightly reflective surface, casting a soft shadow.",
        "L": "dramatic, high-contrast studio lighting, with a key light creating sharp highlights and deep shadows, 8K, masterpiece",
        "Ca": "shot on a Sony A7S III with a 90mm macro lens, eye-level, centered composition",
    },
    "macro_detail": {
        "E": "a neutral, out-of-focus background that doesn't distract from the product texture",
        "A": "A bead of water slowly drips down the side of the product, highlighting its texture.",
        "L": "bright, clean, high-key lighting that reveals every micro-detail and texture, shot with a macro lens",
        "Ca": "extreme close-up, macro shot focusing on the texture of the product's surface, 45-degree angle",
    },
    "pedestal": {
        "E": "a simple, elegant pedestal or block that elevates the product",
        "A": "The product is presented on a pedestal, angled slightly to catch the light.",
        "L": "museum-quality lighting, with a spotlight from above creating a halo effect around the product",
        "Ca": "low-angle shot, looking up at the product to give it a sense of importance and scale",
    },
    "moody_dramatic": {
        "E": "a dark, textured background like slate or rough wood",
        "A": "The product emerges from the shadows, with only one side catching the light.",
        "L": "chiaroscuro lighting, with a single, harsh light source creating a dramatic interplay of light and shadow",
        "Ca": "side-on profile shot, with the camera positioned to capture the dramatic lighting effect",
    },
    "floating": {
        "E": "a zero-gravity environment with subtle, abstract light refractions in the background",
        "A": "The product floats weightlessly in the center of the frame, rotating slowly.",
        "L": "diffuse, ethereal lighting that seems to emanate from all around, eliminating harsh shadows",
        "Ca": "straight-on, eye-level shot, capturing the product as if suspended in mid-air",
    },
    "lifestyle": {
        "E": "a realistic, high-end bathroom counter with marble surfaces and other subtle, elegant props",
        "A": "The product is placed naturally amongst other bathroom items, ready for use.",
        "L": "soft, natural window light, as if from a large bathroom window in the morning",
        "Ca": "shot from a natural, slightly high angle, as if someone is about to pick it up and use it",
    },
}

def build_sealcam_prompt(shot_type: str, product: dict) -> str:
    """Builds a SEALCaM prompt for a given shot type and product."""
    if shot_type not in SHOT_TYPE_PROMPTS:
        raise ValueError(f"Invalid shot_type: {shot_type}")

    prompt_data = SHOT_TYPE_PROMPTS[shot_type]
    va = product.get("visual_description", {})
    product_desc = va.get("visual_description", product.get("name", "the product"))

    # SEALCaM Framework
    S = f"A cinematic product hero shot of {product_desc}."
    E = prompt_data["E"]
    A = prompt_data["A"]
    L = prompt_data["L"]
    Ca = prompt_data["Ca"]
    M = "photorealistic, hyper-detailed, 8K, octane render, trending on ArtStation, professional product photography"

    # Stringified YAML format
    return f"S: {S}\nE: {E}\nA: {A}\nL: {L}\nCa: {Ca}\nM: {M}"
```

---

## 4. Backend: New Generation Functions

Modify `generate_scenes.py` to add two new functions: one for generating the still image and one for animating it.

**File:** `/home/ubuntu/ugc-engine/generate_scenes.py`

```python
# Add at the end of the file, before the if __name__ == "__main__": block

def generate_cinematic_product_image(prompt: str, product_image_url: str, seed: int = None) -> str:
    """
    Calls Nano Banana Pro to generate a single cinematic still image.
    This is a simplified version of generate_composite_image, without the influencer.
    """
    print("   🖼️ Generating cinematic product image with Nano Banana Pro...")
    endpoint = f"{config.KIE_API_URL}/api/v1/jobs/createTask"
    negative_prompt = "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, (mutated hands and fingers:1.4), disconnected limbs, mutation, mutated, ugly, disgusting, blurry, amputation, human, person, character, people"

    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "image_input": [product_image_url],
            "aspect_ratio": "9:16",
            "resolution": "2K"
        }
    }
    if seed:
        payload["input"]["seed"] = seed

    resp = requests.post(endpoint, headers=config.KIE_HEADERS, json=payload)
    if resp.status_code != 200:
        raise RuntimeError(f"Nano Banana API error ({resp.status_code}): {resp.text[:500]}")

    result = resp.json()
    if result.get("code") != 200:
        raise RuntimeError(f"Nano Banana API error: {result.get('msg', str(result))}")

    task_id = result["data"]["taskId"]
    print(f"      Task: {task_id}")

    # Poll for completion
    poll_endpoint = f"{config.KIE_API_URL}/api/v1/jobs/recordInfo"
    for i in range(60):  # 10 minutes max
        time.sleep(10)
        try:
            resp = requests.get(poll_endpoint, headers=config.KIE_HEADERS, params={"taskId": task_id}, timeout=30)
            result = resp.json()
        except Exception as e:
            print(f"      ⚠️ Poll error: {e}")
            continue

        if result.get("code") != 200:
            continue

        data = result.get("data", {})
        state = data.get("state", "processing").lower()

        if state == "success":
            result_json = data.get("resultJson", "{}")
            if isinstance(result_json, str): result_json = json.loads(result_json)
            image_url = result_json.get("resultUrls", [None])[0]
            if image_url:
                print(f"      ✨ Cinematic Image ready! ({i * 10}s)")
                return image_url
        elif state == "fail":
            fail_msg = data.get("failMsg", "Unknown error")
            raise RuntimeError(f"Nano Banana generation failed: {fail_msg}")
        
        print(f"      ⏳ Composing cinematic image... ({i * 10}s)")

    raise RuntimeError("Cinematic image generation timed out")


def animate_product_shot(image_url: str, shot_type: str) -> str:
    """Calls Veo 3.1 to animate a still product shot."""
    print("   🎞️ Animating product shot with Veo 3.1...")
    
    # Simple motion prompts based on shot type
    motion_prompts = {
        "hero": "slowly push in on the product, subtle light glinting off the surface",
        "macro_detail": "pan slowly across the texture of the product, revealing fine details",
        "pedestal": "camera slowly orbits the product on the pedestal, 360-degree view",
        "moody_dramatic": "light source slowly moves, causing shadows to shift dramatically across the product",
        "floating": "product rotates slowly in zero-gravity, with subtle lens flares appearing",
        "lifestyle": "camera performs a very slow, subtle zoom-in on the product in its setting",
    }
    
    prompt = motion_prompts.get(shot_type, "subtle, slow camera movement to bring the still image to life")
    
    return generate_video_with_retry(
        prompt=prompt,
        reference_image_url=image_url,
        model_api="veo-3.1-fast"
    )
```

---

## 5. Backend: New Celery Worker Tasks

Add two new, separate Celery tasks to `ugc_worker/tasks.py` to handle the decoupled generation flow.

**File:** `/home/ubuntu/ugc-engine/ugc_worker/tasks.py`

```python
# Add after the existing imports
from prompts.cinematic_shots import build_sealcam_prompt
from generate_scenes import generate_cinematic_product_image, animate_product_shot

# Add after the execute_social_posts task

# ---------------------------------------------------------------------------
# Cinematic Product Shot Generation Tasks
# ---------------------------------------------------------------------------

@celery.task(name="generate_product_shot_image")
def generate_product_shot_image(shot_id: str):
    """Generates a single still product shot image."""
    from ugc_db.db_manager import get_product_shot, get_product, update_product_shot

    print(f"🖼️ Starting cinematic image generation for Shot {shot_id}...")
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise RuntimeError(f"Product Shot {shot_id} not found.")

        product = get_product(shot["product_id"])
        if not product:
            raise RuntimeError(f"Product {shot['product_id']} not found.")

        # 1. Build Prompt
        prompt = build_sealcam_prompt(shot["shot_type"], product)
        update_product_shot(shot_id, {"prompt": prompt})

        # 2. Generate Image
        image_url = generate_cinematic_product_image(
            prompt=prompt,
            product_image_url=product["image_url"]
        )

        # 3. Update DB
        update_product_shot(shot_id, {
            "status": "image_completed",
            "image_url": image_url
        })
        print(f"✅ Image generation complete for Shot {shot_id}")

    except Exception as e:
        print(f"❌ Image generation failed for Shot {shot_id}: {e}")
        update_product_shot(shot_id, {"status": "failed", "error_message": str(e)})


@celery.task(name="animate_product_shot")
def animate_product_shot(shot_id: str):
    """Animates a single still product shot into a video."""
    from ugc_db.db_manager import get_product_shot, update_product_shot

    print(f"🎥 Starting cinematic animation for Shot {shot_id}...")
    try:
        shot = get_product_shot(shot_id)
        if not shot or not shot.get("image_url"):
            raise RuntimeError(f"Product Shot {shot_id} not found or has no image_url.")

        update_product_shot(shot_id, {"status": "animation_pending"})

        # 1. Animate Image
        video_url = animate_product_shot(
            image_url=shot["image_url"],
            shot_type=shot["shot_type"]
        )

        # 2. Update DB
        update_product_shot(shot_id, {
            "status": "animation_completed",
            "video_url": video_url
        })
        print(f"✅ Animation complete for Shot {shot_id}")

    except Exception as e:
        print(f"❌ Animation failed for Shot {shot_id}: {e}")
        update_product_shot(shot_id, {"status": "failed", "error_message": str(e)})
```

---

## 6. Backend: New API Endpoints

Add three new endpoints to `ugc_backend/main.py` and modify the existing `/jobs` endpoint.

**File:** `/home/ubuntu/ugc-engine/ugc_backend/main.py`

```python
# Add to imports
from ugc_db.db_manager import create_product_shot, list_product_shots, get_product_shot

# Add to Pydantic Models section
class ShotGenerateRequest(BaseModel):
    shot_type: str
    variations: int = 1

class JobCreate(BaseModel):
    # ... (existing fields)
    cinematic_shot_ids: Optional[List[str]] = None # NEW FIELD

# Add new endpoints before the /health endpoint

# ---------------------------------------------------------------------------
# Product Shots API
# ---------------------------------------------------------------------------

@app.get("/api/products/{product_id}/shots")
def api_list_product_shots(product_id: str):
    try:
        return list_product_shots(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products/{product_id}/shots")
def api_generate_shot_image(product_id: str, data: ShotGenerateRequest):
    """Creates a record and dispatches a task to generate a still image."""
    from ugc_worker.tasks import generate_product_shot_image
    try:
        created_shots = []
        for _ in range(data.variations):
            shot = create_product_shot({
                "product_id": product_id,
                "shot_type": data.shot_type,
                "status": "image_pending"
            })
            generate_product_shot_image.delay(shot["id"])
            created_shots.append(shot)
        return created_shots
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shots/{shot_id}/animate")
def api_animate_shot(shot_id: str):
    """Dispatches a task to animate a still image into a video."""
    from ugc_worker.tasks import animate_product_shot
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise HTTPException(status_code=404, detail="Product shot not found")
        animate_product_shot.delay(shot_id)
        return {"status": "animation_queued", "shot_id": shot_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ...

# Modify the /jobs endpoint
@app.post("/jobs")
def api_create_job(data: JobCreate):
    # ... (keep existing validation)

    # Add cinematic_shot_ids to the job data payload
    job_data["cinematic_shot_ids"] = data.cinematic_shot_ids

    # ... (rest of the function)
```

---

## 7. Backend: Core Engine Integration

This is the most critical part of the new architecture. We need to modify `scene_builder.py` to incorporate the selected cinematic shots into the final video's scene list.

**File:** `/home/ubuntu/ugc-engine/scene_builder.py`

```python
# Add to imports
from ugc_db.db_manager import get_product_shot

# Modify the main build_scenes function
def build_scenes(content_row, influencer, app_clip, app_clip_2=None, product=None, product_type="digital"):
    # ... (existing setup)

    # NEW: Check for cinematic shots to include
    cinematic_shot_ids = content_row.get("cinematic_shot_ids", [])
    cinematic_scenes = []
    if product_type == "physical" and cinematic_shot_ids:
        for shot_id in cinematic_shot_ids:
            shot = get_product_shot(shot_id)
            if shot and shot.get("video_url"):
                cinematic_scenes.append({
                    "name": f"cinematic_shot_{shot['shot_type']}",
                    "type": "cinematic_shot", # NEW SCENE TYPE
                    "video_url": shot["video_url"],
                    "target_duration": 4.0, # Or get from DB if stored
                    "subtitle_text": "", # Cinematic shots are silent
                })

    if product_type == "physical" and product:
        ctx["product"] = product
        influencer_scenes = physical_prompts.build_physical_product_scenes(content_row, influencer, product, durations, ctx)
        
        # NEW: Interleave cinematic scenes with influencer scenes
        # Simple strategy: alternate between them
        final_scenes = []
        inf_idx, cin_idx = 0, 0
        total_scenes = len(influencer_scenes) + len(cinematic_scenes)
        for i in range(total_scenes):
            # Prioritize influencer scenes if we run out of cinematic ones, or alternate
            if i % 2 == 0 and inf_idx < len(influencer_scenes):
                final_scenes.append(influencer_scenes[inf_idx])
                inf_idx += 1
            elif cin_idx < len(cinematic_scenes):
                final_scenes.append(cinematic_scenes[cin_idx])
                cin_idx += 1
            elif inf_idx < len(influencer_scenes):
                final_scenes.append(influencer_scenes[inf_idx])
                inf_idx += 1
        
        return final_scenes

    elif length == "30s":
        # ... (existing digital flow)
    else:
        # ... (existing digital flow)
```

Next, modify `core_engine.py` to handle the new `cinematic_shot` scene type.

**File:** `/home/ubuntu/ugc-engine/core_engine.py`

```python
# In run_generation_pipeline, inside the `for i, scene in enumerate(scenes, 1):` loop

            # ... (after the `elif scene["type"] == "veo":` block)

            elif scene["type"] == "cinematic_shot":
                # Pre-rendered cinematic product shot
                print(f"      🎬 Using pre-rendered cinematic shot: {scene['video_url']}")
                generate_scenes.download_video(scene["video_url"], output_path)

            elif scene["type"] == "clip":
                # 📱 App Clip
                generate_scenes.download_video(scene["video_url"], output_path)
```

---

## 8. Backend: Cost Service Update

Update `cost_service.py` to provide cost estimates for the new generation steps.

**File:** `/home/ubuntu/ugc-engine/ugc_backend/cost_service.py`

```python
# Add new functions to the CostService class

    def estimate_shot_image_cost(self) -> float:
        """Cost for a single Nano Banana Pro still image generation."""
        model_cfg = self.config["kie_ai"]["models"].get("nano-banana-pro", {})
        return model_cfg.get("cost_per_image", 0.09)

    def estimate_shot_animation_cost(self, duration: int = 4) -> float:
        """Cost for a single Veo 3.1 Fast animation."""
        model_cfg = self.config["kie_ai"]["models"].get("veo-3.1-fast", {})
        return round(duration * model_cfg.get("cost_per_second", 0.02), 5)

# Modify the main estimate_total_cost function
# This function is now only for the main video generation, not the library asset generation.
# The cost of cinematic shots is now part of the final video cost, but it's a sunk cost
# as they are pre-generated. We will not include it in the main job estimate to avoid confusion.

# Add a new endpoint for getting shot generation costs
```

**File:** `/home/ubuntu/ugc-engine/ugc_backend/main.py`

```python
# Add new endpoint before /health
@app.get("/api/shots/costs")
def api_get_shot_costs():
    return {
        "image_generation_cost": cost_service.estimate_shot_image_cost(),
        "animation_cost": cost_service.estimate_shot_animation_cost(),
    }
```

---

## 9. Frontend: Types & API Hooks

Update the frontend type definitions.

**File:** `/home/ubuntu/ugc-engine/frontend/src/lib/types.ts`

```typescript
// Add new interface
export interface ProductShot {
    id: string;
    product_id: string;
    shot_type: string;
    status: 'image_pending' | 'image_completed' | 'animation_pending' | 'animation_completed' | 'failed';
    image_url?: string;
    video_url?: string;
    prompt?: string;
    error_message?: string;
    created_at: string;
}

// Add to Product interface
export interface Product {
    // ... existing fields
    shots?: ProductShot[]; // To hold fetched shots
}
```

---

## 10. Frontend: Library UI Overhaul

This requires significant changes to the `ProductsTab` component in `library/page.tsx`.

1.  **Add "Generate Shots" Button:** On each product card, add a new button.
2.  **Create `GenerateShotModal.tsx`:** This new component will open when the button is clicked. It will contain a dropdown to select the `shot_type` and a number input for `variations`. It will fetch costs from the new `/api/shots/costs` endpoint to display an estimate.
3.  **Create `ProductShotsGallery.tsx`:** This new component will be displayed below the product details. It will fetch shots from `/api/products/{product_id}/shots` and display them in a grid.
4.  **Gallery Item Logic:** Each item in the gallery will show the still image. If `status` is `image_completed`, it will show an "Animate" button. If `status` is `animation_pending`, it shows a loading state. If `status` is `animation_completed`, it shows the video (ideally with hover-to-play).

**File:** `/home/ubuntu/ugc-engine/frontend/src/app/library/page.tsx` (Conceptual changes for `ProductsTab`)

```jsx
// Inside ProductsTab component

// State for the modal
const [generatingForProduct, setGeneratingForProduct] = useState<Product | null>(null);

// Fetch shots for each product
useEffect(() => {
    const fetchShotsForProducts = async () => {
        if (products.length > 0) {
            const productsWithShots = await Promise.all(products.map(async (p) => {
                const shots = await apiFetch<ProductShot[]>(`/api/products/${p.id}/shots`);
                return { ...p, shots };
            }));
            setProducts(productsWithShots);
        }
    };
    fetchShotsForProducts();
}, [products.length]); // Re-run when products are fetched

// In the product card map
<div key={p.id}>
    {/* ... existing product card UI ... */}
    <div className="absolute inset-0 ...">
        {/* ... existing buttons ... */}
        <button onClick={() => setGeneratingForProduct(p)}>
            Generate Shots
        </button>
    </div>

    {/* Render the new gallery component below the card */}
    {p.shots && p.shots.length > 0 && (
        <ProductShotsGallery product={p} shots={p.shots} onUpdate={fetchData} />
    )}
</div>

// At the end of the component return
{generatingForProduct && (
    <GenerateShotModal
        product={generatingForProduct}
        onClose={() => setGeneratingForProduct(null)}
        onSuccess={fetchData} // Refetch all data on success
    />
)}
```

This is a high-level overview. The actual implementation of the new components (`GenerateShotModal`, `ProductShotsGallery`) will involve state management for loading, API calls for generation and animation, and polling for status updates.

---

## 11. Frontend: Create Page Integration

Modify the `CreatePage` to allow selecting cinematic shots.

**File:** `/home/ubuntu/ugc-engine/frontend/src/app/create/page.tsx`

```jsx
// Add new state
const [cinematicShots, setCinematicShots] = useState<ProductShot[]>([]);
const [selectedCinematicShots, setSelectedCinematicShots] = useState<string[]>([]);

// Fetch cinematic shots when a physical product is selected
useEffect(() => {
    const fetchShots = async () => {
        if (productType === 'physical' && productId) {
            const shots = await apiFetch<ProductShot[]>(`/api/products/${productId}/shots`);
            // Filter for only completed animations
            setCinematicShots(shots.filter(s => s.status === 'animation_completed' && s.video_url));
        }
    };
    fetchShots();
}, [productType, productId]);

// In the handleSubmit function, add the selected shot IDs to the payload
const body = {
    // ... existing fields
    cinematic_shot_ids: selectedCinematicShots,
};

// In the JSX, after the physical product selector
{productType === 'physical' && productId && cinematicShots.length > 0 && (
    <div>
        <label className="text-xs text-slate-400 font-medium mb-3 block">Include Cinematic Shots</label>
        <div className="grid grid-cols-3 gap-2">
            {cinematicShots.map(shot => (
                <div 
                    key={shot.id} 
                    onClick={() => {
                        setSelectedCinematicShots(prev => 
                            prev.includes(shot.id) 
                                ? prev.filter(id => id !== shot.id) 
                                : [...prev, shot.id]
                        );
                    }}
                    className={`cursor-pointer rounded-lg overflow-hidden border-2 ${selectedCinematicShots.includes(shot.id) ? 'border-green-500' : 'border-transparent'}`}>
                    <video src={shot.video_url} muted loop playsInline />
                </div>
            ))}
        </div>
    </div>
)}
```

---

## 12. SEALCaM Prompt Engineering Reference

*(This section remains the same as v1, providing the reference for the `cinematic_shots.py` module)*

The **SEALCaM** framework is used for generating high-quality, cinematic still images. It consists of six components:

*   **S (Subject):** What is the core subject of the image?
*   **E (Environment):** Where is the subject located?
*   **A (Action):** What is the subject doing?
*   **L (Lighting):** How is the scene lit?
*   **Ca (Camera):** What are the camera settings (lens, angle, shot type)?
*   **M (Metatokens):** What are the overall style keywords (e.g., photorealistic, 8K, octane render)?

---

## 13. Cinematic Shot Type Catalog

*(This section remains the same as v1, providing the reference for the `cinematic_shots.py` module and the frontend modal)*

| Shot Type | Description |
|:---|:---|
| **Hero** | A classic, centered, well-lit shot that presents the product in its best light. |
| **Macro Detail** | An extreme close-up focusing on the product's texture, material, or a specific feature. |
| **Pedestal** | The product is elevated on a block or pedestal, giving it a sense of importance and luxury. |
| **Moody/Dramatic** | Uses high-contrast, low-key lighting (chiaroscuro) to create a dramatic, emotional mood. |
| **Floating** | The product is suspended weightlessly against a clean background, often used for tech or futuristic items. |
| **Lifestyle** | The product is shown in a natural, realistic setting, implying how it fits into a user's life. |

---

## 14. End-to-End Flow Summary

1.  **User uploads a product** in the Library.
2.  User clicks **"Generate Shots"** on the product, selects a shot type (e.g., "Hero"), and confirms.
3.  A Celery task generates a **still image** using Nano Banana Pro and saves it to the `product_shots` table.
4.  The still image appears in the product's gallery. The user clicks **"Animate"**.
5.  A second Celery task generates an **animated video** from the still image using Veo 3.1 and updates the record.
6.  The user goes to the **Create page**, selects the same physical product.
7.  A new UI appears showing the animated cinematic shot. The user **selects it**.
8.  The user configures the rest of the video (influencer, etc.) and clicks **"Generate Video"**.
9.  The `scene_builder` creates a scene list containing both the standard influencer scenes and the selected cinematic shot scene.
10. The `core_engine` assembles the final video, which now includes the cinematic product- a cinematic cutaway of the product.
