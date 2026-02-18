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
# CRUD Helpers — Scripts
# ---------------------------------------------------------------------------

def list_scripts(category: str = None):
    sb = get_supabase()
    q = sb.table("scripts").select("*")
    if category:
        q = q.eq("category", category)
    return q.execute().data

def create_script(data: dict):
    sb = get_supabase()
    result = sb.table("scripts").insert(data).execute()
    return result.data[0] if result.data else None

def delete_script(script_id: str):
    sb = get_supabase()
    sb.table("scripts").delete().eq("id", script_id).execute()


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
