"""
Naiara Content Distribution Engine — Core Engine logic

Decoupled from Airtable.
This module provides the industrial generation flow that can be called by 
the CLI, the SaaS worker, or any other interface.
"""
import os
import time
from datetime import datetime
from pathlib import Path

import config
import scene_builder
import generate_scenes
import subtitle_engine
import assemble_video
import elevenlabs_client
import storage_helper

def run_generation_pipeline(
    project_name: str,
    influencer: dict,
    app_clip: dict,
    fields: dict,
    status_callback=None,
    skip_music: bool = False
):
    """
    The main industrial generation flow.
    Takes discrete data objects instead of Airtable record IDs.
    """
    # 1. Build scene structure
    if status_callback:
        status_callback("Building scenes")
    
    scenes = scene_builder.build_scenes(fields, influencer, app_clip)
    
    # 2. Generate all scene videos (ElevenLabs + InfiniteTalk)
    if status_callback:
        status_callback("Generating scenes")
        
    video_paths = []
    output_dir = config.TEMP_DIR / project_name
    output_dir.mkdir(parents=True, exist_ok=True)

    for i, scene in enumerate(scenes, 1):
        if status_callback:
            status_callback(f"Gen: {scene['name'].title()} ({i}/{len(scenes)})")

        output_path = output_dir / f"scene_{i}_{scene['name']}.mp4"

        try:
            if scene["type"] == "veo":
                # 🎙️ ElevenLabs Audio
                audio_file = elevenlabs_client.generate_voiceover(
                    text=scene["subtitle_text"],
                    voice_id=scene.get("voice_id", config.VOICE_MAP.get(influencer['name'], config.VOICE_MAP["Meg"])),
                    filename=f"audio_{i}_{scene['name']}.mp3"
                )
                
                # ☁️ Temporary Storage
                audio_url = storage_helper.upload_temporary_file(audio_file)
                
                # 🎬 Lip-Synced video via InfiniteTalk
                video_url = generate_scenes.generate_lipsync_video(
                    image_url=scene["reference_image_url"],
                    audio_url=audio_url
                )
                
                # 📥 Download final clip
                generate_scenes.download_video(video_url, output_path)

            elif scene["type"] == "clip":
                # 📱 App Clip
                generate_scenes.download_video(scene["video_url"], output_path)

            scene["path"] = str(output_path)
            video_paths.append(scene)

        except Exception as e:
            raise RuntimeError(f"Scene {i} ({scene['name']}) generation failed: {e}")

    # 3. Generate subtitles
    if status_callback:
        status_callback("Subtitling")
        
    subtitle_path = output_dir / "subtitles.ass"
    subtitle_engine.generate_subtitles(scenes, subtitle_path)

    # 4. Generate music (optional)
    music_path = None
    if not skip_music:
        if status_callback:
            status_callback("Adding Music")
            
        theme = fields.get("Theme", "")
        music_prompt = (
            f"upbeat trendy background music for a short social media video about {theme}, "
            f"energetic positive modern pop instrumental"
        )
        music_url = generate_scenes.generate_music(music_prompt)
        if music_url:
            music_file = output_dir / "music.mp3"
            generate_scenes.download_video(music_url, music_file)
            music_path = str(music_file)

    # 5. Assemble final video
    if status_callback:
        status_callback("Assembling")
        
    version = datetime.now().strftime("%H%M%S")
    output_path = config.OUTPUT_DIR / f"{project_name}_v{version}.mp4"
    durations = [s["target_duration"] for s in scenes]
    length = fields.get("Length", "15s")

    final_path = assemble_video.assemble_video(
        video_paths=video_paths,
        subtitle_path=str(subtitle_path),
        music_path=music_path,
        output_path=output_path,
        scene_durations=durations,
        max_duration=config.get_max_duration(length),
    )
    
    # 6. Cleanup temp files
    assemble_video.cleanup_temp(project_name)
    
    return str(final_path)
