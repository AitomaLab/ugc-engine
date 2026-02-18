"""
UGC Engine v3 — Celery Worker Tasks (Supabase REST API)

Self-sufficient worker: fetches all data from Supabase using only a job_id.
Uploads final videos to Supabase Storage.
"""
from celery import Celery
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv(".env.saas")

import sys
from pathlib import Path

# Add project root to path so we can import core_engine
sys.path.append(str(Path(__file__).parent.parent))

import config
import core_engine

# ---------------------------------------------------------------------------
# Celery Setup
# ---------------------------------------------------------------------------

celery = Celery(
    "ugc_engine",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
)

celery.conf.broker_transport_options = config.CELERY_TRANSPORT_OPTIONS
celery.conf.broker_connection_retry_on_startup = True


# ---------------------------------------------------------------------------
# Supabase Storage Helper
# ---------------------------------------------------------------------------

def _upload_to_storage(file_path: str, bucket: str, filename: str) -> str:
    """Upload a file to Supabase Storage and return the public URL."""
    try:
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()
        with open(file_path, "rb") as f:
            sb.storage.from_(bucket).upload(filename, f, file_options={"content-type": "video/mp4"})
        public_url = sb.storage.from_(bucket).get_public_url(filename)
        print(f"      ☁️ Uploaded to Supabase Storage: {public_url}")
        return public_url
    except Exception as e:
        print(f"      ⚠️ Supabase upload failed: {e}, falling back to local path")
        return f"file:///{file_path}"


# ---------------------------------------------------------------------------
# Main Video Generation Task
# ---------------------------------------------------------------------------

@celery.task(name="generate_ugc_video", bind=True)
def generate_ugc_video(self, job_id: str):
    """
    Self-sufficient video generation task.
    Fetches all necessary data from Supabase REST API using only the job_id.
    """
    from ugc_db.db_manager import get_job, get_influencer, update_job

    print(f"🎬 Starting video generation for Job {job_id}...")

    # 1. Fetch job + related data
    try:
        job = get_job(job_id)
        if not job:
            raise RuntimeError(f"Job {job_id} not found in database")

        influencer = get_influencer(job["influencer_id"])
        if not influencer:
            raise RuntimeError(f"Influencer {job['influencer_id']} not found")

        # Ensure Supabase client is available for clip/script lookups
        from ugc_db.db_manager import get_supabase
        sb = get_supabase()

        # Fetch script if linked
        script_text = "Check this out!"
        script_cat = "General"
        if job.get("script_id"):
            script_result = sb.table("scripts").select("*").eq("id", job["script_id"]).execute()
            if script_result.data:
                script_text = script_result.data[0]["text"]
                script_cat = script_result.data[0].get("category", "General")

        # Fetch app clip if linked, or auto-select by influencer category
        app_clip_dict = None
        clip_id = job.get("app_clip_id")
        if clip_id:
            print(f"      🔎 Fetching App Clip: {clip_id}")
            clip_result = sb.table("app_clips").select("*").eq("id", clip_id).execute()
            if clip_result.data:
                clip = clip_result.data[0]
                app_clip_dict = {
                    "name": clip["name"],
                    "description": clip.get("description", ""),
                    "video_url": clip.get("video_url", ""),
                    "duration": clip.get("duration_seconds", 4),
                }
                print(f"      ✅ App Clip found: {clip['name']}")
            else:
                print(f"      ⚠️ App Clip ID {clip_id} not found in database!")
        else:
            # Auto-select: match influencer category to app clip category
            import random
            inf_style = (influencer.get("style") or "").lower().strip()
            print(f"      🔄 Auto-selecting App Clip for category: '{inf_style}'")
            all_clips = sb.table("app_clips").select("*").execute().data or []
            
            # Match by category or description field containing the influencer style
            matching = [
                c for c in all_clips
                if inf_style and (
                    inf_style in (c.get("category") or "").lower()
                    or inf_style in (c.get("description") or "").lower()
                    or inf_style in (c.get("name") or "").lower()
                )
            ]
            
            selected = random.choice(matching) if matching else (random.choice(all_clips) if all_clips else None)
            
            if selected:
                app_clip_dict = {
                    "name": selected["name"],
                    "description": selected.get("description", ""),
                    "video_url": selected.get("video_url", ""),
                    "duration": selected.get("duration_seconds", 4),
                }
                match_type = "category match" if matching else "random fallback"
                print(f"      ✅ Auto-selected: {selected['name']} ({match_type})")
            else:
                print("      ⚠️ No App Clips available for auto-selection!")

        print(f"      👤 Influencer Raw Data (ID: {influencer['id']})")
        print(f"         - Name: {influencer.get('name')}")
        print(f"         - Image URL: {influencer.get('image_url')}")
        print(f"         - Ref Image URL: {influencer.get('reference_image_url')}")

        influencer_dict = {
            "name": influencer["name"],
            "description": influencer.get("description", ""),
            "personality": influencer.get("personality", ""),
            "style": influencer.get("style", ""),
            "image_url": influencer.get("image_url", ""),
            "reference_image_url": influencer.get("image_url", ""),  # Compat for core_engine / scene_builder
            "elevenlabs_voice_id": influencer.get("elevenlabs_voice_id", ""),
        }
        print(f"      📦 Influencer Dict for Engine: {influencer_dict}")

        fields = {
            "Hook": job.get("hook") or script_text,
            "Theme": job.get("assistant_type") or script_cat,
            "Length": f"{job.get('length', 15)}s",
            "model_api": job.get("model_api", "seedance-1.5-pro"),
        }

    except Exception as e:
        update_job(job_id, {"status": "failed", "error_message": f"Data fetch failed: {str(e)}"})
        raise

    # 2. Update status to processing
    update_job(job_id, {"status": "processing", "progress": 5})

    # 3. Status callback for progress tracking
    def status_callback(msg):
        try:
            self.update_state(state="PROGRESS", meta={"status": msg})
        except Exception:
            pass  # Celery backend not available (running in-process)
        print(f"      [Job {job_id}] {msg}")

        progress_map = {
            "Building scenes": 5,
            "Generating scenes": 10,
            "Gen: Hook": 20,
            "Gen: Reaction": 40,
            "Gen: App Demo": 60,
            "Gen: Cta": 80,
            "Subtitling": 90,
            "Assembling": 95,
        }
        for key, val in progress_map.items():
            if key in msg:
                update_job(job_id, {"progress": val})
                break

    # 4. Run the core generation pipeline
    try:
        project_name = f"saas_job_{job_id}_{influencer_dict['name'].lower()}"

        final_video_path = core_engine.run_generation_pipeline(
            project_name=project_name,
            influencer=influencer_dict,
            app_clip=app_clip_dict,
            fields=fields,
            status_callback=status_callback,
            skip_music=False,
        )

        # 5. Upload final video to Supabase Storage
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        storage_filename = f"{influencer_dict['name'].lower()}_{timestamp}_{job_id[:8]}.mp4"
        final_url = _upload_to_storage(final_video_path, "generated-videos", storage_filename)

        # 6. Update job as success
        update_job(job_id, {
            "status": "success",
            "progress": 100,
            "final_video_url": final_url,
        })

        print(f"✅ Job {job_id} complete! Video: {final_url}")
        return {"status": "success", "video_url": final_url, "job_id": job_id}

    except Exception as e:
        error_str = str(e)
        print(f"❌ Job {job_id} failed: {error_str}")

        if "402" in error_str:
            clean_error = "ElevenLabs Payment Required (quota reached)"
        elif "image_url is required" in error_str:
            clean_error = "Kie.ai: Missing image URL for influencer"
        elif "audio file is unavailable" in error_str.lower():
            clean_error = "Audio file not reachable by AI service"
        else:
            clean_error = error_str[:500]

        update_job(job_id, {"status": "failed", "error_message": clean_error})
        raise


# ---------------------------------------------------------------------------
# Social Distribution Tasks (Phase 5)
# ---------------------------------------------------------------------------

@celery.task(name="schedule_social_posts")
def schedule_social_posts(job_ids: list):
    from ugc_db.db_manager import get_job, create_social_post

    platforms = ["tiktok", "instagram", "youtube"]
    scheduled_count = 0
    base_time = datetime.utcnow() + timedelta(hours=1)

    for i, job_id in enumerate(job_ids):
        job = get_job(job_id)
        if not job or job["status"] != "success" or not job.get("final_video_url"):
            continue

        for platform in platforms:
            create_social_post({
                "video_job_id": job["id"],
                "platform": platform,
                "status": "scheduled",
                "scheduled_for": (base_time + timedelta(hours=i * 4)).isoformat(),
            })
            scheduled_count += 1

    print(f"📅 Scheduled {scheduled_count} social posts")
    return {"scheduled": scheduled_count}


@celery.task(name="execute_social_posts")
def execute_social_posts():
    from ugc_db.db_manager import get_supabase, get_job, update_social_post
    from social_media_poster import BlotatoPoster

    sb = get_supabase()
    poster = BlotatoPoster()
    now = datetime.utcnow().isoformat()

    due_posts = (
        sb.table("social_posts")
        .select("*")
        .eq("status", "scheduled")
        .lte("scheduled_for", now)
        .execute()
        .data
    )

    posted_count = 0
    for post in due_posts:
        job = get_job(post["video_job_id"])
        if not job or not job.get("final_video_url"):
            continue

        result = poster.schedule_post(
            video_url=job["final_video_url"],
            caption=f"New UGC content on {post['platform']}!",
            schedule_time=str(post["scheduled_for"]),
        )

        update_social_post(post["id"], {
            "status": "posted",
            "posted_at": datetime.utcnow().isoformat(),
            "blotato_task_id": result.get("task_id"),
        })
        posted_count += 1

    print(f"📤 Executed {posted_count} social posts")
    return {"posted": posted_count}


# ---------------------------------------------------------------------------
# Celery Beat Schedule
# ---------------------------------------------------------------------------

celery.conf.beat_schedule = {
    "execute-posts-every-5-minutes": {
        "task": "execute_social_posts",
        "schedule": 300.0,
    },
}
