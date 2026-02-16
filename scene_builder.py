"""
Naiara Content Distribution Engine — Scene Builder

Takes a Content Calendar row + influencer data and builds scene structures
with AI video prompts. Default model: Seedance 1.5 Pro (native lip-sync + Spanish).
All AI clips use the FULL 8 seconds — no trimming.

Length selector:
  15s → 2 scenes: Hook (8s AI) + App Demo (7s clip) = $0.38
  30s → 4 scenes: Hook + App Demo + Reaction + CTA = $0.94
"""
import random
import config


def build_scenes(content_row, influencer, app_clip, app_clip_2=None):
    """
    Build the scene structure from a Content Calendar row.

    Args:
        content_row: dict with fields from Content Calendar
        influencer: dict from airtable_client.get_influencer()
        app_clip: dict from airtable_client.get_app_clip()
        app_clip_2: unused (kept for API compat)

    Returns:
        List of scene dicts
    """
    length = content_row.get("Length", "15s")
    if length not in config.VALID_LENGTHS:
        length = "15s"

    durations = config.get_scene_durations(length)

    hook = content_row.get("Hook", "Check this out!")
    assistant = content_row.get("AI Assistant", "Travel")
    theme = content_row.get("Theme", "")
    caption = content_row.get("Caption", "Download Naiara now!")

    person_name = influencer.get("name", "Sofia")
    age = influencer.get("age", "25-year-old")
    gender = influencer.get("gender", "Female")
    visuals = influencer.get("visual_description", "casual style")
    personality = influencer.get("personality", "friendly influencer")
    energy = influencer.get("energy_level", "High")
    accent = influencer.get("accent", "Castilian Spanish (Spain)")
    tone = influencer.get("tone", "Enthusiastic")
    # Voice ID for ElevenLabs
    voice_id = influencer.get("elevenlabs_voice_id", config.VOICE_MAP.get(person_name, config.VOICE_MAP["Meg"]))
    ref_image = influencer["reference_image_url"]

    # Pronoun mapping
    p = {
        "subj": "He" if gender == "Male" else "She",
        "poss": "His" if gender == "Male" else "Her",
        "obj": "him" if gender == "Male" else "her",
    }

    # Context context for builder
    ctx = {
        "name": person_name,
        "age": age,
        "gender": gender,
        "visuals": visuals,
        "personality": personality,
        "energy": energy,
        "accent": accent,
        "tone": tone,
        "voice_id": voice_id,
        "p": p,
        "ref_image": ref_image,
        "assistant": assistant,
        "hook": hook,
        "caption": caption
    }

    if length == "30s":
        return _build_30s(durations, app_clip, ctx)
    else:
        return _build_15s(durations, app_clip, ctx)


def _generate_ultra_prompt(scene_type, ctx):
    """
    Generates a 6-section 'Performance Director' prompt for Seedance.
    """
    p = ctx['p']
    
    # Environment based on Assistant
    env_map = {
        "Travel": "cozy bedroom with a bookshelf and a travel map on the wall",
        "Shop": "modern living room with a shopping bag and clothes visible in the background",
        "Fitness": "bright home gym setting with a yoga mat and weights",
    }
    env = env_map.get(ctx['assistant'], "cozy, lived-in apartment")

    # Script construction (Colloquial Spanish)
    if scene_type == "hook":
        interjections = ["¡Eh, ESCUCHA!", "¡Tío, PARA TODO!", "¡No te lo vas a creer!", "¡Madre mía!"]
        # Use simple hash of hook for determinism
        idx = sum(ord(c) for c in ctx['hook']) % len(interjections)
        interjection = interjections[idx]
        script = f"{interjection} {ctx['hook']}. ¡Es BRUTAL! Tienes que probarla."
        expressions = "- [0-2s]: Opens with wide eyes and raised eyebrows in disbelief.\n- [2-5s]: Transitions to a huge, genuine smile showing teeth.\n- [5-8s]: Confident nod and knowing smirk."
        gestures = "- [1s]: Places hand on chest in disbelief.\n- [4s]: Points directly at the viewer.\n- [7s]: Gives an enthusiastic thumbs up."
    elif scene_type == "reaction":
        reaction_text = _get_colloquial_reaction(ctx['assistant'])
        script = f"¡O sea, FLIPANTE! {reaction_text}. De verdad, me ha cambiado la vida."
        expressions = "- [0-3s]: Look of total amazement, shaking head slightly.\n- [3-6s]: Huge crinkly-eyed smile of joy.\n- [6-8s]: Genuine, warm eye contact."
        gestures = "- [2s]: Hand to cheek in amazement.\n- [5s]: Both hands palms up in a 'can you believe it?' gesture."
    else: # cta
        cta_base = ctx['caption'].split('.')[0] if ctx['caption'] else "Descarga Naiara"
        script = f"En serio, no te lo pienses. {cta_base}. ¡Descárgala YA, el link está en mi bio!"
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
        f"- **Language**: Natural, colloquial {ctx['accent']} (informal 'tú').\n"
        f"- **Tone**: EXCITED and AMAZED. Rising pitch on capitalized words.\n"
        f"- **Pacing**: Fast start, dramatic micro-pauses, punchy ending.\n"
        f"- **Colloquialisms**: 'o sea', 'brutal', 'flipante', 'uff', 'serio'.\n\n"
        f"## 5. Script\n"
        f"\"{script}\"\n\n"
        f"## 6. Technical Specifications\n"
        f"Vertical 9:16, handheld (fixed_lens: false), audio enabled."
    )
    return prompt, script


def _get_colloquial_reaction(assistant):
    reactions = {
        "Travel": "¡Me ha organizado TODO el viaje en SEGUNDOS! O sea, vuelos... hoteles... ¡brutal!",
        "Shop": "¡Me ha encontrado unos precios que son una LOCURA! De verdad, flipante.",
        "Fitness": "¡El plan es INCREÍBLE! Se adapta a lo que necesito, en plan, perfecto.",
    }
    return reactions.get(assistant, "¡Esta app es una PASADA! De verdad, me encanta.")


# ---------------------------------------------------------------------------
# 15-second version: Hook (8s AI) + App Demo (7s clip)
# ---------------------------------------------------------------------------

def _build_15s(dur, app_clip, ctx):
    """Simple 2-scene structure with ultra-realistic hook."""
    scenes = []

    # Scene 1: HOOK
    prompt, script_text = _generate_ultra_prompt("hook", ctx)
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

    # Scene 2: APP DEMO
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

    return scenes


# ---------------------------------------------------------------------------
# 30-second version: Hook + App Demo + Reaction + CTA (all 8s)
# ---------------------------------------------------------------------------

def _build_30s(dur, app_clip, ctx):
    """Full 4-scene structure with ultra-realistic performance logic."""
    scenes = []

    # Scene 1: HOOK
    prompt, script_text = _generate_ultra_prompt("hook", ctx)
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

    # Scene 2: APP DEMO
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

    # Scene 3: REACTION
    prompt, script_text = _generate_ultra_prompt("reaction", ctx)
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
    prompt, script_text = _generate_ultra_prompt("cta", ctx)
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


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def _get_reaction(assistant):
    reactions = {
        "Travel": "¡Me organizó todo el itinerario en segundos! Vuelos, hoteles, restaurantes — todo.",
        "Cooking": "¡Me dio la receta perfecta con lo que tenía en la nevera! No tuve que pensar nada.",
        "Fitness": "¡El plan de entrenamiento es justo lo que necesitaba! Se adapta a mi nivel cada semana.",
    }
    return reactions.get(assistant, "¡Esta app es increíble, la uso todos los días!")


def _build_cta(caption):
    if caption and len(caption) > 10:
        first = caption.split(".")[0].strip()
        if len(first) < 100:
            return first + ". ¡Descárgala ya, link en mi bio!"
    return "¡En serio, descarga Naiara ya! Link en mi bio."


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------

def print_scene_summary(scenes, length="15s"):
    total = sum(s["target_duration"] for s in scenes)
    ai_count = sum(1 for s in scenes if s["type"] == "veo")
    clip_cost = 0.28  # Seedance default
    cost = ai_count * clip_cost + 0.10

    print(f"\n🎬 Video Structure — {length} (~{total}s total, {len(scenes)} scenes):")
    print("=" * 60)

    for i, scene in enumerate(scenes, 1):
        icon = "🎥" if scene["type"] == "veo" else "📱"
        print(f"\n  {icon} Scene {i}: {scene['name'].upper()} ({scene['target_duration']}s)")
        print(f"     Type: {scene['type']}")
        if scene["prompt"]:
            print(f"     Prompt: {scene['prompt']}")
        if scene["video_url"]:
            print(f"     Clip: {scene['video_url'][:60]}...")
        if scene["subtitle_text"]:
            print(f"     Subtitle: \"{scene['subtitle_text']}\"")

    print(f"\n{'=' * 60}")
    print(f"  💰 Estimated cost: {ai_count} × ${clip_cost:.2f} = ${ai_count * clip_cost:.2f}")
    print(f"     + music: $0.10 (optional)")
    print(f"     = Total: ~${cost:.2f}")

# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        hook = "This app just planned my entire trip in 30 seconds"
        assistant = "Travel"
        inf_name = "Sofia"
        length = "15s"

        for i, arg in enumerate(sys.argv):
            if arg == "--test" and i + 1 < len(sys.argv):
                hook = sys.argv[i + 1]
            if arg == "--assistant" and i + 1 < len(sys.argv):
                assistant = sys.argv[i + 1]
            if arg == "--influencer" and i + 1 < len(sys.argv):
                inf_name = sys.argv[i + 1]
            if arg == "--length" and i + 1 < len(sys.argv):
                length = sys.argv[i + 1]

        mock_content = {
            "Hook": hook,
            "AI Assistant": assistant,
            "Theme": "beach vacation planning",
            "Caption": "Naiara is the AI travel assistant you didn't know you needed",
            "Length": length,
        }
        mock_inf = {
            "name": inf_name,
            "description": "A young woman in her mid-20s with brown hair, wearing a casual white t-shirt",
            "reference_image_url": "https://example.com/sofia_ref.jpg",
            "gender": "Female",
            "accent": "Castilian Spanish (Spain)",
            "tone": "Enthusiastic"
        }
        mock_clip = {
            "name": "Travel assistant demo",
            "video_url": "https://example.com/travel_demo.mp4",
            "duration": 8,
        }

        scenes = build_scenes(mock_content, mock_inf, mock_clip)
        print_scene_summary(scenes, length)
    else:
        print('Usage: python scene_builder.py --test "Your hook" --length 30s')
