import uuid
from ugc_db.db_manager import SessionLocal, Influencer, AppClip, init_db

def populate():
    # Ensure tables exist
    print("🛠️ Initializing database schema...")
    init_db()
    
    print("🎬 Populating database with standard assets...")
    db = SessionLocal()
    
    # Standard Influencers
    influencers = [
        {
            "name": "Meg",
            "gender": "Female",
            "accent": "Castilian Spanish (Spain)",
            "tone": "Enthusiastic",
            "visual_description": "A stylish young woman in her 20s, energetic and friendly.",
            "reference_image_url": "https://pub-c2a0d7833a6b4121a97d1955b9e5917f.sp.r2.cloudflarestorage.com/meg_ref.png",
            "category": "Travel"
        },
        {
            "name": "Max",
            "gender": "Male",
            "accent": "Castilian Spanish (Spain)",
            "tone": "Confident",
            "visual_description": "A trendy young man in his 20s, professional and engaging.",
            "reference_image_url": "https://pub-c2a0d7833a6b4121a97d1955b9e5917f.sp.r2.cloudflarestorage.com/max_ref.png",
            "category": "Shop"
        }
    ]
    
    for inf in influencers:
        if not db.query(Influencer).filter(Influencer.name == inf["name"]).first():
            db.add(Influencer(id=uuid.uuid4(), **inf))
            print(f"  ✅ Added Influencer: {inf['name']}")

    # Standard App Clips
    clips = [
        {
            "name": "Travel App Demo",
            "category": "Travel",
            "video_url": "https://pub-c2a0d7833a6b4121a97d1955b9e5917f.sp.r2.cloudflarestorage.com/travel_demo.mp4",
            "duration": 4.0
        },
        {
            "name": "Shop App Demo",
            "category": "Shop",
            "video_url": "https://pub-c2a0d7833a6b4121a97d1955b9e5917f.sp.r2.cloudflarestorage.com/shop_demo.mp4",
            "duration": 4.0
        }
    ]
    
    for clip in clips:
        if not db.query(AppClip).filter(AppClip.name == clip["name"]).first():
            db.add(AppClip(id=uuid.uuid4(), **clip))
            print(f"  ✅ Added App Clip: {clip['name']}")
            
    db.commit()
    db.close()
    print("✨ Database restoration complete.")

if __name__ == "__main__":
    populate()
