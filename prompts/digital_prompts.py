"""
Prompt builder for Digital Products (App Clips).
"""
import config

def generate_ultra_prompt(scene_type, ctx):
    """
    Generates a 6-section 'Performance Director' prompt for Seedance/Veo.
    Uses the user's script text verbatim — no wrapping in hard-coded filler.
    """
    p = ctx['p']
    
    # Environment based on Assistant
    env_map = {
        "Travel": "cozy bedroom with a bookshelf and a travel map on the wall",
        "Shop": "modern living room with a shopping bag and clothes visible in the background",
        "Fitness": "bright home gym setting with a yoga mat and weights",
    }
    env = env_map.get(ctx['assistant'], "cozy, lived-in apartment")

    # Use the user's script text directly — no hard-coded Spanish wrapping
    if scene_type == "hook":
        script = ctx['hook']
        expressions = "- [0-2s]: Opens with wide eyes and raised eyebrows in disbelief.\n- [2-5s]: Transitions to a huge, genuine smile showing teeth.\n- [5-8s]: Confident nod and knowing smirk."
        gestures = "- [1s]: Places hand on chest in disbelief.\n- [4s]: Points directly at the viewer.\n- [7s]: Gives an enthusiastic thumbs up."
    elif scene_type == "reaction":
        script = ctx.get('reaction_text', ctx.get('caption', 'This is amazing!'))
        expressions = "- [0-3s]: Look of total amazement, shaking head slightly.\n- [3-6s]: Huge crinkly-eyed smile of joy.\n- [6-8s]: Genuine, warm eye contact."
        gestures = "- [2s]: Hand to cheek in amazement.\n- [5s]: Both hands palms up in a 'can you believe it?' gesture."
    else: # cta / b-roll
        script = ctx.get('caption', 'Check the link in bio!')
        expressions = "- [0-3s]: Warm, encouraging smile.\n- [3-6s]: Direct, friendly eye contact with a wink.\n- [6-8s]: Enthusiastic final nod."
        gestures = "- [2s]: Points to the side (towards 'bio').\n- [5s]: Friendly wave or heart gesture."

    prompt = (
        f"## 1. Core Concept\n"
        f"An authentic, high-energy, handheld smartphone selfie video. {ctx['name']}, a {ctx['age']} {ctx['gender'].lower()} with {ctx['visuals']}, is excitedly sharing an amazing discovery.\n\n"
        
        f"## 2. Visual Style\n"
        f"- **Camera**: Close-up shot, arm's length, slight arm movement and natural handheld shake.\n"
        f"- **Lighting**: Bright natural light from a window, creating a sparkle in {p['poss'].lower()} eyes.\n"
        f"- **Environment**: {env}. Slightly blurry background.\n"
        f"- **Aesthetic**: Raw, genuine TikTok/Reels style. Spontaneous, not polished.\n\n"
        
        f"## 3. Performance - Visual\n"
        f"- **Eye Contact**: CRITICAL: {ctx['name']} MUST maintain direct eye contact with the lens throughout.\n"
        f"**Expressions**:\n{expressions}\n"
        f"- **Body**: Leans INTO the camera for emphasis. Highly animated.\n"
        f"**Gestures**:\n{gestures}\n\n"
        
        f"## 4. Performance - Vocal\n"
        f"- **Language**: Natural, conversational {ctx['accent']}.\n"
        f"- **Tone**: {ctx['tone']}. Rising pitch on emphasized words.\n"
        f"- **Pacing**: Fast start, dramatic micro-pauses, punchy ending.\n\n"
        
        f"## 5. Script\n"
        f"\"{script}\"\n\n"
        
        f"## 6. Technical Specifications\n"
        f"Vertical 9:16, handheld (fixed_lens: false), audio enabled."
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
