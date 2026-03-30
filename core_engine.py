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

import traceback
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
    nano_client = None # Handle missing client gracefully if needed

def should_use_extend_pipeline(scenes):
    """
    Returns True if the scene list begins with 2+ consecutive Veo-type scenes.
    When True, the Extend pipeline chains them into a single seamless video.
    """
    veo_types = {"veo", "physical_product_scene"}
    leading_veo_count = 0
    for scene in scenes:
        if scene.get("type") in veo_types:
            leading_veo_count += 1
        else:
            break
    return leading_veo_count >= 2


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

    # 1. Global Seed for Consistency
    # Generate a single seed for the entire video to keep characters consistent
    # across multiple Nano Banana calls.
    global_seed = random.randint(0, 2**32 - 1)
    print(f"      🌱 Global Video Seed: {global_seed}")

    # 2. Build scene structure
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

    # --- Decide whether to use the Veo Extend pipeline ---
    use_extend = should_use_extend_pipeline(scenes)

    if use_extend:
        try:
            # === VEO EXTEND PIPELINE ===
            # Chains leading Veo scenes into a single seamless video via extend,
            # then appends remaining scenes (clips, cinematic shots) normally.
            print(f"      [EXTEND] Extend pipeline activated for {len(scenes)} scenes")

            veo_types = {"veo", "physical_product_scene"}
            veo_scenes = []
            remaining_scenes = []
            in_veo_block = True
            for scene in scenes:
                if in_veo_block and scene.get("type") in veo_types:
                    veo_scenes.append(scene)
                else:
                    in_veo_block = False
                    remaining_scenes.append(scene)

            print(f"      [EXTEND] {len(veo_scenes)} Veo scenes to chain, {len(remaining_scenes)} remaining")

            # -- Step 1: Generate Scene 1 (first Veo scene) --
            scene_1 = veo_scenes[0]
            if status_callback:
                status_callback(f"Gen: {scene_1['name'].title()} (1/{len(scenes)})")
            print(f"      [EXTEND] Generating Scene 1: {scene_1['name']}")

            extend_chunks = []
            extended_video_path = output_dir / "extended_chain.mp4"

            if scene_1["type"] == "physical_product_scene":
                # Nano Banana composite + Veo animation
                if status_callback:
                    status_callback(f"Gen: Composite Image (1/{len(scenes)})")
                composite_url = generate_scenes.generate_composite_image_with_retry(
                    scene=scene_1,
                    influencer=influencer,
                    product=product,
                    seed=global_seed
                )
                print(f"      [EXTEND] Composite ready: {composite_url}")

                if status_callback:
                    status_callback(f"Gen: Animating Scene (1/{len(scenes)})")
                result = generate_scenes.animate_image(
                    image_url=composite_url,
                    scene=scene_1
                )
                current_task_id = result["taskId"]
                current_video_url = result["videoUrl"]
            else:
                # Pure Veo generation
                result = generate_scenes.generate_video(
                    prompt=scene_1["prompt"],
                    reference_image_url=scene_1.get("reference_image_url"),
                    model_api="veo-3.1-fast"
                )
                current_task_id = result["taskId"]
                current_video_url = result["videoUrl"]

            chunk_0_path = output_dir / "extended_chunk_0.mp4"
            generate_scenes.download_video(current_video_url, chunk_0_path)
            extend_chunks.append(chunk_0_path)
            print(f"      [EXTEND] Scene 1 downloaded: {chunk_0_path}")

            # -- Step 2: Extend chain (Scenes 2..N) --
            for idx, ext_scene in enumerate(veo_scenes[1:], 2):
                if status_callback:
                    status_callback(f"Extend: {ext_scene['name'].title()} ({idx}/{len(scenes)})")
                print(f"      [EXTEND] Extending with Scene {idx}: {ext_scene['name']}")

                extension_prompt = ext_scene.get("video_animation_prompt") or ext_scene.get("prompt", "")
                result = generate_scenes.extend_video_with_retry(
                    task_id=current_task_id,
                    prompt=extension_prompt,
                    seed=ext_scene.get("seed"),
                )
                # The returned video contains ONLY the new extension segment
                chunk_idx_path = output_dir / f"extended_chunk_{idx-1}.mp4"
                generate_scenes.download_video(result["videoUrl"], chunk_idx_path)
                extend_chunks.append(chunk_idx_path)
                current_task_id = result["taskId"]
                print(f"      [EXTEND] Scene {idx} extended successfully")

            # -- Step 2(b): Concatenate extend chunks --
            # -- Step 2(b): Concatenate extend chunks --
            # Veo Extend natively overlays 1.0 seconds of context. To prevent dual-audio echoes,
            # we truncate the trailing 1.0s off every chunk EXCEPT the final one.
            # To cure the millisecond lag AND stop FFmpeg from desynchronizing the A/V streams,
            # we MUST pre-trim and re-encode each chunk individually BEFORE concatenating them!
            print(f"      [EXTEND] Trimming and re-encoding {len(extend_chunks)} extended chunks individually...")
            from assemble_video import get_video_duration, ensure_audio_stream
            
            processed_chunks = []
            for i, chunk_path in enumerate(extend_chunks):
                chunk_path = ensure_audio_stream(chunk_path, output_dir)
                safe_path = str(Path(chunk_path).resolve()).replace("\\", "/")
                if i < len(extend_chunks) - 1:
                    dur = get_video_duration(chunk_path)
                    trim_dur = max(0.1, dur - 1.0)
                    trimmed_path = safe_path.replace(".mp4", "_trimmed.mp4")
                    # Build audio filter: fade-in (non-first) + fade-out at trim boundary
                    af_parts = []
                    if i > 0:
                        af_parts.append("afade=t=in:st=0:d=0.3")
                    af_parts.append(f"afade=t=out:st={max(0, trim_dur - 0.15):.3f}:d=0.15")
                    af_filter = ",".join(af_parts)
                    cmd_trim = [
                        "ffmpeg", "-y", "-i", safe_path,
                        "-t", f"{trim_dur:.3f}",
                        "-c:v", "libx264", "-preset", "fast",
                        "-g", "30", "-keyint_min", "1",
                        "-af", af_filter,
                        "-c:a", "aac",
                        "-movflags", "+faststart",
                        trimmed_path
                    ]
                    subprocess.run(cmd_trim, capture_output=True, check=True)
                    processed_chunks.append(trimmed_path)
                else:
                    encoded_path = safe_path.replace(".mp4", "_encoded.mp4")
                    final_dur = get_video_duration(chunk_path)
                    fade_start = max(0, final_dur - 1.5)
                    # Build audio filter: fade-in (non-first) + fade-out at end
                    af_parts = []
                    if i > 0:
                        af_parts.append("afade=t=in:st=0:d=0.3")
                    af_parts.append(f"afade=t=out:st={fade_start:.3f}:d=1.5")
                    af_filter = ",".join(af_parts)
                    cmd_enc = [
                        "ffmpeg", "-y", "-i", safe_path,
                        "-c:v", "libx264", "-preset", "fast",
                        "-g", "30", "-keyint_min", "1",
                        "-af", af_filter,
                        "-c:a", "aac",
                        "-movflags", "+faststart",
                        encoded_path
                    ]
                    subprocess.run(cmd_enc, capture_output=True, check=True)
                    processed_chunks.append(encoded_path)

            print(f"      [EXTEND] Concatenating perfectly processed uniform chunks...")
            concat_list = output_dir / "extend_concat.txt"
            with open(concat_list, "w") as f:
                for chunk_path in processed_chunks:
                    f.write(f"file '{Path(chunk_path).as_posix()}'\n")

            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", str(concat_list),
                "-c:v", "libx264", "-preset", "fast",
                "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-movflags", "+faststart",
                str(extended_video_path),
            ]
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"      [EXTEND] Chunks successfully concatenated to: {extended_video_path}")

            # -- Step 3: Transcribe the extended video for synced subtitles --
            try:
                print(f"      [EXTEND] Extracting audio for transcription...")
                audio_extract_path = output_dir / "extended_chain.mp3"
                cmd = [
                    "ffmpeg", "-y", "-v", "quiet",
                    "-i", str(extended_video_path),
                    "-vn", "-acodec", "libmp3lame", "-q:a", "2",
                    str(audio_extract_path)
                ]
                subprocess.run(cmd, check=True)

                transcription_client = TranscriptionClient()
                transcription = transcription_client.transcribe_audio(str(audio_extract_path))
            except Exception as e:
                print(f"      [EXTEND] Transcription failed: {e}. Subtitles will use fallback timing.")
                transcription = None

            # -- Step 4: Build the extended video's scene dict --
            combined_subtitle = " ".join(
                s.get("subtitle_text", "") for s in veo_scenes
            ).strip()
            combined_duration = sum(s.get("target_duration", 8) for s in veo_scenes)

            extended_scene = {
                "name": "extended_chain",
                "type": veo_scenes[0]["type"],
                "path": str(extended_video_path),
                "target_duration": combined_duration,
                "subtitle_text": combined_subtitle,
                "voice_id": veo_scenes[0].get("voice_id", ""),
            }
            if transcription:
                extended_scene["transcription"] = transcription
            video_paths.append(extended_scene)

            # -- Step 5: Process remaining scenes (clips, cinematic shots) --
            for idx, scene in enumerate(remaining_scenes, len(veo_scenes) + 1):
                if status_callback:
                    status_callback(f"Gen: {scene['name'].title()} ({idx}/{len(scenes)})")

                r_output_path = output_dir / f"scene_{idx}_{scene['name']}.mp4"

                if scene["type"] == "clip":
                    generate_scenes.download_video(scene["video_url"], r_output_path)
                elif scene["type"] == "cinematic_shot":
                    print(f"      [EXTEND] Downloading cinematic shot: {scene['video_url']}")
                    generate_scenes.download_video(scene["video_url"], r_output_path)
                else:
                    # Unexpected type in remaining — generate normally
                    result = generate_scenes.generate_video(
                        prompt=scene.get("prompt", ""),
                        reference_image_url=scene.get("reference_image_url"),
                        model_api=model_api
                    )
                    generate_scenes.download_video(result["videoUrl"], r_output_path)

                scene["path"] = str(r_output_path)
                video_paths.append(scene)

            print(f"      [EXTEND] Pipeline complete: {len(video_paths)} segments ready for assembly")

        except Exception as extend_err:
            print(f"      [EXTEND] Pipeline failed: {extend_err}")
            traceback.print_exc()
            print(f"      [EXTEND] Falling back to standard scene-by-scene generation...")
            use_extend = False
            video_paths = []

    if not use_extend:
        # === ORIGINAL PIPELINE (scene-by-scene) ===
        for i, scene in enumerate(scenes, 1):
            if status_callback:
                status_callback(f"Gen: {scene['name'].title()} ({i}/{len(scenes)})")

            print(f"      Scene Dict: {scene}")  # DEBUG LOG

            output_path = output_dir / f"scene_{i}_{scene['name']}.mp4"

            try:
                if scene["type"] == "physical_product_scene":
                    # Step 1: Nano Banana (Composite Image)
                    if status_callback: status_callback(f"Gen: Composite Image ({i}/{len(scenes)})")
                    print(f"      Generating composite product image with prompt: {scene['nano_banana_prompt'][:50]}...")

                    composite_url = generate_scenes.generate_composite_image_with_retry(
                        scene=scene,
                        influencer=influencer,
                        product=product,
                        seed=global_seed
                    )
                    print(f"      Composite Ready: {composite_url}")

                    # Step 2: Veo Animation (Image-to-Video)
                    if status_callback: status_callback(f"Gen: Animating Scene ({i}/{len(scenes)})")
                    print(f"      Animating with Veo...")

                    result = generate_scenes.animate_image(
                        image_url=composite_url,
                        scene=scene
                    )

                    generate_scenes.download_video(result["videoUrl"], output_path)

                    # Veo 3.1 image-to-video produces native audio/speech.
                    # Skip ElevenLabs — just extract transcription for subtitle sync.
                    MODELS_WITH_NATIVE_AUDIO = {"veo-3.1-fast", "veo-3.1", "seedance-1.5-pro", "seedance-2.0"}
                    model_used = "veo-3.1-fast"

                    if model_used in MODELS_WITH_NATIVE_AUDIO:
                        print(f"      [OK] Veo 3.1 native audio — skipping ElevenLabs.")
                        try:
                            print(f"      [MIC] Extracting native audio for transcription...")
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
                                print("      [OK] Transcription attached to scene data")
                        except Exception as e:
                            print(f"      !! Transcription failed: {e}. Falling back to default timing.")

                    elif scene.get("subtitle_text"):
                        # Fallback for non-audio models: add ElevenLabs voiceover
                        if status_callback: status_callback(f"Voiceover: {scene['name'].title()}")
                        print(f"      [MIC] Adding ElevenLabs voiceover (model {model_used} has no native audio)...")
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
                        print(f"      [OK] Voiceover added to scene {i}")


                elif scene["type"] == "veo":
                    # Models that include native audio/lip-sync
                    MODELS_WITH_NATIVE_AUDIO = {"infinitalk", "seedance", "veo-3.1", "veo-3.1-fast"}
                    has_native_audio = any(m in model_api.lower() for m in MODELS_WITH_NATIVE_AUDIO)

                    if "infinitalk" in model_api:
                        # ElevenLabs Audio + Lip-Sync
                        audio_file = elevenlabs_client.generate_voiceover(
                            text=scene["subtitle_text"],
                            voice_id=scene.get("voice_id", config.VOICE_MAP.get(influencer['name'], config.VOICE_MAP["Meg"])),
                            filename=f"audio_{i}_{scene['name']}.mp3"
                        )

                        audio_url = storage_helper.upload_temporary_file(audio_file)

                        # Asset Mirroring Strategy (Robust Fix)
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
                                except:
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
                        # Pure AI Model generation (Seedance, Kling, Veo, etc.)
                        result = generate_scenes.generate_video(
                            prompt=scene["prompt"],
                            reference_image_url=scene.get("reference_image_url"),
                            model_api=model_api
                        )
                        video_url = result["videoUrl"]

                    generate_scenes.download_video(video_url, output_path)

                    # Post-generation voiceover for silent models
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
                    # App Clip
                    generate_scenes.download_video(scene["video_url"], output_path)

                elif scene["type"] == "cinematic_shot":
                    # Pre-rendered cinematic product shot — just download
                    print(f"      Using pre-rendered cinematic shot: {scene['video_url']}")
                    generate_scenes.download_video(scene["video_url"], output_path)

                    # Auto-Transition: if enabled, stitch this cinematic shot with
                    # the preceding influencer scene using an xfade transition.
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

    # 3. Generate subtitles (Legacy block removed - now handled in assemble_video)
    # if status_callback:
    #     status_callback("Subtitling")
    # subtitle_path = output_dir / "subtitles.ass"
    # subtitle_engine.generate_subtitles(scenes, subtitle_path)

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
        else:
            print("      [MUSIC] ⚠️ Music generation failed — video will have no background music")

    # 5. Assemble final video (WITHOUT subtitles — subtitles are applied after)
    if status_callback:
        status_callback("Assembling")

    version = datetime.now().strftime("%H%M%S")
    output_path = config.OUTPUT_DIR / f"{project_name}_v{version}.mp4"

    # Build brand names list for subtitle correction
    brand_names = []
    if product:
        if product.get("name"):
            brand_names.append(product["name"])
        visuals = product.get("visual_description") or {}
        if visuals.get("brand_name") and visuals["brand_name"] not in brand_names:
            brand_names.append(visuals["brand_name"])
    if brand_names:
        print(f"      [BRAND] Brand names for subtitle correction: {brand_names}")

    length = fields.get("Length", "15s")
    final_path = assemble_video.assemble_video(
        video_paths=video_paths,
        output_path=output_path,
        music_path=music_path,
        max_duration=config.get_max_duration(length),
        scene_types=[s.get("type", "clip") for s in video_paths],
        brand_names=brand_names or None,
    )

    # 6. Apply subtitles (Remotion primary, FFmpeg fallback)
    subtitles_enabled = fields.get("subtitles_enabled", True)
    subtitle_style = fields.get("subtitle_style", "hormozi")
    subtitle_placement = fields.get("subtitle_placement", "middle")
    use_remotion = os.getenv("USE_REMOTION_SUBTITLES", "true").lower() == "true"

    captioned_path = None

    if subtitles_enabled:
        if status_callback:
            status_callback("Subtitling")

        # Always run Whisper on the FINAL assembled video for accurate timestamps
        # Pass the known script text so Whisper knows what words to expect
        script_text = fields.get("Hook") or fields.get("script_text")
        print("      [SUBTITLES] Transcribing final assembled video with Whisper...")
        if script_text:
            print(f"      [SUBTITLES] Script hint: {script_text[:80]}...")
        transcription = subtitle_engine.extract_transcription_with_whisper(
            str(final_path), brand_names=brand_names or None, script_text=script_text
        )

        if transcription and transcription.get("words"):
            # --- PRIMARY PATH: Remotion ---
            if use_remotion:
                try:
                    print(f"      [SUBTITLES] Rendering with Remotion (style={subtitle_style}, placement={subtitle_placement})...")
                    remotion_url = os.getenv("REMOTION_RENDERER_URL", "http://localhost:8090")
                    payload = {
                        "videoPath": str(final_path),
                        "transcription": transcription,
                        "subtitleStyle": subtitle_style,
                        "subtitlePlacement": subtitle_placement,
                    }
                    response = requests.post(
                        f"{remotion_url}/render",
                        json=payload,
                        timeout=300,  # 5 minutes max
                    )
                    response.raise_for_status()
                    result = response.json()
                    if result.get("success") and result.get("outputLocation"):
                        captioned_path = result["outputLocation"]
                        print(f"      [SUBTITLES] ✅ Remotion render complete: {captioned_path}")
                    else:
                        raise ValueError(f"Remotion returned unexpected response: {result}")
                except Exception as remotion_err:
                    print(f"      [SUBTITLES] ⚠️ Remotion failed: {remotion_err}. Falling back to FFmpeg.")
                    captioned_path = None  # Trigger fallback

            # --- FALLBACK PATH: FFmpeg/ASS ---
            if not captioned_path:
                try:
                    print("      [SUBTITLES] Rendering with FFmpeg fallback...")
                    from pathlib import Path as _Path
                    subtitle_path = _Path(str(final_path)).parent / "subtitles_synced.ass"
                    subtitle_engine.generate_subtitles_from_whisper(
                        transcription, subtitle_path, brand_names=brand_names or None
                    )
                    if subtitle_path.exists() and subtitle_path.stat().st_size > 250:
                        subtitled_path = _Path(str(final_path)).parent / f"{_Path(str(final_path)).stem}_captioned.mp4"
                        sub_path_safe = str(subtitle_path.resolve()).replace("\\", "/").replace(":", "\\:")
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", str(final_path),
                            "-vf", f"ass=\\'{sub_path_safe}\\'",
                            "-c:v", "libx264",
                            "-c:a", "copy",
                            "-preset", "veryfast",
                            str(subtitled_path),
                        ]
                        subprocess.run(cmd, capture_output=True, check=True)
                        captioned_path = str(subtitled_path)
                        print(f"      [SUBTITLES] ✅ FFmpeg fallback complete: {captioned_path}")
                except Exception as ffmpeg_err:
                    print(f"      [SUBTITLES] ❌ FFmpeg fallback also failed: {ffmpeg_err}. Using video without subtitles.")
                    captioned_path = None
        else:
            print("      [SUBTITLES] ⚠️ No transcription words found. Skipping subtitles.")

    # Use captioned video if available, otherwise use the assembled video without subtitles
    final_output_path = captioned_path if captioned_path else str(final_path)

    # 7. Cleanup temp files
    assemble_video.cleanup_temp(project_name)

    return str(final_output_path)

