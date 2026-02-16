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

# Create Celery instance
celery = Celery(
    "ugc_engine",
    broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0"),
    backend=os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
)

@celery.task(name="generate_ugc_video", bind=True)
def generate_ugc_video(self, job_id, influencer, app_clip, fields):
    """
    Background task to generate a UGC video using the core industrial engine.
    """
    print(f"🎬 Starting industrial video generation for Job {job_id}...")
    
    def status_callback(msg):
        # Update Celery task state
        self.update_state(state='PROGRESS', meta={'status': msg})
        print(f"      [Job {job_id}] Progress: {msg}")

    try:
        project_name = f"saas_job_{job_id}_{influencer['name'].lower()}"
        
        final_video_path = core_engine.run_generation_pipeline(
            project_name=project_name,
            influencer=influencer,
            app_clip=app_clip,
            fields=fields,
            status_callback=status_callback,
            skip_music=False
        )
        
        print(f"✅ Job {job_id} complete! Result: {final_video_path}")
        return {
            "status": "success", 
            "video_url": f"file://{final_video_path}",
            "job_id": job_id
        }
        
    except Exception as e:
        print(f"❌ Job {job_id} failed: {e}")
        self.update_state(state='FAILURE', meta={'error': str(e)})
        raise e
