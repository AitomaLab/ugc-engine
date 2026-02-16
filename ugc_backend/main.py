from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
from sqlalchemy.orm import Session

# Absolute imports from root
from ugc_db.db_manager import get_db, init_db, Influencer, AppClip, VideoJob
from ugc_worker.tasks import generate_ugc_video

app = FastAPI(title="UGC Engine SaaS API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, replace with your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    init_db()

class JobCreate(BaseModel):
    influencer_id: uuid.UUID
    app_clip_id: Optional[uuid.UUID] = None
    hook: str
    assistant_type: str
    length: str = "15s"
    user_id: uuid.UUID # In production, this would come from Auth token

class InfluencerCreate(BaseModel):
    name: str
    gender: str
    accent: str
    tone: str
    visual_description: str
    reference_image_url: Optional[str] = None
    elevenlabs_voice_id: Optional[str] = None
    category: str

class AppClipCreate(BaseModel):
    name: str
    category: str
    video_url: str
    duration: float = 4.0

@app.get("/")
async def root():
    return {"message": "Welcome to the UGC Engine SaaS API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/influencers")
async def list_influencers(db: Session = Depends(get_db)):
    return db.query(Influencer).all()

@app.post("/influencers")
async def create_influencer(inf: InfluencerCreate, db: Session = Depends(get_db)):
    db_inf = Influencer(
        id=uuid.uuid4(),
        **inf.dict()
    )
    db.add(db_inf)
    db.commit()
    return db_inf

@app.get("/app_clips")
async def list_app_clips(db: Session = Depends(get_db)):
    return db.query(AppClip).all()

@app.post("/app_clips")
async def create_app_clip(clip: AppClipCreate, db: Session = Depends(get_db)):
    db_clip = AppClip(
        id=uuid.uuid4(),
        **clip.dict()
    )
    db.add(db_clip)
    db.commit()
    return db_clip

@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    total_jobs = db.query(VideoJob).count()
    # Mocking cost: $0.30 per job as an average
    total_cost = total_jobs * 0.30
    return {
        "videos_generated": total_jobs,
        "credits_spent": round(total_cost, 2),
        "status": "Online"
    }

@app.post("/jobs")
async def create_job(job_data: JobCreate, db: Session = Depends(get_db)):
    # 1. Verify Influencer
    influencer = db.query(Influencer).filter(Influencer.id == job_data.influencer_id).first()
    if not influencer:
        raise HTTPException(status_code=404, detail="Influencer not found")
    
    # 2. Verify App Clip (if provided)
    app_clip = None
    if job_data.app_clip_id:
        app_clip = db.query(AppClip).filter(AppClip.id == job_data.app_clip_id).first()
    
    # 3. Create Job Record
    job_id = uuid.uuid4()
    new_job = VideoJob(
        id=job_id,
        user_id=job_data.user_id,
        influencer_id=job_data.influencer_id,
        app_clip_id=job_data.app_clip_id,
        project_name=f"job_{job_id}",
        status="pending",
        metadata_json={
            "hook": job_data.hook,
            "assistant_type": job_data.assistant_type,
            "length": job_data.length
        }
    )
    db.add(new_job)
    db.commit()

    # 4. Prepare data for worker (convert SQLAlchemy objects to dicts)
    inf_dict = {
        "name": influencer.name,
        "description": influencer.visual_description,
        "reference_image_url": influencer.reference_image_url,
        "gender": influencer.gender,
        "accent": influencer.accent,
        "tone": influencer.tone
    }
    
    clip_dict = {
        "name": app_clip.name if app_clip else "auto",
        "video_url": app_clip.video_url if app_clip else None,
        "duration": app_clip.duration if app_clip else 4
    }

    # 5. Trigger Background Task
    generate_ugc_video.delay(
        job_id=str(job_id),
        influencer=inf_dict,
        app_clip=clip_dict,
        fields={
            "Hook": job_data.hook,
            "AI Assistant": job_data.assistant_type,
            "Length": job_data.length
        }
    )

    return {"job_id": job_id, "status": "queued"}

@app.get("/jobs")
async def list_jobs(db: Session = Depends(get_db)):
    return db.query(VideoJob).order_by(VideoJob.created_at.desc()).all()

@app.get("/jobs/{job_id}")
async def get_job_status(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(VideoJob).filter(VideoJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
