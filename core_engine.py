"""
Naiara Content Distribution Engine — Core Engine logic (v3 - Veo Extend)

CHANGES IN v3:
  - Added should_use_extend_pipeline() gate.
  - The Extend pipeline now handles both multi-scene physical product videos
    AND 30s digital product videos (which have 3 Veo scenes).
  - 15s digital product videos (1 Veo scene) continue to use the original
    sequential pipeline.
  - The original pipeline block is preserved verbatim and unchanged.
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
import random
from ugc_backend.transcription_client import TranscriptionClient
try:
    from kie_ai.nano_banana_client import client as nano_client
except ImportError:
    nano_client = None


def should_use_extend_pipeline(scenes):
    """
    Determines if the Veo Extend pipeline should be used.
    Returns True if there are more than one Veo-family scenes.
    This correctly routes:
      - 15s Physical (2 Veo scenes)  -> True  -> Extend pipeline
      - 30s Physical (4 Veo scenes)  -> True  -> Extend pipeline
      - 30s Digital  (3 Veo scenes)  -> True  -> Extend pipeline
      - 15s Digital  (1 Veo scene)   -> False -> Original pipeline
      - Cinematic    (1 Veo scene)   -> False -> Original pipeline
      - InfiniteTalk (0 Veo scenes)  -> False -> Original pipeline
    """
    veo_scene_count = sum(
        1 for s in scenes if s.get("type") in {"veo", "physical_product_scene"}
    )
    return veo_scene_count > 1


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

            print(f"      Analyzing product image: {product['image_url']}")
            client = LLMVisionClient()
            analysis = client.describe_product_image(product['image_url'])

            if analysis:
                print(f"      Analysis complete: {analysis.get('brand_name')}")
                update_product(product['id'], {"visual_description": analysis})
                product["visual_description"] = analysis
            else:
                print("      Analysis failed or returned empty.")
        except Exception as e:
            print(f"      Product analysis error: {e}")

    # 1. Global Seed for Consistency
    global_seed = random.randint(0, 2**32 - 1)
    print(f"      Global Video Seed: {global_seed}")

    # 2. Build scene structure
    if status_callback:
        status_callback("Building scenes")

    scenes = scene_builder.build_scenes(fields, influencer, app_clip, product=product, product_type=product_type)

    # 3. Generate all scene videos
    if status_callback:
        status_callback("Generating scenes")

    video_paths = []
    output_dir = config.TEMP_DIR / project_name
    output_dir.mkdir(parents=True, exist_ok=True)

    model_api = fields.get("model_api", "infinitalk-audio")

    if should_use_extend_pipeline(scenes):
        # -----------------------------------------------------------------------
        # NEW v3: Unified Sequential Veo Extend Pipeline
        # Handles both multi-scene physical product videos AND 30s digital videos.
        # -----------------------------------------------------------------------
        print("      Entering Unified Veo Extend Pipeline...")
        current_task_id = None
        final_video_url = None

        # Separate Veo scenes from non-Veo scenes (e.g., app clips)
        veo_scenes = [s for s in scenes if s.get("type") in {"veo", "physical_product_scene"}]
        other_scenes = [s for s in scenes if s.get("type") not in {"veo", "physical_product_scene"}]

        for i, scene in enumerate(veo_scenes, 1):
            if status_callback:
                status_callback(f"Gen: Veo Scene {i}/{len(veo_scenes)}")
            print(f"\n{'='*50}\nScene {i}/{len(veo_scenes)}: {scene['name'].upper()} (Extend Pipeline)\n{'='*50}")

            if i == 1:
                # First scene: Generate from scratch
                if scene["type"] == "physical_product_scene":
                    # Step A: Nano Banana composite image
                    if status_callback:
                        status_callback(f"Gen: Composite Image ({i}/{len(veo_scenes)})")
                    print(f"      Generating composite product image...")
                    composite_url = generate_scenes.generate_composite_image_with_retry(
                        scene=scene,
                        influencer=influencer,
                        product=product,
                        seed=global_seed
                    )
                    print(f"      Composite Ready: {composite_url}")
                    # Step B: Veo animate the composite
                    if status_callback:
                        status_callback(f"Gen: Animating Scene ({i}/{len(veo_scenes)})")
                    print(f"      Animating with Veo 3.1...")
                    result = generate_scenes.generate_video_with_retry(
                        prompt=scene.get("video_animation_prompt") or scene.get("prompt"),
                        reference_image_url=composite_url,
                        model_api="veo-3.1-fast"
                    )
                else:
                    # Standard "veo" scene (digital product)
                    result = generate_scenes.generate_video_with_retry(
                        prompt=scene["prompt"],
                        reference_image_url=scene.get("reference_image_url"),
                        model_api=model_api
                    )
                current_task_id = result["taskId"]
                final_video_url = result["videoUrl"]
                print(f"      Scene 1 complete. taskId: {current_task_id[:30]}...")

            else:
                # Subsequent scenes: Extend the previous video
                if status_callback:
                    status_callback(f"Gen: Extending Scene {i}/{len(veo_scenes)}")
                print(f"      Extending video with scene {i} prompt...")

                # For physical product scenes, generate a new composite first,
                # then use its animation prompt for the extension.
                if scene["type"] == "physical_product_scene":
                    if status_callback:
                        status_callback(f"Gen: Composite Image ({i}/{len(veo_scenes)})")
                    composite_url = generate_scenes.generate_composite_image_with_retry(
                        scene=scene,
                        influencer=influencer,
                        product=product,
                        seed=global_seed
                    )
                    extend_prompt = scene.get("video_animation_prompt") or scene.get("prompt")
                else:
                    extend_prompt = scene.get("prompt")

                result = generate_scenes.extend_video_with_retry(
                    task_id=current_task_id,
                    prompt=extend_prompt
                )
                current_task_id = result["taskId"]
                final_video_url = result["videoUrl"]
                print(f"      Scene {i} extension complete. taskId: {current_task_id[:30]}...")

        # Download the single final extended video
        if final_video_url:
            extended_output_path = output_dir / "scene_1_extended.mp4"
            generate_scenes.download_video(final_video_url, extended_output_path)

            # Calculate total duration of all Veo scenes
            total_veo_duration = sum(s.get("target_duration", 8) for s in veo_scenes)

            # Build a single combined scene dict
            combined_scene = {
                "name": "extended_video",
                "type": "veo",
                "path": str(extended_output_path),
                "target_duration": total_veo_duration,
                "subtitle_text": " ".join(
                    s.get("subtitle_text", "") for s in veo_scenes if s.get("subtitle_text")
                ).strip()
            }

            # Transcribe the full extended video for subtitle sync
            try:
                print("      Extracting native audio for transcription...")
                audio_extract_path = output_dir / "extended_audio.mp3"
                cmd = [
                    "ffmpeg", "-y", "-v", "quiet",
                    "-i", str(extended_output_path),
                    "-vn",
                    "-acodec", "libmp3lame",
                    "-q:a", "2",
                    str(audio_extract_path)
                ]
                subprocess.run(cmd, check=True)
                transcription_client = TranscriptionClient()
                transcription = transcription_client.transcribe_audio(str(audio_extract_path))
                if transcription:
                    combined_scene["transcription"] = transcription
                    print("      Transcription attached to scene data")
            except Exception as e:
                print(f"      Transcription failed: {e}. Falling back to default timing.")

            video_paths.append(combined_scene)

        # Process non-Veo scenes (e.g., app clips for digital products)
        for scene in other_scenes:
            output_path = output_dir / f"scene_{scene['name']}.mp4"
            if scene["type"] == "clip":
                generate_scenes.download_video(scene["video_url"], output_path)
            elif scene["type"] == "cinematic_shot":
                generate_scenes.download_video(scene["video_url"], output_path)
            scene["path"] = str(output_path)
            video_paths.append(scene)

    else:
        # -----------------------------------------------------------------------
        # ORIGINAL: Sequential pipeline (15s digital, cinematic, single-scene)
        # This block is identical to the original core_engine.py. No changes.
        # -----------------------------------------------------------------------
        print("      Entering Original Sequential Pipeline...")
        MODELS_WITH_NATIVE_AUDIO = {"veo-3.1-fast", "veo-3.1", "seedance-1.5-pro", "seedance-2.0"}

        for i, scene in enumerate(scenes, 1):
            if status_callback:
                status_callback(f"Gen: {scene['name'].title()} ({i}/{len(scenes)})")

            print(f"      Scene Dict: {scene}")
            output_path = output_dir / f"scene_{i}_{scene['name']}.mp4"

            try:
                if scene["type"] == "physical_product_scene":
                    if status_callback:
                        status_callback(f"Gen: Composite Image ({i}/{len(scenes)})")
                    print(f"      Generating composite product image with prompt: {scene['nano_banana_prompt'][:50]}...")

                    composite_url = generate_scenes.generate_composite_image_with_retry(
                        scene=scene,
                        influencer=influencer,
                        product=product,
                        seed=global_seed
                    )
                    print(f"      Composite Ready: {composite_url}")

                    if status_callback:
                        status_callback(f"Gen: Animating Scene ({i}/{len(scenes)})")
                    print(f"      Animating with Veo...")

                    video_url = generate_scenes.animate_image(
                        image_url=composite_url,
                        scene=scene
                    )

                    generate_scenes.download_video(video_url, output_path)

                    model_used = "veo-3.1-fast"

                    if scene.get("subtitle_text") and model_used not in MODELS_WITH_NATIVE_AUDIO:
                        if status_callback:
                            status_callback(f"Voiceover: {scene['name'].title()}")
                        print(f"      Adding Voiceover (model {model_used} has no native audio)...")

                        voice_id = scene.get("voice_id", config.VOICE_MAP.get(influencer['name'], "pNInz6obpgDQGcFmaJgB"))
                        audio_file = elevenlabs_client.generate_voiceover(
                            text=scene["subtitle_text"],
                            voice_id=voice_id,
                            filename=f"vo_{i}_{scene['name']}.mp3"
                        )

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
                    else:
                        print(f"      Skipping ElevenLabs: Model '{model_used}' has native audio.")

                        if model_used in MODELS_WITH_NATIVE_AUDIO:
                            try:
                                print(f"      Extracting native audio for transcription...")
                                audio_extract_path = output_dir / f"scene_{i}_{scene['name']}.mp3"

                                cmd = [
                                    "ffmpeg", "-y", "-v", "quiet",
                                    "-i", str(output_path),
                                    "-vn",
                                    "-acodec", "libmp3lame",
                                    "-q:a", "2",
                                    str(audio_extract_path)
                                ]
                                subprocess.run(cmd, check=True)

                                transcription_client = TranscriptionClient()
                                transcription = transcription_client.transcribe_audio(str(audio_extract_path))

                                if transcription:
                                    scene["transcription"] = transcription
                                    print("      Transcription attached to scene data")

                            except Exception as e:
                                print(f"      Transcription failed: {e}. Falling back to default timing.")

                elif scene["type"] == "veo":
                    has_native_audio = any(m in model_api.lower() for m in {"infinitalk", "seedance", "veo-3.1", "veo-3.1-fast"})

                    if "infinitalk" in model_api:
                        audio_file = elevenlabs_client.generate_voiceover(
                            text=scene["subtitle_text"],
                            voice_id=scene.get("voice_id", config.VOICE_MAP.get(influencer['name'], config.VOICE_MAP["Meg"])),
                            filename=f"audio_{i}_{scene['name']}.mp3"
                        )

                        audio_url = storage_helper.upload_temporary_file(audio_file)

                        raw_ref_url = scene["reference_image_url"]
                        print(f"      Mirroring asset: {raw_ref_url}")

                        try:
                            if "cloudflarestorage.com" in raw_ref_url or "r2.dev" in raw_ref_url:
                                clean_url = raw_ref_url.replace("https://", "")
                                download_url = f"https://images.weserv.nl/?url={clean_url}"
                            else:
                                download_url = raw_ref_url

                            img_resp = requests.get(download_url, timeout=10)
                            if img_resp.status_code == 200:
                                try:
                                    img_content = img_resp.content
                                    with Image.open(io.BytesIO(img_content)) as pil_img:
                                        pil_img = pil_img.convert("RGB")
                                        temp_img_path = output_dir / f"mirror_{i}_{int(time.time())}.jpg"
                                        pil_img.save(temp_img_path, format="JPEG", quality=95)
                                except Exception as e:
                                    print(f"      Image conversion failed: {e}, falling back to raw write")
                                    temp_img_path = output_dir / f"mirror_{i}_{int(time.time())}.jpg"
                                    with open(temp_img_path, "wb") as f:
                                        f.write(img_resp.content)

                                image_url = storage_helper.upload_temporary_file(temp_img_path)
                                print(f"      Asset mirrored successfully: {image_url}")

                                try:
                                    os.remove(temp_img_path)
                                except Exception:
                                    pass
                            else:
                                print(f"      Mirror download failed ({img_resp.status_code}), reverting to raw URL")
                                image_url = raw_ref_url
                        except Exception as e:
                            print(f"      Mirroring failed: {e}, reverting to raw URL")
                            image_url = raw_ref_url

                        print(f"      Waiting 10s for propagation: {audio_url}")
                        time.sleep(10)

                        video_url = generate_scenes.generate_lipsync_video(
                            image_url=image_url,
                            audio_url=audio_url,
                            prompt=scene["prompt"]
                        )
                    else:
                        result = generate_scenes.generate_video(
                            prompt=scene["prompt"],
                            reference_image_url=scene.get("reference_image_url"),
                            model_api=model_api
                        )
                        video_url = result["videoUrl"]

                    generate_scenes.download_video(video_url, output_path)

                    if not has_native_audio and scene.get("subtitle_text"):
                        if status_callback:
                            status_callback(f"Voiceover: {scene['name'].title()} ({i}/{len(scenes)})")
                        print(f"      Silent model detected — generating ElevenLabs voiceover...")

                        voice_id = scene.get("voice_id", config.VOICE_MAP.get(
                            influencer['name'], config.VOICE_MAP.get("Meg", "pNInz6obpgDQGcFmaJgB")
                        ))
                        audio_file = elevenlabs_client.generate_voiceover(
                            text=scene["subtitle_text"],
                            voice_id=voice_id,
                            filename=f"vo_{i}_{scene['name']}.mp3"
                        )

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
                        print(f"      Voiceover added to scene {i}")

                elif scene["type"] == "clip":
                    generate_scenes.download_video(scene["video_url"], output_path)

                elif scene["type"] == "cinematic_shot":
                    print(f"      Using pre-rendered cinematic shot: {scene['video_url']}")
                    generate_scenes.download_video(scene["video_url"], output_path)

                    auto_trans = fields.get("auto_transition_type")
                    if auto_trans and video_paths:
                        prev_scene = video_paths[-1]
                        prev_path = prev_scene.get("path")
                        if prev_path and prev_scene.get("type") == "physical_product_scene":
                            try:
                                if status_callback:
                                    status_callback(f"Transition: {scene['name'].title()} ({i}/{len(scenes)})")
                                print(f"      Applying {auto_trans} transition...")
                                from ugc_worker.video_tools import stitch_with_transition
                                stitched_path = output_dir / f"scene_{i}_{scene['name']}_stitched.mp4"
                                stitch_with_transition(
                                    influencer_clip=prev_path,
                                    cinematic_clip=str(output_path),
                                    transition_type=auto_trans,
                                    output_path=str(stitched_path),
                                )
                                shutil.move(str(stitched_path), prev_path)
                                print(f"      Transition applied — merged into preceding scene")
                                scene["_merged"] = True
                            except Exception as e:
                                print(f"      Auto-transition failed: {e}. Using hard cut.")

                scene["path"] = str(output_path)
                if not scene.get("_merged"):
                    video_paths.append(scene)

            except Exception as e:
                raise RuntimeError(f"Scene {i} ({scene['name']}) generation failed: {e}")

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
    length = fields.get("Length", "15s")

    final_path = assemble_video.assemble_video(
        video_paths=video_paths,
        output_path=output_path,
        music_path=music_path,
        max_duration=config.get_max_duration(length),
        scene_types=[s.get("type", "clip") for s in video_paths],
    )

    # 6. Cleanup temp files
    assemble_video.cleanup_temp(project_name)

    return str(final_path)
