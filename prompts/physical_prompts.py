"""
Prompt builder for Physical Products (Cosmetics, Bottles).
"""
import random
import config


def build_scene_1_veo_prompt(ctx, script_part):
    """Scene 1: Holding product up close to camera."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    energy_str = ctx.get('energy', 'High').lower()
    
    return (
        f"A realistic, high-quality, authentic UGC video selfie of a {age_str} {visuals_str} {gender_str} influencer. "
        f"Upper body shot from chest up, filmed in a well-lit, casual home environment. "
        f"The influencer is holding exactly one product bottle in her right hand, positioned at chest level between her face and the camera. "
        f"The product label is facing the camera and clearly visible. "
        f"Her left hand is relaxed at her side or near her shoulder. "
        f"The shot shows exactly two arms and exactly two hands. "
        f"Both hands are anatomically correct with five fingers each. "
        f"There is exactly one product bottle in the scene. "
        f"The product is held firmly in the influencer's right hand throughout the entire video. "
        f"The product does not float, duplicate, merge, or change position unnaturally. "
        f"All objects obey gravity. No objects are floating in mid-air. "
        f"Natural hand-product interaction with realistic grip. "
        f"The influencer is looking directly at the camera with a positive, {energy_str} expression. "
        f"Natural, authentic UGC-style movements. Professional quality with realistic human proportions. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, third hand, deformed hands, mutated hands, "
        f"anatomical errors, multiple arms, distorted body, unnatural proportions, floating objects, objects in mid-air, "
        f"duplicate products, multiple bottles, extra products, merged objects, product duplication, disembodied hands, "
        f"blurry, low quality, unrealistic, artificial, CGI-looking, unnatural movements."
    )


def build_scene_2_veo_prompt(ctx, script_part):
    """Scene 2: Demonstrating product texture on hand."""
    age_str = ctx.get('age', '25-year-old')
    visuals_str = ctx.get('visuals', 'casual style')
    gender_str = ctx.get('gender', 'Female').lower()
    name_str = ctx.get('name', 'Meg')
    energy_str = ctx.get('energy', 'High').lower()

    return (
        f"A realistic, high-quality, cinematic video of a {age_str} {visuals_str} {gender_str} influencer named {name_str}. "
        f"The scene shows the upper body from the chest up. She is demonstrating the product's texture on her hand. "
        f"The shot must be anatomically correct with exactly two arms and two hands visible. "
        f"The style is a natural, authentic, UGC-style shot in a well-lit, casual environment. "
        f"The influencer is looking directly at the camera with a positive, {energy_str} expression. "
        f"Ensure the product is clearly visible and held naturally. High-fidelity, professional quality with realistic human proportions. "
        f"NEGATIVE PROMPT: extra limbs, extra hands, extra fingers, deformed hands, mutated hands, anatomical errors, "
        f"multiple arms, distorted body, unnatural proportions, blurry, low quality."
    )


def generate_nano_banana_prompt(influencer_name: str, product_description: str, scene_description: str) -> str:
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


def build_physical_product_scenes(fields, influencer, product, durations, ctx):
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
            "target_duration": 7.5, # Split 15s evenly
            "subtitle_text": scene_script,
            "voice_id": influencer.get("elevenlabs_voice_id", config.VOICE_MAP.get(influencer["name"], config.VOICE_MAP["Meg"])),
        })
        
    return scenes
