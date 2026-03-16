"""
Prompt builder for Physical Products (Cosmetics, Bottles).
"""
import random
import config
from prompts import sanitize_dialogue


def build_scene_1_veo_prompt(ctx, script_part, product_desc="product"):
    """Scene 1: Holding product up close to camera. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()

    dialogue = sanitize_dialogue(script_part) if script_part else "oh my god you guys have to see this"

    return (
        f"dialogue: {dialogue}\n"
        f"product: {product_desc}\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"only one right hand holds the product, left hand rests naturally at side or on hip, "
        f"no third arm or hand appears at any time during the video\n"
        f"action: character holds product in right hand at chest level showing label to camera, "
        f"left arm relaxed at side, slight natural body sway, maintains eye contact with camera\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores, "
        f"not airbrushed, {energy_str} energy expression\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, arm length distance, "
        f"natural handheld shake\n"
        f"setting: well-lit casual home environment, natural window light, slightly blurry background\n"
        f"emotion: {energy_str}, genuine excitement, authentic reaction\n"
        f"voice_type: casual, {tone_str}, conversational {accent_str}\n"
        f"style: raw UGC realism, candid, not polished, imperfections intact\n"
        f"speech_constraint: start speaking immediately with no introductory filler, speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"motion_constraint: character has only two arms and two hands throughout the entire video, "
        f"never show a third hand or arm, no limbs appear from outside the frame\n"
        f"negative: no auditory hallucinations, no spoken filler words, no introductory thanks or umm, no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
        f"no floating hands, no hands appearing from off-screen, no duplicate body parts, "
        f"no airbrushed skin, no studio lighting, no geometric distortion"
    )


def build_scene_2_veo_prompt(ctx, script_part, product_desc="product"):
    """Scene 2: Showing product close to face. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()

    dialogue = sanitize_dialogue(script_part) if script_part else "and the texture is seriously so good"

    return (
        f"dialogue: {dialogue}\n"
        f"product: {product_desc}\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"only one right hand holds the product near face, left hand is not visible or rests on chest, "
        f"no third arm or hand appears at any time during the video\n"
        f"action: character holds product up near face with one hand, tilts it slightly to show label, "
        f"smiles warmly and nods while speaking directly to camera, other arm stays down out of frame\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores "
        f"and subtle grain, not airbrushed\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, warm tones, "
        f"natural daylight, upper body framing\n"
        f"setting: casual home environment, soft diffused window light, lived-in background\n"
        f"emotion: {energy_str}, satisfied, genuine approval\n"
        f"voice_type: casual, {tone_str}, conversational {accent_str}\n"
        f"style: candid UGC look, no filters, realism, high detail, skin texture\n"
        f"speech_constraint: start speaking immediately with no introductory filler, speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"motion_constraint: character has only two arms and two hands throughout the entire video, "
        f"never show a third hand or arm, no limbs appear from outside the frame\n"
        f"negative: no auditory hallucinations, no spoken filler words, no introductory thanks or umm, no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
        f"no floating hands, no hands appearing from off-screen, no duplicate body parts, "
        f"no extra fingers, no airbrushed skin, no studio backdrop, no geometric distortion"
    )


def build_scene_3_veo_prompt(ctx, script_part, product_desc="product"):
    """Scene 3 (30s CTA): Pointing at product, warm call-to-action. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()

    dialogue = sanitize_dialogue(script_part) if script_part else "seriously you need to try this, link in my bio"

    return (
        f"dialogue: {dialogue}\n"
        f"product: {product_desc}\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"one hand points at product held in other hand, "
        f"no third arm or hand appears at any time during the video\n"
        f"action: character holds product in one hand at chest level, points at it with other hand, "
        f"looks directly at camera with warm encouraging expression, nods while speaking\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores, "
        f"not airbrushed, {energy_str} energy expression\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, arm length distance, "
        f"natural handheld shake\n"
        f"setting: well-lit casual home environment, natural window light, slightly blurry background\n"
        f"emotion: warm, encouraging, genuine recommendation, direct\n"
        f"voice_type: casual, {tone_str}, conversational {accent_str}\n"
        f"style: raw UGC realism, candid, not polished, imperfections intact\n"
        f"speech_constraint: start speaking immediately with no introductory filler, speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"motion_constraint: character has only two arms and two hands throughout the entire video, "
        f"never show a third hand or arm, no limbs appear from outside the frame\n"
        f"negative: no auditory hallucinations, no spoken filler words, no introductory thanks or umm, no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
        f"no floating hands, no hands appearing from off-screen, no duplicate body parts, "
        f"no extra fingers, no airbrushed skin, no studio backdrop, no geometric distortion"
    )


def generate_nano_banana_prompt(influencer_name: str, product_description: str, scene_description: str) -> str:
    """
    Generates a structured prompt for Nano Banana Pro image composition.
    Note: influencer_name kept for signature compat but not used in prompt text.
    """
    return (
        f"action: character {scene_description}\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"one hand holds product, other hand relaxed at side or not visible\n"
        f"character: infer from reference image, preserve exact facial features and appearance\n"
        f"product: holding a {product_description} in one hand, show product with all visible text clear and accurate\n"
        f"setting: well-lit casual home environment, natural lighting\n"
        f"camera: amateur iPhone photo, casual selfie, slightly uneven framing\n"
        f"style: candid UGC look, no filters, realism, high detail, natural skin texture with visible pores\n"
        f"text_accuracy: preserve all visible product text exactly as in reference image\n"
        f"negative: no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
        f"no extra fingers, no airbrushed skin, no studio backdrop, no geometric distortion"
    )


def generate_physical_image_prompt(ctx, close_up=False):
    """
    Generates the pure image composition prompt for Nano Banana.
    Uses the YAML visual description if available.
    """
    product = ctx.get("product", {})
    va = product.get("visual_description") or product.get("visual_analysis") or {}

    # Extract visual details
    brand = va.get("brand_name", product.get("name", "Product"))
    desc = va.get("visual_description", "a physical product")
    colors = ", ".join([c.get("name", "") for c in va.get("color_scheme", [])])

    if close_up:
        return (
            f"action: close-up macro shot of {brand} product on clean surface\n"
            f"product: {desc}, featuring colors {colors}\n"
            f"setting: clean modern surface, aesthetic lighting, soft shadows\n"
            f"camera: shot on iPhone 15 Pro, shallow depth of field, warm tones\n"
            f"style: professional product photography, high detail, realism\n"
            f"text_accuracy: preserve all visible product text exactly as in reference image\n"
            f"negative: no geometric distortion, no watermarks, no text overlays"
        )
    else:
        return (
            f"action: character holds {brand} product naturally in one hand, showing label to camera\n"
            f"anatomy: exactly one person with exactly two arms and two hands, "
            f"one hand holds product, other hand relaxed at side or not visible\n"
            f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
            f"natural skin texture with visible pores, subtle grain, not airbrushed\n"
            f"product: {desc}, featuring colors {colors}, all visible text clear and accurate\n"
            f"setting: {ctx.get('assistant', 'indoor')} environment, natural lighting\n"
            f"camera: amateur iPhone selfie, slightly uneven framing, warm tones\n"
            f"style: candid UGC look, no filters, realism, high detail, skin texture\n"
            f"text_accuracy: preserve all visible product text exactly as in reference image\n"
            f"negative: no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
            f"no extra fingers, no airbrushed skin, no studio backdrop, no geometric distortion"
        )


def build_physical_product_scenes(fields, influencer, product, durations, ctx, max_scenes=None):
    """Builds scenes for a physical product video.
    
    Args:
        max_scenes: If set, limits the number of UGC scenes generated.
                    Use max_scenes=1 when cinematic shots will fill the remaining time.
    """
    # ✨ NEW: Generate a single seed for character consistency across all scenes
    consistency_seed = random.randint(10000, 99999)

    scenes = []

    # ---------------------------------------------------------------
    # Script Source: Manual override OR AI persona-driven generation
    # ---------------------------------------------------------------
    # Priority: 1) User-provided script from job.hook  2) AI persona generation  3) Fallback
    manual_script = fields.get("Hook") or fields.get("Script") or fields.get("caption") or ""
    is_manual_script = manual_script and manual_script.strip() not in ("", "Check this out!")

    if is_manual_script:
        script = manual_script
        print(f"      [Script] Using manual/pre-generated script: {script[:60]}...")
    else:
        try:
            from ugc_backend.ai_script_client import AIScriptClient

            product_analysis = product.get("visual_description") or product.get("visual_analysis") or {}
            if isinstance(product_analysis, str):
                product_analysis = {"visual_description": product_analysis}
            if not product_analysis.get("brand_name") and product.get("name"):
                product_analysis = {**product_analysis, "brand_name": product.get("name")}

            video_duration = int(str(fields.get("Length", "15s")).replace("s", ""))
            client = AIScriptClient()
            script = client.generate_physical_product_script(
                product_analysis=product_analysis,
                duration=video_duration,
                influencer_data=influencer,
            )
            print(f"      [Script] AI persona-generated: {script[:60]}...")
        except Exception as e:
            script = manual_script or "Check this out!"
            print(f"      [Script] AI generation failed ({e}), using fallback: {script[:60]}...")
    # Use correct pronoun based on influencer gender
    poss = "his" if ctx.get("gender", "Female") == "Male" else "her"
    
    video_length = str(fields.get("Length", "15s"))

    # 2 scenes for 15s (Hook + Showcase), 3 scenes for 30s (Hook + Showcase + CTA)
    scene_descriptions = [
        "holding the product up close to the camera with an excited expression",
        f"holding the product near {poss} face, tilting it to show the label with a warm smile",
    ]
    if video_length == "30s":
        scene_descriptions.append(
            f"pointing at the product with one hand while looking directly at camera with a warm encouraging smile"
        )
    
    # Limit scene count when cinematic shots will fill the remaining time
    if max_scenes and max_scenes < len(scene_descriptions):
        scene_descriptions = scene_descriptions[:max_scenes]
        print(f"      🎬 Cinematic mode: reduced UGC scenes to {max_scenes}")
    
    # Get visual description safely
    prod_desc = product.get("visual_description", {})
    if isinstance(prod_desc, str):
        # Handle case where it might be a string (legacy)
        visual_desc_str = prod_desc
    else:
        visual_desc_str = prod_desc.get("visual_description", "the product")

    # SPLIT SCRIPT LOGIC
    # The AI script generator outputs "Part1 ||| Part2" (15s) or
    # "Part1 ||| Part2 ||| Part3" (30s) for clean pre-split dialogue.
    # Each part is timed to ~7s of speech (max ~17 words) to fit inside 8s Veo scenes.
    # NOTE: Split on ||| BEFORE sanitizing, since sanitize_dialogue strips | characters.
    import re

    num_scenes = len(scene_descriptions)

    # Single scene mode: use only the FIRST part of the script
    if num_scenes == 1:
        if "|||" in script:
            first_part = script.split("|||")[0].strip()
        else:
            sanitized = sanitize_dialogue(script)
            sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sanitized) if s.strip()]
            if len(sentences) >= 2:
                mid = len(sentences) // 2
                first_part = " ".join(sentences[:mid])
            else:
                first_part = sanitized
        script_parts = [sanitize_dialogue(first_part)]
    # Preferred: Split on ||| delimiter from AI script generator
    elif "|||" in script:
        parts = [sanitize_dialogue(p.strip()) for p in script.split("|||") if p.strip()]
        # Pad to num_scenes if fewer parts than scenes
        while len(parts) < num_scenes:
            parts.append(parts[-1] if parts else sanitize_dialogue(script))
        script_parts = parts[:num_scenes]
    else:
        # No delimiter — sanitize then distribute across scenes
        script = sanitize_dialogue(script)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]

        if len(sentences) >= num_scenes:
            chunk_size = len(sentences) // num_scenes
            script_parts = []
            for i in range(num_scenes):
                start = i * chunk_size
                end = start + chunk_size if i < num_scenes - 1 else len(sentences)
                script_parts.append(" ".join(sentences[start:end]))
        elif len(sentences) >= 2:
            mid = len(sentences) // 2
            script_parts = [" ".join(sentences[:mid]), " ".join(sentences[mid:])]
            while len(script_parts) < num_scenes:
                script_parts.append(script_parts[-1])
        else:
            clauses = [c.strip() for c in re.split(r'[,;]\s*', script) if c.strip()]
            if len(clauses) >= 2:
                mid = len(clauses) // 2
                script_parts = [", ".join(clauses[:mid]), ", ".join(clauses[mid:])]
                while len(script_parts) < num_scenes:
                    script_parts.append(script_parts[-1])
            else:
                script_parts = [script] * num_scenes

    # Generate Scenes
    for i, desc in enumerate(scene_descriptions):
        nano_banana_prompt = (
            f"action: character {desc}, maintaining eye contact with camera\n"
            f"anatomy: exactly one person with exactly two arms and two hands, "
            f"one hand holds product, other hand relaxed at side or not visible\n"
            f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
            f"natural skin texture with visible pores, not airbrushed\n"
            f"product: holding a {visual_desc_str} in one hand, show product with all visible text clear and accurate\n"
            f"setting: well-lit casual home environment, natural window light\n"
            f"camera: amateur iPhone photo, casual selfie, slightly uneven framing\n"
            f"style: candid UGC look, no filters, realism, high detail, skin texture\n"
            f"text_accuracy: preserve all visible product text exactly as in reference image\n"
            f"negative: no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
            f"no extra fingers, no airbrushed skin, no studio backdrop, no geometric distortion"
        )
        
        scene_script = script_parts[i] if i < len(script_parts) else ""
        
        # ✨ FIX: Pass the script part to the prompt builders
        if i == 0:
            visual_animation_prompt = build_scene_1_veo_prompt(ctx, scene_script, visual_desc_str)
        elif i == 1:
            visual_animation_prompt = build_scene_2_veo_prompt(ctx, scene_script, visual_desc_str)
        elif i == 2:
            visual_animation_prompt = build_scene_3_veo_prompt(ctx, scene_script, visual_desc_str)
        else:
            visual_animation_prompt = build_scene_1_veo_prompt(ctx, scene_script, visual_desc_str)
        
        scene_script = script_parts[i] if i < len(script_parts) else ""
        
        scenes.append({
            "name": f"physical_scene_{i+1}",
            "type": "physical_product_scene", # NEW TYPE
            "seed": consistency_seed, # ✨ NEW: Add the shared seed
            "nano_banana_prompt": nano_banana_prompt, # CORRECT PROMPT
            "video_animation_prompt": visual_animation_prompt, # CORRECT VISUAL PROMPT
            "reference_image_url": influencer["reference_image_url"],
            "product_image_url": product["image_url"],
            "target_duration": 8.0, # 8s Veo scene, ~7s dialogue + 1s buffer
            "subtitle_text": scene_script,
            "voice_id": influencer.get("elevenlabs_voice_id", config.VOICE_MAP.get(influencer["name"], config.VOICE_MAP["Meg"])),
        })
        
    return scenes
