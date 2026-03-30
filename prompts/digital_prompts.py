"""
Prompt builder for Digital Products (App Clips).
"""
import config
from prompts import sanitize_dialogue

def generate_ultra_prompt(scene_type, ctx, script_override=None, is_last_scene=False):
    """
    Generates a structured stringified-YAML prompt for Seedance/Veo.
    Uses the provided script verbatim as dialogue.
    Returns (prompt, script_text) tuple.
    """

    # Environment: use influencer-specific setting from ctx, fall back to reference image match
    env = ctx.get("setting", "natural environment matching the background visible in the reference image")

    if scene_type == "hook":
        script = script_override if script_override else sanitize_dialogue(ctx.get('hook', ''))
        action = (
            "character looks directly at camera with wide eyes and raised eyebrows in disbelief, "
            "transitions to a genuine smile showing teeth, places hand on chest then points at viewer, "
            "finishes with an enthusiastic thumbs up and confident nod"
        )
        emotion = "disbelief turning to excitement, high energy, genuine amazement"
    elif scene_type == "reaction":
        script = script_override if script_override else sanitize_dialogue(ctx.get('reaction_text', ctx.get('caption', 'This is amazing!')))
        action = (
            "character shakes head slightly in amazement, hand to cheek, transitions to a huge "
            "crinkly-eyed smile, both hands palms up in a can-you-believe-it gesture, "
            "then warm direct eye contact with camera"
        )
        emotion = "total amazement, joy, genuine warmth"
    else:  # cta / b-roll
        script = script_override if script_override else sanitize_dialogue(ctx.get('caption', 'Check the link in bio!'))
        action = (
            "character gives a warm encouraging smile, points to the side towards bio, "
            "friendly wave or heart gesture, direct eye contact with a wink, "
            "enthusiastic final nod"
        )
        emotion = "warm, encouraging, friendly, direct"

    speech_constraint = "speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables"
    if is_last_scene:
        speech_constraint += ", speaking pace is consistent, MUST finish speaking all words entirely 1 second before the end of the video, character remains completely silent and just smiles warmly during the final 1-2 seconds"

    prompt = (
        f"dialogue: {script}\n"
        f"action: {action}, maintains eye contact with camera throughout\n"
        f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
        f"natural skin texture with visible pores, subtle grain, not airbrushed\n"
        f"camera: amateur iPhone selfie video, arms length, slight natural handheld shake, "
        f"slightly uneven framing\n"
        f"setting: {env}, slightly blurry background, bright natural light from window\n"
        f"emotion: {emotion}\n"
        f"voice_type: clear confident pronunciation, casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone, consistent medium-fast pacing\n"
        f"style: raw authentic TikTok/Reels UGC, spontaneous not polished, "
        f"candid UGC look, realism, high detail, skin texture\n"
        f"speech_constraint: {speech_constraint}\n"
        f"negative: no airbrushed skin, no studio lighting, no ring light reflection in eyes, "
        f"no geometric distortion, no extra fingers, no word repetition, no stuttering, no repeated syllables, "
        f"no subtitles, no captions, no text overlays, no burned-in text, no on-screen text, no words rendered on screen"
    )
    return prompt, script


def build_15s(dur, app_clip, ctx):
    """Simple 2-scene structure with ultra-realistic hook."""
    scenes = []

    # Scene 1: HOOK
    prompt, script_text = generate_ultra_prompt("hook", ctx)
    scenes.append({
        "name": "hook",
        "type": "veo",
        "prompt": prompt,
        "reference_image_url": ctx["ref_image"],
        "video_url": None,
        "target_duration": dur["hook"],
        "subtitle_text": script_text,
        "voice_id": ctx["voice_id"],
        "trim_mode": "start",
    })

    # Scene 2: APP DEMO (or Fallback)
    if app_clip:
        scenes.append({
            "name": "app_demo",
            "type": "clip",
            "prompt": None,
            "reference_image_url": None,
            "video_url": app_clip["video_url"],
            "target_duration": dur["app_demo"],
            "subtitle_text": "",
            "trim_mode": "end",
        })
    else:
        # Fallback: Generic AI Lifestyle Scene if no clip provided
        prompt_b, _ = generate_ultra_prompt("b-roll", ctx)
        scenes.append({
            "name": "lifestyle_fallback",
            "type": "veo",
            "prompt": f"{prompt_b} -- close up of phone screen showing app interface",
            "reference_image_url": ctx["ref_image"],
            "video_url": None,
            "target_duration": dur["app_demo"],
            "subtitle_text": "Check out the link in bio!",
            "voice_id": ctx["voice_id"],
            "trim_mode": "start",
        })

    return scenes


def build_30s(dur, app_clip, ctx, product=None, influencer=None):
    """
    30s structure optimised for the Veo 3.1 Extend pipeline.

    All Veo scenes are placed FIRST (so they can be chained via extend),
    followed by the app clip at the end.

    When a product with first_frame_url is available, Scene 1 uses a Nano Banana
    composite (influencer holding device with app on screen) to anchor the visual.
    Subsequent scenes extend from that established visual context.

    Scene count adapts to clip duration:
      - clip <= 10s  -> 3 Veo scenes (hook + reaction + cta) + clip
      - clip > 10s   -> 2 Veo scenes (hook + reaction) + clip
      - no clip      -> 3 Veo scenes (hook + reaction + cta), no clip
    """
    from prompts import sanitize_dialogue

    scenes = []

    # Determine how many Veo scenes based on app clip duration
    clip_duration = (app_clip.get("duration") or 8) if app_clip else 0
    if not app_clip:
        num_veo_scenes = 3
    elif clip_duration <= 10:
        num_veo_scenes = 3
    else:
        num_veo_scenes = 2

    import re
    
    parts = []
    if ctx.get("hook"): parts.append(ctx["hook"])
    if ctx.get("reaction_text"): parts.append(ctx["reaction_text"])
    if ctx.get("caption"): parts.append(ctx["caption"])
    full_script = " ||| ".join(parts) if parts else "Okay you guys, I found this app and I am obsessed. You need to check it out."

    if ctx.get("scene_dialogues"):
        script_parts = ctx["scene_dialogues"]
    elif "|||" in full_script:
        parts = [sanitize_dialogue(p.strip()) for p in full_script.split("|||") if p.strip()]
        script_parts = parts[:num_veo_scenes]
    else:
        sanitized = sanitize_dialogue(full_script)
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', sanitized) if s.strip()]

        # Instead of a strict 15-word minimum that drains the script into 1 chunk,
        # we evenly divide the available sentences across num_veo_scenes.
        num_sentences = len(sentences)
        sentences_per_scene = max(1, num_sentences // num_veo_scenes)
        
        script_parts = []
        for i in range(num_veo_scenes):
            if i == num_veo_scenes - 1:
                chunk = " ".join(sentences[i * sentences_per_scene :])
            else:
                chunk = " ".join(sentences[i * sentences_per_scene : (i + 1) * sentences_per_scene])
            script_parts.append(chunk)

    brand = product.get("name", "this") if product else "this app"
    fallbacks = [
        f"Honestly, {brand} is a total game changer for me, I use it literally every single day now.",
        f"You have got to try {brand} for yourself, I promise it makes everything so much easier and faster.",
        f"I cannot stop using {brand}, it is genuinely that good, trust me you are going to love it.",
        f"Seriously, go check out {brand} right now, it is going to save you so much time and stress."
    ]
    
    # Pad if necessary
    while len(script_parts) < num_veo_scenes:
        script_parts.append(fallbacks[len(script_parts) % len(fallbacks)])

    # POST-SPLIT VALIDATION: Ensure time boundary (18-22 words ≈ 6-7s at 3 words/sec)
    MIN_WORDS = 18
    MAX_WORDS = 22
    for idx, part in enumerate(script_parts):
        word_count = len(part.split())
        if word_count < MIN_WORDS or word_count > MAX_WORDS:
            script_parts[idx] = fallbacks[idx % len(fallbacks)]

    # Check if we can use composite image for Scene 1 (digital product with first frame)
    first_frame_url = app_clip.get("first_frame_url") if app_clip else None
    use_composite = bool(product and influencer and first_frame_url)

    if use_composite:
        # Determine device type from product visual_description
        visual_desc = product.get("visual_description") or {}
        if isinstance(visual_desc, str):
            app_type = "mobile"
        else:
            app_type = visual_desc.get("app_type", "mobile").lower()
        is_mobile = "desktop" not in app_type and "web" not in app_type

        device_str = "iPhone" if is_mobile else "laptop screen"
        product_name = product.get("name") or product.get("brand_name") or "the app"
        device_action = (
            "standing naturally in front of the camera, PHYSICALLY holding an iPhone in one hand with the FRONT screen facing directly toward the camera and viewer, pointing at the phone screen with the other hand"
            if is_mobile else
            "sitting at a desk, pointing at a laptop screen facing the camera"
        )

    # --- Veo Scene 1: HOOK (always present) ---
    prompt, script_text = generate_ultra_prompt("hook", ctx, script_override=script_parts[0])

    if use_composite:
        # Scene 1 uses Nano Banana composite (influencer holding device with app)
        env = ctx.get("setting", "natural environment matching the background visible in the reference image")
        nano_banana_prompt = (
            f"action: character {device_action}, maintaining eye contact with camera\n"
            f"anatomy: exactly one person with exactly two arms and two hands, "
            f"one hand holds {device_str}, other hand points at the screen or rests naturally AT THE PERSON'S SIDE\n"
            f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
            f"natural skin texture with visible pores and subtle grain, fine lines, skin imperfections, unretouched complexion, not airbrushed\n"
            f"device: the {device_str} is PHYSICALLY held by the character, the FRONT screen faces the camera, the screen is fully visible to the viewer "
            f"showing the {product_name} app interface from the provided product image physically ON the screen of the device, "
            f"the app interface is NOT floating in mid-air, it is physically embedded in the device screen, "
            f"the viewer can clearly read and see the screen content, "
            f"the back of the phone is NOT visible, only the front glass screen faces outward\n"
            f"setting: {env}, natural lighting\n"
            f"camera: amateur UGC video, stationary POV camera, character does NOT hold the filming camera, locked off, NO camera movement, NO panning, slightly uneven framing\n"
            f"style: candid UGC look, no filters, realism, high detail, skin texture, visible pores, micro skin texture, raw unedited photo quality\n"
            f"negative: no smooth skin, no poreless skin, no beauty filter, no skin retouching, "
            f"no floating screens, no screens in mid-air, no floating app interface, no disconnected screens, "
            f"no third arm, no third hand, no extra limbs, no extra fingers, no camera panning, no scene wipe, no transitions, "
            f"no airbrushed skin, no studio backdrop, no geometric distortion, "
            f"no back of phone, no phone case visible, no rear camera lenses visible, "
            f"no phone held backwards, no screen facing away from camera, "
            f"no mutated hands, no floating limbs, no disconnected limbs, "
            f"no arm crossing screen, no unnatural arm position, no character holding the filming camera"
        )

        veo_animation_prompt = (
            f"dialogue: {script_text}\n"
            f"action: character {device_action}, slight natural body movement, "
            f"genuine excited expression, maintains eye contact with camera\n"
            f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
            f"natural skin texture with visible pores, not airbrushed\n"
            f"device: the {device_str} is PHYSICALLY held by the character, the FRONT screen faces the camera, the screen is fully visible to the viewer showing the app interface from the provided product image physically ON the screen of the device, the app interface is NOT floating in mid-air\n"
            f"camera: amateur UGC video, stationary POV camera, character does NOT hold the filming camera, locked camera, NO camera movement, NO panning\n"
            f"setting: {env}, slightly blurry background\n"
            f"emotion: genuine excitement, authentic discovery reaction\n"
            f"voice_type: casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone\n"
            f"audio: character speaks clearly and audibly\n"
            f"style: raw authentic TikTok/Reels UGC, candid, not polished\n"
            f"speech_constraint: speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush\n"
            f"negative: no airbrushed skin, no studio lighting, no camera panning, no scene wipe, no transitions, "
            f"no extra fingers, no silent video, no mutated hands, no stuttering, "
            f"no subtitles, no captions, no text overlays, no burned-in text, no on-screen text, no words rendered on screen"
        )

        scenes.append({
            "name": "digital_ugc_hook",
            "type": "physical_product_scene",
            "nano_banana_prompt": nano_banana_prompt,
            "video_animation_prompt": veo_animation_prompt,
            "reference_image_url": influencer["reference_image_url"],
            "product_image_url": first_frame_url,
            "target_duration": config.AI_CLIP_DURATION,
            "subtitle_text": script_text,
            "voice_id": ctx["voice_id"],
            "seed": ctx.get("consistency_seed"),
        })
    else:
        # Fallback: pure Veo scene (no product context available)
        scenes.append({
            "name": "hook",
            "type": "veo",
            "prompt": prompt,
            "reference_image_url": ctx["ref_image"],
            "video_url": None,
            "target_duration": config.AI_CLIP_DURATION,
            "subtitle_text": script_text,
            "voice_id": ctx["voice_id"],
            "seed": ctx.get("consistency_seed"),
            "trim_mode": "start",
        })

    # --- Veo Scene 2: REACTION (always present) ---
    is_scene_2_last = (num_veo_scenes == 2)
    prompt, script_text = generate_ultra_prompt("reaction", ctx, script_override=script_parts[1], is_last_scene=is_scene_2_last)

    if use_composite:
        # Extension scene: prompt includes device context so Veo maintains it
        env = ctx.get("setting", "natural environment matching the background visible in the reference image")
        if is_scene_2_last:
            speech_constraint = "speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speaking pace is consistent, MUST finish speaking all words entirely 1.5 seconds before the end of the video, character remains completely silent and just smiles warmly during the final 1.5 seconds"
        else:
            speech_constraint = "speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush"

        veo_prompt_with_device = (
                f"dialogue: {script_text}\n"
                f"action: character continues exactly the same pose and position as previous shot, "
                f"still holding {device_str} showing the app, natural subtle movements, maintains eye contact with camera\n"
                f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
                f"natural skin texture with visible pores\n"
                f"camera: amateur UGC video, same camera angle, stationary camera, locked off, NO panning, NO movement\n"
                f"setting: {env}, slightly blurry background\n"
                f"emotion: total amazement, joy, genuine warmth\n"
                f"voice_type: clear confident pronunciation, casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone, consistent medium pacing\n"
                f"style: raw authentic TikTok/Reels UGC, candid, not polished\n"
                f"speech_constraint: {speech_constraint}\n"
                f"negative: no airbrushed skin, no studio lighting, no camera movement, no panning, no scene wipe, no cuts, no transitions, no extra fingers, no stuttering, no extra limbs, "
                f"no subtitles, no captions, no text overlays, no burned-in text, no on-screen text, no words rendered on screen"
            )
        scenes.append({
            "name": "reaction",
            "type": "veo",
            "prompt": veo_prompt_with_device,
            "video_animation_prompt": veo_prompt_with_device,
            "reference_image_url": ctx["ref_image"],
            "video_url": None,
            "target_duration": config.AI_CLIP_DURATION,
            "subtitle_text": script_text,
            "voice_id": ctx["voice_id"],
            "seed": ctx.get("consistency_seed"),
            "trim_mode": "start",
        })
    else:
        scenes.append({
            "name": "reaction",
            "type": "veo",
            "prompt": prompt,
            "reference_image_url": ctx["ref_image"],
            "video_url": None,
            "target_duration": config.AI_CLIP_DURATION,
            "subtitle_text": script_text,
            "voice_id": ctx["voice_id"],
            "seed": ctx.get("consistency_seed"),
            "trim_mode": "start",
        })

    # --- Veo Scene 3: CTA (only when 3 Veo scenes) ---
    if num_veo_scenes >= 3:
        prompt, script_text = generate_ultra_prompt("cta", ctx, script_override=script_parts[2], is_last_scene=True)

        if use_composite:
            env = ctx.get("setting", "natural environment matching the background visible in the reference image")
            speech_constraint_3 = "speak ONLY the exact dialogue words provided without alterations, crystal-clear pronunciation, absolutely no stuttering, zero auditory hallucinations, no duplicate syllables, speaking pace is consistent, MUST finish speaking all words entirely 1.5 seconds before the end of the video, character remains completely silent and just smiles warmly during the final 1.5 seconds"
            
            veo_prompt_with_device = (
                f"dialogue: {script_text}\n"
                f"action: character continues exactly the same pose and position as previous shot, "
                f"still holding {device_str} showing the app, gentle smile, maintains eye contact with camera\n"
                f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
                f"natural skin texture with visible pores\n"
                f"camera: amateur UGC video, same camera angle, stationary camera, locked off, NO panning, NO movement\n"
                f"setting: {env}, slightly blurry background\n"
                f"emotion: warm, encouraging, friendly, direct\n"
                f"voice_type: clear confident pronunciation, casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone, consistent medium pacing\n"
                f"style: raw authentic TikTok/Reels UGC, candid, not polished\n"
                f"speech_constraint: {speech_constraint_3}\n"
                f"negative: no airbrushed skin, no studio lighting, no camera movement, no panning, no scene wipe, no cuts, no transitions, no extra fingers, no stuttering, no extra limbs, "
                f"no subtitles, no captions, no text overlays, no burned-in text, no on-screen text, no words rendered on screen"
            )
            scenes.append({
                "name": "cta",
                "type": "veo",
                "prompt": veo_prompt_with_device,
                "video_animation_prompt": veo_prompt_with_device,
                "reference_image_url": ctx["ref_image"],
                "video_url": None,
                "target_duration": config.AI_CLIP_DURATION,
                "subtitle_text": script_text,
                "voice_id": ctx["voice_id"],
                "seed": ctx.get("consistency_seed"),
                "trim_mode": "start",
            })
        else:
            scenes.append({
                "name": "cta",
                "type": "veo",
                "prompt": prompt,
                "reference_image_url": ctx["ref_image"],
                "video_url": None,
                "target_duration": config.AI_CLIP_DURATION,
                "subtitle_text": script_text,
                "voice_id": ctx["voice_id"],
                "seed": ctx.get("consistency_seed"),
                "trim_mode": "start",
            })

    # --- Last Scene: APP DEMO clip (or fallback) ---
    if app_clip:
        scenes.append({
            "name": "app_demo",
            "type": "clip",
            "prompt": None,
            "reference_image_url": None,
            "video_url": app_clip["video_url"],
            "target_duration": app_clip.get("duration", dur.get("app_demo", 8)),
            "subtitle_text": "",
            "trim_mode": "end",
        })
    else:
        # Fallback: Generic AI Lifestyle Scene if no clip provided
        prompt_b, _ = generate_ultra_prompt("b-roll", ctx)
        scenes.append({
            "name": "lifestyle_fallback",
            "type": "veo",
            "prompt": f"{prompt_b} -- close up of phone screen showing app interface",
            "reference_image_url": ctx["ref_image"],
            "video_url": None,
            "target_duration": dur.get("app_demo", 8),
            "subtitle_text": "Check out the link in bio!",
            "voice_id": ctx["voice_id"],
            "seed": ctx.get("consistency_seed"),
            "trim_mode": "start",
        })

    return scenes


def build_digital_unified(influencer: dict, product: dict, app_clip: dict, duration: int, ctx: dict) -> list:
    """
    NEW: Builds the 2-scene digital product pipeline.

    Scene 1: Nano Banana Pro + Veo 3.1 — Influencer holding device with app's
             first frame composited onto the screen.
    Scene 2: App Clip — The actual screen recording.

    The first_frame_url from the app clip is used as the product_image_url
    for Nano Banana Pro, ensuring the device screen in Scene 1 exactly matches
    the beginning of the app clip in Scene 2.

    Args:
        influencer: Influencer dict with reference_image_url, name, etc.
        product:    Product dict with name, visual_description, website_url.
        app_clip:   App clip dict with video_url, first_frame_url.
        duration:   Target video duration in seconds (15 or 30).
        ctx:        Context dict from scene_builder.build_scenes.

    Returns:
        List of 2 scene dicts.
    """
    import config
    from prompts import sanitize_dialogue

    # Determine device type from visual_description
    visual_desc = product.get("visual_description") or {}
    app_type = visual_desc.get("app_type", "mobile").lower()
    is_mobile = "desktop" not in app_type and "web" not in app_type

    device_str = "iPhone" if is_mobile else "laptop screen"
    device_action = (
        "standing naturally in front of the camera, holding an iPhone in one hand with the FRONT screen facing directly toward the camera and viewer, "
        "pointing at the phone screen with the other hand"
        if is_mobile else
        "sitting at a desk, pointing at a laptop screen facing the camera"
    )

    # Get the script — use product's generated script or fallback
    script = ctx.get("hook", "")
    part1, part2 = "", ""

    if "|||" in script:
        parts = [sanitize_dialogue(p.strip()) for p in script.split("|||") if p.strip()]
        part1 = parts[0] if len(parts) > 0 else ""
        part2 = parts[1] if len(parts) > 1 else ""
    elif script:
        part1 = sanitize_dialogue(script)
        part2 = "Link in my bio, seriously check it out."
    else:
        product_name = product.get("name", "this app")
        part1 = f"Okay you guys, I found this app called {product_name} and I am obsessed."
        part2 = "Link is in my bio, you need to try it."

    # Scene 1: Nano Banana + Veo (Influencer with device)
    # The first_frame_url is used as the product image composited onto the device screen
    product_name = product.get("name") or product.get("brand_name") or "the app"
    first_frame_url = app_clip.get("first_frame_url") or app_clip.get("video_url")

    nano_banana_prompt = (
        f"action: character {device_action}, maintaining eye contact with camera\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"one hand holds {device_str}, other hand points at the screen or rests naturally AT THE PERSON'S SIDE\n"
        f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
        f"natural skin texture with visible pores and subtle grain, fine lines, skin imperfections, unretouched complexion, not airbrushed\n"
        f"device: the {device_str} FRONT screen faces the camera, the screen is fully visible to the viewer "
        f"showing the {product_name} app interface from the provided product image, "
        f"the viewer can clearly read and see the screen content, "
        f"the back of the phone is NOT visible, only the front glass screen faces outward\n"
        f"setting: {ctx.get('setting', 'natural environment matching the background visible in the reference image')}, natural lighting\n"
        f"camera: amateur UGC video, stationary POV camera, character does NOT hold the filming camera, slightly uneven framing\n"
        f"style: candid UGC look, no filters, realism, high detail, skin texture, visible pores, micro skin texture, raw unedited photo quality\n"
        f"negative: no smooth skin, no poreless skin, no beauty filter, no skin retouching, "
        f"no third arm, no third hand, no extra limbs, no extra fingers, "
        f"no airbrushed skin, no studio backdrop, no geometric distortion, "
        f"no back of phone, no phone case visible, no rear camera lenses visible, "
        f"no phone held backwards, no screen facing away from camera, "
        f"no mutated hands, no floating limbs, no disconnected limbs, "
        f"no arm crossing screen, no unnatural arm position, no character holding the filming camera"
    )

    veo_animation_prompt = (
        f"dialogue: {part1}\n"
        f"action: character {device_action}, slight natural body movement, "
        f"genuine excited expression, maintains eye contact with camera\n"
        f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
        f"natural skin texture with visible pores, not airbrushed\n"
        f"camera: amateur UGC video, stationary POV camera, character does NOT hold the filming camera, slight natural handheld shake\n"
        f"setting: {ctx.get('setting', 'natural environment matching the background visible in the reference image')}, slightly blurry background\n"
        f"emotion: genuine excitement, authentic discovery reaction\n"
        f"voice_type: casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone\n"
        f"audio: character speaks clearly and audibly, voice must be present in the generated video\n"
        f"style: raw authentic TikTok/Reels UGC, candid, not polished\n"
        f"speech_constraint: speak ONLY the exact dialogue words provided, do not add or improvise any words, never repeat or stutter any word, each word must be spoken exactly once, speak at a relaxed unhurried natural pace filling the full duration of the video, do not rush\n"
        f"negative: no airbrushed skin, no studio lighting, no geometric distortion, no extra fingers, "
        f"no silent video, no muted audio, no word repetition, no stuttering, no repeated syllables, "
        f"no subtitles, no captions, no text overlays, no burned-in text, no on-screen text, no words rendered on screen"
    )

    scene_1 = {
        "name": "digital_ugc",
        "type": "physical_product_scene",  # Reuses the Nano Banana + Veo pipeline
        "nano_banana_prompt": nano_banana_prompt,
        "video_animation_prompt": veo_animation_prompt,
        "reference_image_url": influencer["reference_image_url"],
        "product_image_url": first_frame_url,  # App's first frame on the device screen
        "target_duration": 8.0,
        "subtitle_text": part1,
        "voice_id": ctx.get("voice_id", ""),
        "seed": ctx.get("consistency_seed", 0),
    }

    # Scene 2: App Clip (raw screen recording)
    scene_2 = {
        "name": "app_clip",
        "type": "clip",
        "prompt": None,
        "reference_image_url": None,
        "video_url": app_clip["video_url"],
        "target_duration": 7.0,
        "subtitle_text": part2,  # CTA subtitle overlay during the app clip
        "trim_mode": "start",
    }

    return [scene_1, scene_2]


# ---------------------------------------------------------------------------
# Dynamic Influencer Variation — Setting Prompt Generator
# ---------------------------------------------------------------------------

def generate_variation_prompt(influencer_name: str, default_setting: str) -> str | None:
    """Generate a unique one-line environment/setting description for campaign diversity.

    Uses gpt-4.1-mini to create a fresh, plausible UGC environment that differs
    from the influencer's default setting.  Returns None on any error so the
    caller can safely fall back to the default.

    Args:
        influencer_name: Name of the influencer (for context).
        default_setting: The influencer's default ``setting`` field value.

    Returns:
        A single-line setting string, or None if generation fails.
    """
    import os
    try:
        from openai import OpenAI
    except ImportError:
        print("[variation] openai package not installed — skipping variation")
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("[variation] OPENAI_API_KEY not set — skipping variation")
        return None

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            max_tokens=60,
            temperature=1.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate SHORT one-line UGC video environment descriptions. "
                        "Output ONLY the setting description — no quotes, no prefix, no explanation. "
                        "Examples: 'cozy bedroom with fairy lights and a messy bed', "
                        "'bright modern kitchen with white countertops', "
                        "'sunny park bench under a large oak tree'."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Create a new, unique UGC video setting for influencer '{influencer_name}'. "
                        f"It must be DIFFERENT from: '{default_setting}'. "
                        f"Output one line only."
                    ),
                },
            ],
        )
        result = resp.choices[0].message.content.strip().strip("\"'")
        if result and len(result) > 5:
            print(f"[variation] Generated setting: {result}")
            return result
        return None
    except Exception as e:
        print(f"[variation] GPT call failed: {e}")
        return None
