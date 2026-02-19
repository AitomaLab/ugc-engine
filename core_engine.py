"""
Naiara Content Distribution Engine — Core Engine logic

Decoupled from Airtable.
This module provides the industrial generation flow that can be called by 
the CLI, the SaaS worker, or any other interface.
"""
import os
import time
import subprocess
import shutil
from datetime import datetime
from pathlib import Path

import requests
from PIL import Image
import io
import config
import scene_builder
import generate_scenes
import subtitle_engine
import assemble_video
import elevenlabs_client
import storage_helper
try:
    from kie_ai.nano_banana_client import client as nano_client
except ImportError:
    nano_client = None # Handle missing client gracefully if needed

def run_generation_pipeline(
    project_name: str,
    influencer: dict,
    app_clip: dict,
    fields: dict,
    status_callback=None,
    skip_music: bool = False,
    product: dict = None,
    product_type: str = "digital"
):
    """
    The main industrial generation flow.
    Takes discrete data objects instead of Airtable record IDs.
    """
    # 0. Product Analysis (Just-in-Time)
    if product and not product.get("visual_description") and not product.get("visual_analysis"):
        try:
            from ugc_backend.llm_vision_client import LLMVisionClient
            from ugc_db.db_manager import update_product

            if status_callback:
                status_callback("Analyzing Product")

            print(f"      👁️ Analyzing product image: {product['image_url']}")
            client = LLMVisionClient()
            analysis = client.describe_product_image(product['image_url'])

            if analysis:
                print(f"      ✅ Analysis complete: {analysis.get('brand_name')}")
                # Update DB
                update_product(product['id'], {"visual_description": analysis})
                # Update local object
                product["visual_description"] = analysis
            else:
                print("      ⚠️ Analysis failed or returned empty.")
        except Exception as e:
            print(f"      ❌ Product analysis error: {e}")

    # 1. Build scene structure
    if status_callback:
        status_callback("Building scenes")

    scenes = scene_builder.build_scenes(fields, influencer, app_clip, product=product, product_type=product_type)
    

    
    # 2. Generate all scene videos (Multi-API Support)
    if status_callback:
        status_callback("Generating scenes")
        
    video_paths = []
    output_dir = config.TEMP_DIR / project_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Extract model preference
    model_api = fields.get("model_api", "infinitalk-audio")

    for i, scene in enumerate(scenes, 1):
        if status_callback:
            status_callback(f"Gen: {scene['name'].title()} ({i}/{len(scenes)})")

        print(f"      Scene Dict: {scene}")  # DEBUG LOG

        output_path = output_dir / f"scene_{i}_{scene['name']}.mp4"

        try:
            if scene["type"] == "physical_product_scene":
                # 🍌 Step 1: Nano Banana (Composite Image)
                if status_callback: status_callback(f"Gen: Composite Image ({i}/{len(scenes)})")
                print(f"      🍌 Generating composite product image with prompt: {scene['nano_banana_prompt'][:50]}...")
                
                composite_url = generate_scenes.generate_composite_image(
                    scene=scene,
                    influencer=influencer,
                    product=product
                )
                print(f"      ✅ Composite Ready: {composite_url}")

                # 🎥 Step 2: Veo Animation (Image-to-Video)
                if status_callback: status_callback(f"Gen: Animating Scene ({i}/{len(scenes)})")
                print(f"      🎥 Animating with Veo...")
                
                video_url = generate_scenes.animate_image(
                    image_url=composite_url,
                    scene=scene
                )
                
                generate_scenes.download_video(video_url, output_path)

                # Veo is silent, so generates voiceover if needed
                if scene.get("subtitle_text"):
                    if status_callback: status_callback(f"Voiceover: {scene['name'].title()}")
                    print(f"      🎙️ Adding Voiceover...")
                    
                    voice_id = scene.get("voice_id", config.VOICE_MAP.get(influencer['name'], "pNInz6obpgDQGcFmaJgB"))
                    audio_file = elevenlabs_client.generate_voiceover(
                        text=scene["subtitle_text"],
                        voice_id=voice_id,
                        filename=f"vo_{i}_{scene['name']}.mp3"
                    )
                    
                    # Overlay voiceover
                    video_with_vo = output_dir / f"scene_{i}_{scene['name']}_vo.mp4"
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(output_path),
                        "-i", str(audio_file),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-map", "0:v",
                        "-map", "1:a",
                        "-shortest",
                        str(video_with_vo),
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)
                    shutil.move(str(video_with_vo), str(output_path))


            elif scene["type"] == "veo":
                if "infinitalk" in model_api:
                    # 🎙️ ElevenLabs Audio + Lip-Sync
                    audio_file = elevenlabs_client.generate_voiceover(
                        text=scene["subtitle_text"],
                        voice_id=scene.get("voice_id", config.VOICE_MAP.get(influencer['name'], config.VOICE_MAP["Meg"])),
                        filename=f"audio_{i}_{scene['name']}.mp3"
                    )
                    
                    audio_url = storage_helper.upload_temporary_file(audio_file)
                    
                    # 🖼️ Asset Mirroring Strategy (Robust Fix)
                    # 1. Try to download the image (using proxy if needed)
                    # 2. Re-upload to tmpfiles.org to get a clean, public URL for Kie.ai
                    raw_ref_url = scene["reference_image_url"]
                    print(f"      🪞 Mirroring asset: {raw_ref_url}")
                    
                    try:
                        # Determine download URL (proxy or direct)
                        if "cloudflarestorage.com" in raw_ref_url or "r2.dev" in raw_ref_url:
                            clean_url = raw_ref_url.replace("https://", "")
                            download_url = f"https://images.weserv.nl/?url={clean_url}"
                        else:
                            download_url = raw_ref_url

                        # Download to temp
                        img_resp = requests.get(download_url, timeout=10)
                        if img_resp.status_code == 200:
                            # Convert to standard JPEG to satisfy Kie.ai strictness
                            try:
                                img_content = img_resp.content
                                with Image.open(io.BytesIO(img_content)) as pil_img:
                                    pil_img = pil_img.convert("RGB")
                                    temp_img_path = output_dir / f"mirror_{i}_{int(time.time())}.jpg"
                                    pil_img.save(temp_img_path, format="JPEG", quality=95)
                            except Exception as e:
                                print(f"      ⚠️ Image conversion failed: {e}, falling back to raw write")
                                temp_img_path = output_dir / f"mirror_{i}_{int(time.time())}.jpg"
                                with open(temp_img_path, "wb") as f:
                                    f.write(img_resp.content)
                            
                            # Upload to tmpfiles.org
                            image_url = storage_helper.upload_temporary_file(temp_img_path)
                            print(f"      ✅ Asset mirrored successfully: {image_url}")
                            
                            # Cleanup temp mirror file
                            try:
                                os.remove(temp_img_path)
                            except:
                                pass
                        else:
                            print(f"      ⚠️ Mirror download failed ({img_resp.status_code}), reverting to raw URL")
                            image_url = raw_ref_url
                    except Exception as e:
                        print(f"      ⚠️ Mirroring failed: {e}, reverting to raw URL")
                        image_url = raw_ref_url

                    # ⏳ Propagation Delay: Give audio storage time to broadcast
                    print(f"      ⏳ Waiting 10s for propagation: {audio_url}")
                    time.sleep(10)
                    
                    video_url = generate_scenes.generate_lipsync_video(
                        image_url=image_url,
                        audio_url=audio_url,
                        prompt=scene["prompt"]
                    )
                else:
                    # 🎭 Pure AI Model generation (Seedance, Kling, Veo, etc.)
                    video_url = generate_scenes.generate_video(
                        prompt=scene["prompt"],
                        reference_image_url=scene.get("reference_image_url"),
                        model_api=model_api
                    )
                
                generate_scenes.download_video(video_url, output_path)

                # 🔊 Post-generation voiceover for silent models
                # Models like Kling produce silent video — we need to add
                # ElevenLabs voiceover and overlay it onto the video.
                SILENT_MODELS = {"kling"}  # Add model families that produce silent video
                model_family = model_api.split("-")[0] if "-" in model_api else model_api
                is_silent = any(s in model_api.lower() for s in SILENT_MODELS)
                
                if is_silent and scene.get("subtitle_text"):
                    if status_callback:
                        status_callback(f"Voiceover: {scene['name'].title()} ({i}/{len(scenes)})")
                    print(f"      🎙️ Silent model detected — generating ElevenLabs voiceover...")
                    
                    voice_id = scene.get("voice_id", config.VOICE_MAP.get(
                        influencer['name'], config.VOICE_MAP.get("Meg", "pNInz6obpgDQGcFmaJgB")
                    ))
                    audio_file = elevenlabs_client.generate_voiceover(
                        text=scene["subtitle_text"],
                        voice_id=voice_id,
                        filename=f"vo_{i}_{scene['name']}.mp3"
                    )
                    
                    # Overlay voiceover onto the silent video using FFmpeg
                    video_with_vo = output_dir / f"scene_{i}_{scene['name']}_vo.mp4"
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", str(output_path),
                        "-i", str(audio_file),
                        "-c:v", "copy",
                        "-c:a", "aac",
                        "-map", "0:v",
                        "-map", "1:a",
                        "-shortest",
                        str(video_with_vo),
                    ]
                    subprocess.run(cmd, capture_output=True, check=True)
                    
                    # Replace the silent video with the voiced version
                    shutil.move(str(video_with_vo), str(output_path))
                    print(f"      ✅ Voiceover added to scene {i}")

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
