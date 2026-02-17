from celery import Celery
import os
from dotenv import load_dotenv

# Load SaaS production environment if present
load_dotenv(".env.saas")
import sys
from pathlib import Path

# Add project root to path so we can import core_engine
sys.path.append(str(Path(__file__).parent.parent))

import core_engine

import config

# Create Celery instance
celery = Celery(
    "ugc_engine",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

# Apply stability settings
celery.conf.broker_transport_options = config.CELERY_TRANSPORT_OPTIONS
celery.conf.broker_connection_retry_on_startup = True

@celery.task(name="generate_ugc_video", bind=True)
def generate_ugc_video(self, job_id, influencer, app_clip, fields):
    """
    Background task to generate a UGC video using the core industrial engine.
    """
    print(f"🎬 Starting industrial video generation for Job {job_id}...")
    
    def status_callback(msg):
        # 1. Update Celery task state (internal)
        self.update_state(state='PROGRESS', meta={'status': msg})
        print(f"      [Job {job_id}] Progress: {msg}")
        
        # 2. Update Production Database (for Frontend UI)
        try:
            from ugc_db.db_manager import SessionLocal, VideoJob
            db = SessionLocal()
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "processing"
                # Map message to roughly approximate percentage
                progress_map = {
                    "Building scenes": 5,
                    "Generating scenes": 10,
                    "Gen: Hook": 20,
                    "Gen: Reaction": 40,
                    "Gen: App Demo": 60,
                    "Gen: Cta": 80,
                    "Subtitling": 90,
                    "Assembling": 95
                }
                for key, val in progress_map.items():
                    if key in msg:
                        job.progress_percent = val
                        break
                db.commit()
            db.close()
        except Exception as db_err:
            print(f"      ⚠️ Progress DB sync warning: {db_err}")

    try:
        project_name = f"saas_job_{job_id}_{influencer['name'].lower()}"
        
        # Extract model preference if provided
        model_api = fields.get("model_api", "infinitalk-audio")
        
        final_video_path = core_engine.run_generation_pipeline(
            project_name=project_name,
            influencer=influencer,
            app_clip=app_clip,
            fields=fields,
            status_callback=status_callback,
            skip_music=False
        )
        
        # 3. Mark as SUCCESS in DB
        try:
            from ugc_db.db_manager import SessionLocal, VideoJob
            db = SessionLocal()
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "success"
                job.progress_percent = 100
                job.final_video_url = f"file:///{final_video_path}" # In prod, this would be an S3/Cloudinary URL
                db.commit()
            db.close()
        except Exception as db_err:
            print(f"      ⚠️ Final DB sync warning: {db_err}")

        print(f"✅ Job {job_id} complete! Result: {final_video_path}")
        return {
            "status": "success", 
            "video_url": f"file://{final_video_path}",
            "job_id": job_id
        }
        
    except Exception as e:
        print(f"❌ Job {job_id} failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        
        # Mark as FAILED in DB
        try:
            from ugc_db.db_manager import SessionLocal, VideoJob
            db = SessionLocal()
            job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
            if job:
                job.status = "failed"
                db.commit()
            db.close()
        except: pass
        
        raise e
