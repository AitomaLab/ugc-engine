"""
Generic repair script to assemble existing scenes for any project.
Usage: python repair.py <project_name> <influencer_name>
"""
import sys
import requests
import json
from datetime import datetime
from pathlib import Path
import config
import airtable_client
import assemble_video
import subtitle_engine
import scene_builder

def repair_project(project_name, record_id, fields, length="30s"):
    print(f"🛠️ Repairing project: {project_name}")
    
    project_dir = config.TEMP_DIR / project_name
    if not project_dir.exists():
        print(f"❌ Project directory {project_dir} not found!")
        return

    # 1. Collect existing scene video paths
    video_paths = []
    for i in range(1, 10):
        pattern = f"scene_{i}_*.mp4"
        matches = list(project_dir.glob(pattern))
        if matches:
            video_paths.append(str(matches[0]))
        else:
            break

    if not video_paths:
        print("❌ No scenes found!")
        return

    # 2. Reconstruct scene data for subtitle generation
    print("   🔤 Regenerating premium subtitles...")
    influencer_name = fields.get("Influencer Name") or fields.get("Influencer", "Sofia")
    influencer = airtable_client.get_influencer(influencer_name)
    
    # Fetch app clip
    app_clip = airtable_client.get_app_clip(
        fields.get("AI Assistant", "Shop"),
        specific_clip_url=fields.get("Clip URL")
    )
    
    scenes = scene_builder.build_scenes(fields, influencer, app_clip)

    subtitle_path = project_dir / "subtitles.ass"
    subtitle_engine.generate_subtitles(scenes, subtitle_path)
    
    # 3. Assemble
    airtable_client.update_status(record_id, "Assembling")
    version = datetime.now().strftime("%H%M%S")
    output_path = config.OUTPUT_DIR / f"{project_name}_v{version}.mp4"
    
    durations = [s["target_duration"] for s in scenes]

    print(f"🎬 Assembling {len(video_paths)} scenes...")
    final_path = assemble_video.assemble_video(
        video_paths=video_paths,
        subtitle_path=str(subtitle_path),
        music_path=None,
        output_path=output_path,
        scene_durations=durations[:len(video_paths)],
        max_duration=config.get_max_duration(length)
    )

    # 4. Log asset
    veo_scenes = sum(1 for s in scenes if s["type"] == "veo")
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

    # 5. Link final video to Content Calendar
    airtable_client.attach_final_video(record_id, f"file://{final_path}")
    print(f"\n🎉 REPAIR COMPLETE: {final_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python repair.py <project_name> <influencer_name>")
        # Default for Meg
        project_name = "meg_30s_20260211_153745"
        influencer = "Meg"
    else:
        project_name = sys.argv[1]
        influencer = sys.argv[2]

    # Fetch records directly via requests
    url = f"{config.AIRTABLE_API_URL}/{config.TABLE_CONTENT_CALENDAR}"
    resp = requests.get(url, headers={"Authorization": f"Bearer {config.AIRTABLE_TOKEN}"})
    items = resp.json().get("records", [])
    
    rec = next((r for r in items if r["fields"].get("Influencer Name") == influencer), None)
    
    if rec:
        repair_project(project_name, rec["id"], rec["fields"])
    else:
        print(f"❌ Could not find {influencer}'s record in Content Calendar")
