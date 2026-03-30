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

# Fix Windows cp1252 console encoding — allows emoji/unicode in print() calls
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if sys.stderr and hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

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


def _upload_url_to_storage(url: str, bucket: str, filename: str, content_type: str = "image/png") -> str:
    """Download a remote URL and re-upload to Supabase Storage. Returns permanent public URL."""
    import requests as _req
    from ugc_db.db_manager import get_supabase
    resp = _req.get(url, timeout=120)
    resp.raise_for_status()
    sb = get_supabase()
    sb.storage.from_(bucket).upload(filename, resp.content, file_options={"content-type": content_type})
    public_url = sb.storage.from_(bucket).get_public_url(filename)
    print(f"      ☁️ Re-uploaded to Supabase Storage: {public_url}")
    return public_url


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
                    "first_frame_url": clip.get("first_frame_url", ""),
                    "product_id": clip.get("product_id", ""),
                }
                print(f"      ✅ App Clip found: {clip['name']}")

                # Ensure first_frame_url exists for the digital unified pipeline.
                # The background extractor may not have finished, so extract now.
                if app_clip_dict["video_url"] and not app_clip_dict["first_frame_url"]:
                    print(f"      🎞️ first_frame_url missing — extracting synchronously...")
                    try:
                        from ugc_backend.frame_extractor import extract_first_frame
                        from ugc_db.db_manager import update_app_clip
                        frame_url = extract_first_frame(app_clip_dict["video_url"])
                        if frame_url:
                            app_clip_dict["first_frame_url"] = frame_url
                            update_app_clip(clip_id, {"first_frame_url": frame_url})
                            print(f"      ✅ First frame extracted: {frame_url[:60]}...")
                        else:
                            print(f"      ⚠️ Frame extraction returned None")
                    except Exception as e:
                        print(f"      ⚠️ Sync frame extraction failed: {e}")
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
                    "first_frame_url": selected.get("first_frame_url", ""),
                    "product_id": selected.get("product_id", ""),
                }
                match_type = "category match" if matching else "random fallback"
                print(f"      ✅ Auto-selected: {selected['name']} ({match_type})")

                # Ensure first_frame_url for auto-selected clips too
                if app_clip_dict["video_url"] and not app_clip_dict["first_frame_url"]:
                    print(f"      🎞️ first_frame_url missing — extracting synchronously...")
                    try:
                        from ugc_backend.frame_extractor import extract_first_frame
                        from ugc_db.db_manager import update_app_clip
                        frame_url = extract_first_frame(app_clip_dict["video_url"])
                        if frame_url:
                            app_clip_dict["first_frame_url"] = frame_url
                            update_app_clip(selected["id"], {"first_frame_url": frame_url})
                            print(f"      ✅ First frame extracted: {frame_url[:60]}...")
                    except Exception as e:
                        print(f"      ⚠️ Sync frame extraction failed: {e}")
            else:
                print("      ⚠️ No App Clips available for auto-selection!")

        # Fetch product if linked (any product type — physical or digital)
        product_dict = None
        if job.get("product_id"):
            prod_id = job["product_id"]
            print(f"      📦 Fetching Product: {prod_id}")
            prod_result = sb.table("products").select("*").eq("id", prod_id).execute()
            if prod_result.data:
                prod = prod_result.data[0]

                # Check for visual_description (Auto-Analysis)
                visual_desc = prod.get("visual_description")
                if not visual_desc:
                    print(f"      👁️ Auto-analyzing product {prod_id}...")
                    try:
                        from ugc_backend.llm_vision_client import LLMVisionClient
                        from ugc_db.db_manager import update_product

                        client = LLMVisionClient()
                        analysis = client.describe_product_image(prod["image_url"])
                        if analysis:
                            print(f"      ✅ Analysis success: {analysis.get('brand_name')}")
                            update_product(prod_id, {"visual_description": analysis})
                            visual_desc = analysis
                            # Update local prod object to reflect new state
                            prod["visual_description"] = analysis
                    except Exception as e:
                        print(f"      ⚠️ Auto-analysis failed: {e}")

                product_dict = {
                    "id": prod["id"],
                    "name": prod["name"],
                    "description": prod.get("description", ""),
                    "image_url": prod["image_url"],
                    "category": prod.get("category", ""),
                    "visual_description": visual_desc,
                    "website_url": prod.get("website_url", ""),
                }
                print(f"      ✅ Product found: {prod['name']}")
            else:
                 print(f"      ⚠️ Product ID {prod_id} not found!")

        print(f"      👤 Influencer Raw Data (ID: {influencer['id']})")
        print(f"         - Name: {influencer.get('name')}")
        print(f"         - Image URL: {influencer.get('image_url')}")
        print(f"         - Ref Image URL: {influencer.get('reference_image_url')}")

        influencer_dict = {
            "name": influencer["name"],
            "description": influencer.get("description", ""),
            "personality": influencer.get("personality", ""),
            "style": influencer.get("style", ""),
            "gender": influencer.get("gender") or "Female",
            "age": influencer.get("age", "25-year-old"),
            "accent": influencer.get("accent", "neutral English"),
            "tone": influencer.get("tone", "Enthusiastic"),
            "energy_level": influencer.get("energy_level", "High"),
            "image_url": influencer.get("image_url", ""),
            "reference_image_url": influencer.get("image_url", ""),  # Compat for core_engine / scene_builder
            "elevenlabs_voice_id": influencer.get("elevenlabs_voice_id", ""),
            "setting": influencer.get("setting", ""),
        }
        print(f"      📦 Influencer Dict for Engine: {influencer_dict}")

        # Pass variation_prompt from job into influencer_dict (if set)
        # This overrides the influencer's default setting in the scene builder
        if job.get("variation_prompt"):
            influencer_dict["variation_prompt"] = job["variation_prompt"]
            print(f"      🎲 Variation prompt applied: {job['variation_prompt']}")


        # Read auto_transition_type from metadata JSONB (where api stores it)
        job_metadata = job.get("metadata") or {}
        auto_trans_type = job_metadata.get("auto_transition_type") or job.get("auto_transition_type")

        fields = {
            "Hook": job.get("hook") or job_metadata.get("hook") or script_text,
            "Theme": job.get("assistant_type") or script_cat,
            "Length": f"{job.get('length', 15)}s",
            "model_api": job.get("model_api", "seedance-1.5-pro"),
            "cinematic_shot_ids": job.get("cinematic_shot_ids") or job_metadata.get("cinematic_shot_ids") or [],
            "auto_transition_type": auto_trans_type,
            # Subtitle configuration — read from job, fall back to safe defaults
            "subtitles_enabled": job.get("subtitles_enabled", True),
            "subtitle_style": job.get("subtitle_style", "hormozi"),
            "subtitle_placement": job.get("subtitle_placement", "middle"),
        }

    except Exception as e:
        update_job(job_id, {"status": "failed", "error_message": f"Data fetch failed: {str(e)}"})
        raise

    # 2. Update status to processing — record actual start time in metadata
    from datetime import datetime, timezone as tz
    job_metadata["processing_started_at"] = datetime.now(tz.utc).isoformat()
    update_job(job_id, {"status": "processing", "progress": 5, "metadata": job_metadata})

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
            product=product_dict,
            product_type=job.get("product_type", "digital"),
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
# Cinematic Product Shot Generation Tasks
# ---------------------------------------------------------------------------

@celery.task(name="generate_product_shot_image")
def generate_product_shot_image(shot_id: str):
    """Generates a single still cinematic product shot image."""
    from ugc_db.db_manager import get_product_shot, get_product, update_product_shot
    from prompts.cinematic_shots import build_sealcam_prompt
    import generate_scenes

    print(f"Starting cinematic image generation for Shot {shot_id}...")
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise RuntimeError(f"Product Shot {shot_id} not found.")

        product = get_product(shot["product_id"])
        if not product:
            raise RuntimeError(f"Product {shot['product_id']} not found.")

        # 1. Build SEALCaM Prompt
        prompt = build_sealcam_prompt(shot["shot_type"], product)
        update_product_shot(shot_id, {"prompt": prompt})

        # 2. Generate Image via Nano Banana Pro
        image_url = generate_scenes.generate_cinematic_product_image(
            prompt=prompt,
            product_image_url=product["image_url"]
        )

        # 3. Re-upload to Supabase Storage for permanent URL
        try:
            image_url = _upload_url_to_storage(image_url, "cinematic-shots", f"shot_{shot_id}.png", "image/png")
        except Exception as e:
            print(f"      ⚠️ Storage re-upload failed, using raw URL: {e}")

        # 4. Update DB with result
        update_product_shot(shot_id, {
            "status": "image_completed",
            "image_url": image_url
        })
        print(f"Image generation complete for Shot {shot_id}")

    except Exception as e:
        print(f"Image generation failed for Shot {shot_id}: {e}")
        from ugc_db.db_manager import update_product_shot as _update
        try:
            _update(shot_id, {"status": "failed", "error_message": str(e)[:500]})
        except Exception:
            pass


@celery.task(name="animate_product_shot_video")
def animate_product_shot_video(shot_id: str):
    """Animates a single still product shot into a video clip."""
    from ugc_db.db_manager import get_product_shot, update_product_shot
    import generate_scenes

    print(f"Starting cinematic animation for Shot {shot_id}...")
    try:
        shot = get_product_shot(shot_id)
        if not shot or not shot.get("image_url"):
            raise RuntimeError(f"Product Shot {shot_id} not found or has no image_url.")

        update_product_shot(shot_id, {"status": "animation_pending"})

        # Animate via Veo 3.1 (uses RENAMED function to avoid name collision)
        video_url = generate_scenes.animate_cinematic_still(
            image_url=shot["image_url"],
            shot_type=shot["shot_type"]
        )

        # Re-upload to Supabase Storage for permanent URL
        try:
            video_url = _upload_url_to_storage(video_url, "cinematic-shots", f"shot_{shot_id}_video.mp4", "video/mp4")
        except Exception as e:
            print(f"      ⚠️ Storage re-upload failed, using raw URL: {e}")

        # Update DB with result
        update_product_shot(shot_id, {
            "status": "animation_completed",
            "video_url": video_url
        })
        print(f"Animation complete for Shot {shot_id}")

    except Exception as e:
        print(f"Animation failed for Shot {shot_id}: {e}")
        from ugc_db.db_manager import update_product_shot as _update
        try:
            _update(shot_id, {"status": "failed", "error_message": str(e)[:500]})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Transition Shot Generation Task (Workflow B)
# ---------------------------------------------------------------------------

@celery.task(name="generate_transition_shot")
def generate_transition_shot(shot_id: str):
    """
    Generates a context-aware transition shot that seamlessly blends with
    the preceding UGC scene. Pipeline:
      1. Download preceding scene video
      2. Extract last frame
      3. Analyze frame with GPT-4o Vision
      4. Generate context-aware image prompt
      5. Generate still image via Nano Banana Pro
      6. Animate via Veo 3.1
      7. Stitch with preceding clip using xfade transition
    """
    from ugc_db.db_manager import get_product_shot, get_product, update_product_shot
    from prompts.cinematic_shots import build_transition_prompt
    from ugc_backend.vision_analysis import analyze_ugc_frame, extract_last_frame
    from ugc_worker.video_tools import stitch_with_transition
    import generate_scenes
    import config
    import tempfile
    from pathlib import Path

    print(f"Starting transition shot generation for Shot {shot_id}...")
    try:
        shot = get_product_shot(shot_id)
        if not shot:
            raise RuntimeError(f"Product Shot {shot_id} not found.")

        product = get_product(shot["product_id"])
        if not product:
            raise RuntimeError(f"Product {shot['product_id']} not found.")

        transition_type = shot.get("transition_type", "match_cut")
        preceding_url = shot.get("preceding_video_url")
        if not preceding_url:
            raise RuntimeError("No preceding_video_url on shot record.")

        work_dir = Path(tempfile.mkdtemp(prefix="transition_"))

        # Step 1: Download preceding scene video
        print(f"   Downloading preceding scene: {preceding_url[:60]}...")
        preceding_path = work_dir / "preceding.mp4"
        generate_scenes.download_video(preceding_url, str(preceding_path))

        # Step 2: Extract last frame
        print("   Extracting last frame...")
        frame_path = work_dir / "last_frame.jpg"
        extract_last_frame(str(preceding_path), str(frame_path))

        # Step 3: Analyze frame with GPT-4o Vision
        print("   Analyzing frame with GPT-4o Vision...")
        analysis = analyze_ugc_frame(str(frame_path))
        update_product_shot(shot_id, {"analysis_json": analysis})
        print(f"   Analysis: framing={analysis.get('product_framing_style')}, "
              f"angle={analysis.get('camera_angle')}, "
              f"lighting={analysis.get('lighting_description')}")

        # Step 4: Build context-aware prompts
        target_style = shot.get("target_style")
        image_prompt, animation_prompt = build_transition_prompt(
            product=product,
            analysis=analysis,
            transition_type=transition_type,
            target_style=target_style,
        )
        update_product_shot(shot_id, {"prompt": image_prompt})

        # Step 5: Generate still image via Nano Banana Pro
        print("   Generating transition image via Nano Banana Pro...")
        image_url = generate_scenes.generate_cinematic_product_image(
            prompt=image_prompt,
            product_image_url=product["image_url"],
        )
        update_product_shot(shot_id, {"status": "image_completed", "image_url": image_url})
        print(f"   Image ready: {image_url[:60]}...")

        # Step 6: Animate via Veo 3.1
        print("   Animating transition shot with Veo 3.1...")
        update_product_shot(shot_id, {"status": "animation_pending"})
        cinematic_video_url = generate_scenes.generate_video_with_retry(
            prompt=animation_prompt,
            reference_image_url=image_url,
            model_api="veo-3.1-fast",
        )

        # Step 7: Download cinematic clip and stitch with preceding scene
        print("   Stitching with preceding scene...")
        cinematic_path = work_dir / "cinematic.mp4"
        generate_scenes.download_video(cinematic_video_url, str(cinematic_path))

        stitched_path = work_dir / "stitched.mp4"
        stitch_with_transition(
            influencer_clip=str(preceding_path),
            cinematic_clip=str(cinematic_path),
            transition_type=transition_type,
            output_path=str(stitched_path),
        )

        # Upload stitched video to storage
        import storage_helper
        final_video_url = storage_helper.upload_file(
            str(stitched_path),
            f"transition_shots/{shot_id}.mp4",
        )

        update_product_shot(shot_id, {
            "status": "animation_completed",
            "video_url": final_video_url,
        })
        print(f"Transition shot complete for Shot {shot_id}: {final_video_url}")

        # Cleanup temp files
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)

    except Exception as e:
        print(f"Transition shot failed for Shot {shot_id}: {e}")
        import traceback
        traceback.print_exc()
        from ugc_db.db_manager import update_product_shot as _update
        try:
            _update(shot_id, {"status": "failed", "error_message": str(e)[:500]})
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Celery Beat Schedule
# ---------------------------------------------------------------------------

celery.conf.beat_schedule = {
    "execute-posts-every-5-minutes": {
        "task": "execute_social_posts",
        "schedule": 300.0,
    },
}
