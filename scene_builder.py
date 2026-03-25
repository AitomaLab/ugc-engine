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
from prompts import digital_prompts, physical_prompts
from ugc_db.db_manager import get_product_shot
def _extract_visual_appearance(influencer: dict) -> str:
    """Extract only the visual/physical appearance from the influencer data.
    
    The full influencer 'description' can be hundreds of words (personality,
    voice style, target audience, style guide, etc.). Veo 3.1 Extend has a
    prompt length limit and rejects oversized prompts with a 400 error.
    
    This function extracts just the physical appearance info (build, hair,
    skin, clothing) — typically 1-2 sentences, ~100-200 chars.
    """
    # Prefer a dedicated short visual description if available
    short_desc = influencer.get("visual_description", "")
    if short_desc and len(short_desc) < 300:
        return short_desc
    
    full_desc = influencer.get("description", "")
    if not full_desc:
        return "casual style"
    
    # If the description is already short, use it as-is
    if len(full_desc) < 300:
        return full_desc
    
    # Extract from the "Style Guide:" section which contains physical appearance
    import re
    
    # Try to find the Style Guide section
    style_match = re.search(r'Style Guide[:\s]*(.*?)(?:\n\n|\Z)', full_desc, re.DOTALL | re.IGNORECASE)
    if style_match:
        style_text = style_match.group(1).strip()
        # Extract sentences about physical appearance (build, hair, skin, clothing)
        appearance_keywords = ['build', 'hair', 'skin', 'height', 'complexion', 'wear', 
                              'clothing', 'shirt', 'dress', 'stocky', 'athletic', 'slender',
                              'blonde', 'brunette', 'stubble', 'jawline', 'muscular',
                              'ponytail', 'coily', 'fade']
        sentences = re.split(r'(?<=[.!])\s+', style_text)
        appearance_sentences = []
        for sent in sentences:
            if any(kw in sent.lower() for kw in appearance_keywords):
                appearance_sentences.append(sent.strip())
        if appearance_sentences:
            result = ' '.join(appearance_sentences)
            # Cap at ~250 chars
            if len(result) > 250:
                result = result[:247] + '...'
            return result
    
    # Fallback: extract just the Summary section (first paragraph)
    summary_match = re.search(r'Summary[:\s]*(.*?)(?:\n\n|\Z)', full_desc, re.DOTALL | re.IGNORECASE)
    if summary_match:
        summary = summary_match.group(1).strip()
        # Take first sentence only
        first_sent = summary.split('.')[0] + '.'
        if len(first_sent) > 250:
            first_sent = first_sent[:247] + '...'
        return first_sent
    
    # Last resort: take first 200 chars of description
    return full_desc[:200].rsplit(' ', 1)[0] + '...'




def build_scenes(content_row, influencer, app_clip, app_clip_2=None, product=None, product_type="digital", script_json=None):
    """
    Build the scene structure from a Content Calendar row.

    NEW: If product_type == 'digital' AND a product dict is provided AND
    the app_clip has a first_frame_url, uses the new unified 2-scene digital
    pipeline (build_digital_unified). Falls back to the original logic otherwise.

    script_json (optional): When provided, scene dialogues are extracted from
    this structured object instead of splitting content_row["Hook"] on |||.
    All existing callers pass no script_json, so they hit the unchanged path.
    """
    length = content_row.get("Length", "15s")
    if length not in config.VALID_LENGTHS:
        length = "15s"

    durations = config.get_scene_durations(length)

    hook = content_row.get("Hook") or content_row.get("Script") or content_row.get("caption") or "Check this out!"
    assistant = content_row.get("AI Assistant", "Travel")
    theme = content_row.get("Theme", "")
    caption = content_row.get("Caption", "Link in bio!")

    person_name = influencer.get("name", "Sofia")
    age = influencer.get("age", "25-year-old")
    gender = influencer.get("gender", "Female")
    visuals = _extract_visual_appearance(influencer)
    personality = influencer.get("personality") or "friendly influencer"
    energy = influencer.get("energy_level", "High")
    accent = influencer.get("accent", "Castilian Spanish (Spain)")
    tone = influencer.get("tone", "Enthusiastic")
    voice_id = influencer.get("elevenlabs_voice_id", config.VOICE_MAP.get(person_name, config.VOICE_MAP["Meg"]))
    ref_image = influencer["reference_image_url"]
    # Influencer-specific background/environment -- falls back to reference-image matching
    setting = (influencer.get("setting") or "").strip()

    p = {
        "subj": "He" if gender == "Male" else "She",
        "poss": "His" if gender == "Male" else "Her",
        "obj": "him" if gender == "Male" else "her",
    }

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
        "caption": caption,
        "consistency_seed": random.randint(10000, 99999),
        "setting": setting or "natural environment matching the background visible in the reference image",
    }

    # Dynamic Influencer Variation: override setting if a variation_prompt was
    # generated for this job (70% of bulk digital campaigns). The original
    # setting is preserved as the fallback for the remaining 30%.
    if influencer.get("variation_prompt"):
        ctx["setting"] = influencer["variation_prompt"]
        print(f"      [SCENE] Variation setting override: {ctx['setting']}")


    # -----------------------------------------------------------------------
    # NEW: If a structured script_json object is provided, extract scene
    # dialogues from it and populate ctx fields directly. This bypasses the
    # ||| split logic below while keeping all downstream consumers working.
    # -----------------------------------------------------------------------
    if script_json and script_json.get("scenes"):
        scenes_data = script_json["scenes"]
        dialogues = [s.get("dialogue", "") for s in scenes_data]
        # Populate the standard ctx keys from the structured data
        if len(dialogues) >= 1:
            ctx["hook"] = dialogues[0]
        if len(dialogues) >= 2:
            ctx["reaction_text"] = dialogues[1]
        if len(dialogues) >= 3:
            ctx["caption"] = dialogues[2]
        # Store full scene dialogues list for consumers that need it
        ctx["scene_dialogues"] = dialogues
        # Also set the legacy hook field to ||| string for any downstream
        # consumer that might still split on it (belt and suspenders)
        from ugc_backend.ai_script_client import AIScriptClient
        content_row["Hook"] = AIScriptClient.script_json_to_legacy(script_json)
        hook = content_row["Hook"]
        print(f"      [scene_builder] Using script_json ({len(dialogues)} scenes)")

    # -----------------------------------------------------------------------
    # LEGACY: For 30s videos, split the ||| -delimited script into separate
    # ctx keys so generate_ultra_prompt picks up the correct dialogue:
    #   hook scene  -> ctx['hook']
    #   reaction    -> ctx['reaction_text']
    #   cta         -> ctx['caption']
    # Skipped when script_json was already processed above.
    # -----------------------------------------------------------------------
    elif length == "30s" and "|||" in hook:
        parts = [p.strip() for p in hook.split("|||") if p.strip()]
        if len(parts) >= 3:
            ctx["hook"] = parts[0]
            ctx["reaction_text"] = parts[1]
            ctx["caption"] = parts[2]
        elif len(parts) == 2:
            ctx["hook"] = parts[0]
            ctx["reaction_text"] = parts[1]

    # -----------------------------------------------------------------------
    # NEW: Digital Product Unified Pipeline (15s ONLY)
    # Triggered when: product_type is digital AND a product dict is provided
    # AND the app_clip has a first_frame_url AND length is 15s.
    # 30s digital videos use build_30s which produces multiple Veo scenes
    # for the Extend pipeline (seamless chaining via Veo 3.1 Extend API).
    # -----------------------------------------------------------------------
    if (
        product_type == "digital"
        and product is not None
        and app_clip is not None
        and app_clip.get("first_frame_url")
        and length == "15s"
    ):
        print(f"      [SCENE] Using unified digital pipeline (15s) for product: {product.get('name')}")
        return digital_prompts.build_digital_unified(
            influencer=influencer,
            product=product,
            app_clip=app_clip,
            duration=int(length.replace("s", "")),
            ctx=ctx,
        )

    # -----------------------------------------------------------------------
    # Physical Product Pipeline (UNCHANGED)
    # -----------------------------------------------------------------------
    cinematic_shot_ids = content_row.get("cinematic_shot_ids") or []
    cinematic_scenes = []
    if product_type == "physical" and cinematic_shot_ids:
        for shot_id in cinematic_shot_ids:
            shot = get_product_shot(shot_id)
            if shot and shot.get("video_url"):
                scene_data = {
                    "name": f"cinematic_{shot['shot_type']}",
                    "type": "cinematic_shot",
                    "video_url": shot["video_url"],
                    "target_duration": 4.0,
                    "subtitle_text": "",
                }
                if shot.get("transition_type"):
                    scene_data["transition_type"] = shot["transition_type"]
                cinematic_scenes.append(scene_data)

    if product_type == "physical" and product:
        ctx["product"] = product
        if cinematic_scenes:
            if length == "30s":
                # 30s: preserve >= 2 UGC scenes for extend pipeline activation
                max_ugc_scenes = max(2, 3 - len(cinematic_scenes))
            else:
                # 15s: original formula (2 total scene slots)
                max_ugc_scenes = max(1, 2 - len(cinematic_scenes))
        else:
            max_ugc_scenes = None
        influencer_scenes = physical_prompts.build_physical_product_scenes(
            content_row, influencer, product, durations, ctx,
            max_scenes=max_ugc_scenes
        )

        if not cinematic_scenes:
            return influencer_scenes

        if length == "30s":
            # 30s: all UGC scenes first (enables extend pipeline), cinematics appended
            return influencer_scenes + cinematic_scenes
        else:
            # 15s: interleave for visual variety
            final_scenes = []
            inf_idx, cin_idx = 0, 0
            while inf_idx < len(influencer_scenes) or cin_idx < len(cinematic_scenes):
                if inf_idx < len(influencer_scenes):
                    final_scenes.append(influencer_scenes[inf_idx])
                    inf_idx += 1
                if cin_idx < len(cinematic_scenes):
                    final_scenes.append(cinematic_scenes[cin_idx])
                    cin_idx += 1
            return final_scenes

    # -----------------------------------------------------------------------
    # Digital Pipeline — 30s uses Extend-optimised build_30s,
    # 15s uses basic 2-scene build_15s.
    # -----------------------------------------------------------------------
    elif length == "30s":
        print(f"      [SCENE] Using 30s Extend pipeline (build_30s) — {len(config.get_scene_durations(length))} scene slots")
        return digital_prompts.build_30s(durations, app_clip, ctx, product=product, influencer=influencer)
    else:
        return digital_prompts.build_15s(durations, app_clip, ctx)


# (Extracted prompt logic to prompts/digital_prompts.py and prompts/physical_prompts.py)


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
