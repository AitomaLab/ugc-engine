"""
UGC Engine v3 — FastAPI Backend (Supabase REST API)

Production API using Supabase REST API for all database operations.
No raw PostgreSQL TCP connections needed.
"""
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import random
from datetime import datetime, timezone

from ugc_backend.cost_service import cost_service

from ugc_db.db_manager import (
    get_supabase,
    list_influencers, get_influencer, create_influencer, update_influencer, delete_influencer,
    list_scripts, create_script, delete_script, get_script,
    list_app_clips, create_app_clip, delete_app_clip,
    list_jobs, get_job, create_job, update_job,
    get_stats,
    list_products, create_product, delete_product,
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
            print(f"✅ Job {job_id} dispatched to Celery worker")
            return True
        except Exception as e:
            print(f"⚠️ Celery dispatch failed: {e}, falling back to in-process")

    # Fallback: run the task directly in a background thread
    import threading

    def _run_in_background():
        try:
            print(f"🔧 Running job {job_id} in-process (no Redis)...")
            from ugc_worker.tasks import generate_ugc_video
            # Call the underlying function directly (not as a Celery task)
            generate_ugc_video(job_id)
        except Exception as e:
            print(f"❌ In-process job {job_id} failed: {e}")
            from ugc_db.db_manager import update_job
            update_job(job_id, {"status": "failed", "error_message": str(e)})

    thread = threading.Thread(target=_run_in_background, daemon=True)
    thread.start()
    print(f"🚀 Job {job_id} started in background thread (no Redis)")
    return True

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(title="UGC Engine SaaS API v3")

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
        print("🗄️  Connected to Supabase (REST API)")
    except Exception as e:
        print(f"⚠️  Supabase connection failed: {e}")


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class InfluencerCreate(BaseModel):
    name: str
    description: Optional[str] = None
    personality: Optional[str] = None
    style: Optional[str] = None
    speaking_style: Optional[str] = None
    target_audience: Optional[str] = None
    image_url: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None

class ScriptCreate(BaseModel):
    text: str
    category: Optional[str] = None

class AppClipCreate(BaseModel):
    name: str
    description: Optional[str] = None
    video_url: str
    duration_seconds: Optional[int] = None

class ProductCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    image_url: str

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

class BulkJobCreate(BaseModel):
    influencer_id: str
    count: int = 1
    duration: int = 15
    model_api: str = "seedance-1.5-pro"
    assistant_type: str = "Travel"
    product_type: str = "digital"               # NEW for Physical Products
    product_id: Optional[str] = None            # NEW for Physical Products
    user_id: Optional[str] = None
    campaign_name: Optional[str] = None     # Campaign grouping name

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
def api_list_products(category: Optional[str] = None):
    try:
        print(f"DEBUG: api_list_products called with category={category}")
        return list_products(category)
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



class ScriptGenerateRequest(BaseModel):
    product_id: str
    duration: int = 15

@app.post("/api/scripts/generate")
def api_generate_script(data: ScriptGenerateRequest):
    try:
        from ugc_backend.ai_script_client import AIScriptClient
        from ugc_db.db_manager import get_product
        
        print(f"DEBUG: Generating script for product {data.product_id} ({data.duration}s)")
        
        # 1. Fetch Product
        product = get_product(data.product_id)
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
            
        # 2. Generate Script
        client = AIScriptClient()
        # Use visual_description if available, otherwise empty dict (client handles defaults)
        visuals = product.get("visual_description") or {}
        
        script = client.generate_physical_product_script(
            product_analysis=visuals, 
            duration=data.duration, 
            product_name=product.get("name", "Product")
        )
        
        return {"script": script}
        
    except Exception as e:
        print(f"ERROR in api_generate_script: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

@app.post("/jobs")
def api_create_job(data: JobCreate):
    """
    Creates a new video generation job.
    Supports both digital (app demo) and physical product flows.
    """
    # 1. Validate Influencer
    inf = get_influencer(data.influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")

    # 2. Flow-specific Validation
    if data.product_type == "physical" and not data.product_id:
        raise HTTPException(status_code=400, detail="product_id required for physical products")

    # 3. Calculate Cost Estimate
    script_text = ""
    if data.script_id:
        s = get_script(data.script_id)
        if s: script_text = s.get("text", "")
    elif data.hook:
        script_text = data.hook

    costs = cost_service.estimate_total_cost(
        script_text=script_text,
        duration=data.length,
        model=data.model_api,
        product_type=data.product_type
    )

    # 4. Prepare Job Data
    job_data = data.model_dump(exclude_none=True)
    job_data.update(costs)
    job_data["status"] = "pending"
    job_data["progress"] = 0
    
    # 5. Create in DB
    job = create_job(job_data)
    
    # 6. Dispatch to Worker (non-blocking)
    worker_dispatched = _dispatch_worker(job["id"])
    
    return {**job, "worker_dispatched": worker_dispatched}




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
def api_list_influencers():
    return list_influencers()

@app.get("/influencers/{influencer_id}")
def api_get_influencer(influencer_id: str):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    return inf

@app.post("/influencers")
def api_create_influencer(data: InfluencerCreate):
    try:
        result = create_influencer(data.model_dump(exclude_none=True))
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
    result = update_influencer(influencer_id, data.model_dump(exclude_none=True))
    return result

@app.delete("/influencers/{influencer_id}")
def api_delete_influencer(influencer_id: str):
    inf = get_influencer(influencer_id)
    if not inf:
        raise HTTPException(status_code=404, detail="Influencer not found")
    delete_influencer(influencer_id)
    return {"status": "deleted", "id": influencer_id}


# ---------------------------------------------------------------------------
# Scripts CRUD
# ---------------------------------------------------------------------------

@app.get("/scripts")
def api_list_scripts(category: Optional[str] = None):
    return list_scripts(category)

@app.post("/scripts")
def api_create_script(data: ScriptCreate):
    return create_script(data.model_dump(exclude_none=True))

@app.delete("/scripts/{script_id}")
def api_delete_script(script_id: str):
    delete_script(script_id)
    return {"status": "deleted", "id": script_id}


# ---------------------------------------------------------------------------
# App Clips CRUD
# ---------------------------------------------------------------------------

@app.get("/app-clips")
def api_list_app_clips():
    return list_app_clips()

@app.post("/app-clips")
def api_create_app_clip(data: AppClipCreate):
    return create_app_clip(data.model_dump(exclude_none=True))

@app.delete("/app-clips/{clip_id}")
def api_delete_app_clip(clip_id: str):
    delete_app_clip(clip_id)
    return {"status": "deleted", "id": clip_id}


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

    created_jobs = []
    for _ in range(data.count):
        selected_script = random.choice(scripts)
        selected_clip = random.choice(clip_pool) if clip_pool else None

        # Calculate cost for this specific job
        script_text = selected_script.get("text", "")
        costs = cost_service.estimate_total_cost(
            script_text=script_text,
            duration=data.duration,
            model=data.model_api,
            product_type=data.product_type
        )

        job = create_job({
            "influencer_id": data.influencer_id,
            "script_id": selected_script["id"],
            "app_clip_id": selected_clip["id"] if selected_clip else None,
            "product_type": data.product_type,
            "product_id": data.product_id,
            "model_api": data.model_api,
            "campaign_name": data.campaign_name,
            "status": "pending",
            "progress": 0,
            **costs,
        })
        _dispatch_worker(job["id"])
        created_jobs.append(job["id"])

    return {"status": "dispatched", "count": len(created_jobs), "job_ids": created_jobs}


# ---------------------------------------------------------------------------
# Jobs: Status + History
# ---------------------------------------------------------------------------

@app.get("/jobs")
def api_list_jobs(status: Optional[str] = None, limit: int = Query(default=50, le=200)):
    return list_jobs(status, limit)

@app.get("/jobs/{job_id}")
def api_get_job(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

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
def api_get_stats():
    return get_stats()


@app.post("/estimate")
def api_estimate_cost(data: CostEstimateRequest):
    """Real-time cost estimation for the Create page."""
    return cost_service.estimate_total_cost(data.script_text, data.duration, data.model)


@app.get("/stats/costs")
def api_get_cost_stats():
    """Aggregate spend stats for the Activity page."""
    sb = get_supabase()
    # All jobs with costs
    all_jobs = sb.table("video_jobs").select("total_cost,created_at").not_.is_("total_cost", "null").execute()
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

