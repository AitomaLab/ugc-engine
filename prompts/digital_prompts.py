"""
Prompt builder for Digital Products (App Clips).
"""
import config
from prompts import sanitize_dialogue

def generate_ultra_prompt(scene_type, ctx):
    """
    Generates a structured stringified-YAML prompt for Seedance/Veo.
    Uses the user's script text verbatim as dialogue.
    Returns (prompt, script_text) tuple.

    SAFETY BUFFER: All script text is capped at 17 words (approx 7s of speech)
    to ensure dialogue finishes 1 second before the 8s scene ends.
    """
    MAX_WORDS = 17

    def _cap_words(text, max_words=MAX_WORDS):
        """Truncate text to max_words words at a sentence boundary if possible."""
        words = text.split()
        if len(words) <= max_words:
            return text
        truncated = " ".join(words[:max_words])
        if not truncated.endswith((".", "!", "?")):
            truncated = truncated.rstrip(",;") + "."
        return truncated

    # Environment based on Assistant
    env_map = {
        "Travel": "cozy bedroom with a bookshelf and a travel map on the wall",
        "Shop": "modern living room with a shopping bag and clothes visible in the background",
        "Fitness": "bright home gym setting with a yoga mat and weights",
    }
    env = env_map.get(ctx['assistant'], "cozy, lived-in apartment")

    if scene_type == "hook":
        script = _cap_words(sanitize_dialogue(ctx['hook']))
        action = (
            "character looks directly at camera with wide eyes and raised eyebrows in disbelief, "
            "transitions to a genuine smile showing teeth, places hand on chest then points at viewer, "
            "finishes with an enthusiastic thumbs up and confident nod"
        )
        emotion = "disbelief turning to excitement, high energy, genuine amazement"
    elif scene_type == "reaction":
        script = _cap_words(sanitize_dialogue(ctx.get('reaction_text', ctx.get('caption', 'This is amazing!'))))
        action = (
            "character shakes head slightly in amazement, hand to cheek, transitions to a huge "
            "crinkly-eyed smile, both hands palms up in a can-you-believe-it gesture, "
            "then warm direct eye contact with camera"
        )
        emotion = "total amazement, joy, genuine warmth"
    else:  # cta / b-roll
        script = _cap_words(sanitize_dialogue(ctx.get('caption', 'Check the link in bio!')))
        action = (
            "character gives a warm encouraging smile, points to the side towards bio, "
            "friendly wave or heart gesture, direct eye contact with a wink, "
            "enthusiastic final nod"
        )
        emotion = "warm, encouraging, friendly, direct"

    prompt = (
        f"dialogue: {script}\n"
        f"action: {action}, maintains eye contact with camera throughout\n"
        f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
        f"natural skin texture with visible pores, subtle grain, not airbrushed\n"
        f"camera: amateur iPhone selfie video, arms length, slight natural handheld shake, "
        f"slightly uneven framing\n"
        f"setting: {env}, slightly blurry background, bright natural light from window\n"
        f"emotion: {emotion}\n"
        f"voice_type: casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone, "
        f"fast start with dramatic micro-pauses\n"
        f"style: raw authentic TikTok/Reels UGC, spontaneous not polished, "
        f"candid UGC look, realism, high detail, skin texture\n"
        f"speech_constraint: speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"negative: no airbrushed skin, no studio lighting, no ring light reflection in eyes, "
        f"no geometric distortion, no extra fingers"
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


def build_30s(dur, app_clip, ctx):
    """Full 4-scene structure with ultra-realistic performance logic."""
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

    # Scene 3: REACTION
    prompt, script_text = generate_ultra_prompt("reaction", ctx)
    scenes.append({
        "name": "reaction",
        "type": "veo",
        "prompt": prompt,
        "reference_image_url": ctx["ref_image"],
        "video_url": None,
        "target_duration": dur["reaction"],
        "subtitle_text": script_text,
        "voice_id": ctx["voice_id"],
        "trim_mode": "start",
    })

    # Scene 4: CTA
    prompt, script_text = generate_ultra_prompt("cta", ctx)
    scenes.append({
        "name": "cta",
        "type": "veo",
        "prompt": prompt,
        "reference_image_url": ctx["ref_image"],
        "video_url": None,
        "target_duration": dur["cta"],
        "subtitle_text": script_text,
        "voice_id": ctx["voice_id"],
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
        "holding an iPhone up to the camera, screen facing viewer, pointing at the screen with one finger"
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
    first_frame_url = app_clip.get("first_frame_url") or app_clip.get("video_url")

    nano_banana_prompt = (
        f"action: character {device_action}, maintaining eye contact with camera\n"
        f"anatomy: exactly one person with exactly two arms and two hands, "
        f"one hand holds {device_str}, other hand points at screen or rests naturally\n"
        f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
        f"natural skin texture with visible pores, not airbrushed\n"
        f"device: {device_str} with a clearly visible app interface on screen, "
        f"screen content matches the provided product image exactly\n"
        f"setting: well-lit casual home environment, natural window light\n"
        f"camera: amateur iPhone selfie, slightly uneven framing, warm tones\n"
        f"style: candid UGC look, no filters, realism, high detail, skin texture\n"
        f"negative: no third arm, no third hand, no extra limbs, no extra fingers, "
        f"no airbrushed skin, no studio backdrop, no geometric distortion"
    )

    veo_animation_prompt = (
        f"dialogue: {part1}\n"
        f"action: character {device_action}, slight natural body movement, "
        f"genuine excited expression, maintains eye contact with camera\n"
        f"character: {ctx['age']} {ctx['gender'].lower()}, {ctx['visuals']}, "
        f"natural skin texture with visible pores, not airbrushed\n"
        f"camera: amateur iPhone selfie video, arms length, slight natural handheld shake\n"
        f"setting: cozy home environment, natural window light, slightly blurry background\n"
        f"emotion: genuine excitement, authentic discovery reaction\n"
        f"voice_type: casual, conversational {ctx['accent']}, {ctx['tone'].lower()} tone\n"
        f"style: raw authentic TikTok/Reels UGC, candid, not polished\n"
        f"speech_constraint: speak ONLY the exact dialogue words provided, do not add or improvise any words\n"
        f"negative: no airbrushed skin, no studio lighting, no geometric distortion, no extra fingers"
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
