"""
UGC Engine v3 — FastAPI Backend (Supabase REST API)

Production API using Supabase REST API for all database operations.
No raw PostgreSQL TCP connections needed.
"""
# Fix Windows cp1252 console encoding — allows emoji/unicode in print() calls
import sys
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import random
from datetime import datetime, timezone

from ugc_backend.cost_service import cost_service
from ugc_backend.auth import get_current_user, get_optional_user
from ugc_backend.credit_cost_service import get_video_credit_cost, get_shot_credit_cost

from ugc_db.db_manager import (
    get_supabase,
    get_stats,
    list_influencers, get_influencer, create_influencer, update_influencer, delete_influencer,
    list_projects,
    list_scripts, create_script, update_script, delete_script, get_script,
    bulk_create_scripts, increment_script_usage,
    list_app_clips, list_app_clips_by_product, update_app_clip, create_app_clip, delete_app_clip,
    list_jobs, get_job, create_job, update_job, delete_job,
    list_products, create_product, delete_product, get_product, update_product,
    list_product_shots, get_product_shot, create_product_shot, update_product_shot, delete_product_shot,
    # SaaS layer
    get_profile, update_profile,
    create_project as db_create_project, update_project as db_update_project, delete_project as db_delete_project,
    get_subscription, get_wallet, list_transactions, deduct_credits, refund_credits,
    list_influencers_scoped, list_scripts_scoped, list_products_scoped,
    list_app_clips_scoped, list_jobs_scoped, list_product_shots_scoped,
    get_stats_scoped,
)

# Lazy Celery import — avoids blocking the backend if Redis isn't running
def _dispatch_worker(job_id: str) -> bool:
    """Try to dispatch a job to the Celery worker. Returns True if successful.
    First checks if Redis is reachable to avoid blocking.
    Falls back to running the task directly in a background thread."""
    import socket
    from urllib.parse import urlparse

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    parsed = urlparse(broker_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    # Quick socket check — if Redis isn't reachable, run in-process
    redis_available = False
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        redis_available = True
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass

    if redis_available:
        try:
            from ugc_worker.tasks import generate_ugc_video
            generate_ugc_video.delay(job_id)
            print(f"[OK] Job {job_id} dispatched to Celery worker")
            return True
        except Exception as e:
            print(f"!! Celery dispatch failed: {e}, falling back to in-process")

    # Fallback: run the task directly in a background thread
    import threading

    def _run_in_background():
        try:
            print(f"[RUN] Running job {job_id} in-process (no Redis)...")
            from ugc_worker.tasks import generate_ugc_video
            # Call the underlying function directly (not as a Celery task)
            generate_ugc_video(job_id)
        except Exception as e:
            print(f"[FAIL] In-process job {job_id} failed: {e}")
            from ugc_db.db_manager import update_job
            update_job(job_id, {"status": "failed", "error_message": str(e)})

    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()
    print(f"[START] Job {job_id} started in background thread (no Redis)")
    return True

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(title="UGC Engine SaaS API v3")


def _resolve_project_id(request: Request, user: dict | None) -> str | None:
    """Read X-Project-Id header sent by the frontend.
    Falls back to the user's default project if the header is missing."""
    pid = request.headers.get("x-project-id")
    if pid:
        return pid
    if user:
        user_projects = list_projects(user["id"])
        default_proj = next((p for p in (user_projects or []) if p.get("is_default")), (user_projects or [None])[0])
        return default_proj["id"] if default_proj else None
    return None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------

@app.on_event("startup")
def startup_event():
    try:
        get_supabase()
        print(">> Connected to Supabase (REST API)")
    except Exception as e:
        print(f"!! WARNING: Supabase connection failed: {e}")


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class InfluencerCreate(BaseModel):
    name: str
    gender: Optional[str] = None
    description: Optional[str] = None
    personality: Optional[str] = None
    style: Optional[str] = None
    speaking_style: Optional[str] = None
    target_audience: Optional[str] = None
    image_url: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    setting: Optional[str] = None  # Background/environment description (e.g. "outdoor garden with trees")

class ScriptCreate(BaseModel):
    """Create a script. Supports both legacy (text only) and v2 (structured JSON)."""
    text: Optional[str] = None             # Legacy ||| delimited string
    name: Optional[str] = None
    script_json: Optional[dict] = None     # New structured format
    category: Optional[str] = "General"
    methodology: Optional[str] = "Hook/Benefit/CTA"
    video_length: Optional[int] = 15
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None
    source: Optional[str] = "manual"

class ScriptUpdate(BaseModel):
    """Partial update for a script."""
    name: Optional[str] = None
    text: Optional[str] = None
    script_json: Optional[dict] = None
    category: Optional[str] = None
    methodology: Optional[str] = None
    video_length: Optional[int] = None
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None

class ScriptBulkItem(BaseModel):
    name: Optional[str] = None
    script_json: dict
    category: str = "General"
    methodology: str = "Hook/Benefit/CTA"
    video_length: int = 15
    source: str = "csv_upload"


class AppClipCreate(BaseModel):
    name: str
    description: Optional[str] = None
    video_url: str
    duration_seconds: Optional[int] = None
    product_id: Optional[str] = None       # NEW: Link to a digital product
    first_frame_url: Optional[str] = None  # NEW: Auto-populated on upload

class ProductCreate(BaseModel):
    name: str
    type: Optional[str] = None              # "physical" or "digital"
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: str
    website_url: Optional[str] = None      # NEW: For dual-source AI analysis

class AppClipUpdate(BaseModel):            # NEW: For PATCH endpoint
    product_id: Optional[str] = None
    first_frame_url: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None

class ShotGenerateRequest(BaseModel):
    shot_type: str
    variations: int = 1

class TransitionShotRequest(BaseModel):
    transition_type: str = "match_cut"      # 'match_cut', 'whip_pan', 'focus_pull'
    target_style: Optional[str] = None      # 'studio_white', 'natural_setting', 'moody'
    preceding_scene_video_url: str          # URL of the preceding influencer scene video

class JobCreate(BaseModel):
    influencer_id: str
    script_id: Optional[str] = None
    app_clip_id: Optional[str] = None
    product_id: Optional[str] = None            # NEW for Physical Products
    product_type: str = "digital"               # 'digital' or 'physical'
    hook: Optional[str] = None
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    length: int = 15
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None
    cinematic_shot_ids: Optional[List[str]] = None  # Cinematic Product Shots
    auto_transition_type: Optional[str] = None      # 'match_cut', 'whip_pan', 'focus_pull'

class BulkJobCreate(BaseModel):
    influencer_id: str
    count: int = 1
    duration: int = 15
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    product_type: str = "digital"               # NEW for Physical Products
    product_id: Optional[str] = None            # NEW for Physical Products
    hook: Optional[str] = None                  # AI-generated script from frontend
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None         # Campaign grouping name
    cinematic_shot_ids: Optional[List[str]] = None  # Cinematic Product Shots
    auto_transition_type: Optional[str] = None      # 'match_cut', 'whip_pan', 'focus_pull'

class SignedUrlRequest(BaseModel):
    bucket: str
    file_name: str

class CostEstimateRequest(BaseModel):
    script_text: str = ""
    duration: int = 15
    model: str = "seedance-1.5-pro"


# ... (existing classes)

# ---------------------------------------------------------------------------
# Products CRUD
# ---------------------------------------------------------------------------

@app.get("/api/products")
def api_list_products(request: Request, category: Optional[str] = None, user: dict = Depends(get_optional_user)):
    try:
        if user:
            pid = _resolve_project_id(request, user)
            if pid:
                products = list_products_scoped(user["id"], pid, category)
            else:
                products = []
        else:
            products = list_products(category)
        return products
    except Exception as e:
        print(f"ERROR in api_list_products: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products")
def api_create_product(data: ProductCreate):
    try:
        print(f"DEBUG: api_create_product called with {data}")
        result = create_product(data.model_dump(exclude_none=True))
        print(f"DEBUG: create_product result: {result}")
        return result
    except Exception as e:
        print(f"ERROR in api_create_product: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/products/{product_id}")
def api_update_product(product_id: str, data: dict):
    try:
        from ugc_db.db_manager import update_product
        print(f"DEBUG: api_update_product {product_id} with {data}")
        result = update_product(product_id, data)
        return result
    except Exception as e:
        print(f"ERROR in api_update_product: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/products/{product_id}")
def api_delete_product(product_id: str):
    try:
        delete_product(product_id)
        return {"status": "deleted", "id": product_id}
    except Exception as e:
        error_str = str(e)
        if "foreign key constraint" in error_str or "23503" in error_str:
            raise HTTPException(
                status_code=409, 
                detail="Cannot delete product because it is used in existing videos. Please delete the videos first."
            )
        print(f"ERROR in api_delete_product: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/products/upload")
def api_product_upload_url(data: SignedUrlRequest):
    try:
        # Generate unique filename to avoid 409 Duplicate
        import uuid
        name_parts = data.file_name.rsplit('.', 1)
        ext = f".{name_parts[1]}" if len(name_parts) > 1 else ""
        unique_name = f"{uuid.uuid4()}{ext}"
        
        print(f"DEBUG: api_product_upload_url processing {data.file_name} -> {unique_name}")
        
        sb = get_supabase()
        bucket = "product-images"
        
        try:
            result = sb.storage.from_(bucket).create_signed_upload_url(unique_name)
            # Construct public URL with the new unique name
            public_url = sb.storage.from_(bucket).get_public_url(unique_name)
            return {
                "signed_url": result.get("signedURL") or result.get("signed_url"), 
                "public_url": public_url, 
                "path": unique_name
            }
        except Exception as e:
            print(f"ERROR inside api_product_upload_url inner block: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create signed URL: {str(e)}")
            
    except Exception as e:
        print(f"ERROR in api_product_upload_url: {e}")
        import traceback
        traceback.print_exc()
        raise


class ProductAnalyzeRequest(BaseModel):
    product_id: str

@app.post("/api/products/analyze")
def api_analyze_product(data: ProductAnalyzeRequest):
    try:
        from ugc_backend.llm_vision_client import LLMVisionClient
        from ugc_db.db_manager import get_product, update_product
        
        print(f"DEBUG: Analyzing product {data.product_id}")
        
        # 1. Fetch Product
        product = get_product(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
            
        if not product.get("image_url"):
            raise HTTPException(status_code=400, detail="Product has no image URL")
            
        # 2. Analyze
        client = LLMVisionClient()
        analysis = client.describe_product_image(product["image_url"])
        
        if not analysis:
            raise HTTPException(status_code=500, detail="Vision analysis failed or returned empty")
            
        print(f"DEBUG: Analysis result: {analysis}")
        
        # 3. Update DB
        # Note: Using visual_description column as per Directive, mapping analysis result to it.
        # Ensure the column used matches DB schema. 
        # The prompt requested 'visual_description' JSONB. 
        # If migration 005 used 'visual_analysis', we should align. 
        # I will use 'visual_description' here and ensure migration 006 adds it.
        update_product(data.product_id, {"visual_description": analysis})
        
        return analysis
        
    except Exception as e:
        print(f"ERROR in api_analyze_product: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id}/analyze-digital")
def api_analyze_digital_product(product_id: str):
    """
    Runs dual-source analysis on a digital product:
    1. Scrapes the website_url for marketing copy.
    2. Runs vision analysis on the product image_url.
    3. Synthesizes both into a visual_description JSON and saves it.
    """
    try:
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
                print(f"      [OK] Vision analysis complete for product {product_id}")
            except Exception as e:
                print(f"      !! Vision analysis failed (non-fatal): {e}")

        # Step 2: Website scraping
        if product.get("website_url"):
            try:
                scraper = WebScraperClient()
                website_text = scraper.scrape(product["website_url"])
                if website_text:
                    analysis["website_content_summary"] = website_text[:500]
                    print(f"      [OK] Website scraping complete for product {product_id}")
            except Exception as e:
                print(f"      !! Website scraping failed (non-fatal): {e}")

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


class ScriptGenerateRequest(BaseModel):
    product_id: str
    duration: int = 15
    influencer_id: Optional[str] = None
    product_type: str = "physical"         # "digital" or "physical"
    output_format: str = "json"            # "json" (new) or "legacy" (||| string)
    methodology: Optional[str] = None      # Force a specific methodology
    context: Optional[str] = None          # Additional user instructions

@app.post("/api/scripts/generate")
def api_generate_script(data: ScriptGenerateRequest):
    """
    Generates a UGC script for a product.

    output_format="json" -> Uses three-call prompt chain, returns script_json.
    output_format="legacy" -> Uses the original single-call method, returns ||| string.
    """
    try:
        from ugc_backend.ai_script_client import AIScriptClient

        print(f"DEBUG: Generating {data.product_type} script for product {data.product_id} ({data.duration}s, format={data.output_format})")

        product = get_product(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        client = AIScriptClient()

        # Build influencer data dict (used by both paths)
        influencer_data = None
        if data.influencer_id:
            influencer = get_influencer(data.influencer_id)
            if influencer:
                influencer_data = {
                    "name": influencer.get("name", ""),
                    "personality": influencer.get("personality", ""),
                    "style": influencer.get("style", ""),
                    "gender": influencer.get("gender", "Female"),
                    "age": influencer.get("age", "25-year-old"),
                    "accent": influencer.get("accent", "neutral English"),
                    "tone": influencer.get("tone", "Enthusiastic"),
                    "energy_level": influencer.get("energy_level", "High"),
                }

        # === NEW: Structured JSON output via three-call prompt chain ===
        if data.output_format == "json":
            product_data = {
                "name": product.get("name", "Product"),
                "brand_name": product.get("name", "Product"),
                "category": product.get("category", data.product_type),
                **(product.get("visual_description") or {}),
            }
            script_json = client.generate_structured_script(
                product_data=product_data,
                influencer_data=influencer_data or {"name": "Creator"},
                video_length=data.duration,
                methodology=data.methodology,
                context=data.context,
            )
            return {"script_json": script_json, "product_id": data.product_id}

        # === LEGACY FALLBACK: ||| delimited string ===
        if data.product_type == "physical":
            visuals = product.get("visual_description") or {}
            script = client.generate_physical_product_script(
                product_analysis=visuals,
                duration=data.duration,
                product_name=product.get("name", "Product"),
                influencer_data=influencer_data,
            )
        else:
            visuals = product.get("visual_description") or {}
            website_content = None

            if product.get("website_url"):
                try:
                    from ugc_backend.web_scraper import WebScraperClient
                    scraper = WebScraperClient()
                    website_content = scraper.scrape(product["website_url"])
                    print(f"      [OK] Scraped {len(website_content or '')} chars from {product['website_url']}")
                except Exception as e:
                    print(f"      !! Website scraping failed (non-fatal): {e}")

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


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.post("/jobs")
def api_create_job(request: Request, data: JobCreate, user: dict = Depends(get_optional_user)):
    """
    Creates a new video generation job.
    Supports both digital (app demo) and physical product flows.
    """
    try:
        # 0. Credit Gate (only for authenticated users)
        if user:
            try:
                credit_cost = get_video_credit_cost(data.product_type, data.length)
                wallet = get_wallet(user["id"])
                if not wallet:
                    raise HTTPException(status_code=402, detail="Credit wallet not found. Please contact support.")
                if wallet["balance"] < credit_cost:
                    raise HTTPException(
                        status_code=402,
                        detail=f"Insufficient credits. Current balance: {wallet['balance']}. Required: {credit_cost}."
                    )
            except HTTPException:
                raise
            except Exception as e:
                print(f"      [Credit] Warning: credit check failed ({e}), proceeding anyway")
                credit_cost = None
        else:
            credit_cost = None

        # 1. Validate Influencer
        inf = get_influencer(data.influencer_id)
        if not inf:
            raise HTTPException(status_code=404, detail="Influencer not found")

        # 2. Flow-specific Validation
        if data.product_type == "physical" and not data.product_id:
            raise HTTPException(status_code=400, detail="product_id required for physical products")

        # 3. Auto-Select Script if missing
        script_text = ""
        if data.script_id:
            s = get_script(data.script_id)
            if s: script_text = s.get("text", "")
        elif data.hook:
            script_text = data.hook
        else:
            scripts = list_scripts()
            if scripts:
                s = random.choice(scripts)
                data.script_id = s.get("id")
                script_text = s.get("text", "")

        # 4. Auto-Select App Clip if missing (for digital products)
        if data.product_type == "digital" and not data.app_clip_id:
            clips = list_app_clips()
            if clips:
                inf_style = (inf.get("style") or "").lower().strip()
                matching_clips = [
                    c for c in clips
                    if inf_style and (
                        inf_style in (c.get("category") or "").lower()
                        or inf_style in (c.get("description") or "").lower()
                        or inf_style in (c.get("name") or "").lower()
                    )
                ]
                clip_pool = matching_clips if matching_clips else clips
                if clip_pool:
                    c = random.choice(clip_pool)
                    data.app_clip_id = c.get("id")

        # 5. Calculate Cost Estimate
        costs = cost_service.estimate_total_cost(
            script_text=script_text,
            duration=data.length,
            model=data.model_api,
            product_type=data.product_type
        )

        # 6. Prepare Job Data — dynamically detect actual DB columns
        # Query one row to discover real column names (empty table → fallback list)
        try:
            _probe = get_supabase().table("video_jobs").select("*").limit(1).execute()
            db_columns = set(_probe.data[0].keys()) if _probe.data else set()
        except Exception:
            db_columns = set()

        # Fallback: known safe columns if table is empty or query fails
        if not db_columns:
            db_columns = {
                "id", "user_id", "influencer_id", "app_clip_id", "script_id",
                "status", "progress", "final_video_url", "created_at", "updated_at",
                "product_type", "product_id", "cost_image",
                "hook", "model_api", "assistant_type", "length", "campaign_name",
                "cost_video", "cost_voice", "cost_music", "cost_processing", "total_cost",
                "cinematic_shot_ids", "error_message",
            }

        job_data = data.model_dump(exclude_none=True)
        job_data.update(costs)
        job_data["status"] = "pending"
        job_data["progress"] = 0

        # Inject user_id and project_id if authenticated
        if user:
            job_data["user_id"] = user["id"]
            pid = _resolve_project_id(request, user)
            if pid and "project_id" in db_columns:
                job_data["project_id"] = pid

        # Extract transition info for the worker (stored in job_data if column exists)
        auto_trans = job_data.pop("auto_transition_type", None)
        if auto_trans and "auto_transition_type" in db_columns:
            job_data["auto_transition_type"] = auto_trans

        # Store metadata if the column exists, otherwise just log it
        if "metadata" in db_columns:
            metadata = {}
            if auto_trans:
                metadata["auto_transition_type"] = auto_trans
            if job_data.get("cinematic_shot_ids"):
                metadata["cinematic_shot_ids"] = job_data["cinematic_shot_ids"]
            if data.hook:
                metadata["hook"] = data.hook
            if metadata:
                job_data["metadata"] = metadata

        # Strip any fields that don't exist as actual DB columns
        unknown_keys = [k for k in list(job_data.keys()) if k not in db_columns]
        for k in unknown_keys:
            val = job_data.pop(k)
            try:
                safe_val = str(val).encode('ascii', 'ignore').decode('ascii')[:80]
                print(f"   !! Stripped unknown column '{k}' (value: {safe_val})")
            except:
                pass

        print(f"DEBUG api_create_job: inserting keys={list(job_data.keys())}")

        # 7. Deduct credits (before creating job, so failed creation doesn't lose credits)
        deduction_result = None
        if user and credit_cost:
            try:
                deduction_result = deduct_credits(user["id"], credit_cost, {
                    "product_type": data.product_type,
                    "length": data.length,
                })
                print(f"      [Credit] Deducted {credit_cost} credits. New balance: {deduction_result['balance']}")
            except ValueError as e:
                raise HTTPException(status_code=402, detail=str(e))

        # 8. Create in DB
        job = create_job(job_data)
        if not job:
            # Refund if job creation failed
            if deduction_result and user:
                refund_credits(user["id"], credit_cost, {"reason": "job_creation_failed"})
            raise HTTPException(status_code=500, detail="Job creation returned empty result")

        # 9. Dispatch to Worker (non-blocking)
        worker_dispatched = _dispatch_worker(job["id"])

        return {**job, "worker_dispatched": worker_dispatched, "credits_deducted": credit_cost}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Job creation failed: {str(e)}")




# ---------------------------------------------------------------------------
# Product Shots API (Cinematic Product Shots)
# ---------------------------------------------------------------------------

@app.get("/api/products/{product_id}/shots")
def api_list_product_shots(product_id: str):
    """List all cinematic shots for a product."""
    try:
        return list_product_shots(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def _dispatch_shot_task(task_func, shot_id: str, task_name: str):
    """Dispatch a cinematic shot task — tries Celery, falls back to in-process thread."""
    import socket, threading
    from urllib.parse import urlparse

    broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
    parsed = urlparse(broker_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379

    redis_available = False
    try:
        sock = socket.create_connection((host, port), timeout=1)
        sock.close()
        redis_available = True
    except (socket.timeout, ConnectionRefusedError, OSError):
        pass

    if redis_available:
        try:
            task_func.delay(shot_id)
            print(f"[OK] Shot task '{task_name}' dispatched to Celery for {shot_id}")
            return
        except Exception as e:
            print(f"!! Celery dispatch failed: {e}, falling back to in-process")

    # Fallback: run directly in a background thread (no Redis needed)
    def _run():
        try:
            print(f"[RUN] Running shot task '{task_name}' in-process for {shot_id}...")
            task_func(shot_id)
        except Exception as e:
            print(f"[FAIL] Shot task '{task_name}' failed: {e}")
            update_product_shot(shot_id, {"status": "failed", "error_message": str(e)})

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    print(f"[START] Shot task '{task_name}' started in background thread for {shot_id}")


@app.post("/api/products/{product_id}/shots")
def api_generate_shot_image(product_id: str, data: ShotGenerateRequest):
    """Creates records and dispatches tasks to generate still images."""
    from ugc_worker.tasks import generate_product_shot_image
    try:
        created_shots = []
        for _ in range(data.variations):
            shot = create_product_shot({
                "product_id": product_id,
                "shot_type": data.shot_type,
                "status": "image_pending"
            })
            _dispatch_shot_task(generate_product_shot_image, shot["id"], "generate_product_shot_image")
            created_shots.append(shot)
        return created_shots
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/products/{product_id}/shots")
def api_get_product_shots(product_id: str):
    """Get all existing shots for a specific product."""
    from ugc_db.db_manager import list_product_shots
    try:
        return list_product_shots(product_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/shots/{shot_id}/animate")
def api_animate_shot(shot_id: str):
    """Dispatches a task to animate a still image into a video."""
    from ugc_worker.tasks import animate_product_shot_video
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise HTTPException(status_code=404, detail="Product shot not found")
        if not shot.get("image_url"):
            raise HTTPException(status_code=400, detail="Shot has no image yet")
        _dispatch_shot_task(animate_product_shot_video, shot_id, "animate_product_shot_video")
        return {"status": "animation_queued", "shot_id": shot_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/shots/costs")
def api_get_shot_costs():
    """Return cost estimates for cinematic shot generation."""
    return {
        "image_generation_cost": cost_service.estimate_shot_image_cost(),
        "animation_cost": cost_service.estimate_shot_animation_cost(),
    }

@app.delete("/api/shots/{shot_id}")
def api_delete_shot(shot_id: str):
    """Delete a product shot from the database."""
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise HTTPException(status_code=404, detail="Product shot not found")
        delete_product_shot(shot_id)
        return {"status": "deleted", "shot_id": shot_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/products/{product_id}/transition-shot")
def api_create_transition_shot(product_id: str, data: TransitionShotRequest):
    """
    Creates a transition shot that seamlessly blends with the preceding UGC scene.
    Pipeline: extract last frame → analyze → generate context-aware image → animate → stitch.
    """
    from ugc_worker.tasks import generate_transition_shot
    from ugc_db.db_manager import get_product

    valid_transitions = {"match_cut", "whip_pan", "focus_pull"}
    if data.transition_type not in valid_transitions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid transition_type. Must be one of: {valid_transitions}",
        )

    try:
        product = get_product(product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        # Create a product_shot record with transition metadata
        shot = create_product_shot({
            "product_id": product_id,
            "shot_type": "hero",  # Default base shot type for transitions
            "status": "image_pending",
            "transition_type": data.transition_type,
            "preceding_video_url": data.preceding_scene_video_url,
        })

        _dispatch_shot_task(
            generate_transition_shot,
            shot["id"],
            "generate_transition_shot",
        )

        return {
            "status": "transition_shot_queued",
            "shot_id": shot["id"],
            "transition_type": data.transition_type,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# ENDPOINTS
# =========================================================================

@app.get("/health")
def health():
    return {"status": "ok", "version": "3.0.0", "database": "supabase-rest"}


# ---------------------------------------------------------------------------
# Influencers CRUD
# ---------------------------------------------------------------------------

@app.get("/influencers")
def api_list_influencers(request: Request, user: dict = Depends(get_optional_user)):
    if user:
        pid = _resolve_project_id(request, user)
        if pid:
            return list_influencers_scoped(user["id"], pid)
        return []
    return list_influencers()

@app.get("/influencers/{influencer_id}")
def api_get_influencer(influencer_id: str):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    return inf

@app.post("/influencers")
def api_create_influencer(data: InfluencerCreate, request: Request, user: dict = Depends(get_optional_user)):
    try:
        payload = data.model_dump(exclude_none=True)
        # Inject ownership so the influencer appears in scoped queries
        if user:
            payload["user_id"] = user["id"]
            pid = _resolve_project_id(request, user)
            if pid:
                payload["project_id"] = pid
            print(f"  [DEBUG] CREATE INFLUENCER: user={user['id']}, project_id={pid}, payload_keys={list(payload.keys())}")
        else:
            print(f"  [DEBUG] CREATE INFLUENCER: NO USER (unauthenticated)")
        result = create_influencer(payload)
        print(f"  [DEBUG] CREATED: id={result.get('id')}, user_id={result.get('user_id')}, project_id={result.get('project_id')}")

        # Auto-analyze background setting from reference image (non-blocking)
        if result and result.get("image_url") and not result.get("setting"):
            import threading
            def _analyze_setting():
                try:
                    from ugc_backend.llm_vision_client import LLMVisionClient
                    client = LLMVisionClient()
                    setting = client.analyze_influencer_setting(result["image_url"])
                    if setting:
                        update_influencer(result["id"], {"setting": setting})
                        print(f"      [OK] Auto-analyzed setting for {result.get('name')}: {setting}")
                except Exception as e:
                    print(f"      !! Setting analysis failed for {result.get('name')}: {e}")
            threading.Thread(target=_analyze_setting, daemon=True).start()

        return result
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Influencer '{data.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/influencers/{influencer_id}")
def api_update_influencer(influencer_id: str, data: InfluencerCreate):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    update_data = data.model_dump(exclude_none=True)
    result = update_influencer(influencer_id, update_data)

    # Re-analyze setting if image_url changed and no explicit setting was provided
    image_changed = update_data.get("image_url") and update_data["image_url"] != inf.get("image_url")
    if image_changed and "setting" not in update_data:
        import threading
        def _analyze_setting():
            try:
                from ugc_backend.llm_vision_client import LLMVisionClient
                client = LLMVisionClient()
                setting = client.analyze_influencer_setting(update_data["image_url"])
                if setting:
                    update_influencer(influencer_id, {"setting": setting})
                    print(f"      [OK] Re-analyzed setting for {inf.get('name')}: {setting}")
            except Exception as e:
                print(f"      !! Setting re-analysis failed for {inf.get('name')}: {e}")
        threading.Thread(target=_analyze_setting, daemon=True).start()

    return result

@app.delete("/influencers/{influencer_id}")
def api_delete_influencer(influencer_id: str):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    delete_influencer(influencer_id)
    return {"status": "deleted", "id": influencer_id}


@app.post("/influencers/analyze-settings")
def api_analyze_all_influencer_settings():
    """Batch-analyze background/environment settings for all influencers that have an image but no setting."""
    from ugc_backend.llm_vision_client import LLMVisionClient

    all_influencers = list_influencers()
    if not all_influencers:
        return {"status": "no_influencers", "updated": 0, "skipped": 0, "failed": 0}

    client = LLMVisionClient()
    updated, skipped, failed = 0, 0, 0
    results = []

    for inf in all_influencers:
        name = inf.get("name", "Unknown")
        image_url = inf.get("image_url") or inf.get("reference_image_url")

        if not image_url:
            skipped += 1
            results.append({"name": name, "status": "skipped", "reason": "no image_url"})
            continue

        try:
            setting = client.analyze_influencer_setting(image_url)
            if setting:
                update_influencer(inf["id"], {"setting": setting})
                updated += 1
                results.append({"name": name, "status": "updated", "setting": setting})
                print(f"      [OK] Setting for {name}: {setting}")
            else:
                failed += 1
                results.append({"name": name, "status": "failed", "reason": "empty response"})
        except Exception as e:
            failed += 1
            results.append({"name": name, "status": "failed", "reason": str(e)})
            print(f"      !! Setting analysis failed for {name}: {e}")

    return {"status": "done", "updated": updated, "skipped": skipped, "failed": failed, "details": results}


# ---------------------------------------------------------------------------
# Scripts CRUD (v2 with structured JSON support)
# Legacy routes (/scripts) kept for backward compatibility.
# New routes (/api/scripts/*) for the new frontend.
# ---------------------------------------------------------------------------

@app.get("/scripts")
@app.get("/api/scripts")
def api_list_scripts(
    request: Request,
    category: Optional[str] = None,
    methodology: Optional[str] = None,
    video_length: Optional[int] = None,
    influencer_id: Optional[str] = None,
    product_id: Optional[str] = None,
    source: Optional[str] = None,
    is_trending: Optional[bool] = None,
    sort_by: Optional[str] = None,
    search: Optional[str] = None,
    user: dict = Depends(get_optional_user),
):
    filters = {}
    if methodology: filters["methodology"] = methodology
    if video_length: filters["video_length"] = video_length
    if influencer_id: filters["influencer_id"] = influencer_id
    if product_id: filters["product_id"] = product_id
    if source: filters["source"] = source
    if is_trending is not None: filters["is_trending"] = is_trending
    if sort_by: filters["sort_by"] = sort_by
    if search: filters["search"] = search
    if user:
        pid = _resolve_project_id(request, user)
        if pid:
            return list_scripts_scoped(user["id"], pid, **filters)
        return []
    return list_scripts(category, **filters)

@app.post("/scripts")
@app.post("/api/scripts")
def api_create_script(data: ScriptCreate):
    payload = data.model_dump(exclude_none=True)
    # Auto-generate name from hook if not provided
    if not payload.get("name"):
        if payload.get("script_json") and payload["script_json"].get("hook"):
            payload["name"] = payload["script_json"]["hook"][:80]
        elif payload.get("text"):
            payload["name"] = payload["text"][:80]
    return create_script(payload)

@app.put("/scripts/{script_id}")
@app.put("/api/scripts/{script_id}")
def api_update_script(script_id: str, data: ScriptUpdate):
    payload = data.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update.")
    result = update_script(script_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Script not found.")
    return result

@app.delete("/scripts/{script_id}")
@app.delete("/api/scripts/{script_id}")
def api_delete_script(script_id: str):
    delete_script(script_id)
    return {"status": "deleted", "id": script_id}

@app.post("/api/scripts/bulk")
def api_bulk_create_scripts(items: List[ScriptBulkItem]):
    """Insert multiple scripts at once (for CSV upload)."""
    scripts_data = []
    for item in items:
        d = item.model_dump(exclude_none=True)
        # Auto-generate name from hook
        if not d.get("name") and d.get("script_json", {}).get("hook"):
            d["name"] = d["script_json"]["hook"][:80]
        scripts_data.append(d)
    result = bulk_create_scripts(scripts_data)
    return {"imported": len(result), "scripts": result}

@app.post("/api/scripts/{script_id}/use")
def api_use_script(script_id: str):
    """Increment the times_used counter for a script."""
    new_count = increment_script_usage(script_id)
    return {"script_id": script_id, "times_used": new_count}

class FindTrendingRequest(BaseModel):
    topic: str = "UGC ads"
    max_scripts: int = 5
    sources: list[str] | None = None

@app.post("/api/scripts/find-trending")
def api_find_trending(data: FindTrendingRequest):
    """Trigger trending script discovery in the background."""
    import threading

    def _run_scraper():
        try:
            from ugc_backend.trending_scraper import scrape_trending_scripts
            scripts_data = scrape_trending_scripts(
                topic=data.topic,
                sources=data.sources,
                max_scripts=data.max_scripts,
            )
            # Save each extracted script
            for s in scripts_data:
                create_script({
                    "name": s.get("name", "Trending Script"),
                    "script_json": s,
                    "category": data.topic if data.topic != "UGC ads" else "General",
                    "methodology": s.get("methodology", "Hook/Benefit/CTA"),
                    "video_length": s.get("target_duration_sec", 15),
                    "source": "web_scraped",
                    "is_trending": True,
                })
            print(f"      [Trending] Saved {len(scripts_data)} scripts to database.")
        except Exception as e:
            import traceback
            print(f"      [Trending] Background job failed: {e}")
            traceback.print_exc()

    threading.Thread(target=_run_scraper, daemon=True).start()
    return {"status": "started", "message": f"Finding trending scripts for '{data.topic}'. Check back in a few seconds."}


# ---------------------------------------------------------------------------
# App Clips CRUD
# ---------------------------------------------------------------------------

@app.get("/app-clips")
def api_list_app_clips(request: Request, user: dict = Depends(get_optional_user)):
    if user:
        pid = _resolve_project_id(request, user)
        if pid:
            return list_app_clips_scoped(user["id"], pid)
        return []
    return list_app_clips()

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
                        print(f"      [OK] Auto-extracted first frame for clip {new_clip['id']}")
                except Exception as e:
                    print(f"      !! Auto frame extraction failed for clip {new_clip['id']}: {e}")
            threading.Thread(target=_extract_in_background, daemon=True).start()

        return new_clip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/app-clips/{clip_id}")
def api_delete_app_clip(clip_id: str):
    delete_app_clip(clip_id)
    return {"status": "deleted", "id": clip_id}


@app.get("/api/app-clips")
def api_list_app_clips_filtered(product_id: Optional[str] = None):
    """
    List app clips, optionally filtered by product_id.
    GET /api/app-clips                    -> all clips (backwards compatible)
    GET /api/app-clips?product_id={id}    -> clips linked to a specific product
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


# ---------------------------------------------------------------------------
# Storage: Signed URL for Direct Upload
# ---------------------------------------------------------------------------

@app.post("/assets/signed-url")
def create_signed_url(data: SignedUrlRequest):
    sb = get_supabase()
    allowed_buckets = {"influencer-images", "app-clips", "generated-videos"}
    if data.bucket not in allowed_buckets:
        raise HTTPException(status_code=400, detail=f"Invalid bucket. Allowed: {allowed_buckets}")
    try:
        result = sb.storage.from_(data.bucket).create_signed_upload_url(data.file_name)
        return {"signed_url": result.get("signedURL") or result.get("signed_url"), "path": data.file_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create signed URL: {str(e)}")


# ---------------------------------------------------------------------------
# Jobs: Single + Bulk
# ---------------------------------------------------------------------------




@app.post("/jobs/bulk")
def api_create_bulk_jobs(data: BulkJobCreate):
    try:
        inf = get_influencer(data.influencer_id)
        if not inf:
            raise HTTPException(status_code=404, detail="Influencer not found")

        scripts = list_scripts()
        clips = list_app_clips()
        if not scripts:
            raise HTTPException(status_code=400, detail="No scripts available. Add scripts first.")

        # Category-match clips to influencer
        inf_style = (inf.get("style") or "").lower().strip()
        matching_clips = [
            c for c in clips
            if inf_style and (
                inf_style in (c.get("category") or "").lower()
                or inf_style in (c.get("description") or "").lower()
                or inf_style in (c.get("name") or "").lower()
            )
        ] if clips else []
        clip_pool = matching_clips if matching_clips else clips

        # Detect actual DB columns dynamically (same approach as single job)
        try:
            _probe = get_supabase().table("video_jobs").select("*").limit(1).execute()
            db_columns = set(_probe.data[0].keys()) if _probe.data else set()
        except Exception:
            db_columns = set()

        if not db_columns:
            db_columns = {
                "id", "user_id", "influencer_id", "app_clip_id", "script_id",
                "status", "progress", "final_video_url", "created_at", "updated_at",
                "product_type", "product_id", "cost_image",
                "hook", "model_api", "assistant_type", "length", "campaign_name",
                "cost_video", "cost_voice", "cost_music", "cost_processing", "total_cost",
                "cinematic_shot_ids", "error_message",
            }

        created_jobs = []
        for _ in range(data.count):
            selected_script = random.choice(scripts)
            selected_clip = random.choice(clip_pool) if clip_pool else None

            # Use frontend hook if provided, otherwise fall back to random script text
            script_text = data.hook if data.hook else selected_script.get("text", "")
            costs = cost_service.estimate_total_cost(
                script_text=script_text,
                duration=data.duration,
                model=data.model_api,
                product_type=data.product_type
            )

            job_data = {
                "influencer_id": data.influencer_id,
                "script_id": selected_script["id"] if not data.hook else None,
                "app_clip_id": selected_clip["id"] if selected_clip else None,
                "product_type": data.product_type,
                "product_id": data.product_id,
                "model_api": data.model_api,
                "campaign_name": data.campaign_name,
                "length": data.duration,
                "status": "pending",
                "progress": 0,
                **costs,
            }
            if data.hook:
                job_data["hook"] = data.hook
            if data.cinematic_shot_ids:
                job_data["cinematic_shot_ids"] = data.cinematic_shot_ids

            # Store auto_transition_type directly if column exists
            if data.auto_transition_type and "auto_transition_type" in db_columns:
                job_data["auto_transition_type"] = data.auto_transition_type

            # Store metadata if the column exists
            if "metadata" in db_columns:
                metadata = {}
                if data.auto_transition_type:
                    metadata["auto_transition_type"] = data.auto_transition_type
                if job_data.get("cinematic_shot_ids"):
                    metadata["cinematic_shot_ids"] = job_data["cinematic_shot_ids"]
                if data.hook:
                    metadata["hook"] = data.hook
                if metadata:
                    job_data["metadata"] = metadata

            # Strip unknown columns
            unknown_keys = [k for k in list(job_data.keys()) if k not in db_columns]
            for k in unknown_keys:
                val = job_data.pop(k)
                try:
                    safe_val = str(val).encode('ascii', 'ignore').decode('ascii')[:80]
                    print(f"   !! [Bulk] Stripped unknown column '{k}' (value: {safe_val})")
                except:
                    pass

            job = create_job(job_data)
            if not job:
                print(f"WARNING: create_job returned None for bulk job")
                continue
            _dispatch_worker(job["id"])
            created_jobs.append(job["id"])

        return {"status": "dispatched", "count": len(created_jobs), "job_ids": created_jobs}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Bulk job creation failed: {str(e)}")


# ---------------------------------------------------------------------------
# Jobs: Status + History
# ---------------------------------------------------------------------------

@app.get("/jobs")
def api_list_jobs(request: Request, status: Optional[str] = None, limit: int = Query(default=50, le=200), user: dict = Depends(get_optional_user)):
    if user:
        pid = _resolve_project_id(request, user)
        return list_jobs_scoped(user["id"], project_id=pid, status=status, limit=limit)
    return list_jobs(status, limit)

@app.get("/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@app.delete("/jobs/{job_id}")
def api_delete_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    delete_job(job_id)
    return {"status": "deleted", "id": job_id}

@app.get("/jobs/{job_id}/status")
def api_get_job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "id": job["id"],
        "status": job["status"],
        "progress": job["progress"],
        "final_video_url": job.get("final_video_url"),
        "error_message": job.get("error_message"),
    }


# ---------------------------------------------------------------------------
# Dashboard Stats
# ---------------------------------------------------------------------------

@app.get("/stats")
def api_get_stats(user: dict = Depends(get_optional_user)):
    if user:
        stats = get_stats_scoped(user["id"])
        # Add projects count for the dashboard KPI
        user_projects = list_projects(user["id"])
        stats["projects"] = len(user_projects or [])
        return stats
    return get_stats()


@app.post("/estimate")
def api_estimate_cost(data: CostEstimateRequest):
    """Real-time cost estimation for the Create page."""
    return cost_service.estimate_total_cost(data.script_text, data.duration, data.model)


@app.get("/stats/costs")
def api_get_cost_stats(user: dict = Depends(get_optional_user)):
    """Aggregate spend stats for the Activity page — scoped per user when authenticated."""
    sb = get_supabase()
    # Build query — scope by user if authenticated
    q = sb.table("video_jobs").select("total_cost,created_at").not_.is_("total_cost", "null")
    if user:
        q = q.eq("user_id", user["id"])
    all_jobs = q.execute()
    rows = all_jobs.data or []

    total_all = sum(float(r.get("total_cost", 0) or 0) for r in rows)

    # This month
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_rows = [r for r in rows if r.get("created_at", "") >= month_start]
    total_month = sum(float(r.get("total_cost", 0) or 0) for r in month_rows)

    return {
        "total_spend_month": round(total_month, 2),
        "total_spend_all": round(total_all, 2),
    }


# ---------------------------------------------------------------------------
# AI Hook Generation (template-based, no external API needed)
# ---------------------------------------------------------------------------

class HookRequest(BaseModel):
    category: str = "General"
    influencer_id: Optional[str] = None

HOOK_TEMPLATES: dict[str, list[str]] = {
    "Travel": [
        "I found the most insane hidden spot and nobody's talking about it...",
        "This place literally broke my brain. You NEED to see this.",
        "POV: You just discovered your new favourite destination.",
        "Stop scrolling. This view is about to change your whole mood.",
        "I wasn't supposed to share this location, but...",
        "If this doesn't make you want to book a flight, nothing will.",
    ],
    "Fashion": [
        "This outfit hack is about to save you hundreds of dollars.",
        "Everyone's wearing this wrong. Here's how it's actually done.",
        "The fashion industry doesn't want you to know this trick.",
        "I found the exact dupe and it's even better than the original.",
        "Stop buying fast fashion. Try this instead.",
        "This one styling trick makes any outfit look 10x more expensive.",
    ],
    "Tech": [
        "This app just changed everything for me.",
        "Your phone can do this and you had NO idea.",
        "Delete that app. Use this instead.",
        "I've been using this wrong my entire life.",
        "This feature is hidden and nobody talks about it.",
        "The one setting you need to change right now.",
    ],
    "Fitness": [
        "I tried this for 30 days and the results are insane.",
        "Your trainer doesn't want you to know this.",
        "This one exercise replaces your entire workout.",
        "Stop doing crunches. Do this instead.",
        "The workout that actually transformed my body.",
        "3 minutes. That's all it takes. Watch this.",
    ],
    "Food": [
        "This recipe broke the internet and I had to try it.",
        "You've been making this wrong your entire life.",
        "The secret ingredient that changes everything.",
        "This 5-minute meal tastes like it took 2 hours.",
        "I can't believe this actually works.",
        "Chefs don't want you to know this simple trick.",
    ],
    "General": [
        "Wait for it... this is going to blow your mind.",
        "I need to tell you something nobody's talking about.",
        "This changed my entire perspective. Seriously.",
        "You're going to want to save this one.",
        "I wasn't going to post this, but you need to see it.",
        "If you only watch one video today, make it this one.",
        "POV: You just discovered something game-changing.",
        "Stop what you're doing. You need to hear this.",
    ],
}

@app.post("/ai/hook")
def api_generate_hook(data: HookRequest):
    category = data.category
    # Find the best matching template category
    templates = HOOK_TEMPLATES.get(category, None)
    if not templates:
        # Try case-insensitive match
        for key, val in HOOK_TEMPLATES.items():
            if key.lower() == category.lower():
                templates = val
                break
    if not templates:
        templates = HOOK_TEMPLATES["General"]

    hook = random.choice(templates)
    return {"hook": hook, "category": category}


# ===========================================================================
# SaaS ENDPOINTS — Authentication, Projects, Subscriptions, Credits
# ===========================================================================


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@app.get("/api/profile")
def api_get_profile(user: dict = Depends(get_current_user)):
    profile = get_profile(user["id"])
    if not profile:
        return {"id": user["id"], "email": user["email"], "name": None, "avatar_url": None}
    return profile

class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None

@app.put("/api/profile")
def api_update_profile(data: ProfileUpdateRequest, user: dict = Depends(get_current_user)):
    payload = data.model_dump(exclude_none=True)
    if not payload:
        raise HTTPException(status_code=400, detail="No fields to update")
    result = update_profile(user["id"], payload)
    if not result:
        raise HTTPException(status_code=404, detail="Profile not found")
    return result


# ---------------------------------------------------------------------------
# Projects CRUD
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str

class ProjectUpdate(BaseModel):
    name: str

@app.get("/api/projects")
def api_list_projects(user: dict = Depends(get_current_user)):
    return list_projects(user["id"])

@app.post("/api/projects")
def api_create_project(data: ProjectCreate, user: dict = Depends(get_current_user)):
    result = db_create_project(user["id"], data.name)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create project")
    return result

@app.put("/api/projects/{project_id}")
def api_update_project(project_id: str, data: ProjectUpdate, user: dict = Depends(get_current_user)):
    result = db_update_project(project_id, user["id"], {"name": data.name})
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return result

@app.delete("/api/projects/{project_id}")
def api_delete_project_endpoint(project_id: str, user: dict = Depends(get_current_user)):
    try:
        db_delete_project(project_id, user["id"])
        return {"status": "deleted", "id": project_id}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Subscription
# ---------------------------------------------------------------------------

@app.get("/api/plans")
def api_list_plans():
    """Return all active subscription plans from the database."""
    sb = get_supabase()
    result = sb.table("subscription_plans").select("*").eq("is_active", True).order("price_monthly", desc=False).execute()
    return result.data or []

@app.get("/api/subscription")
def api_get_subscription(user: dict = Depends(get_current_user)):
    sub = get_subscription(user["id"])
    if not sub:
        return {"status": "none", "plan": {"name": "Free", "credits_monthly": 0}}
    return sub


# ---------------------------------------------------------------------------
# Credit Wallet & Transactions
# ---------------------------------------------------------------------------

@app.get("/api/wallet")
def api_get_wallet(user: dict = Depends(get_current_user)):
    wallet = get_wallet(user["id"])
    if not wallet:
        return {"balance": 0, "user_id": user["id"]}
    return wallet

@app.get("/api/wallet/transactions")
def api_get_transactions(user: dict = Depends(get_current_user), limit: int = Query(default=50, le=200)):
    return list_transactions(user["id"], limit)


# ---------------------------------------------------------------------------
# Credit Costs Reference
# ---------------------------------------------------------------------------

@app.get("/api/credits/costs")
def api_get_credit_costs():
    """Return the full credit cost table for frontend display."""
    return {
        "digital_15s": 39,
        "digital_30s": 77,
        "physical_15s": 100,
        "physical_30s": 199,
        "cinematic_image_1k": 13,
        "cinematic_image_2k": 13,
        "cinematic_image_4k": 16,
        "cinematic_video_8s": 51,
    }


# ---------------------------------------------------------------------------
# Job Refund (for failed generations)
# ---------------------------------------------------------------------------

@app.post("/jobs/{job_id}/refund")
def api_refund_job(job_id: str, user: dict = Depends(get_current_user)):
    """Refund credits for a failed generation job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Only refund failed jobs
    if job.get("status") not in ("failed",):
        raise HTTPException(status_code=400, detail="Can only refund failed jobs")

    # Determine the credit cost to refund
    try:
        credit_cost = get_video_credit_cost(
            job.get("product_type", "digital"),
            job.get("length", 15)
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Cannot determine credit cost for this job type")

    try:
        result = refund_credits(user["id"], credit_cost, {
            "job_id": job_id,
            "reason": "failed_generation",
        })
        return {"status": "refunded", "amount": credit_cost, "new_balance": result["balance"]}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
