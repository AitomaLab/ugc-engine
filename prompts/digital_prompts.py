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
    """
    # Environment based on Assistant
    env_map = {
        "Travel": "cozy bedroom with a bookshelf and a travel map on the wall",
        "Shop": "modern living room with a shopping bag and clothes visible in the background",
        "Fitness": "bright home gym setting with a yoga mat and weights",
    }
    env = env_map.get(ctx['assistant'], "cozy, lived-in apartment")

    if scene_type == "hook":
        script = sanitize_dialogue(ctx['hook'])
        action = (
            "character looks directly at camera with wide eyes and raised eyebrows in disbelief, "
            "transitions to a genuine smile showing teeth, places hand on chest then points at viewer, "
            "finishes with an enthusiastic thumbs up and confident nod"
        )
        emotion = "disbelief turning to excitement, high energy, genuine amazement"
    elif scene_type == "reaction":
        script = sanitize_dialogue(ctx.get('reaction_text', ctx.get('caption', 'This is amazing!')))
        action = (
            "character shakes head slightly in amazement, hand to cheek, transitions to a huge "
            "crinkly-eyed smile, both hands palms up in a can-you-believe-it gesture, "
            "then warm direct eye contact with camera"
        )
        emotion = "total amazement, joy, genuine warmth"
    else:  # cta / b-roll
        script = sanitize_dialogue(ctx.get('caption', 'Check the link in bio!'))
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
