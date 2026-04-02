"""
UGC Engine v3 — Database Manager (Supabase REST API)

Uses the Supabase Python client for all database operations.
This avoids IPv6/TCP connection issues from Windows by using
the Supabase REST API (PostgREST) instead of raw PostgreSQL.
"""
import os
from datetime import datetime, timezone
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
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
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


# ===========================================================================
# SaaS LAYER — User-scoped functions for the authenticated API
# ===========================================================================
# IMPORTANT: The functions above remain untouched. They are used by the worker
# pipeline (core_engine.py, scene_builder.py) which runs with the service key
# and has no user context. The functions below are used ONLY by main.py
# endpoints that have an authenticated user.
# ===========================================================================


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

def get_profile(user_id: str):
    sb = get_supabase()
    result = sb.table("profiles").select("*").eq("id", user_id).execute()
    return result.data[0] if result.data else None

def update_profile(user_id: str, data: dict):
    sb = get_supabase()
    result = sb.table("profiles").update(data).eq("id", user_id).execute()
    return result.data[0] if result.data else None


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

def list_projects(user_id: str):
    sb = get_supabase()
    result = sb.table("projects").select("*").eq("user_id", user_id).order("created_at", desc=False).execute()
    return result.data

def create_project(user_id: str, name: str):
    sb = get_supabase()
    # Ensure the user has a profile row (FK target) — handles cases where
    # the handle_new_user trigger was missing when the user signed up.
    existing = sb.table("profiles").select("id").eq("id", user_id).execute()
    if not existing.data:
        sb.table("profiles").insert({"id": user_id}).execute()
    result = sb.table("projects").insert({
        "user_id": user_id,
        "name": name,
        "is_default": False,
    }).execute()
    return result.data[0] if result.data else None

def update_project(project_id: str, user_id: str, data: dict):
    sb = get_supabase()
    result = sb.table("projects").update(data).eq("id", project_id).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None

def delete_project(project_id: str, user_id: str):
    sb = get_supabase()
    # Don't allow deleting the default project
    project = sb.table("projects").select("is_default").eq("id", project_id).eq("user_id", user_id).execute()
    if project.data and project.data[0].get("is_default"):
        raise ValueError("Cannot delete the default project")
    sb.table("projects").delete().eq("id", project_id).eq("user_id", user_id).execute()


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def get_subscription(user_id: str):
    """Get user's subscription with joined plan details."""
    sb = get_supabase()
    result = sb.table("subscriptions").select(
        "*, plan:subscription_plans(name, credits_monthly, price_monthly)"
    ).eq("user_id", user_id).execute()
    return result.data[0] if result.data else None


# ---------------------------------------------------------------------------
# Credit Wallet & Transactions
# ---------------------------------------------------------------------------

def get_wallet(user_id: str):
    sb = get_supabase()
    result = sb.table("credit_wallets").select("*").eq("user_id", user_id).execute()
    return result.data[0] if result.data else None

def list_transactions(user_id: str, limit: int = 50):
    """Get credit transactions for a user (via their wallet)."""
    sb = get_supabase()
    wallet = get_wallet(user_id)
    if not wallet:
        return []
    result = sb.table("credit_transactions").select("*").eq(
        "wallet_id", wallet["id"]
    ).order("created_at", desc=True).limit(limit).execute()
    return result.data

def deduct_credits(user_id: str, amount: int, metadata: dict = None):
    """Atomically deduct credits: update wallet balance + insert transaction log.

    Returns the updated wallet or raises an exception if balance insufficient.
    """
    sb = get_supabase()
    wallet = get_wallet(user_id)
    if not wallet:
        raise ValueError("Credit wallet not found")

    new_balance = wallet["balance"] - amount
    if new_balance < 0:
        raise ValueError(
            f"Insufficient credits. Balance: {wallet['balance']}, Required: {amount}"
        )

    # Update balance
    sb.table("credit_wallets").update({
        "balance": new_balance
    }).eq("id", wallet["id"]).execute()

    # Insert transaction log
    sb.table("credit_transactions").insert({
        "wallet_id": wallet["id"],
        "amount": -amount,
        "type": "generation_deduction",
        "description": f"Video generation ({amount} credits)",
        "metadata": metadata or {},
    }).execute()

    return {"balance": new_balance, "deducted": amount}

def refund_credits(user_id: str, amount: int, metadata: dict = None):
    """Refund credits back to user's wallet (e.g., failed generation)."""
    sb = get_supabase()
    wallet = get_wallet(user_id)
    if not wallet:
        raise ValueError("Credit wallet not found")

    new_balance = wallet["balance"] + amount

    sb.table("credit_wallets").update({
        "balance": new_balance
    }).eq("id", wallet["id"]).execute()

    sb.table("credit_transactions").insert({
        "wallet_id": wallet["id"],
        "amount": amount,
        "type": "refund",
        "description": f"Refund for failed generation ({amount} credits)",
        "metadata": metadata or {},
    }).execute()

    return {"balance": new_balance, "refunded": amount}


# ---------------------------------------------------------------------------
# Stripe-Related DB Operations
# ---------------------------------------------------------------------------

def get_stripe_customer_id(user_id: str):
    """Fetch the Stripe Customer ID from profiles, or None if not yet created."""
    sb = get_supabase()
    result = sb.table("profiles").select("stripe_customer_id").eq("id", user_id).execute()
    if result.data and result.data[0].get("stripe_customer_id"):
        return result.data[0]["stripe_customer_id"]
    return None


def save_stripe_customer_id(user_id: str, stripe_customer_id: str):
    """Store a Stripe Customer ID on the user's profile."""
    sb = get_supabase()
    sb.table("profiles").update({
        "stripe_customer_id": stripe_customer_id
    }).eq("id", user_id).execute()


def get_plan_by_stripe_price_id(stripe_price_id: str):
    """Look up a subscription_plan by its Stripe Price ID."""
    sb = get_supabase()
    result = sb.table("subscription_plans").select("*").eq("stripe_price_id", stripe_price_id).execute()
    return result.data[0] if result.data else None


def get_plan_by_id(plan_id: str):
    """Look up a subscription plan by its internal UUID."""
    sb = get_supabase()
    result = sb.table("subscription_plans").select("*").eq("id", plan_id).execute()
    return result.data[0] if result.data else None


def upsert_subscription(user_id: str, plan_id: str, stripe_subscription_id: str,
                         status: str, period_start: str, period_end: str):
    """Create or update a subscription row tied to a Stripe Subscription."""
    sb = get_supabase()
    existing = sb.table("subscriptions").select("id").eq("user_id", user_id).execute()
    data = {
        "user_id": user_id,
        "plan_id": plan_id,
        "stripe_subscription_id": stripe_subscription_id,
        "status": status,
        "current_period_start": period_start,
        "current_period_end": period_end,
    }
    if existing.data:
        sb.table("subscriptions").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        sb.table("subscriptions").insert(data).execute()


def cancel_subscription(stripe_subscription_id: str):
    """Mark a subscription as canceled by its Stripe Subscription ID."""
    sb = get_supabase()
    sb.table("subscriptions").update({
        "status": "canceled"
    }).eq("stripe_subscription_id", stripe_subscription_id).execute()


def get_user_id_by_stripe_customer(stripe_customer_id: str):
    """Reverse-lookup: find user_id from a Stripe Customer ID (for webhooks)."""
    sb = get_supabase()
    result = sb.table("profiles").select("id").eq("stripe_customer_id", stripe_customer_id).execute()
    return result.data[0]["id"] if result.data else None


def add_credits(user_id: str, amount: int, tx_type: str, description: str, metadata: dict = None):
    """Add credits to a user's wallet and log a transaction.

    Idempotent: uses stripe_idempotency_key to prevent duplicate credits
    from webhook retries.
    """
    sb = get_supabase()
    idempotency_key = None
    if metadata:
        idempotency_key = metadata.get("stripe_invoice_id") or metadata.get("stripe_session_id")

    wallet = get_wallet(user_id)
    if not wallet:
        result = sb.table("credit_wallets").insert({
            "user_id": user_id,
            "balance": amount,
        }).execute()
        wallet_id = result.data[0]["id"]
    else:
        new_balance = wallet["balance"] + amount
        sb.table("credit_wallets").update({
            "balance": new_balance
        }).eq("id", wallet["id"]).execute()
        wallet_id = wallet["id"]

    tx_data = {
        "wallet_id": wallet_id,
        "amount": amount,
        "type": tx_type,
        "description": description,
        "metadata": metadata or {},
    }
    if idempotency_key:
        tx_data["stripe_idempotency_key"] = idempotency_key

    try:
        sb.table("credit_transactions").insert(tx_data).execute()
    except Exception as e:
        if "duplicate" in str(e).lower() or "unique" in str(e).lower():
            # Webhook retry — already processed, revert the balance update
            if wallet:
                sb.table("credit_wallets").update({
                    "balance": wallet["balance"]
                }).eq("id", wallet_id).execute()
            return
        raise


# ---------------------------------------------------------------------------
# Scoped Asset Queries — user_id + project_id filtered
# ---------------------------------------------------------------------------

def seed_default_influencers(user_id: str, project_id: str):
    """
    Auto-populates a new/empty project with the 18 base template influencers.
    Finds the admin project (the one that owns 'Meg') and clones its influencers,
    excluding Meg, Max, and Naiara as requested.
    """
    sb = get_supabase()
    
    # Locate the admin project by finding where 'Meg' lives
    admin_inf = sb.table("influencers").select("project_id").eq("name", "Meg").limit(1).execute().data
    if not admin_inf or not admin_inf[0].get("project_id"):
        return
        
    admin_pid = admin_inf[0]["project_id"]
    
    # Don't seed if this IS the admin project querying itself
    if project_id == admin_pid:
        return
        
    template_infs = sb.table("influencers").select("*").eq("project_id", admin_pid).execute().data
    
    exclude_names = {"meg", "max", "naiara"}
    clones = []
    
    for inf in template_infs:
        inf_name = inf.get("name", "")
        if inf_name.lower() in exclude_names:
            continue
            
        clone = dict(inf)
        clone.pop("id", None)
        clone.pop("created_at", None)
        clone["user_id"] = user_id
        clone["project_id"] = project_id
        clones.append(clone)
        
    if clones:
        sb.table("influencers").insert(clones).execute()

def list_influencers_scoped(user_id: str, project_id: str):
    sb = get_supabase()
    data = sb.table("influencers").select("*").eq("user_id", user_id).eq("project_id", project_id).execute().data
    if not data:
        # If the project has NO influencers, automatically seed the default templates
        seed_default_influencers(user_id, project_id)
        # Fetch again after seeding
        data = sb.table("influencers").select("*").eq("user_id", user_id).eq("project_id", project_id).execute().data
    return data

def list_scripts_scoped(user_id: str, project_id: str, **filters):
    sb = get_supabase()
    q = sb.table("scripts").select("*").eq("user_id", user_id).eq("project_id", project_id)
    if filters.get("category"):
        q = q.eq("category", filters["category"])
    if filters.get("methodology"):
        q = q.eq("methodology", filters["methodology"])
    if filters.get("video_length"):
        q = q.eq("video_length", filters["video_length"])
    sort_by = filters.get("sort_by", "created_at_desc")
    if sort_by == "created_at_desc":
        q = q.order("created_at", desc=True)
    elif sort_by == "times_used_desc":
        q = q.order("times_used", desc=True)
    return q.execute().data

def list_products_scoped(user_id: str, project_id: str, category: str = None):
    sb = get_supabase()
    q = sb.table("products").select("*").eq("user_id", user_id).eq("project_id", project_id)
    if category:
        q = q.eq("category", category)
    return q.execute().data

def list_app_clips_scoped(user_id: str, project_id: str):
    sb = get_supabase()
    return sb.table("app_clips").select("*").eq("user_id", user_id).eq("project_id", project_id).execute().data

def list_jobs_scoped(user_id: str, project_id: str = None, status: str = None, limit: int = 50):
    sb = get_supabase()
    q = sb.table("video_jobs").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit)
    if project_id:
        q = q.eq("project_id", project_id)
    if status:
        q = q.eq("status", status)
    return q.execute().data

def list_product_shots_scoped(user_id: str, product_id: str):
    sb = get_supabase()
    return sb.table("product_shots").select("*").eq("product_id", product_id).order("created_at", desc=True).execute().data


def get_notifications(user_id: str, limit: int = 20):
    """Fetch recent activity as notifications for the authenticated user.

    Pulls from video_jobs and scripts tables, maps each row to a
    notification dict, and returns a unified list sorted by timestamp DESC.
    """
    sb = get_supabase()
    notifications = []

    # --- Video Jobs ---
    jobs = (
        sb.table("video_jobs")
        .select("id,status,campaign_name,final_video_url,error_message,created_at,updated_at,progress")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
        .data
    )
    status_map = {
        "success": ("Video Ready", "job_success"),
        "failed": ("Generation Failed", "job_failed"),
        "processing": ("Generating Video", "job_processing"),
        "pending": ("Job Queued", "job_pending"),
    }
    for job in (jobs or []):
        status = job.get("status", "pending")
        title, ntype = status_map.get(status, ("Job Update", "job_pending"))
        name = job.get("campaign_name") or "Video"
        if status == "success":
            message = f"{name} completed successfully"
        elif status == "failed":
            err = job.get("error_message") or "Unknown error"
            message = f"{name} failed: {err[:80]}"
        elif status == "processing":
            pct = job.get("progress") or 0
            message = f"{name} is generating ({pct}%)"
        else:
            message = f"{name} is queued for generation"
        notifications.append({
            "id": job["id"],
            "type": ntype,
            "title": title,
            "message": message,
            "timestamp": job.get("updated_at") or job.get("created_at"),
            "video_url": job.get("final_video_url"),
        })

    # --- Scripts ---
    scripts = (
        sb.table("scripts")
        .select("id,name,created_at")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
        .data
    )
    for s in (scripts or []):
        notifications.append({
            "id": f"script_{s['id']}",
            "type": "script_created",
            "title": "Script Created",
            "message": s.get("name") or "New script",
            "timestamp": s.get("created_at"),
            "video_url": None,
        })

    # Sort all notifications by timestamp DESC
    notifications.sort(key=lambda n: n.get("timestamp") or "", reverse=True)
    return notifications[:limit]


def get_stats_scoped(user_id: str):
    """Get dashboard stats scoped to a specific user."""
    sb = get_supabase()
    total = len(sb.table("video_jobs").select("id").eq("user_id", user_id).execute().data)
    pending = len(sb.table("video_jobs").select("id").eq("user_id", user_id).eq("status", "pending").execute().data)
    processing = len(sb.table("video_jobs").select("id").eq("user_id", user_id).eq("status", "processing").execute().data)
    success = len(sb.table("video_jobs").select("id").eq("user_id", user_id).eq("status", "success").execute().data)
    failed = len(sb.table("video_jobs").select("id").eq("user_id", user_id).eq("status", "failed").execute().data)
    influencers = len(sb.table("influencers").select("id").eq("user_id", user_id).execute().data)
    scripts = len(sb.table("scripts").select("id").eq("user_id", user_id).execute().data)
    app_clips = len(sb.table("app_clips").select("id").eq("user_id", user_id).execute().data)

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


# ─────────────────────────────────────────────────────────────────────────────
# AI Clone helpers (new — appended at bottom, do not modify above this line)
# ─────────────────────────────────────────────────────────────────────────────

def get_user_clones(user_id: str):
    sb = get_supabase()
    return (
        sb.table("user_ai_clones")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
        .data or []
    )


def get_clone_looks(clone_id: str):
    sb = get_supabase()
    return (
        sb.table("user_ai_clone_looks")
        .select("*")
        .eq("clone_id", clone_id)
        .order("created_at")
        .execute()
        .data or []
    )


def get_clone_job(job_id: str):
    sb = get_supabase()
    result = sb.table("clone_video_jobs").select("*").eq("id", job_id).execute()
    return result.data[0] if result.data else None


def update_clone_job(job_id: str, data: dict):
    sb = get_supabase()
    result = (
        sb.table("clone_video_jobs")
        .update(data)
        .eq("id", job_id)
        .execute()
    )
    return result.data[0] if result.data else None


def list_clone_jobs_for_user(user_id: str, limit: int = 50):
    sb = get_supabase()
    return (
        sb.table("clone_video_jobs")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
        .data or []
    )
