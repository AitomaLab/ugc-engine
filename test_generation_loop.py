import os
import sys
import time
from dotenv import load_dotenv

# Ensure we can import from current directory
sys.path.append(os.getcwd())

load_dotenv(".env.saas")

from ugc_db.db_manager import get_supabase
import core_engine

def status_callback(msg):
    print(f"[{time.strftime('%H:%M:%S')}] 🎬 STATUS: {msg}")

def main():
    print("🚀 Starting Test Generation Loop...")
    sb = get_supabase()

    # 1. Fetch Influencer (Meg)
    print("🔎 Fetching Influencer 'Meg'...")
    files = sb.table("influencers").select("*").eq("name", "Meg").execute()
    if not files.data:
        print("❌ Meg not found in DB!")
        return
    influencer = files.data[0]
    
    print(f"✅ Found Influencer: {influencer['name']}")
    print(f"   Raw Image Code: {influencer.get('image_url')}")
    
    # 5. Build Influencer Dict (Mimic tasks.py)
    influencer_dict = {
        "name": influencer["name"],
        "description": influencer.get("description", ""),
        "personality": influencer.get("personality", ""),
        "style": influencer.get("style", ""),
        "image_url": influencer.get("image_url", ""),
        "reference_image_url": influencer.get("image_url", ""), # Compat
        "elevenlabs_voice_id": influencer.get("elevenlabs_voice_id", ""),
    }
    print(f"   Constructed Dict: {influencer_dict}")

    # 2. Fetch App Clip
    print("🔎 Fetching a Travel App Clip...")
    clips = sb.table("app_clips").select("*").ilike("name", "%Travel%").execute()
    app_clip_dict = None
    if clips.data:
        clip = clips.data[0]
        app_clip_dict = {
            "name": clip["name"],
            "description": clip.get("description", ""),
            "video_url": clip.get("video_url", ""),
            "duration": clip.get("duration_seconds", 4),
        }
        print(f"✅ Found clip: {clip['name']}")
    else:
        print("⚠️ No Travel clip found, testing fallback path (None).")

    # 3. Setup Fields (Simulate 15s job)
    fields = {
        "Hook": "¡No me creo que esto exista, es brutal!",
        "Angle (Hook)": "Disbelief",
        "AI Assistant": "Travel",
        "Theme": "Travel Planner",
        "Length": "15s",
        "model_api": "seedance-1.5-pro"
    }

    # 4. Run Pipeline
    project_name = f"test_gen_{int(time.time())}"
    print(f"\n🎬 Running Pipeline: {project_name}")
    try:
        video_path = core_engine.run_generation_pipeline(
            project_name=project_name,
            influencer=influencer_dict,
            app_clip=app_clip_dict,
            fields=fields,
            status_callback=status_callback
        )
        print(f"\n✅ SUCCESS! Video generated at: {video_path}")
    except Exception as e:
        print(f"\n❌ FAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
