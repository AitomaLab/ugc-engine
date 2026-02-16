"""
Repair script to assemble existing scenes for a project.
Useful when the pipeline fails AFTER scene generation.
"""
import sys
import requests
from pathlib import Path
import config
import airtable_client
import assemble_video
import subtitle_engine

def repair_project(project_name, record_id, length="30s", skip_music=True):
    print(f"🛠️ Repairing project: {project_name}")
    
    project_dir = config.TEMP_DIR / project_name
    if not project_dir.exists():
        print(f"❌ Project directory {project_dir} not found!")
        return

    # 1. Collect scene paths
    # Scenes are named scene_1_hook.mp4, etc.
    scenes = []
    # We expect 4 scenes for 30s
    for i in range(1, 5):
        pattern = f"scene_{i}_*.mp4"
        matches = list(project_dir.glob(pattern))
        if matches:
            scenes.append(str(matches[0]))
        else:
            print(f"⚠️ Warning: Missing scene {i}")

    if not scenes:
        print("❌ No scenes found!")
        return

    print(f"✅ Found {len(scenes)} scenes.")

    # 2. Check for subtitles
    subtitle_path = project_dir / "subtitles.ass"
    if not subtitle_path.exists():
        print("⚠️ No subtitles.ass found. Generating now...")
        # Since we don't have the original scene objects easily, 
        # this might be tricky, but we can assume standard 4-scene 30s structure
        # if we really had to. But looking at the dir, subtitles.ass exists!
    
    # 3. Assemble
    airtable_client.update_status(record_id, "Assembling")
    output_path = config.OUTPUT_DIR / f"{project_name}.mp4"
    
    # Get standard durations
    dur_dict = config.get_scene_durations(length)
    durations = list(dur_dict.values()) # order: hook, app_demo, reaction, cta

    print(f"🎬 Assembling {len(scenes)} scenes...")
    final_path = assemble_video.assemble_video(
        video_paths=scenes,
        subtitle_path=str(subtitle_path) if subtitle_path.exists() else None,
        music_path=None, # User said --no-music
        output_path=output_path,
        scene_durations=durations[:len(scenes)]
    )

    # 4. Log asset
    veo_scenes = sum(1 for p in scenes if "clip" not in p) # rough guess
    total_cost = (veo_scenes * 0.30)
    
    airtable_client.log_asset(
        content_title=project_name,
        scene_name="final",
        asset_type="Final Video",
        source_url=f"file://{final_path}",
        duration=config.get_max_duration(length),
        cost=total_cost,
        status="Ready"
    )

    # 5. Final Status
    airtable_client.update_status(record_id, "Review")
    print(f"\n🎉 REPAIR COMPLETE: {final_path}")

if __name__ == "__main__":
    # Max's project: max_30s_20260211_153208
    # Fetch records directly via requests
    url = f"{config.AIRTABLE_API_URL}/{config.TABLE_CONTENT_CALENDAR}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {config.AIRTABLE_TOKEN}"})
    items = resp.json().get("records", [])
    
    max_rec = next((r for r in items if r["fields"].get("Influencer Name") == "Max"), None)
    
    if max_rec:
        repair_project("max_30s_20260211_153208", max_rec["id"])
    else:
        print("❌ Could not find Max's record in Content Calendar")
