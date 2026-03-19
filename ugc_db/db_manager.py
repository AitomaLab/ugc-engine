"""
UGC Engine v3 — Database Manager (Supabase REST API)

Uses the Supabase Python client for all database operations.
This avoids IPv6/TCP connection issues from Windows by using
the Supabase REST API (PostgREST) instead of raw PostgreSQL.
"""
import os
from dotenv import load_dotenv

# Load SaaS production environment
load_dotenv(".env.saas")

# ---------------------------------------------------------------------------
# Supabase Client Singleton
# ---------------------------------------------------------------------------

_client = None

def create_supabase_client():
    """Create a new Supabase client instance."""
    from supabase import create_client, ClientOptions
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")
    if not url or not key:
        raise RuntimeError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env.saas. "
            "Get these from your Supabase dashboard > Settings > API."
        )
    # increase timeout for stability
    return create_client(url, key, options=ClientOptions(postgrest_client_timeout=20))

def get_supabase():
    """Get a fresh Supabase client (no singleton) to avoid thread/connection issues.
    This creates a new SSL connection for each logic block, which is safer for
    threaded environments + httpx/http2 stability."""
    # global _client
    # if _client is None:
    #     _client = create_supabase_client()
    # return _client
    return create_supabase_client()


# ---------------------------------------------------------------------------
# CRUD Helpers — Influencers
# ---------------------------------------------------------------------------

def list_influencers():
    sb = get_supabase()
    result = sb.table("influencers").select("*").execute()
    return result.data

def get_influencer(influencer_id: str):
    sb = get_supabase()
    result = sb.table("influencers").select("*").eq("id", influencer_id).execute()
    return result.data[0] if result.data else None

def create_influencer(data: dict):
    sb = get_supabase()
    result = sb.table("influencers").insert(data).execute()
    return result.data[0] if result.data else None

def update_influencer(influencer_id: str, data: dict):
    sb = get_supabase()
    result = sb.table("influencers").update(data).eq("id", influencer_id).execute()
    return result.data[0] if result.data else None

def delete_influencer(influencer_id: str):
    sb = get_supabase()
    sb.table("influencers").delete().eq("id", influencer_id).execute()


# ---------------------------------------------------------------------------
# CRUD Helpers — Scripts (v2 with structured JSON support)
# ---------------------------------------------------------------------------

def list_scripts(category: str = None, **filters):
    """List scripts with optional filtering, search, and sort.

    Backward-compatible: calling list_scripts() or list_scripts(category)
    works exactly as before. New callers can pass keyword args:
      methodology, video_length, influencer_id, product_id,
      source, is_trending, sort_by, search
    """
    sb = get_supabase()
    q = sb.table("scripts").select("*")
    if category:
        q = q.eq("category", category)
    if filters.get("methodology"):
        q = q.eq("methodology", filters["methodology"])
    if filters.get("video_length"):
        q = q.eq("video_length", filters["video_length"])
    if filters.get("influencer_id"):
        q = q.eq("influencer_id", filters["influencer_id"])
    if filters.get("product_id"):
        q = q.eq("product_id", filters["product_id"])
    if filters.get("source"):
        q = q.eq("source", filters["source"])
    if filters.get("is_trending") is not None:
        q = q.eq("is_trending", filters["is_trending"])
    if filters.get("search"):
        term = filters["search"]
        q = q.or_(f"name.ilike.%{term}%,text.ilike.%{term}%")

    sort_by = filters.get("sort_by", "created_at_desc")
    if sort_by == "created_at_desc":
        q = q.order("created_at", desc=True)
    elif sort_by == "times_used_desc":
        q = q.order("times_used", desc=True)
    elif sort_by == "name_asc":
        q = q.order("name", desc=False)

    return q.execute().data

def create_script(data: dict):
    sb = get_supabase()
    # Known columns in the scripts table (strip anything else)
    VALID_COLS = {
        "id", "name", "text", "script_json", "category", "methodology",
        "video_length", "product_id", "influencer_id", "source",
        "is_trending", "times_used", "created_at",
    }
    # If name was provided, store it inside script_json
    if "name" in data and data.get("script_json"):
        if isinstance(data["script_json"], dict):
            data["script_json"]["name"] = data["name"]
    # Also store name as legacy text fallback if text not provided
    if "name" in data and not data.get("text"):
        data["text"] = data["name"]
    clean = {k: v for k, v in data.items() if k in VALID_COLS}
    result = sb.table("scripts").insert(clean).execute()
    return result.data[0] if result.data else None

def update_script(script_id: str, data: dict):
    """Update a script by ID. Supports partial updates."""
    sb = get_supabase()
    VALID_COLS = {
        "name", "text", "script_json", "category", "methodology",
        "video_length", "product_id", "influencer_id", "source",
        "is_trending", "times_used",
    }
    if "name" in data and data.get("script_json"):
        if isinstance(data["script_json"], dict):
            data["script_json"]["name"] = data["name"]
    clean = {k: v for k, v in data.items() if k in VALID_COLS}
    result = sb.table("scripts").update(clean).eq("id", script_id).execute()
    return result.data[0] if result.data else None

def delete_script(script_id: str):
    sb = get_supabase()
    sb.table("scripts").delete().eq("id", script_id).execute()

def get_script(script_id: str):
    sb = get_supabase()
    result = sb.table("scripts").select("*").eq("id", script_id).execute()
    return result.data[0] if result.data else None

def bulk_create_scripts(scripts_list: list):
    """Insert multiple scripts in a single call (for CSV upload)."""
    if not scripts_list:
        return []
    sb = get_supabase()
    VALID_COLS = {
        "id", "name", "text", "script_json", "category", "methodology",
        "video_length", "product_id", "influencer_id", "source",
        "is_trending", "times_used", "created_at",
    }
    cleaned = []
    for item in scripts_list:
        if "name" in item and item.get("script_json"):
            if isinstance(item["script_json"], dict):
                item["script_json"]["name"] = item["name"]
        if "name" in item and not item.get("text"):
            item["text"] = item["name"]
        cleaned.append({k: v for k, v in item.items() if k in VALID_COLS})
    result = sb.table("scripts").insert(cleaned).execute()
    return result.data

def increment_script_usage(script_id: str):
    """Increment the times_used counter for a script."""
    sb = get_supabase()
    script = get_script(script_id)
    if script:
        new_count = (script.get("times_used") or 0) + 1
        sb.table("scripts").update({"times_used": new_count}).eq("id", script_id).execute()
        return new_count
    return 0


# ---------------------------------------------------------------------------
# CRUD Helpers — App Clips
# ---------------------------------------------------------------------------

def list_app_clips():
    sb = get_supabase()
    return sb.table("app_clips").select("*").execute().data

def create_app_clip(data: dict):
    sb = get_supabase()
    result = sb.table("app_clips").insert(data).execute()
    return result.data[0] if result.data else None

def delete_app_clip(clip_id: str):
    sb = get_supabase()
    sb.table("app_clips").delete().eq("id", clip_id).execute()

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


# ---------------------------------------------------------------------------
# CRUD Helpers — Products
# ---------------------------------------------------------------------------

def list_products(category: str = None):
    sb = get_supabase()
    q = sb.table("products").select("*")
    if category:
        q = q.eq("category", category)
    return q.execute().data

def get_product(product_id: str):
    sb = get_supabase()
    result = sb.table("products").select("*").eq("id", product_id).execute()
    return result.data[0] if result.data else None

def create_product(data: dict):
    sb = get_supabase()
    result = sb.table("products").insert(data).execute()
    return result.data[0] if result.data else None

def update_product(product_id: str, data: dict):
    sb = get_supabase()
    result = sb.table("products").update(data).eq("id", product_id).execute()
    return result.data[0] if result.data else None

def delete_product(product_id: str):
    sb = get_supabase()
    # Cascade: nullify product_id in video_jobs so videos aren't deleted
    sb.table("video_jobs").update({"product_id": None}).eq("product_id", product_id).execute()
    # Cascade: delete associated product shots
    sb.table("product_shots").delete().eq("product_id", product_id).execute()
    # Now safe to delete the product itself
    sb.table("products").delete().eq("id", product_id).execute()


# ---------------------------------------------------------------------------
# CRUD Helpers — Video Jobs
# ---------------------------------------------------------------------------

def list_jobs(status: str = None, limit: int = 50):
    sb = get_supabase()
    q = sb.table("video_jobs").select("*").order("created_at", desc=True).limit(limit)
    if status:
        q = q.eq("status", status)
    return q.execute().data

def get_job(job_id: str):
    sb = get_supabase()
    result = sb.table("video_jobs").select("*").eq("id", job_id).execute()
    return result.data[0] if result.data else None

def create_job(data: dict):
    sb = get_supabase()
    result = sb.table("video_jobs").insert(data).execute()
    return result.data[0] if result.data else None

def update_job(job_id: str, data: dict):
    sb = get_supabase()
    result = sb.table("video_jobs").update(data).eq("id", job_id).execute()
    return result.data[0] if result.data else None

def delete_job(job_id: str):
    sb = get_supabase()
    sb.table("video_jobs").delete().eq("id", job_id).execute()


# ---------------------------------------------------------------------------
# CRUD Helpers — Social Posts
# ---------------------------------------------------------------------------

def list_social_posts(status: str = None):
    sb = get_supabase()
    q = sb.table("social_posts").select("*")
    if status:
        q = q.eq("status", status)
    return q.execute().data

def create_social_post(data: dict):
    sb = get_supabase()
    result = sb.table("social_posts").insert(data).execute()
    return result.data[0] if result.data else None

def update_social_post(post_id: str, data: dict):
    sb = get_supabase()
    sb.table("social_posts").update(data).eq("id", post_id).execute()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

def get_stats():
    sb = get_supabase()
    total = len(sb.table("video_jobs").select("id").execute().data)
    pending = len(sb.table("video_jobs").select("id").eq("status", "pending").execute().data)
    processing = len(sb.table("video_jobs").select("id").eq("status", "processing").execute().data)
    success = len(sb.table("video_jobs").select("id").eq("status", "success").execute().data)
    failed = len(sb.table("video_jobs").select("id").eq("status", "failed").execute().data)
    influencers = len(sb.table("influencers").select("id").execute().data)
    scripts = len(sb.table("scripts").select("id").execute().data)
    app_clips = len(sb.table("app_clips").select("id").execute().data)

    return {
        "total_jobs": total,
        "pending": pending,
        "processing": processing,
        "success": success,
        "failed": failed,
        "influencers": influencers,
        "scripts": scripts,
        "app_clips": app_clips,
    }


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

def delete_product_shot(shot_id: str):
    sb = get_supabase()
    sb.table("product_shots").delete().eq("id", shot_id).execute()

