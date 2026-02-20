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


def build_scenes(content_row, influencer, app_clip, app_clip_2=None, product=None, product_type="digital"):
    """
    Build the scene structure from a Content Calendar row.

    Args:
        content_row: dict with fields from Content Calendar
        influencer: dict from airtable_client.get_influencer()
        app_clip: dict from airtable_client.get_app_clip()
        app_clip_2: unused (kept for API compat)
        product: dict from products table (optional, for physical flow)
        product_type: "digital" or "physical"

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
    caption = content_row.get("Caption", "Link in bio!")

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

    if product_type == "physical" and product:
        ctx["product"] = product
        return _build_physical_product_scenes(content_row, influencer, product, durations, ctx)
    elif length == "30s":
        return _build_30s(durations, app_clip, ctx)
    else:
        return _build_15s(durations, app_clip, ctx)


def _generate_nano_banana_prompt(influencer_name: str, product_description: str, scene_description: str) -> str:
    """
    Generates a simple, descriptive prompt for Nano Banana Pro image composition.
    """
    prompt = (
        f"A realistic, high-quality photo of a female influencer named {influencer_name} {scene_description}. "
        f"She is holding a {product_description}. "
        f"The style is a natural, authentic, UGC-style selfie shot in a well-lit, casual environment. "
        f"The influencer is looking directly at the camera with a positive expression. "
        f"Ensure the product is clearly visible and held naturally."
    )
    return prompt


def _build_scene_1_veo_prompt(ctx, script_part):
    """Scene 1: Holding product up close to camera - WITH SCRIPT INTEGRATION"""
    return (
        # VISUAL DESCRIPTION
        f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "
        f"CRITICAL: The person's identity, facial features, skin tone, hair, and body remain COMPLETELY IDENTICAL and CONSISTENT throughout the ENTIRE video from the first frame to the last frame. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The person is holding exactly one product bottle in their right hand, positioned at chest level between their face and the camera. "
        f"The product label is facing the camera and clearly visible. "
        f"Their left hand is relaxed at their side or near their shoulder. "
        f"The shot shows exactly two arms and exactly two hands. "
        f"Both hands are anatomically correct with five fingers each. "
        f"There is exactly one product bottle in the scene. "
        f"The product is held firmly in the person's right hand throughout the entire video. "
        f"The product does not float, duplicate, merge, or change position unnaturally. "
        f"All objects obey gravity. No objects are floating in mid-air. "
        f"Natural hand-product interaction with realistic grip. "
        f"The person is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
        
        # DIALOGUE REPLACEMENT
        f"- **Speaking**: The person is speaking enthusiastically to the camera, with natural mouth movements.\n"
        
        # CONSTRAINTS
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"The person remains THE SAME INDIVIDUAL with NO CHANGES to their face, identity, or appearance at any point in the video. "
        
        # NEGATIVE PROMPT
        f"NEGATIVE PROMPT: "
        f"extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements, "
        f"character morphing, face morphing, different person, facial feature changes, identity switching, "
        f"person changing, character inconsistency, multiple people, appearance changes, face changes, "
        f"different face, changing identity, morphing person, switching characters."
    )


def _build_scene_2_veo_prompt(ctx, script_part):
    """Scene 2: Demonstrating product texture on hand - WITH SCRIPT INTEGRATION"""
    return (
        # VISUAL DESCRIPTION
        f"A realistic, high-quality, authentic UGC video selfie of THE EXACT SAME PERSON from the reference image. "
        f"CRITICAL: The person's identity, facial features, skin tone, hair, and body remain COMPLETELY IDENTICAL and CONSISTENT throughout the ENTIRE video from the first frame to the last frame. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The person is holding exactly one product bottle in their left hand at chest level. "
        f"They are using their right hand to apply product from the bottle, demonstrating the texture. "
        f"Their right hand shows a small amount of product (cream/conditioner) on the palm or fingers. "
        f"Both hands are clearly visible in the frame throughout the scene. "
        f"The shot shows exactly two arms and exactly two hands. "
        f"Both hands are anatomically correct with five fingers each. "
        f"There is exactly one product bottle in the scene. "
        f"The product is held firmly in their left hand throughout the entire video. "
        f"The product does not float, duplicate, merge, or change position unnaturally. "
        f"All objects obey gravity. No objects are floating in mid-air. "
        f"Natural hand-product interaction with realistic grip and texture demonstration. "
        f"The person is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
        
        # DIALOGUE REPLACEMENT
        f"- **Speaking**: The person is speaking enthusiastically to the camera, with natural mouth movements.\n"
        
        # CONSTRAINTS
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"The person remains THE SAME INDIVIDUAL with NO CHANGES to their face, identity, or appearance at any point in the video. "
        
        # NEGATIVE PROMPT
        f"NEGATIVE PROMPT: "
        f"extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, "
        f"floating objects, objects in mid-air, duplicate products, multiple bottles, extra products, "
        f"merged objects, product duplication, disembodied hands, blurry, low quality, unrealistic, "
        f"artificial, CGI-looking, unnatural movements, product floating, hands not holding product, "
        f"character morphing, face morphing, different person, facial feature changes, identity switching, "
        f"person changing, character inconsistency, multiple people, appearance changes, face changes, "
        f"different face, changing identity, morphing person, switching characters."
    )


def _build_physical_product_scenes(fields, influencer, product, durations, ctx):
    """Builds scenes for a physical product video."""
    # ✨ NEW: Generate a single seed for character consistency across all scenes
    consistency_seed = random.randint(1, 1000000)

    scenes = []
    # ✨ FIX: Check multiple possible keys for the script, not just "Hook"
    # The AI script generator might return "Script", "caption", or "Hook"
    script = fields.get("Hook") or fields.get("Script") or fields.get("caption") or "Check this out!"
    
    # 2 scenes for a 15s video (Hook + Showcase)
    scene_descriptions = [
        "holding the product up close to the camera with an excited expression",
        "demonstrating the product's texture on her hand", 
    ]
    
    # Get visual description safely
    prod_desc = product.get("visual_description", {})
    if isinstance(prod_desc, str):
        # Handle case where it might be a string (legacy)
        visual_desc_str = prod_desc
    else:
        visual_desc_str = prod_desc.get("visual_description", "the product")

    # SPLIT SCRIPT LOGIC
    # Split the script into 2 parts for the 2 scenes
    # Simple split by sentence or half words
    import re
    sentences = re.split(r'(?<=[.!?])\s+', script)
    if len(sentences) < 2:
        # If only 1 sentence, split by words
        words = script.split()
        mid = len(words) // 2
        part1 = " ".join(words[:mid])
        part2 = " ".join(words[mid:])
    else:
        mid = len(sentences) // 2
        part1 = " ".join(sentences[:mid])
        part2 = " ".join(sentences[mid:])
        
    script_parts = [part1, part2]

    # Generate Scenes
    for i, desc in enumerate(scene_descriptions):
        # ✨ FIX: Create a new, stronger prompt that explicitly references the input image
        nano_banana_prompt = (
            f"A realistic, high-quality UGC-style photo using the exact person from the reference image. "
            f"The person is {desc}. "
            f"They are holding a {visual_desc_str}. "
            f"The style is a natural, authentic selfie shot in a well-lit, casual environment. "
            f"The influencer is looking directly at the camera with a positive, {ctx['energy'].lower()} expression. "
            f"IMPORTANT: Use the exact same person from the reference image, maintaining their facial features, skin tone, and appearance. Do not change the person."
        )
        
        scene_script = script_parts[i] if i < len(script_parts) else ""
        
        # ✨ FIX: Pass the script part to the prompt builders
        if i == 0:
            visual_animation_prompt = _build_scene_1_veo_prompt(ctx, scene_script)
        elif i == 1:
            visual_animation_prompt = _build_scene_2_veo_prompt(ctx, scene_script)
        else:
            # Fallback for any additional scenes
            visual_animation_prompt = _build_scene_1_veo_prompt(ctx, scene_script)
        
        scene_script = script_parts[i] if i < len(script_parts) else ""
        
        scenes.append({
            "name": f"physical_scene_{i+1}",
            "type": "physical_product_scene", # NEW TYPE
            "seed": consistency_seed, # ✨ NEW: Add the shared seed
            "nano_banana_prompt": nano_banana_prompt, # CORRECT PROMPT
            "video_animation_prompt": visual_animation_prompt, # CORRECT VISUAL PROMPT
            "reference_image_url": influencer["reference_image_url"],
            "product_image_url": product["image_url"],
            "target_duration": 7.5, # Split 15s evenly
            "subtitle_text": scene_script,
            "voice_id": influencer.get("elevenlabs_voice_id", config.VOICE_MAP.get(influencer["name"], config.VOICE_MAP["Meg"])),
        })
        
    return scenes


def _generate_physical_image_prompt(ctx, close_up=False):
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
    
    # Construct prompt
    if close_up:
         return (
            f"A high-quality close-up macro shot of {brand}, described as {desc}. "
            f"The product features colors like {colors}. "
            f"Placed on a clean, modern surface with aesthetic lighting. Professional product photography."
        )
    else:
        return (
            f"A realistic, casual, handheld smartphone selfie of a {ctx['age']} {ctx['visuals']} {ctx['gender'].lower()} influencer, "
            f"smiling openly while looking at the camera. {ctx['p']['subj']} is holding a {brand} ({desc}) "
            f"to the camera. The product features colors like {colors}. "
            f"The setting is {ctx.get('assistant', 'indoor')} with natural lighting. "
            f"The style should be very casual and candid, unposed, with an authentic expression."
        )


# ---------------------------------------------------------------------------
# Ultra Realistic Prompt Generator
# ---------------------------------------------------------------------------

def _generate_ultra_prompt(scene_type, ctx):
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
        # ✨ FIX: Remove person-identifying information
        f"An authentic, high-energy, handheld smartphone selfie video. THE EXACT SAME PERSON from the reference image is excitedly sharing an amazing discovery.\n\n"
        
        f"## 2. Visual Style\n"
        f"- **Camera**: Close-up shot, arm's length, slight arm movement and natural handheld shake.\n"
        f"- **Lighting**: Bright natural light from a window, creating a sparkle in {p['poss'].lower()} eyes.\n"
        f"- **Environment**: {env}. Slightly blurry background.\n"
        f"- **Aesthetic**: Raw, genuine TikTok/Reels style. Spontaneous, not polished.\n\n"
        
        f"## 3. Performance - Visual\n"
        # ✨ FIX: Remove person's name
        f"- **Eye Contact**: CRITICAL: The person MUST maintain direct eye contact with the lens throughout.\n"
        f"**Expressions**:\n{expressions}\n"
        f"- **Body**: Leans INTO the camera for emphasis. Highly animated.\n"
        f"**Gestures**:\n{gestures}\n\n"
        
        f"## 4. Performance - Action\n"
        f"- **Speaking**: The person is speaking enthusiastically to the camera, with natural mouth movements and facial animation.\n\n"
        
        f"## 5. Technical Specifications\n"
        f"Vertical 9:16, handheld (fixed_lens: false)."
    )
    return prompt, script

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
        prompt_b, _ = _generate_ultra_prompt("b-roll", ctx)
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
        prompt_b, _ = _generate_ultra_prompt("b-roll", ctx)
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
