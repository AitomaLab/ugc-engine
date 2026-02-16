import sys
import uuid
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from ugc_db.db_manager import SessionLocal, Influencer, AppClip, init_db
import airtable_client

def migrate_data():
    print("🚀 Starting data migration from Airtable to PostgreSQL...")
    init_db()
    db = SessionLocal()

    try:
        # 1. Migrate Influencers
        print("👤 Migrating Influencers...")
        airtable_influencers = airtable_client.get_records("Influencers")
        for record in airtable_influencers:
            fields = record["fields"]
            name = fields.get("Name")
            if not name: continue
            
            # Check if exists
            existing = db.query(Influencer).filter(Influencer.name == name).first()
            if not existing:
                ref_images = fields.get("Reference Image", [])
                ref_url = ref_images[0]["url"] if ref_images else None
                
                db_inf = Influencer(
                    id=uuid.uuid4(),
                    name=name,
                    gender=fields.get("Gender"),
                    accent=fields.get("Accent"),
                    tone=fields.get("Tone"),
                    visual_description=fields.get("Visual Description"),
                    reference_image_url=ref_url,
                    elevenlabs_voice_id=fields.get("ElevenLabs Voice ID"),
                    category=fields.get("Category")
                )
                db.add(db_inf)
                print(f"   ✅ Added: {name}")

        # 2. Migrate App Clips
        print("\n📱 Migrating App Clips...")
        airtable_clips = airtable_client.get_records("App Clips")
        for record in airtable_clips:
            fields = record["fields"]
            name = fields.get("Clip Name")
            if not name: continue
            
            videos = fields.get("Video", [])
            video_url = videos[0]["url"] if videos else None
            if not video_url: continue

            db_clip = AppClip(
                id=uuid.uuid4(),
                name=name,
                category=fields.get("AI Assistant"),
                video_url=video_url,
                duration=fields.get("Duration", 4.0)
            )
            db.add(db_clip)
            print(f"   ✅ Added clip: {name}")

        db.commit()
        print("\n✨ Migration complete!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    migrate_data()
