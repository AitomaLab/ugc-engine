"""
Prompt builder for Physical Products (Cosmetics, Bottles).
"""
import random
import config
from prompts import sanitize_dialogue


def build_scene_1_veo_prompt(ctx, script_part):
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
        f"speech_constraint: speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"motion_constraint: character has only two arms and two hands throughout the entire video, "
        f"never show a third hand or arm, no limbs appear from outside the frame\n"
        f"negative: no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
        f"no floating hands, no hands appearing from off-screen, no duplicate body parts, "
        f"no airbrushed skin, no studio lighting, no geometric distortion"
    )


def build_scene_2_veo_prompt(ctx, script_part):
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
        f"speech_constraint: speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"motion_constraint: character has only two arms and two hands throughout the entire video, "
        f"never show a third hand or arm, no limbs appear from outside the frame\n"
        f"negative: no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
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


def build_physical_product_scenes(fields, influencer, product, durations, ctx):
    """Builds scenes for a physical product video."""
    # ✨ NEW: Generate a single seed for character consistency across all scenes
    consistency_seed = random.randint(1, 1000000)

    scenes = []
    # ✨ FIX: Check multiple possible keys for the script, not just "Hook"
    # The AI script generator might return "Script", "caption", or "Hook"
    script = fields.get("Hook") or fields.get("Script") or fields.get("caption") or "Check this out!"
    # Use correct pronoun based on influencer gender
    poss = "his" if ctx.get("gender", "Female") == "Male" else "her"
    
    # 2 scenes for a 15s video (Hook + Showcase)
    scene_descriptions = [
        "holding the product up close to the camera with an excited expression",
        f"holding the product near {poss} face, tilting it to show the label with a warm smile",
    ]
    
    # Get visual description safely
    prod_desc = product.get("visual_description", {})
    if isinstance(prod_desc, str):
        # Handle case where it might be a string (legacy)
        visual_desc_str = prod_desc
    else:
        visual_desc_str = prod_desc.get("visual_description", "the product")

    # SPLIT SCRIPT LOGIC
    # The AI script generator outputs "Part1 ||| Part2" for clean pre-split dialogue.
    # Each part is timed to ~7s of speech (max ~17 words) to fit inside 8s Veo scenes.
    # NOTE: Split on ||| BEFORE sanitizing, since sanitize_dialogue strips | characters.
    import re

    # Strategy 0 (preferred): Split on ||| delimiter from GPT-4o
    if "|||" in script:
        parts = [sanitize_dialogue(p) for p in script.split("|||") if p.strip()]
        if len(parts) >= 2:
            part1, part2 = parts[0], parts[1]
        else:
            part1 = parts[0] if parts else sanitize_dialogue(script)
            part2 = part1
    else:
        # No delimiter — sanitize then try sentence/clause splitting
        script = sanitize_dialogue(script)

        # Strategy 1: Split at sentence boundaries (. ! ?)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]
        if len(sentences) >= 2:
            mid = len(sentences) // 2
            part1 = " ".join(sentences[:mid])
            part2 = " ".join(sentences[mid:])
        else:
            # Strategy 2: Split at clause boundaries (, ;)
            clauses = [c.strip() for c in re.split(r'[,;]\s*', script) if c.strip()]
            if len(clauses) >= 2:
                mid = len(clauses) // 2
                part1 = ", ".join(clauses[:mid])
                part2 = ", ".join(clauses[mid:])
            else:
                # Strategy 3: Script is too short to split — use full script for both scenes
                part1 = script
                part2 = script

    script_parts = [part1, part2]

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
            visual_animation_prompt = build_scene_1_veo_prompt(ctx, scene_script)
        elif i == 1:
            visual_animation_prompt = build_scene_2_veo_prompt(ctx, scene_script)
        else:
            # Fallback for any additional scenes
            visual_animation_prompt = build_scene_1_veo_prompt(ctx, scene_script)
        
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
