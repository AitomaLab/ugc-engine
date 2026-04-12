"""
Prompt builder for Physical Products (Cosmetics, Bottles).
"""
import random
import config
from prompts import sanitize_dialogue


def build_scene_1_veo_prompt(ctx, script_part, product_desc="product", is_last_scene=False):
    """Scene 1: Holding product up close to camera. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()
    setting_str = ctx.get('setting', 'natural environment matching the background visible in the reference image')
    # i18n: override accent for Spanish videos
    video_language = ctx.get('video_language', 'en')
    if video_language == 'es':
        accent_str = 'native Spanish accent, speaking entirely in Spanish'

    dialogue = sanitize_dialogue(script_part) if script_part else "oh my god you guys have to see this"

    return (
        f"dialogue: {dialogue}\n"
        f"action: person holds product at chest level showing it to camera, excited expression, eye contact\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores and fine details, realistic imperfections\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
        f"setting: {setting_str}, natural lighting\n"
        f"emotion: {energy_str}, genuine excitement\n"
        f"voice_type: clear confident pronunciation, casual, {tone_str}, conversational {accent_str}, consistent medium-fast pacing\n"
        f"style: raw UGC, candid, not polished\n"
        f"speech_constraint: {'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speaking pace is consistent, MUST finish speaking all words entirely 1 second before the end of the video, character remains completely silent and just smiles warmly during the final 1-2 seconds' if is_last_scene else 'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush'}\n"
        f"negative: no auditory hallucinations, no filler words, no repeated words, no stuttering, no repeated syllables, no extra limbs, no smooth skin, no poreless skin, no beauty filter, no airbrushed skin, no extra fingers, no mutated hands"
    )


def build_scene_2_veo_prompt(ctx, script_part, product_desc="product", is_last_scene=False):
    """Scene 2 (30s Benefits): Tilting product to show details. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()
    setting_str = ctx.get('setting', 'natural environment matching the background visible in the reference image')
    video_language = ctx.get('video_language', 'en')
    if video_language == 'es':
        accent_str = 'native Spanish accent, speaking entirely in Spanish'

    dialogue = sanitize_dialogue(script_part) if script_part else "the quality on this is honestly insane"

    return (
        f"dialogue: {dialogue}\n"
        f"action: person continues exactly the same pose and position as previous shot, still holding product at the exact same height and angle as Scene 1, product remains fully visible throughout, slight nod, maintains eye contact\n"
        f"product: person is holding the exact same {product_desc} product as in the reference image, product appearance must not change\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores and fine details, realistic imperfections\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
        f"setting: {setting_str}, natural lighting\n"
        f"emotion: {energy_str}, genuine excitement\n"
        f"voice_type: clear confident pronunciation, casual, {tone_str}, conversational {accent_str}, consistent medium-fast pacing\n"
        f"style: raw UGC, candid, not polished\n"
        f"speech_constraint: {'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speaking pace is consistent, MUST finish speaking all words entirely 1 second before the end of the video, character remains completely silent and just smiles warmly during the final 1-2 seconds' if is_last_scene else 'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush'}\n"
        f"negative: no auditory hallucinations, no filler words, no repeated words, no stuttering, no repeated syllables, no extra limbs, no product disappearing, no change in product position, no dropping the product, no smooth skin, no poreless skin, no beauty filter, no airbrushed skin, no extra fingers, no mutated hands"
    )


def build_scene_3_veo_prompt(ctx, script_part, product_desc="product", is_last_scene=False):
    """Scene 3 (30s Reaction): Holding product near face, genuine amazement. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()
    setting_str = ctx.get('setting', 'natural environment matching the background visible in the reference image')
    video_language = ctx.get('video_language', 'en')
    if video_language == 'es':
        accent_str = 'native Spanish accent, speaking entirely in Spanish'

    dialogue = sanitize_dialogue(script_part) if script_part else "and the texture is seriously so good"

    return (
        f"dialogue: {dialogue}\n"
        f"action: person continues exactly the same pose and position as previous shot, still holding product at the exact same height and angle as Scene 1, product remains fully visible throughout, gentle smile and nod while speaking\n"
        f"product: person is holding the exact same {product_desc} product as in the reference image, product appearance must not change\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores and fine details, realistic imperfections\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
        f"setting: {setting_str}, natural lighting\n"
        f"emotion: {energy_str}, genuine excitement\n"
        f"voice_type: clear confident pronunciation, casual, {tone_str}, conversational {accent_str}, consistent medium-fast pacing\n"
        f"style: raw UGC, candid, not polished\n"
        f"speech_constraint: {'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speaking pace is consistent, MUST finish speaking all words entirely 1 second before the end of the video, character remains completely silent and just smiles warmly during the final 1-2 seconds' if is_last_scene else 'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush'}\n"
        f"negative: no auditory hallucinations, no filler words, no repeated words, no stuttering, no repeated syllables, no extra limbs, no product disappearing, no change in product position, no dropping the product, no smooth skin, no poreless skin, no beauty filter, no airbrushed skin, no extra fingers, no mutated hands"
    )


def build_scene_4_veo_prompt(ctx, script_part, product_desc="product", is_last_scene=False):
    """Scene 4 (30s CTA): Pointing at product, warm call-to-action. Stringified YAML for Veo 3.1."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    accent_str = ctx.get('accent', 'neutral English')
    tone_str = ctx.get('tone', 'Enthusiastic').lower()
    setting_str = ctx.get('setting', 'natural environment matching the background visible in the reference image')
    video_language = ctx.get('video_language', 'en')
    if video_language == 'es':
        accent_str = 'native Spanish accent, speaking entirely in Spanish'

    dialogue = sanitize_dialogue(script_part) if script_part else "seriously you need to try this, link in my bio"

    return (
        f"dialogue: {dialogue}\n"
        f"action: person continues exactly the same pose and position as previous shot, still holding product at the exact same height and angle as Scene 1, product remains fully visible throughout, warm encouraging expression\n"
        f"product: person is holding the exact same {product_desc} product as in the reference image, product appearance must not change\n"
        f"character: {age_str} {gender_str}, {visuals_str}, natural skin texture with visible pores and fine details, realistic imperfections\n"
        f"camera: amateur iPhone selfie video, slightly uneven framing, handheld\n"
        f"setting: {setting_str}, natural lighting\n"
        f"emotion: warm, encouraging, genuine recommendation\n"
        f"voice_type: clear confident pronunciation, casual, {tone_str}, conversational {accent_str}, consistent medium-fast pacing\n"
        f"style: raw UGC, candid, not polished\n"
        f"speech_constraint: {'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speaking pace is consistent, MUST finish speaking all words entirely 1 second before the end of the video, character remains completely silent and just smiles warmly during the final 1-2 seconds' if is_last_scene else 'speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush'}\n"
        f"negative: no auditory hallucinations, no filler words, no repeated words, no stuttering, no repeated syllables, no extra limbs, no product disappearing, no change in product position, no dropping the product, no smooth skin, no poreless skin, no beauty filter, no airbrushed skin, no extra fingers, no mutated hands"
    )



def generate_nano_banana_prompt(influencer_name: str, product_description: str, scene_description: str) -> str:
    """
    Generates a structured prompt for Nano Banana Pro image composition.
    Note: influencer_name kept for signature compat but not used in prompt text.
    """
    return (
        f"a single person {scene_description}, "
        f"casually presenting a {product_description}, "
        f"candid iPhone selfie, natural skin texture, UGC style, "
        f"all product text clearly readable, "
        f"natural environment with warm lighting, slightly blurry background\n"
        f"negative: deformed, disfigured, blurry, watermark, text overlay"
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
            f"anatomy: exactly one person with exactly two arms and two hands, accurate hands with realistic proportions, "
            f"one hand holds product, other hand relaxed at side or not visible\n"
            f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
            f"natural skin texture with visible pores, subtle grain, not airbrushed, natural highlight roll-off on skin\n"
            f"product: {desc}, featuring colors {colors}, all visible text clear and accurate, "
            f"preserve exact product proportions, do not redesign or reinterpret the product\n"
            f"setting: {ctx.get('setting', 'natural environment matching the background visible in the reference image')}, "
            f"tidy and clean with premium casual art direction\n"
            f"lighting: soft directional natural window light, subtle shadows for depth, natural highlight roll-off on skin\n"
            f"camera: iPhone 1x aesthetic, clean but slightly organic composition, naturally blurred background, slightly uneven framing\n"
            f"style: candid UGC look, no filters, realism, high detail, skin texture\n"
            f"text_accuracy: preserve all visible product text exactly as in reference image\n"
            f"negative: no third arm, no third hand, no extra limbs, no extra arms, no extra hands, "
            f"no extra fingers, no airbrushed skin, no plastic skin, no waxy skin, "
            f"no studio backdrop, no geometric distortion, "
            f"no flat lighting, no overexposed lighting, no blown highlights"
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

    # Validate manual script length for 30s videos — each scene needs ~17 words
    # Scripts like "Meet Phebus." (2 words) are way too short for 4 scenes
    video_length = str(fields.get("Length", "15s"))
    min_words_for_30s = 30  # 4 scenes × ~8 words minimum = 32, with some slack
    min_words_for_15s = 12  # 2 scenes × ~8 words minimum = 16, with some slack
    if is_manual_script:
        word_count = len(manual_script.split())
        min_words = min_words_for_30s if video_length == "30s" else min_words_for_15s
        if word_count < min_words:
            print(f"      [Script] Manual script too short ({word_count} words, need {min_words}+ for {video_length}). Forcing AI generation.")
            is_manual_script = False

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
            model_api = fields.get("model_api", "")
            video_language = fields.get("video_language", "en")
            client = AIScriptClient()
            script = client.generate_physical_product_script(
                product_analysis=product_analysis,
                duration=video_duration,
                influencer_data=influencer,
                model_api=model_api,
                video_language=video_language,
            )
            print(f"      [Script] AI persona-generated: {script[:60]}...")
        except Exception as e:
            script = manual_script or "Check this out!"
            print(f"      [Script] AI generation failed ({e}), using fallback: {script[:60]}...")
    # Use correct pronoun based on influencer gender
    poss = "his" if ctx.get("gender", "Female") == "Male" else "her"
    
    video_length = str(fields.get("Length", "15s"))

    # 2 scenes for 15s (Hook + Showcase), 4 scenes for 30s (Hook + Benefits + Reaction + CTA)
    if video_length == "30s":
        scene_descriptions = [
            "holding the product up close to the camera with an excited expression",
            f"tilting the product to show different angles while nodding with genuine satisfaction",
            f"holding the product near {poss} face, tilting it to show the label with a warm smile",
            f"pointing at the product with one hand while looking directly at camera with a warm encouraging smile",
        ]
    else:
        scene_descriptions = [
            "holding the product up close to the camera with an excited expression",
            f"holding the product near {poss} face, tilting it to show the label with a warm smile",
        ]
    
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
    # "Part1 ||| Part2 ||| Part3 ||| Part4" (30s) for clean pre-split dialogue.
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
        script_parts = parts[:num_scenes]
    else:
        # No delimiter — sanitize then distribute across scenes
        script = sanitize_dialogue(script)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', script) if s.strip()]

        # Combine sentences to reach a minimum word count per part (~12 words)
        combined_parts = []
        current_part = ""
        for s in sentences:
            if current_part:
                current_part += " " + s
            else:
                current_part = s
            if len(current_part.split()) >= 12:
                combined_parts.append(current_part)
                current_part = ""
        if current_part:
            if combined_parts:
                combined_parts[-1] += " " + current_part
            else:
                combined_parts.append(current_part)

        # Now we have parts roughly 12+ words. If we have more than num_scenes, combine the extras into the last part.
        if len(combined_parts) > num_scenes:
            extra = " ".join(combined_parts[num_scenes-1:])
            combined_parts = combined_parts[:num_scenes-1] + [extra]
            
        script_parts = combined_parts

    if num_scenes > 1:
        # Pad to num_scenes with distinct fallbacks (never duplicate the last part)
        brand = product.get("name", "this")
        _fallbacks = [
            f"You guys, I literally just discovered {brand} and honestly it is so incredible, you seriously have to see this.",
            f"The quality on {brand} is seriously next level, I was honestly not expecting this at all, it really impressed me.",
            f"I have been using {brand} nonstop lately and I am genuinely obsessed with it, my life is so much better now.",
            f"Seriously, go check out {brand} right now, the link is in my bio, I promise you will thank me later.",
        ]
        while len(script_parts) < num_scenes:
            script_parts.append(_fallbacks[len(script_parts) % len(_fallbacks)])
        
        script_parts = script_parts[:num_scenes]

        # POST-SPLIT VALIDATION: Replace any part outside word count range
        # Seedance 2.0 uses variable durations (4s/12s) → different word counts per scene
        is_seedance = "seedance" in str(fields.get("model_api", "")).lower()
        if is_seedance and video_length == "15s":
            # 15s physical: Part 1 (4s → 7-9 words), Part 2 (12s → 28-33 words)
            word_ranges = [(5, 12), (25, 38)]
        elif is_seedance and video_length == "30s":
            # 30s physical: Part 1 (4s), Part 2 (12s), Part 3 (12s), Part 4 (4s)
            word_ranges = [(5, 12), (25, 38), (25, 38), (5, 12)]
        else:
            # Veo: uniform 8s scenes → 17-23 words each
            word_ranges = [(17, 23)] * num_scenes

        for idx, part in enumerate(script_parts):
            word_count = len(part.split())
            min_w, max_w = word_ranges[idx] if idx < len(word_ranges) else (17, 23)
            if word_count < min_w:
                old_part = part
                script_parts[idx] = _fallbacks[idx % len(_fallbacks)]
                print(f"      [Script] Part {idx+1} too short ({len(old_part.split())} words, min {min_w}: '{old_part}'). Replaced with fallback.")
            elif word_count > max_w:
                old_part = part
                script_parts[idx] = _fallbacks[idx % len(_fallbacks)]
                print(f"      [Script] Part {idx+1} too long ({len(old_part.split())} words, max {max_w}). Replaced with fallback.")

    # Generate Scenes
    for i, desc in enumerate(scene_descriptions):
        nano_banana_prompt = (
            f"action: character {desc}, casually presenting the product\n"
            f"anatomy: exactly one person with exactly two arms and two hands, accurate hands with realistic proportions, "
            f"one hand explicitly holds the product, other arm rests naturally TO THE PERSON'S SIDE\n"
            f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
            f"natural skin texture with visible pores and subtle grain, fine lines, skin imperfections, unretouched complexion, not airbrushed, natural highlight roll-off on skin\n"
            f"product: the {visual_desc_str} is clearly visible, "
            f"preserve all visible text and logos exactly as in reference image, "
            f"preserve exact product proportions, do not redesign or reinterpret the product\n"
            f"setting: {ctx.get('setting', 'natural environment matching the background visible in the reference image')}, "
            f"tidy and clean with premium casual art direction\n"
            f"lighting: soft directional natural window light, subtle shadows for depth, natural highlight roll-off on skin\n"
            f"camera: iPhone 1x aesthetic, clean but slightly organic composition, naturally blurred background, slightly uneven framing\n"
            f"style: candid UGC look, no filters, realism, high detail, skin texture, visible pores, micro skin texture, raw unedited photo quality\n"
            f"negative: no smooth skin, no poreless skin, no plastic skin, no waxy skin, no beauty filter, no skin retouching, "
            f"no third arm, no third hand, no extra limbs, no extra fingers, "
            f"no airbrushed skin, no studio backdrop, no geometric distortion, "
            f"no mutated hands, no floating limbs, disconnected limbs, mutation, "
            f"no arm crossing screen, no unnatural arm position, "
            f"no flat lighting, no overexposed lighting, no blown highlights"
        )
        
        scene_script = script_parts[i] if i < len(script_parts) else ""
        
        # ✨ FIX: Pass the script part to the prompt builders
        is_last = (i == len(scene_descriptions) - 1)
        if i == 0:
            visual_animation_prompt = build_scene_1_veo_prompt(ctx, scene_script, visual_desc_str, is_last_scene=is_last)
        elif i == 1:
            visual_animation_prompt = build_scene_2_veo_prompt(ctx, scene_script, visual_desc_str, is_last_scene=is_last)
        elif i == 2:
            visual_animation_prompt = build_scene_3_veo_prompt(ctx, scene_script, visual_desc_str, is_last_scene=is_last)
        elif i == 3:
            visual_animation_prompt = build_scene_4_veo_prompt(ctx, scene_script, visual_desc_str, is_last_scene=is_last)
        else:
            visual_animation_prompt = build_scene_1_veo_prompt(ctx, scene_script, visual_desc_str, is_last_scene=is_last)
        
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
