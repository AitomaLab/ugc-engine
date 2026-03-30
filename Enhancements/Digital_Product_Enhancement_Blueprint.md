# UGC Engine — Digital Product & Campaign Generation: Definitive Implementation Blueprint

**Prepared by:** Manus AI
**Date:** 2026-03-25
**Version:** 1.0 — Authoritative Source of Truth

---

## 1. Introduction & Purpose

This document is the definitive technical blueprint for a set of high-priority enhancements to the UGC Engine's digital product management and campaign video generation workflows. It is written from scratch based on a thorough analysis of the latest production codebase (`AitomaLab/ugc-engine`, commit `c1992d2`) and supersedes all previous discussions on these topics.

Antigravity must treat this document as the sole source of truth, analyse it together with the existing codebase, and implement everything described here without breaking any existing functionality. The existing video generation pipeline, API endpoints, and frontend workflows must remain fully operational throughout.

The four enhancements addressed are:

1. **Dynamic Influencer Variation** — Bulk campaigns will produce visually diverse videos by varying the influencer's environment, clothing, and pose across 70% of generated videos, while retaining the exact reference image look for the remaining 30%.
2. **Unified Digital Product & Clip Hierarchy** — The digital tab on `/products` will be restructured so that app clips are nested within their parent digital product, rather than displayed as a separate flat list.
3. **Redesigned "Add Clip" Modal** — The clip creation modal will be updated to allow linking to an existing digital product or creating a new one inline, and will remove the now-redundant asset type selector.
4. **New "Create Digital Product" CTA** — A dedicated button for creating digital products will be added to the digital tab toolbar, alongside the existing "Add Clip" button.

---

## 2. Codebase Analysis Summary

The following is a summary of the key findings from the codebase analysis that directly inform the implementation decisions in this blueprint.

### 2.1. Campaign Generation Flow

When a user creates a bulk campaign (`POST /jobs/bulk`), the backend iterates `data.count` times. In each iteration, it selects a random script and a random app clip from a pool, then calls `create_job(job_data)` and `_dispatch_worker(job["id"])`. Every single job in the batch receives the **identical** `influencer_id` and, consequently, the same `reference_image_url` from the influencer record. There is currently no mechanism to introduce visual variation between jobs in the same campaign.

The worker (`ugc_worker/tasks.py`, function `generate_video_job`) fetches the influencer record and constructs an `influencer_dict`. This dict is passed to `core_engine.run_generation_pipeline`, which calls `scene_builder.build_scenes`. The `scene_builder` constructs a `ctx` dictionary that includes a `setting` key derived from `influencer.get("setting")`. This `setting` string is passed verbatim into the scene prompts in `prompts/digital_prompts.py` as the `env` variable. This is the precise injection point for variation.

### 2.2. Digital Product & Clip Data Model

The `products` table has a `type` column (`'physical'` or `'digital'`), added in migration `011_digital_overhaul.sql`. The `app_clips` table has a `product_id` foreign key column, also added in migration `011`. The data relationship already exists at the database level. The frontend, however, displays digital products and app clips as two separate, parallel sections on the same page, and does not leverage the parent-child relationship for navigation.

### 2.3. "Add Clip" Modal

The `AppClipModal` component in `frontend/src/app/products/page.tsx` currently collects a clip name and a video URL (via upload or paste). It does **not** accept a `product_id` at creation time. After a clip is created, the user must manually link it to a product using a dropdown selector on the clip card. The modal also does not offer the ability to create a new digital product inline.

### 2.4. Digital Tab Toolbar

The digital tab toolbar currently has a single "Add Clip" button. There is no CTA for creating a new digital product from this tab; the user must navigate to the physical products tab or use the `ProductModal` component, which is accessible via the edit button on existing product cards.

---

## 3. Enhancement 1: Dynamic Influencer Variation in Campaigns

### 3.1. Mechanism

The variation system uses a **70/30 split** applied at the point of job creation in the bulk endpoint. For each video in the campaign batch, a random number is drawn. If it falls below 0.70, a variation prompt is generated using the OpenAI API and stored on the job record. The worker then passes this variation prompt into the scene builder, which uses it to override the `setting` in the generated video prompts. If the random number is 0.70 or above, no variation prompt is generated and the job proceeds exactly as it does today — using the influencer's default setting, which matches the reference image.

This approach is entirely additive. The existing code path for the 30% of unmodified jobs is not touched. The variation only affects the `setting` string injected into the Veo/Nano Banana prompts; the `reference_image_url` remains the same for all jobs, ensuring the influencer's face and identity are always preserved by the AI model.

### 3.2. Database Change

A new optional column must be added to the `video_jobs` table via a new migration script.

**File:** `ugc_db/migrations/013_add_variation_prompt.sql`

```sql
-- Migration 013: Add variation_prompt to video_jobs for campaign diversity
ALTER TABLE video_jobs
ADD COLUMN IF NOT EXISTS variation_prompt TEXT;

COMMENT ON COLUMN video_jobs.variation_prompt IS
  'Optional AI-generated scene variation (environment, clothing, pose) for bulk campaign diversity. NULL means use the influencer default setting.';
```

This is a non-breaking, additive change. The column is nullable and has no default, so all existing rows and all existing code paths are unaffected.

### 3.3. New Helper Function

**File:** `prompts/digital_prompts.py`

Add a new standalone function at the bottom of the file:

```python
def generate_variation_prompt(influencer: dict) -> str:
    """
    Uses the OpenAI API to generate a short, visually distinct scene description
    for a campaign video, based on the influencer's bio and style.
    Returns a plain string describing the new environment, clothing, and pose.
    Falls back to the influencer's default setting on any error.
    """
    import os
    from openai import OpenAI

    client = OpenAI()
    description = influencer.get("description", "")
    style = influencer.get("style", "")
    default_setting = influencer.get("setting", "natural indoor environment")

    if not description and not style:
        return default_setting

    system_prompt = (
        "You are a creative director for short-form social media video campaigns. "
        "Your job is to suggest visually varied but brand-appropriate scenes for an influencer."
    )
    user_prompt = (
        f"Based on the following influencer description, generate ONE concise sentence "
        f"(maximum 25 words) describing a new, visually distinct scene. "
        f"The sentence must naturally incorporate: a new environment or location, "
        f"a different outfit or clothing style, and a different pose or activity. "
        f"The scene must feel authentic and match the influencer's personality and brand. "
        f"Do NOT mention the influencer by name. Do NOT use quotation marks.\n\n"
        f"Influencer description: {description[:500]}\n"
        f"Influencer style: {style[:200]}"
    )

    try:
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=60,
            temperature=0.9,
        )
        result = response.choices[0].message.content.strip().strip('"').strip("'")
        print(f"      [Variation] Generated: {result}")
        return result
    except Exception as e:
        print(f"      [Variation] Generation failed (non-fatal), using default: {e}")
        return default_setting
```

### 3.4. Backend Changes — `ugc_backend/main.py`

**Modify `POST /jobs/bulk`** — inside the `for _ in range(data.count):` loop, add the following logic immediately after `selected_clip` is determined and before `job_data` is constructed:

```python
# --- Influencer Variation Logic (70/30 split) ---
variation_prompt = None
if data.product_type == "digital" and data.count > 1:
    if random.random() < 0.70:
        try:
            from prompts.digital_prompts import generate_variation_prompt
            variation_prompt = generate_variation_prompt(inf)
        except Exception as ve:
            print(f"   [Variation] Skipped due to error: {ve}")
```

Then, in the `job_data` dictionary, add the new field:

```python
job_data = {
    ...existing fields...,
    "variation_prompt": variation_prompt,  # None for 30% of jobs
}
```

Also add `"variation_prompt"` to the `db_columns` fallback set so it is never stripped.

**Important:** This variation logic must only activate when `data.count > 1` (i.e., it is a campaign, not a single video) and when `data.product_type == "digital"`. Physical product campaigns are not affected.

### 3.5. Worker Changes — `ugc_worker/tasks.py`

In the `generate_video_job` function, after `influencer_dict` is constructed, add:

```python
# Pass variation prompt into influencer dict for scene builder
variation_prompt = job.get("variation_prompt")
if variation_prompt:
    influencer_dict["variation_prompt"] = variation_prompt
    print(f"      [Variation] Applying variation: {variation_prompt[:80]}")
```

### 3.6. Scene Builder Changes — `scene_builder.py`

In the `build_scenes` function, after the `ctx` dictionary is constructed, add:

```python
# Override setting with variation prompt if present (campaign diversity)
variation = influencer.get("variation_prompt")
if variation:
    ctx["setting"] = variation
```

This single line is all that is needed. The `ctx["setting"]` key is already consumed by all prompt-building functions in `digital_prompts.py` as the `env` variable. No further changes to `digital_prompts.py` are required.

---

## 4. Enhancement 2: Unified Digital Product & Clip Hierarchy

### 4.1. UI Behaviour

The digital tab will now operate in two modes, controlled by a new state variable `selectedDigitalProduct`.

**Mode 1 — Product List (default):** When `selectedDigitalProduct` is `null`, the page renders the grid of digital product cards. Each card is now fully clickable (not just the edit button) and clicking it sets `selectedDigitalProduct` to that product object. The "App Clips" section that currently appears below the products grid is removed from this view entirely.

**Mode 2 — Product Detail:** When `selectedDigitalProduct` is set, the page renders a detail view for that product. This view has a breadcrumb/back navigation at the top (`← Back to Digital Products`), the product name and image, and below that, a grid of app clips filtered to only show clips where `clip.product_id === selectedDigitalProduct.id`. The "Add Clip" button in this view will open the `AppClipModal` with the current product pre-selected.

### 4.2. Frontend Changes — `frontend/src/app/products/page.tsx`

**State additions:**
```typescript
const [selectedDigitalProduct, setSelectedDigitalProduct] = useState<Product | null>(null);
```

**Modify the `activeTab === 'digital'` render block:**

Replace the existing block with the following conditional structure:

```tsx
{activeTab === 'digital' && (
  <>
    {selectedDigitalProduct ? (
      // --- MODE 2: Product Detail View ---
      <DigitalProductDetail
        product={selectedDigitalProduct}
        clips={clips.filter(c => c.product_id === selectedDigitalProduct.id)}
        onBack={() => setSelectedDigitalProduct(null)}
        onAddClip={() => {
          // Open modal with product pre-selected
          setClipModalDefaultProductId(selectedDigitalProduct.id);
          setClipModalOpen(true);
        }}
        onDeleteClip={handleDeleteClip}
        onPreview={setPreviewAssetUrl}
      />
    ) : (
      // --- MODE 1: Product List View ---
      <>
        <div className='asset-toolbar'>
          ...existing toolbar...
        </div>
        <div className='products-grid'>
          {digitalProducts.map(product => (
            <div
              key={product.id}
              className='product-card'
              style={{ cursor: 'pointer' }}
              onClick={() => setSelectedDigitalProduct(product)}
            >
              ...existing card content, but remove the separate "App Clips" section below...
            </div>
          ))}
        </div>
      </>
    )}
  </>
)}
```

**New `DigitalProductDetail` component:** This should be defined as a separate function component within the same file, above `ProductsContent`. It accepts `product`, `clips`, `onBack`, `onAddClip`, `onDeleteClip`, and `onPreview` as props. It renders the back button, product header, and the clips grid. This keeps the `ProductsContent` component clean and readable.

**New state variable:**
```typescript
const [clipModalDefaultProductId, setClipModalDefaultProductId] = useState<string | null>(null);
```
This is passed to `AppClipModal` as a `defaultProductId` prop, so the modal can pre-select the correct product.

---

## 5. Enhancement 3: Redesigned "Add Clip" Modal

### 5.1. Changes to `AppClipModal`

**Remove:** The `asset_type` selector field. Since the modal is only accessible from the digital tab, the type is always `'digital'` and the selector is redundant.

**Add:** A product association section at the top of the modal form, rendered before the clip name input. This section has two modes toggled by a segmented control:

- **"Link to Existing Product"** (default): Renders a `<Select>` dropdown populated with `products.filter(p => p.type === 'digital')`. The selected value is stored in `const [linkedProductId, setLinkedProductId] = useState<string>(defaultProductId || '')`.
- **"Create New Product"**: Renders a single text input for `const [newProductName, setNewProductName] = useState('');`.

**Modify `handleSave`:**

```typescript
const handleSave = async () => {
  setSaving(true);
  try {
    let productId = linkedProductId || null;

    // If creating a new product, do that first
    if (productSelectionMode === 'new' && newProductName.trim()) {
      const newProduct = await apiFetch<Product>('/api/products', {
        method: 'POST',
        body: JSON.stringify({
          name: newProductName.trim(),
          type: 'digital',
          // A placeholder image_url is required by the backend; use a default
          image_url: 'https://placeholder.com/digital-product.png',
        }),
      });
      productId = newProduct.id;
    }

    // Upload video if needed (existing logic)
    let finalVideoUrl = videoUrl;
    // ... existing upload logic ...

    // Create the clip, now with product_id
    await apiFetch('/api/app-clips', {
      method: 'POST',
      body: JSON.stringify({
        name: name.trim(),
        video_url: finalVideoUrl,
        product_id: productId,
        category: 'digital',
      }),
    });

    onSaved();
  } catch (err) {
    setError('Failed to save. Please try again.');
  } finally {
    setSaving(false);
  }
};
```

**Note on `image_url` for new digital products:** The `POST /api/products` endpoint currently requires an `image_url`. If the user is creating a new digital product from this modal without an image, the backend should be updated to make `image_url` optional for `type === 'digital'` products, as digital products are represented by their app clip video, not a static image. This is a minor, non-breaking backend change: modify the `ProductCreate` model in `main.py` to set `image_url: Optional[str] = None` and update the `create_product` call to handle a null image URL.

**Props update:**
```typescript
function AppClipModal({
  isOpen,
  onClose,
  onSaved,
  defaultProductId,
  products,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
  defaultProductId?: string | null;
  products: Product[];
})
```

The `products` list must be passed in from `ProductsContent` so the modal can populate the existing product dropdown without making a separate API call.

---

## 6. Enhancement 4: New "Create Digital Product" CTA

### 6.1. Changes to the Digital Tab Toolbar

**File:** `frontend/src/app/products/page.tsx`

In the `asset-toolbar` div for the digital tab (Mode 1 — Product List view only), add a new primary button immediately before the existing "Add Clip" button:

```tsx
<button className='btn-primary' onClick={() => {
  setSelectedProduct(null); // Ensure modal is in create mode
  setIsModalOpen(true);
}}>
  <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
  New Digital Product
</button>
```

**Modify `ProductModal` to handle digital products:** The existing `ProductModal` component (`frontend/src/components/ui/ProductModal.tsx`) must be reviewed. When opened from the digital tab, it should default the product type to `'digital'`. The simplest approach is to pass an optional `defaultType` prop to `ProductModal`. When `defaultType === 'digital'`, the type selector should be pre-set to `'digital'` and the `image_url` field should be optional (consistent with the backend change described in Section 5).

---

## 7. Non-Breaking Implementation Guarantee

This is a mandatory constraint. The following rules must be observed throughout the entire implementation.

**Backend:** The only new file is `ugc_db/migrations/013_add_variation_prompt.sql`. The only modified backend files are `ugc_backend/main.py` (additive changes to the bulk jobs loop), `ugc_worker/tasks.py` (additive pass-through of the variation prompt), `scene_builder.py` (additive override of `ctx["setting"]`), and `prompts/digital_prompts.py` (additive new function). No existing function signatures, return values, or API response shapes are changed.

**Frontend:** The `AppClipModal` component is modified, but its `onSaved` callback contract is unchanged. The `ProductsContent` component gains new state and a new conditional render block, but all existing state variables and data fetching logic remain intact. The physical products tab and all its functionality are completely untouched.

**Single-video creation:** The variation logic in `POST /jobs/bulk` is explicitly gated behind `data.count > 1`. A user creating a single digital video via `POST /jobs` (the single-job endpoint) is completely unaffected.

**Physical product campaigns:** The variation logic is gated behind `data.product_type == "digital"`. Physical product campaigns are completely unaffected.

Before beginning, Antigravity must audit the `ProductModal` component to confirm the `defaultType` prop addition is safe, and must verify that the `POST /api/app-clips` endpoint in `main.py` already accepts and stores a `product_id` in its request body (confirmed in migration `011`, but must be verified against the actual endpoint implementation at line `1203`).

---

## 8. Implementation Order

The four phases should be implemented in the following order to allow independent testing at each stage.

| Phase | Scope | Acceptance Criterion |
| :--- | :--- | :--- |
| 1 | Dynamic Influencer Variation | A bulk digital campaign of 5+ videos produces visually distinct scenes across the batch. The 30% unmodified jobs are indistinguishable from a pre-change campaign. |
| 2 | Redesigned "Add Clip" Modal | A user can add a new clip and either link it to an existing digital product or create a new product — all within the same modal, in a single flow. |
| 3 | Unified Hierarchy | The digital tab shows only product cards. Clicking a card reveals only the clips for that product. The back button returns to the product list. |
| 4 | New "Create Digital Product" CTA | The "New Digital Product" button appears in the digital tab toolbar and opens the product creation modal pre-set to the digital type. |
