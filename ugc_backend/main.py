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
    script_id: Optional[uuid.UUID] = None # new: predefined script
    hook: Optional[str] = None # manual hook
    model_api: str = "infinitalk-audio" # new: user choice
    assistant_type: str = "Travel"
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

class ScriptCreate(BaseModel):
    text: str
    category: Optional[str] = None
    influencer_id: Optional[uuid.UUID] = None

from ugc_db.db_manager import ScriptLibrary, UsedCombination
import random
import scene_builder # for scripts

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

@app.get("/scripts")
async def list_scripts(db: Session = Depends(get_db)):
    return db.query(ScriptLibrary).all()

@app.post("/scripts")
async def create_script(script: ScriptCreate, db: Session = Depends(get_db)):
    db_script = ScriptLibrary(
        id=uuid.uuid4(),
        **script.dict()
    )
    db.add(db_script)
    db.commit()
    return db_script

@app.post("/scripts/generate")
async def generate_script(influencer_id: uuid.UUID, category: str):
    # Industrial AI Hook Generation Mock (would call GPT-4/Claude)
    # Since we have the industrial core, we can use scene_builder for this
    hook = f"¡Eh, ESCUCHA! Tío, no te vas a creer lo que he descubierto en esta app de {category}..."
    return {"text": hook}

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
    
    # 2. Handle Script & App Clip (Manual vs Auto-Select Unique)
    final_hook = job_data.hook
    final_script_id = job_data.script_id
    final_clip_id = job_data.app_clip_id
    
    # AUTO-SELECTION LOGIC (Uniqueness Check)
    if not final_hook and not final_script_id:
        # Pick a script that hasn't been used for this influencer + any clip yet
        # (Simplified unique check: pick random script from library)
        available_scripts = db.query(ScriptLibrary).filter(
            (ScriptLibrary.influencer_id == job_data.influencer_id) | (ScriptLibrary.influencer_id == None)
        ).all()
        if available_scripts:
            random.shuffle(available_scripts)
            # Find a script+clip combination not in UsedCombination
            for script in available_scripts:
                # If clip is auto-select too
                if not final_clip_id:
                    possible_clips = db.query(AppClip).filter(AppClip.category == influencer.category).all()
                    random.shuffle(possible_clips)
                    for clip in possible_clips:
                        # Check uniqueness
                        exists = db.query(UsedCombination).filter(
                            UsedCombination.influencer_id == job_data.influencer_id,
                            UsedCombination.script_id == script.id,
                            UsedCombination.app_clip_id == clip.id
                        ).first()
                        if not exists:
                            final_script_id = script.id
                            final_hook = script.text
                            final_clip_id = clip.id
                            break
                if final_script_id: break
        
        if not final_hook:
            # Fallback to AI generation if no library scripts
            final_hook = f"¡Mira esto! Increíble oferta de {influencer.category} que acabo de ver..."
            
    # 3. Finalize Selection
    app_clip = db.query(AppClip).filter(AppClip.id == final_clip_id).first() if final_clip_id else None
    
    # 4. Create Job Record
    job_id = uuid.uuid4()
    new_job = VideoJob(
        id=job_id,
        user_id=job_data.user_id,
        influencer_id=job_data.influencer_id,
        app_clip_id=final_clip_id,
        project_name=f"job_{job_id}",
        status="pending",
        model_api=job_data.model_api,
        metadata_json={
            "hook": final_hook,
            "assistant_type": job_data.assistant_type,
            "length": job_data.length,
            "script_id": str(final_script_id) if final_script_id else None
        }
    )
    db.add(new_job)
    
    # 5. Record Combination usage
    if final_script_id and final_clip_id:
        used = UsedCombination(
            id=uuid.uuid4(),
            influencer_id=job_data.influencer_id,
            script_id=final_script_id,
            app_clip_id=final_clip_id
        )
        db.add(used)
        
    db.commit()

    # 6. Prepare data for worker
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

    # 7. Trigger Background Task
    generate_ugc_video.delay(
        job_id=str(job_id),
        influencer=inf_dict,
        app_clip=clip_dict,
        fields={
            "Hook": final_hook,
            "AI Assistant": job_data.assistant_type,
            "Length": job_data.length,
            "model_api": job_data.model_api # Pass model preference
        }
    )

    return {"job_id": job_id, "status": "queued", "selection": {"hook": final_hook, "clip": app_clip.name if app_clip else "none"}}

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
