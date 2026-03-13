# UGC Engine: Complete Implementation Blueprint
## Digital Product & App Clip Overhaul + Scene Transitions + Script Safety Buffer

**Date:** Mar 13, 2026
**Author:** Manus AI
**Repository:** `AitomaLab/ugc-engine`

---

## ABSOLUTE PRESERVATION RULES

Before any code is written, these rules govern every change in this document. Violating any of them is not acceptable.

1. **Physical product flow is untouched.** `build_physical_product_scenes` in `prompts/physical_prompts.py` is not modified. The Nano Banana + Veo pipeline for physical products continues to work exactly as before.
2. **Existing digital flow is preserved as a fallback.** If a digital job has no `product_id` linked, the system falls back to the existing random/specific app clip selection logic in `ugc_worker/tasks.py`. No existing jobs break.
3. **No API fields are removed.** Only new optional fields are added to Pydantic models and database tables.
4. **No existing database tables are dropped or renamed.** Only `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migrations are used.
5. **No existing frontend state or submit logic is removed.** Only new state variables and conditional rendering blocks are added.

---

## SCOPE OF CHANGES

This blueprint covers three separate but related enhancements that are implemented together:

| Enhancement | Files Affected |
| :--- | :--- |
| **A. Digital Product + App Clip Overhaul** | DB schema, `db_manager.py`, `main.py`, `web_scraper.py` (new), `ai_script_client.py`, `digital_prompts.py`, `scene_builder.py`, `tasks.py`, frontend create/products/app-clips pages |
| **B. Scene Transitions Between Veo 3.1 Scenes** | `assemble_video.py` |
| **C. 1-Second Script Safety Buffer** | `prompts/physical_prompts.py`, `prompts/digital_prompts.py`, `ugc_backend/ai_script_client.py` |

---

## PART A: DIGITAL PRODUCT & APP CLIP OVERHAUL

### A1. Database Migration

**File to create:** `ugc_db/migrations/011_digital_overhaul.sql`

This migration adds three columns. All use `IF NOT EXISTS` so they are safe to run multiple times.

```sql
-- Migration 011: Digital Product & App Clip Overhaul
-- Run this in the Supabase SQL Editor.

-- 1. Add website_url to products for dual-source AI analysis
ALTER TABLE products
ADD COLUMN IF NOT EXISTS website_url TEXT;

-- 2. Link app_clips to a specific digital product
ALTER TABLE app_clips
ADD COLUMN IF NOT EXISTS product_id UUID REFERENCES products(id) ON DELETE SET NULL;

-- 3. Store the extracted first frame for Nano Banana Pro visual consistency
ALTER TABLE app_clips
ADD COLUMN IF NOT EXISTS first_frame_url TEXT;

-- 4. Index for fast lookup of clips by product
CREATE INDEX IF NOT EXISTS idx_app_clips_product_id ON app_clips(product_id);
```

**Why `ON DELETE SET NULL` and not `ON DELETE CASCADE`:** If a product is deleted, we do not want to delete the app clips. The clips are independent assets. We simply unlink them.

---

### A2. Database Manager Updates

**File to modify:** `ugc_db/db_manager.py`

Add the following three functions. Place them directly after the existing `delete_app_clip` function.

```python
# ---------------------------------------------------------------------------
# NEW: App Clips — filtered by product
# ---------------------------------------------------------------------------

def list_app_clips_by_product(product_id: str):
    """Returns all app clips linked to a specific digital product."""
    sb = get_supabase()
    return sb.table("app_clips").select("*").eq("product_id", product_id).execute().data

def update_app_clip(clip_id: str, data: dict):
    """Updates fields on an existing app clip record."""
    sb = get_supabase()
    result = sb.table("app_clips").update(data).eq("id", clip_id).execute()
    return result.data[0] if result.data else None
```

Also update the import line at the top of `ugc_backend/main.py` to include these two new functions:

```python
# In ugc_backend/main.py — update the db_manager import line to add the two new functions:
from ugc_db.db_manager import (
    get_supabase,
    list_influencers, get_influencer, create_influencer, update_influencer, delete_influencer,
    list_scripts, create_script, delete_script, get_script,
    list_app_clips, list_app_clips_by_product, update_app_clip, create_app_clip, delete_app_clip,
    list_jobs, get_job, create_job, update_job,
    get_stats,
    list_products, create_product, delete_product, get_product, update_product,
    list_product_shots, get_product_shot, create_product_shot, update_product_shot, delete_product_shot,
)
```

---

### A3. New Backend Service: Web Scraper

**File to create:** `ugc_backend/web_scraper.py`

This is a new, self-contained module. It has no dependencies on the rest of the engine.

```python
"""
UGC Engine — Web Scraper Client

Scrapes a product's website URL to extract key marketing copy (benefits,
features, taglines) for use in AI script generation.

Dependencies: requests, beautifulsoup4 (both already in requirements.txt)
"""
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional


class WebScraperClient:
    """Fetches and extracts the most relevant marketing text from a product URL."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-US,en;q=0.9",
    }
    MAX_CHARS = 3000  # Cap to avoid exceeding LLM context limits

    def scrape(self, url: str) -> Optional[str]:
        """
        Fetches the URL and returns a clean, condensed string of the most
        relevant marketing content on the page.

        Returns None if the URL is unreachable or parsing fails.
        """
        if not url or not url.startswith("http"):
            return None
        try:
            response = requests.get(url, headers=self.HEADERS, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")

            # Remove noise: scripts, styles, nav, footer, cookie banners
            for tag in soup(["script", "style", "nav", "footer", "header",
                              "aside", "form", "noscript", "iframe"]):
                tag.decompose()

            # Priority 1: Extract from semantic marketing elements
            priority_text = []
            for selector in ["h1", "h2", "h3", "[class*='hero']", "[class*='benefit']",
                              "[class*='feature']", "[class*='tagline']", "[class*='headline']"]:
                for el in soup.select(selector)[:5]:
                    text = el.get_text(strip=True)
                    if text and len(text) > 10:
                        priority_text.append(text)

            # Priority 2: All paragraph text as fallback
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 30]

            combined = "\n".join(priority_text + paragraphs)

            # Clean up whitespace
            combined = re.sub(r'\n{3,}', '\n\n', combined).strip()

            return combined[:self.MAX_CHARS] if combined else None

        except requests.RequestException as e:
            print(f"      ⚠️ WebScraperClient: Failed to fetch {url}: {e}")
            return None
        except Exception as e:
            print(f"      ⚠️ WebScraperClient: Parsing error for {url}: {e}")
            return None
```

---

### A4. Updated AI Script Client

**File to modify:** `ugc_backend/ai_script_client.py`

Replace the entire file contents with the following. This adds the new `generate_digital_product_script` method while keeping `generate_physical_product_script` completely intact.

```python
"""
UGC Engine — AI Script Client (v2)

Generates UGC scripts for both physical and digital products.

Physical products: Uses visual_description (image analysis) from the DB.
Digital products:  Uses dual-source analysis — image/screenshot analysis
                   PLUS scraped website content for accurate benefit copy.

SCRIPT SAFETY BUFFER RULE (applies to ALL scripts):
  All generated scripts are timed for 7 seconds of speech per 8-second scene.
  Max 17 words per scene part. This ensures the dialogue always finishes
  1 second before the scene ends, preventing audio cutoff at scene transitions.
"""
import os
from openai import OpenAI
from typing import Dict, Any, Optional


class AIScriptClient:

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY not found. Script generation will fail.")
        self.client = OpenAI(api_key=self.api_key)

    # -------------------------------------------------------------------------
    # Physical Products (unchanged from v1)
    # -------------------------------------------------------------------------

    def generate_physical_product_script(
        self,
        product_analysis: Dict[str, Any],
        duration: int,
        product_name: str = ""
    ) -> str:
        """
        Generates a compelling UGC script for a physical product.
        Output format: "Part 1 dialogue ||| Part 2 dialogue"
        Each part is timed for 7s of speech (max 17 words) to fit inside 8s Veo scenes.
        """
        if not self.api_key:
            return "Error: OpenAI API Key not configured."

        brand = product_analysis.get("brand_name") or product_name or "the product"
        visuals = product_analysis.get("visual_description", "A product.")
        colors = product_analysis.get("color_scheme", [])
        font = product_analysis.get("font_style", "N/A")

        color_str = ""
        if isinstance(colors, list):
            color_str = "\n".join([
                f"  - hex: {c.get('hex', '')}, name: {c.get('name', '')}"
                for c in colors if isinstance(c, dict)
            ])

        # 17 words = ~7s of natural speech at 2.5 words/sec
        words_per_scene = 17
        total_words = words_per_scene * 2

        system_prompt = f"""You are a world-class copywriter specializing in viral User-Generated Content (UGC) for social media platforms like TikTok and Instagram.
Your task is to generate a UGC script for a {duration}-second video that will be split across 2 video scenes (8 seconds each). The dialogue in each scene must last approximately 7 seconds so it finishes naturally before the scene ends.

**STRUCTURE — output exactly 2 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity. Max {words_per_scene} words.
Part 2 (Benefits + CTA): Highlight the product's key benefit and end with a soft call-to-action. Max {words_per_scene} words.

**Example format:**
You guys, I finally found the one product that completely changed my skin game. ||| The texture is insane, it absorbs in seconds and leaves your skin glowing. Link in bio!

**RULES:**
- Total script must be approximately {total_words} words. Do NOT exceed this.
- Each part must be a complete, natural-sounding sentence or two.
- Tone: conversational, enthusiastic, genuine, as if sharing a real discovery.
- Language: simple, direct, persuasive.

**CRITICAL FORMAT RULES — the script will be spoken aloud by an AI video model:**
- Output ONLY the exact words to be spoken, separated by |||
- Do NOT include emojis, hashtags, or special symbols.
- Do NOT include stage directions, actions, or annotations like [Shows product], (holds up), *smiles*, etc.
- Do NOT include scene labels like "Hook:", "Scene 1:", "Part 1:", etc.
- Do NOT use ellipsis (...). Use a comma or period instead for pauses.
- Do NOT add any text before Part 1 or after Part 2."""

        user_prompt = f"""**Product Analysis:**
```yaml
brand_name: {brand}
color_scheme:
{color_str}
font_style: {font}
visual_description: {visuals}
```
Generate the 2-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.8,
                top_p=1.0,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ AI Script Generation Failed: {e}")
            return f"Check out {brand}! It's amazing. You have to try it."

    # -------------------------------------------------------------------------
    # Digital Products (NEW)
    # -------------------------------------------------------------------------

    def generate_digital_product_script(
        self,
        product_name: str,
        product_analysis: Optional[Dict[str, Any]] = None,
        website_content: Optional[str] = None,
        duration: int = 15,
    ) -> str:
        """
        Generates a UGC script for a digital product (app/SaaS).

        Uses dual-source analysis:
        - product_analysis: Vision analysis of the app screenshot/first frame.
        - website_content:  Scraped text from the product's website URL.

        Output format: "Scene 1 dialogue ||| Scene 2 dialogue"
        Scene 1 = Influencer hook (7s of speech max, 17 words)
        Scene 2 = App clip plays (no dialogue needed, but CTA is generated
                  for use as a subtitle overlay if desired)
        """
        if not self.api_key:
            return f"I have to show you this app. ||| It's seriously changed everything for me, link in bio!"

        # Build context from available sources
        app_description_parts = []

        if product_analysis:
            ui_desc = product_analysis.get("visual_description", "")
            app_type = product_analysis.get("app_type", "")
            key_features = product_analysis.get("key_features", [])
            if ui_desc:
                app_description_parts.append(f"App UI: {ui_desc}")
            if app_type:
                app_description_parts.append(f"App type: {app_type}")
            if key_features and isinstance(key_features, list):
                app_description_parts.append(f"Key features: {', '.join(key_features[:5])}")

        if website_content:
            # Truncate to keep prompt manageable
            app_description_parts.append(f"Website content (first 1500 chars):\n{website_content[:1500]}")

        if not app_description_parts:
            app_description_parts.append(f"A digital product called '{product_name}'.")

        app_context = "\n\n".join(app_description_parts)

        words_per_scene = 17

        system_prompt = f"""You are a viral UGC content creator writing a script for a {duration}-second social media video promoting a digital app or software product.

The video has 2 scenes:
- Scene 1 (8 seconds): An AI influencer speaks directly to camera, holding a phone/device showing the app. Your script for Scene 1 must be max {words_per_scene} words — enough for exactly 7 seconds of natural speech.
- Scene 2 (7 seconds): The actual app screen recording plays. Your script for Scene 2 is a short, punchy CTA that can be used as a subtitle overlay. Max {words_per_scene} words.

**STRUCTURE — output exactly 2 parts separated by |||**
Part 1 (Hook): Creates immediate curiosity about the app. Sounds like a real person sharing a discovery, not an ad. Max {words_per_scene} words.
Part 2 (CTA): Short, punchy call-to-action. References a specific benefit found in the website content. Max {words_per_scene} words.

**TONE RULES — this must sound like a real human, not AI:**
- Use contractions: "I've", "it's", "you're", "don't"
- Start with a conversational opener: "So,", "Okay,", "I found this app", "You guys,"
- Avoid: "game-changer", "seamlessly", "unlock", "elevate", "transform", "revolutionize"
- Avoid: "real talk", "let me tell you", "I cannot stress this enough"
- Use specific details from the website content — vague scripts do not convert

**CRITICAL FORMAT RULES:**
- Output ONLY the spoken words, separated by |||
- No emojis, hashtags, stage directions, or scene labels
- No ellipsis (...) — use commas or periods for pauses
- No text before Part 1 or after Part 2"""

        user_prompt = f"""**Product Name:** {product_name}

**Product Context:**
{app_context}

Generate the 2-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.85,
                top_p=1.0,
                frequency_penalty=0.2,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Digital AI Script Generation Failed: {e}")
            return f"I found this app called {product_name} and honestly I can't stop using it. ||| It does everything, link is in my bio right now."
```

---

### A5. New Backend Utility: Frame Extractor

**File to create:** `ugc_backend/frame_extractor.py`

This module is called when an app clip is uploaded. It extracts the first frame and uploads it to Supabase Storage.

```python
"""
UGC Engine — Frame Extractor

Extracts the first frame from a video URL using FFmpeg and uploads it
to Supabase Storage. Used to generate first_frame_url for app clips.
"""
import os
import uuid
import subprocess
import tempfile
import requests
from pathlib import Path
from typing import Optional


def extract_first_frame(video_url: str) -> Optional[str]:
    """
    Downloads a video from a URL, extracts its first frame using FFmpeg,
    uploads the frame to Supabase Storage, and returns the public URL.

    Args:
        video_url: Public URL of the video to extract the frame from.

    Returns:
        Public URL of the uploaded frame image, or None on failure.
    """
    if not video_url:
        return None

    work_id = uuid.uuid4().hex[:8]

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        video_file = tmp_path / f"clip_{work_id}.mp4"
        frame_file = tmp_path / f"frame_{work_id}.jpg"

        # Step 1: Download the video
        try:
            print(f"      🎞️ Downloading clip for frame extraction: {video_url[:60]}...")
            response = requests.get(video_url, timeout=30, stream=True)
            response.raise_for_status()
            with open(video_file, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        except Exception as e:
            print(f"      ❌ Frame extractor: Failed to download video: {e}")
            return None

        # Step 2: Extract the first frame with FFmpeg
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_file),
                "-vframes", "1",        # Extract exactly 1 frame
                "-q:v", "2",            # High quality JPEG
                str(frame_file),
            ]
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            if result.returncode != 0:
                print(f"      ❌ Frame extractor: FFmpeg failed: {result.stderr.decode()[-500:]}")
                return None
        except Exception as e:
            print(f"      ❌ Frame extractor: FFmpeg error: {e}")
            return None

        # Step 3: Upload to Supabase Storage
        try:
            from ugc_db.db_manager import get_supabase
            sb = get_supabase()
            bucket = "app-clip-frames"
            filename = f"frame_{work_id}.jpg"

            with open(frame_file, "rb") as f:
                sb.storage.from_(bucket).upload(
                    filename, f,
                    file_options={"content-type": "image/jpeg"}
                )

            public_url = sb.storage.from_(bucket).get_public_url(filename)
            print(f"      ✅ First frame extracted and uploaded: {public_url}")
            return public_url

        except Exception as e:
            print(f"      ❌ Frame extractor: Supabase upload failed: {e}")
            return None
```

**Important:** Create the `app-clip-frames` bucket in Supabase Storage with public read access before deploying.

---

### A6. Updated API Endpoints in `main.py`

**File to modify:** `ugc_backend/main.py`

Apply the following targeted changes. Do not replace the entire file.

#### A6.1 — Update Pydantic Models

Find the existing `AppClipCreate` and `ProductCreate` models and replace them with these expanded versions:

```python
class AppClipCreate(BaseModel):
    name: str
    description: Optional[str] = None
    video_url: str
    duration_seconds: Optional[int] = None
    product_id: Optional[str] = None       # NEW: Link to a digital product
    first_frame_url: Optional[str] = None  # NEW: Auto-populated on upload

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: str
    website_url: Optional[str] = None      # NEW: For dual-source AI analysis

class AppClipUpdate(BaseModel):            # NEW: For PATCH endpoint
    product_id: Optional[str] = None
    first_frame_url: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

class ScriptGenerateRequest(BaseModel):
    product_id: str
    duration: int = 15
    product_type: str = "physical"         # NEW: "digital" or "physical"
```

#### A6.2 — Add New App Clips Endpoints

Add the following three new endpoints directly after the existing `DELETE /app-clips/{clip_id}` endpoint:

```python
@app.get("/api/app-clips")
def api_list_app_clips_filtered(product_id: Optional[str] = None):
    """
    List app clips, optionally filtered by product_id.
    GET /api/app-clips                    → all clips (backwards compatible)
    GET /api/app-clips?product_id={id}    → clips linked to a specific product
    """
    try:
        if product_id:
            return list_app_clips_by_product(product_id)
        return list_app_clips()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/app-clips/{clip_id}")
def api_update_app_clip(clip_id: str, data: AppClipUpdate):
    """Update an app clip's product_id or other fields."""
    try:
        result = update_app_clip(clip_id, data.model_dump(exclude_none=True))
        if not result:
            raise HTTPException(status_code=404, detail="App clip not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/app-clips/{clip_id}/extract-frame")
def api_extract_frame(clip_id: str):
    """
    Manually trigger first-frame extraction for an existing app clip.
    Also called automatically on clip creation if video_url is present.
    """
    try:
        sb = get_supabase()
        result = sb.table("app_clips").select("*").eq("id", clip_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="App clip not found")
        clip = result.data[0]
        if not clip.get("video_url"):
            raise HTTPException(status_code=400, detail="App clip has no video_url")

        from ugc_backend.frame_extractor import extract_first_frame
        frame_url = extract_first_frame(clip["video_url"])
        if not frame_url:
            raise HTTPException(status_code=500, detail="Frame extraction failed")

        update_app_clip(clip_id, {"first_frame_url": frame_url})
        return {"status": "success", "first_frame_url": frame_url}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### A6.3 — Update App Clip Creation to Auto-Extract Frame

Find the existing `POST /app-clips` endpoint and replace it with this version:

```python
@app.post("/app-clips")
def api_create_app_clip(data: AppClipCreate):
    """
    Creates a new app clip. If video_url is provided, automatically
    triggers first-frame extraction in a background thread.
    """
    try:
        clip_data = data.model_dump(exclude_none=True)
        new_clip = create_app_clip(clip_data)
        if not new_clip:
            raise HTTPException(status_code=500, detail="Failed to create app clip")

        # Auto-extract first frame in background (non-blocking)
        if new_clip.get("video_url") and not new_clip.get("first_frame_url"):
            import threading
            def _extract_in_background():
                try:
                    from ugc_backend.frame_extractor import extract_first_frame
                    frame_url = extract_first_frame(new_clip["video_url"])
                    if frame_url:
                        update_app_clip(new_clip["id"], {"first_frame_url": frame_url})
                        print(f"      ✅ Auto-extracted first frame for clip {new_clip['id']}")
                except Exception as e:
                    print(f"      ⚠️ Auto frame extraction failed for clip {new_clip['id']}: {e}")
            threading.Thread(target=_extract_in_background, daemon=True).start()

        return new_clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

#### A6.4 — Update Script Generation Endpoint to Support Digital Products

Find the existing `POST /api/scripts/generate` endpoint and replace it with:

```python
@app.post("/api/scripts/generate")
def api_generate_script(data: ScriptGenerateRequest):
    """
    Generates a UGC script for a product.
    - physical: Uses visual_description (image analysis only)
    - digital:  Uses dual-source analysis (image analysis + website scraping)
    """
    try:
        from ugc_backend.ai_script_client import AIScriptClient
        from ugc_db.db_manager import get_product

        print(f"DEBUG: Generating {data.product_type} script for product {data.product_id} ({data.duration}s)")

        product = get_product(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        client = AIScriptClient()

        if data.product_type == "physical":
            visuals = product.get("visual_description") or {}
            script = client.generate_physical_product_script(
                product_analysis=visuals,
                duration=data.duration,
                product_name=product.get("name", "Product")
            )
        else:
            # Digital product: dual-source analysis
            visuals = product.get("visual_description") or {}
            website_content = None

            if product.get("website_url"):
                try:
                    from ugc_backend.web_scraper import WebScraperClient
                    scraper = WebScraperClient()
                    website_content = scraper.scrape(product["website_url"])
                    print(f"      ✅ Scraped {len(website_content or '')} chars from {product['website_url']}")
                except Exception as e:
                    print(f"      ⚠️ Website scraping failed (non-fatal): {e}")

            script = client.generate_digital_product_script(
                product_name=product.get("name", "App"),
                product_analysis=visuals,
                website_content=website_content,
                duration=data.duration,
            )

        return {"script": script, "product_id": data.product_id}

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in api_generate_script: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

#### A6.5 — Add Product Website Analysis Endpoint

Add this new endpoint directly after the existing `POST /api/products/analyze` endpoint:

```python
@app.post("/api/products/{product_id}/analyze-digital")
def api_analyze_digital_product(product_id: str):
    """
    Runs dual-source analysis on a digital product:
    1. Scrapes the website_url for marketing copy.
    2. Runs vision analysis on the product image_url.
    3. Synthesizes both into a visual_description JSON and saves it.
    """
    try:
        from ugc_db.db_manager import get_product, update_product
        from ugc_backend.llm_vision_client import LLMVisionClient
        from ugc_backend.web_scraper import WebScraperClient

        product = get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        analysis = {}

        # Step 1: Vision analysis on image_url
        if product.get("image_url"):
            try:
                vision_client = LLMVisionClient()
                analysis = vision_client.describe_product_image(product["image_url"]) or {}
                print(f"      ✅ Vision analysis complete for product {product_id}")
            except Exception as e:
                print(f"      ⚠️ Vision analysis failed (non-fatal): {e}")

        # Step 2: Website scraping
        if product.get("website_url"):
            try:
                scraper = WebScraperClient()
                website_text = scraper.scrape(product["website_url"])
                if website_text:
                    analysis["website_content_summary"] = website_text[:500]
                    print(f"      ✅ Website scraping complete for product {product_id}")
            except Exception as e:
                print(f"      ⚠️ Website scraping failed (non-fatal): {e}")

        if analysis:
            update_product(product_id, {"visual_description": analysis})
            return {"status": "analyzed", "product_id": product_id, "analysis": analysis}
        else:
            raise HTTPException(status_code=422, detail="Analysis returned no data. Check image_url and website_url.")

    except HTTPException:
        raise
    except Exception as e:
        print(f"ERROR in api_analyze_digital_product: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### A7. New Digital Scene Builder

**File to modify:** `prompts/digital_prompts.py`

Add the following new function at the end of the file. Do not modify `build_15s`, `build_30s`, or `generate_ultra_prompt`.

```python
def build_digital_unified(influencer: dict, product: dict, app_clip: dict, duration: int, ctx: dict) -> list:
    """
    NEW: Builds the 2-scene digital product pipeline.

    Scene 1: Nano Banana Pro + Veo 3.1 — Influencer holding device with app's
             first frame composited onto the screen.
    Scene 2: App Clip — The actual screen recording.

    The first_frame_url from the app clip is used as the product_image_url
    for Nano Banana Pro, ensuring the device screen in Scene 1 exactly matches
    the beginning of the app clip in Scene 2.

    Args:
        influencer: Influencer dict with reference_image_url, name, etc.
        product:    Product dict with name, visual_description, website_url.
        app_clip:   App clip dict with video_url, first_frame_url.
        duration:   Target video duration in seconds (15 or 30).
        ctx:        Context dict from scene_builder.build_scenes.

    Returns:
        List of 2 scene dicts.
    """
    import config
    from prompts import sanitize_dialogue

    # Determine device type from visual_description
    visual_desc = product.get("visual_description") or {}
    app_type = visual_desc.get("app_type", "mobile").lower()
    is_mobile = "desktop" not in app_type and "web" not in app_type

    device_str = "iPhone" if is_mobile else "laptop screen"
    device_action = (
        "holding an iPhone up to the camera, screen facing viewer, pointing at the screen with one finger"
        if is_mobile else
        "sitting at a desk, pointing at a laptop screen facing the camera"
    )

    # Get the script — use product's generated script or fallback
    script = ctx.get("hook", "")
    part1, part2 = "", ""

    if "|||" in script:
        parts = [sanitize_dialogue(p.strip()) for p in script.split("|||") if p.strip()]
        part1 = parts[0] if len(parts) > 0 else ""
        part2 = parts[1] if len(parts) > 1 else ""
    elif script:
        part1 = sanitize_dialogue(script)
        part2 = "Link in my bio, seriously check it out."
    else:
        product_name = product.get("name", "this app")
        part1 = f"Okay you guys, I found this app called {product_name} and I am obsessed."
        part2 = "Link is in my bio, you need to try it."

    # Scene 1: Nano Banana + Veo (Influencer with device)
    # The first_frame_url is used as the product image composited onto the device screen
    first_frame_url = app_clip.get("first_frame_url") or app_clip.get("video_url")

    nano_banana_prompt = (
        f"action: character {device_action}, maintaining eye contact with camera\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"one hand holds {device_str}, other hand points at screen or rests naturally\n"
        f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
        f"natural skin texture with visible pores, not airbrushed\n"
        f"device: {device_str} with a clearly visible app interface on screen, "
        f"screen content matches the provided product image exactly\n"
        f"setting: well-lit casual home environment, natural window light\n"
        f"camera: amateur iPhone selfie, slightly uneven framing, warm tones\n"
        f"style: candid UGC look, no filters, realism, high detail, skin texture\n"
        f"negative: no third arm, no third hand, no extra limbs, no extra fingers, "
        f"no airbrushed skin, no studio backdrop, no geometric distortion"
    )

    veo_animation_prompt = (
        f"dialogue: {part1}\n"
        f"action: character {device_action}, slight natural body movement, "
        f"genuine excited expression, maintains eye contact with camera\n"
        f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
        f"natural skin texture with visible pores, not airbrushed\n"
        f"camera: amateur iPhone selfie video, arms length, slight natural handheld shake\n"
        f"setting: cozy home environment, natural window light, slightly blurry background\n"
        f"emotion: genuine excitement, authentic discovery reaction\n"
        f"voice_type: casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone\n"
        f"style: raw authentic TikTok/Reels UGC, candid, not polished\n"
        f"speech_constraint: speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"negative: no airbrushed skin, no studio lighting, no geometric distortion, no extra fingers"
    )

    scene_1 = {
        "name": "digital_ugc",
        "type": "physical_product_scene",  # Reuses the Nano Banana + Veo pipeline
        "nano_banana_prompt": nano_banana_prompt,
        "video_animation_prompt": veo_animation_prompt,
        "reference_image_url": influencer["reference_image_url"],
        "product_image_url": first_frame_url,  # App's first frame on the device screen
        "target_duration": 8.0,
        "subtitle_text": part1,
        "voice_id": ctx.get("voice_id", ""),
        "seed": ctx.get("consistency_seed", 0),
    }

    # Scene 2: App Clip (raw screen recording)
    scene_2 = {
        "name": "app_clip",
        "type": "clip",
        "prompt": None,
        "reference_image_url": None,
        "video_url": app_clip["video_url"],
        "target_duration": 7.0,
        "subtitle_text": part2,  # CTA subtitle overlay during the app clip
        "trim_mode": "start",
    }

    return [scene_1, scene_2]
```

---

### A8. Updated Scene Builder

**File to modify:** `scene_builder.py`

Add the following import at the top of the file (after the existing imports):

```python
import random  # already present
import config  # already present
from prompts import digital_prompts, physical_prompts  # already present
from ugc_db.db_manager import get_product_shot  # already present
```

Then find the `build_scenes` function and replace its body with the following. The function signature remains identical.

```python
def build_scenes(content_row, influencer, app_clip, app_clip_2=None, product=None, product_type="digital"):
    """
    Build the scene structure from a Content Calendar row.

    NEW: If product_type == 'digital' AND a product dict is provided AND
    the app_clip has a first_frame_url, uses the new unified 2-scene digital
    pipeline (build_digital_unified). Falls back to the original logic otherwise.
    """
    length = content_row.get("Length", "15s")
    if length not in config.VALID_LENGTHS:
        length = "15s"

    durations = config.get_scene_durations(length)

    hook = content_row.get("Hook") or content_row.get("Script") or content_row.get("caption") or "Check this out!"
    assistant = content_row.get("AI Assistant", "Travel")
    theme = content_row.get("Theme", "")
    caption = content_row.get("Caption", "Link in bio!")

    person_name = influencer.get("name", "Sofia")
    age = influencer.get("age", "25-year-old")
    gender = influencer.get("gender", "Female")
    visuals = influencer.get("visual_description", "casual style")
    personality = influencer.get("personality", "friendly influencer")
    energy = influencer.get("energy_level", "High")
    accent = influencer.get("accent", "Castilian Spanish (Spain)")
    tone = influencer.get("tone", "Enthusiastic")
    voice_id = influencer.get("elevenlabs_voice_id", config.VOICE_MAP.get(person_name, config.VOICE_MAP["Meg"]))
    ref_image = influencer["reference_image_url"]

    p = {
        "subj": "He" if gender == "Male" else "She",
        "poss": "His" if gender == "Male" else "Her",
        "obj": "him" if gender == "Male" else "her",
    }

    ctx = {
        "name": person_name,
        "age": age,
        "gender": gender,
        "visuals": visuals,
        "personality": personality,
        "energy": energy,
        "accent": accent,
        "tone": tone,
        "voice_id": voice_id,
        "p": p,
        "ref_image": ref_image,
        "assistant": assistant,
        "hook": hook,
        "caption": caption,
        "consistency_seed": random.randint(1, 1000000),
    }

    # -----------------------------------------------------------------------
    # NEW: Digital Product Unified Pipeline
    # Triggered when: product_type is digital AND a product dict is provided
    # AND the app_clip has a first_frame_url (set by the frame extractor).
    # Falls back to the original logic if any of these conditions are not met.
    # -----------------------------------------------------------------------
    if (
        product_type == "digital"
        and product is not None
        and app_clip is not None
        and app_clip.get("first_frame_url")
    ):
        print(f"      🆕 Using unified digital pipeline for product: {product.get('name')}")
        return digital_prompts.build_digital_unified(
            influencer=influencer,
            product=product,
            app_clip=app_clip,
            duration=int(length.replace("s", "")),
            ctx=ctx,
        )

    # -----------------------------------------------------------------------
    # Physical Product Pipeline (UNCHANGED)
    # -----------------------------------------------------------------------
    cinematic_shot_ids = content_row.get("cinematic_shot_ids") or []
    cinematic_scenes = []
    if product_type == "physical" and cinematic_shot_ids:
        for shot_id in cinematic_shot_ids:
            shot = get_product_shot(shot_id)
            if shot and shot.get("video_url"):
                cinematic_scenes.append({
                    "name": f"cinematic_{shot['shot_type']}",
                    "type": "cinematic_shot",
                    "video_url": shot["video_url"],
                    "target_duration": 4.0,
                    "subtitle_text": "",
                })

    if product_type == "physical" and product:
        ctx["product"] = product
        influencer_scenes = physical_prompts.build_physical_product_scenes(content_row, influencer, product, durations, ctx)

        if not cinematic_scenes:
            return influencer_scenes

        final_scenes = []
        inf_idx, cin_idx = 0, 0
        while inf_idx < len(influencer_scenes) or cin_idx < len(cinematic_scenes):
            if inf_idx < len(influencer_scenes):
                final_scenes.append(influencer_scenes[inf_idx])
                inf_idx += 1
            if cin_idx < len(cinematic_scenes):
                final_scenes.append(cinematic_scenes[cin_idx])
                cin_idx += 1
        return final_scenes

    # -----------------------------------------------------------------------
    # Original Digital Pipeline (FALLBACK — unchanged)
    # Used when no product is linked or no first_frame_url exists.
    # -----------------------------------------------------------------------
    elif length == "30s":
        return digital_prompts.build_30s(durations, app_clip, ctx)
    else:
        return digital_prompts.build_15s(durations, app_clip, ctx)
```

---

### A9. Updated Worker Task

**File to modify:** `ugc_worker/tasks.py`

The worker already fetches the product dict for physical products. It needs to also fetch the product dict for digital products when a `product_id` is present. Find the section that handles `product_dict` (around line 141) and update it:

```python
        # Fetch product if linked — UPDATED: now also fetches for digital products
        product_dict = None
        if job.get("product_id"):
            prod_id = job["product_id"]
            prod_type = job.get("product_type", "digital")
            print(f"      📦 Fetching Product: {prod_id} (type: {prod_type})")
            prod_result = sb.table("products").select("*").eq("id", prod_id).execute()
            if prod_result.data:
                prod = prod_result.data[0]

                # For physical products: run auto-analysis if not yet done
                if prod_type == "physical" and not prod.get("visual_description"):
                    print(f"      👁️ Auto-analyzing physical product {prod_id}...")
                    try:
                        from ugc_backend.llm_vision_client import LLMVisionClient
                        from ugc_db.db_manager import update_product
                        client = LLMVisionClient()
                        analysis = client.describe_product_image(prod["image_url"])
                        if analysis:
                            update_product(prod_id, {"visual_description": analysis})
                            prod["visual_description"] = analysis
                    except Exception as e:
                        print(f"      ⚠️ Auto-analysis failed: {e}")

                product_dict = {
                    "id": prod["id"],
                    "name": prod["name"],
                    "description": prod.get("description", ""),
                    "image_url": prod.get("image_url", ""),
                    "category": prod.get("category", ""),
                    "visual_description": prod.get("visual_description"),
                    "website_url": prod.get("website_url"),  # NEW
                }
                print(f"      ✅ Product found: {prod['name']}")
            else:
                print(f"      ⚠️ Product ID {prod_id} not found!")
```

Also update the `app_clip_dict` fetching block to include `first_frame_url`:

```python
                app_clip_dict = {
                    "name": clip["name"],
                    "description": clip.get("description", ""),
                    "video_url": clip.get("video_url", ""),
                    "duration": clip.get("duration_seconds", 4),
                    "first_frame_url": clip.get("first_frame_url"),  # NEW
                    "product_id": clip.get("product_id"),            # NEW
                }
```

---

## PART B: SCENE TRANSITIONS BETWEEN VEO 3.1 SCENES

### B1. Transition Logic in `assemble_video.py`

**File to modify:** `assemble_video.py`

Add the following new function to the file. This function generates a smooth cross-dissolve transition between two video clips using FFmpeg's `xfade` filter. It is called by `assemble_video` when two consecutive scenes are both of type `veo` or `physical_product_scene`.

```python
# ---------------------------------------------------------------------------
# NEW: Scene Transition Generator
# ---------------------------------------------------------------------------

TRANSITION_DURATION = 0.5  # seconds — cross-dissolve between Veo scenes

def apply_transitions_between_veo_scenes(
    video_paths: list,
    scene_types: list,
    work_dir: Path,
) -> list:
    """
    Applies a cross-dissolve transition between consecutive Veo 3.1 scenes.
    Clips of type 'clip' or 'cinematic_shot' are passed through unchanged.

    A transition is applied between scene[i] and scene[i+1] ONLY when both
    scenes are AI-generated (type in {'veo', 'physical_product_scene',
    'digital_ugc'}).

    Args:
        video_paths:  Ordered list of local file paths to the scene videos.
        scene_types:  Ordered list of scene type strings (one per video).
        work_dir:     Temporary directory for intermediate files.

    Returns:
        New ordered list of file paths with transitions baked in.
        If no transitions are needed, returns the original list unchanged.
    """
    AI_SCENE_TYPES = {"veo", "physical_product_scene", "digital_ugc"}
    td = TRANSITION_DURATION

    # Check if any transitions are needed
    needs_transition = any(
        scene_types[i] in AI_SCENE_TYPES and scene_types[i + 1] in AI_SCENE_TYPES
        for i in range(len(scene_types) - 1)
    )

    if not needs_transition:
        return video_paths  # No change needed

    print(f"   🎞️ Applying cross-dissolve transitions between AI scenes...")

    result_paths = list(video_paths)  # Copy to avoid mutating the original

    for i in range(len(result_paths) - 1):
        if scene_types[i] not in AI_SCENE_TYPES or scene_types[i + 1] not in AI_SCENE_TYPES:
            continue

        clip_a = result_paths[i]
        clip_b = result_paths[i + 1]
        output = work_dir / f"transition_{i}_{i+1}.mp4"

        # Get duration of clip A to calculate xfade offset
        dur_a = get_video_duration(clip_a)
        if dur_a <= td:
            print(f"   ⚠️ Clip {i} too short for transition ({dur_a:.1f}s). Skipping.")
            continue

        offset = dur_a - td

        cmd = [
            "ffmpeg", "-y",
            "-i", str(clip_a),
            "-i", str(clip_b),
            "-filter_complex",
            (
                f"[0:v][1:v]xfade=transition=fade:duration={td}:offset={offset:.3f}[xv];"
                f"[0:a][1:a]acrossfade=d={td}[xa]"
            ),
            "-map", "[xv]",
            "-map", "[xa]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            str(output),
        ]

        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            print(f"   ⚠️ Transition FFmpeg failed for clips {i}-{i+1}. Using hard cut.")
            continue

        # Replace both clips with the merged transition output
        # Clip A is now the merged clip; clip B is removed from the list
        result_paths[i] = str(output)
        result_paths.pop(i + 1)
        scene_types.pop(i + 1)  # Keep scene_types in sync

        print(f"   ✅ Transition applied between scene {i+1} and scene {i+2}")

    return result_paths
```

Then update the `assemble_video` function signature and body to call this new function. Find the line in `assemble_video` that starts `print("\n🔧 Assembling final video...")` and add the following block immediately before it:

```python
    # Apply transitions between consecutive AI-generated scenes
    if scene_types:
        video_paths = apply_transitions_between_veo_scenes(
            video_paths=list(video_paths),
            scene_types=list(scene_types),
            work_dir=work_dir,
        )
```

This requires updating the `assemble_video` function signature to accept `scene_types`:

```python
def assemble_video(
    video_paths: list,
    output_path: Path,
    music_path: str | None,
    transcriptions: list,
    scene_durations: list,
    max_duration: int,
    scene_types: list | None = None,  # NEW: Optional list of scene type strings
):
```

And update the call site in `core_engine.py` to pass `scene_types`:

```python
    final_path = assemble_video.assemble_video(
        video_paths=video_paths_for_assembly,
        output_path=final_output_path,
        music_path=music_path_result[0],
        transcriptions=transcriptions_for_assembly,
        scene_durations=scene_durations_for_assembly,
        max_duration=config.get_max_duration(length),
        scene_types=[s.get("type", "clip") for s in ordered_scenes],  # NEW
    )
```

---

## PART C: 1-SECOND SCRIPT SAFETY BUFFER

### C1. Physical Products — Already Correct

The existing `ai_script_client.py` already documents the 17-word / 7-second rule. The `build_physical_product_scenes` function in `physical_prompts.py` already sets `target_duration: 8.0` with the comment `"8s Veo scene, ~7s dialogue + 1s buffer"`. No changes are needed for physical products.

### C2. Digital Products — Updated in `digital_prompts.py`

The new `build_digital_unified` function (added in A7 above) already enforces this rule: Scene 1 has `target_duration: 8.0` and the script is generated with a 17-word cap. The `generate_digital_product_script` method in `ai_script_client.py` (added in A4 above) also enforces the 17-word cap per part.

### C3. Original Digital Pipeline — Update `digital_prompts.py`

The existing `generate_ultra_prompt` function does not enforce a word cap. Update the system prompt comment in `ai_script_client.py` and add a word-cap enforcement to `generate_ultra_prompt` in `digital_prompts.py`.

Find the `generate_ultra_prompt` function in `digital_prompts.py` and add the following word-capping utility at the very top of the function body:

```python
def generate_ultra_prompt(scene_type, ctx):
    """
    Generates a structured stringified-YAML prompt for Seedance/Veo.
    Uses the user's script text verbatim as dialogue.
    Returns (prompt, script_text) tuple.

    SAFETY BUFFER: All script text is capped at 17 words (approx 7s of speech)
    to ensure dialogue finishes 1 second before the 8s scene ends.
    """
    MAX_WORDS = 17

    def _cap_words(text: str, max_words: int = MAX_WORDS) -> str:
        """Truncate text to max_words words at a sentence boundary if possible."""
        words = text.split()
        if len(words) <= max_words:
            return text
        # Try to truncate at a sentence boundary within the word limit
        truncated = " ".join(words[:max_words])
        # If the truncated text ends mid-sentence, add a period
        if not truncated.endswith((".", "!", "?")):
            truncated = truncated.rstrip(",;") + "."
        return truncated

    # ... (rest of the existing function body, unchanged)
    # Apply _cap_words to the script variable before it is used in the prompt:
    # Replace: script = sanitize_dialogue(ctx['hook'])
    # With:    script = _cap_words(sanitize_dialogue(ctx['hook']))
    # (Apply to all three script assignments in the if/elif/else block)
```

**Exact diff for the three script assignment lines in `generate_ultra_prompt`:**

```python
# BEFORE (line 22):
script = sanitize_dialogue(ctx['hook'])

# AFTER:
script = _cap_words(sanitize_dialogue(ctx['hook']))

# BEFORE (line 30):
script = sanitize_dialogue(ctx.get('reaction_text', ctx.get('caption', 'This is amazing!')))

# AFTER:
script = _cap_words(sanitize_dialogue(ctx.get('reaction_text', ctx.get('caption', 'This is amazing!'))))

# BEFORE (line 37):
script = sanitize_dialogue(ctx.get('caption', 'Check the link in bio!'))

# AFTER:
script = _cap_words(sanitize_dialogue(ctx.get('caption', 'Check the link in bio!')))
```

---

## PART D: FRONTEND CHANGES

### D1. Updated Types

**File to modify:** `frontend/src/lib/types.ts`

Add the following new interface definitions:

```typescript
export interface AppClip {
    id: string;
    name: string;
    description?: string;
    video_url: string;
    duration_seconds?: number;
    product_id?: string;       // NEW
    first_frame_url?: string;  // NEW
}

export interface Product {
    id: string;
    name: string;
    description?: string;
    category?: string;
    image_url: string;
    website_url?: string;      // NEW
    visual_description?: any;
}
```

### D2. Updated Create Page

**File to modify:** `frontend/src/app/create/page.tsx`

#### D2.1 — Add new state variables

Find the existing state declarations block and add:

```typescript
    // Digital Product — linked clips (NEW)
    const [linkedClips, setLinkedClips] = useState<AppClip[]>([]);
    const [selectedLinkedClip, setSelectedLinkedClip] = useState<string>('');
    const [isGeneratingScript, setIsGeneratingScript] = useState(false);
    const [generatedScript, setGeneratedScript] = useState('');
```

#### D2.2 — Add effect to fetch linked clips when a digital product is selected

Add this `useEffect` directly after the existing cinematic shots `useEffect`:

```typescript
    // Fetch app clips linked to the selected digital product
    useEffect(() => {
        if (productType === 'digital' && productId) {
            apiFetch(`/api/app-clips?product_id=${productId}`)
                .then((clips: AppClip[]) => {
                    setLinkedClips(clips || []);
                    // Auto-select the first linked clip if available
                    if (clips && clips.length > 0) {
                        setSelectedLinkedClip(clips[0].id);
                        setAppClipId(clips[0].id);
                    } else {
                        setLinkedClips([]);
                        setSelectedLinkedClip('');
                        // Fall back to 'auto' (random clip selection) if no linked clips
                        setAppClipId('auto');
                    }
                })
                .catch(() => {
                    setLinkedClips([]);
                    setAppClipId('auto');
                });
        }
    }, [productType, productId]);
```

#### D2.3 — Add script generation function for digital products

Add this function alongside the existing `generateHook` function:

```typescript
    async function generateDigitalScript() {
        if (!productId || productType !== 'digital') return;
        setIsGeneratingScript(true);
        try {
            const res = await fetch(`${API_URL}/api/scripts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: productId,
                    duration,
                    product_type: 'digital',
                }),
            });
            if (res.ok) {
                const data = await res.json();
                setGeneratedScript(data.script || '');
                setCustomScript(data.script || '');
            }
        } catch { /* silent */ }
        finally { setIsGeneratingScript(false); }
    }
```

#### D2.4 — Update the submit handler to pass `product_id` for digital products

In the `handleSubmit` function, update the single job creation body:

```typescript
            // Single creation
            await apiFetch('/jobs', {
                method: 'POST',
                body: JSON.stringify({
                    influencer_id: selectedInfluencer,
                    script_id: scriptSource === 'specific' ? selectedScript : undefined,
                    app_clip_id: (productType === 'digital' && appClipId !== 'auto') ? appClipId : undefined,
                    product_id: productId || undefined,           // NOW SENT FOR BOTH TYPES
                    product_type: productType,
                    hook: effectiveHook,
                    model_api: modelApi,
                    assistant_type: selectedInf?.style || 'Travel',
                    length: duration,
                    cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
                }),
            });
```

#### D2.5 — Add the linked clips selector UI

In the JSX, find the existing digital product section (the `productType === 'digital'` branch that shows the app clip grid) and replace it with:

```tsx
                {/* Digital Product Selection */}
                {productType === 'digital' && (
                    <div className="space-y-5">
                        {/* Step 1: Select Product */}
                        <div>
                            <label className="text-xs text-slate-400 font-medium mb-3 block">
                                Select Digital Product
                            </label>
                            {products.filter(p => p.category === 'digital' || !p.category).length === 0 ? (
                                <p className="text-slate-500 text-sm italic">
                                    No digital products found. Add one in the Library.
                                </p>
                            ) : (
                                <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
                                    {products.map((prod) => (
                                        <div
                                            key={prod.id}
                                            onClick={() => setProductId(prod.id)}
                                            className={`cursor-pointer rounded-xl overflow-hidden border-2 transition-all relative aspect-[3/4] bg-slate-800 ${
                                                productId === prod.id
                                                    ? 'border-blue-500 shadow-blue-500/20 shadow-lg scale-[1.02]'
                                                    : 'border-transparent opacity-60 hover:opacity-100'
                                            }`}
                                        >
                                            <img src={prod.image_url} alt={prod.name} className="w-full h-full object-cover" />
                                            <div className="absolute bottom-0 left-0 right-0 bg-black/70 p-2">
                                                <p className="text-xs text-white truncate">{prod.name}</p>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Step 2: Generate Script (only when product selected) */}
                        {productId && (
                            <div>
                                <div className="flex items-center justify-between mb-2">
                                    <label className="text-xs text-slate-400 font-medium">
                                        Script
                                    </label>
                                    <button
                                        onClick={generateDigitalScript}
                                        disabled={isGeneratingScript}
                                        className="text-xs text-blue-400 hover:text-blue-300 disabled:opacity-50 transition-colors"
                                    >
                                        {isGeneratingScript ? 'Generating...' : 'Generate with AI'}
                                    </button>
                                </div>
                                <textarea
                                    value={customScript}
                                    onChange={(e) => setCustomScript(e.target.value)}
                                    placeholder="AI will generate a script based on your product and website..."
                                    rows={3}
                                    className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500 resize-none"
                                />
                            </div>
                        )}

                        {/* Step 3: Select Linked App Clip */}
                        {productId && (
                            <div>
                                <label className="text-xs text-slate-400 font-medium mb-3 block">
                                    App Clip
                                    <span className="text-slate-600 ml-1">(linked to this product)</span>
                                </label>
                                {linkedClips.length === 0 ? (
                                    <div className="space-y-2">
                                        <p className="text-slate-500 text-sm italic">
                                            No clips linked to this product. Using auto-selection.
                                        </p>
                                        {/* Fallback: show all clips */}
                                        <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
                                            {appClips.slice(0, 8).map((clip) => (
                                                <div
                                                    key={clip.id}
                                                    onClick={() => setAppClipId(clip.id)}
                                                    className={`cursor-pointer rounded-xl overflow-hidden border-2 transition-all relative aspect-[9/16] bg-slate-800 ${
                                                        appClipId === clip.id
                                                            ? 'border-blue-500 shadow-blue-500/20 shadow-lg scale-[1.02]'
                                                            : 'border-transparent opacity-60 hover:opacity-100'
                                                    }`}
                                                >
                                                    <video src={clip.video_url} className="w-full h-full object-cover" muted />
                                                    <div className="absolute bottom-0 left-0 right-0 bg-black/70 p-2">
                                                        <p className="text-xs text-white truncate">{clip.name}</p>
                                                    </div>
                                                </div>
                                            ))}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
                                        {linkedClips.map((clip) => (
                                            <div
                                                key={clip.id}
                                                onClick={() => {
                                                    setSelectedLinkedClip(clip.id);
                                                    setAppClipId(clip.id);
                                                }}
                                                className={`cursor-pointer rounded-xl overflow-hidden border-2 transition-all relative aspect-[9/16] bg-slate-800 ${
                                                    selectedLinkedClip === clip.id
                                                        ? 'border-blue-500 shadow-blue-500/20 shadow-lg scale-[1.02]'
                                                        : 'border-transparent opacity-60 hover:opacity-100'
                                                }`}
                                            >
                                                {clip.first_frame_url ? (
                                                    <img
                                                        src={clip.first_frame_url}
                                                        alt={clip.name}
                                                        className="w-full h-full object-cover"
                                                    />
                                                ) : (
                                                    <video src={clip.video_url} className="w-full h-full object-cover" muted />
                                                )}
                                                <div className="absolute bottom-0 left-0 right-0 bg-black/70 p-2">
                                                    <p className="text-xs text-white truncate">{clip.name}</p>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}
```

### D3. Updated App Clips Page

**File to modify:** `frontend/src/app/library/page.tsx` (or wherever the App Clips tab is rendered)

Add a "Link to Product" dropdown to each app clip card. Find the app clip card rendering and add:

```tsx
{/* Link to Product dropdown — shown in edit mode or as inline control */}
<select
    value={clip.product_id || ''}
    onChange={async (e) => {
        const newProductId = e.target.value || null;
        await fetch(`${API_URL}/api/app-clips/${clip.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ product_id: newProductId }),
        });
        // Refresh the clips list
        fetchAppClips();
    }}
    className="w-full mt-2 bg-slate-800 border border-slate-700 rounded text-xs text-slate-300 px-2 py-1"
>
    <option value="">No product linked</option>
    {products.map((p) => (
        <option key={p.id} value={p.id}>{p.name}</option>
    ))}
</select>
```

### D4. Updated Products Page

**File to modify:** `frontend/src/app/library/page.tsx` (Products tab) or `frontend/src/app/products/page.tsx`

Add a `website_url` input field to the product creation/edit modal:

```tsx
{/* Website URL field — NEW */}
<div>
    <label className="text-xs text-slate-400 font-medium mb-1 block">
        Website URL
        <span className="text-slate-600 ml-1">(optional — used for AI script generation)</span>
    </label>
    <input
        type="url"
        value={websiteUrl}
        onChange={(e) => setWebsiteUrl(e.target.value)}
        placeholder="https://yourproduct.com"
        className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-blue-500"
    />
</div>
```

And update the product creation API call to include `website_url`:

```typescript
await fetch(`${API_URL}/api/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        name: productName,
        description: productDescription,
        category: productCategory,
        image_url: uploadedImageUrl,
        website_url: websiteUrl || undefined,  // NEW
    }),
});
```

---

## IMPLEMENTATION ORDER

Apply changes in this exact sequence to avoid dependency errors:

| Order | Action | Risk if Skipped |
| :--- | :--- | :--- |
| 1 | Run `011_digital_overhaul.sql` in Supabase | All subsequent steps fail |
| 2 | Create `app-clip-frames` bucket in Supabase Storage (public read) | Frame extraction uploads fail |
| 3 | Add `list_app_clips_by_product` + `update_app_clip` to `db_manager.py` | New API endpoints fail |
| 4 | Create `ugc_backend/web_scraper.py` | Digital script generation falls back silently |
| 5 | Create `ugc_backend/frame_extractor.py` | First-frame extraction unavailable |
| 6 | Replace `ugc_backend/ai_script_client.py` | Digital script generation unavailable |
| 7 | Update Pydantic models in `ugc_backend/main.py` | New API endpoints fail |
| 8 | Add new API endpoints to `ugc_backend/main.py` | Frontend cannot link clips to products |
| 9 | Add `build_digital_unified` to `prompts/digital_prompts.py` | New pipeline unavailable |
| 10 | Update `scene_builder.py` | New pipeline not triggered |
| 11 | Update `ugc_worker/tasks.py` | Product dict not passed for digital jobs |
| 12 | Add `apply_transitions_between_veo_scenes` to `assemble_video.py` | No transitions (not a blocker) |
| 13 | Update `assemble_video` signature and call site in `core_engine.py` | Transitions not applied |
| 14 | Update `digital_prompts.py` word cap | Scripts may be slightly long (not a blocker) |
| 15 | Update frontend types, create page, app clips page, products page | UI changes not visible |

---

## FINAL VALIDATION CHECKLIST

- [ ] Physical product video generation works end-to-end without any changes in behavior
- [ ] Digital video without a linked product still works (auto-selects a random clip)
- [ ] Digital video with a linked product uses the new 2-scene pipeline
- [ ] App clip creation automatically triggers first-frame extraction in the background
- [ ] The `first_frame_url` appears on the clip card in the App Clips page
- [ ] The Create page shows only clips linked to the selected digital product
- [ ] The AI script generation for digital products uses website content when available
- [ ] Cross-dissolve transitions appear between consecutive AI-generated scenes
- [ ] No script audio is cut off at scene boundaries
