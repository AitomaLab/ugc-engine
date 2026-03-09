"""
SEALCaM Prompt builder for Cinematic Product Shots (Still Images).
Generates structured prompts for Nano Banana Pro.

Also provides build_transition_prompt() for context-aware transition shots
that seamlessly blend with preceding UGC scenes (Workflow B).
"""

SHOT_TYPE_PROMPTS = {
    "hero": {
        "E": "a clean, minimalist studio setting with a single soft light source from the side",
        "A": "The product sits centered on a slightly reflective surface, casting a soft shadow.",
        "L": "dramatic, high-contrast studio lighting, with a key light creating sharp highlights and deep shadows, 8K, masterpiece",
        "Ca": "shot on a Sony A7S III with a 90mm macro lens, eye-level, centered composition",
    },
    "macro_detail": {
        "E": "a neutral, out-of-focus background that doesn't distract from the product texture",
        "A": "A bead of water slowly drips down the side of the product, highlighting its texture.",
        "L": "bright, clean, high-key lighting that reveals every micro-detail and texture, shot with a macro lens",
        "Ca": "extreme close-up, macro shot focusing on the texture of the product's surface, 45-degree angle",
    },
    "elevated": {
        "E": "a simple, elegant pedestal or block made of marble or stone that elevates the product",
        "A": "The product is presented on a pedestal, angled slightly to catch the light.",
        "L": "museum-quality lighting, with a spotlight from above creating a halo effect around the product",
        "Ca": "low-angle shot, looking up at the product to give it a sense of importance and scale",
    },
    "moody_dramatic": {
        "E": "a dark, textured background like slate or rough wood",
        "A": "The product emerges from the shadows, with only one side catching the light.",
        "L": "chiaroscuro lighting, with a single, harsh light source creating a dramatic interplay of light and shadow",
        "Ca": "side-on profile shot, with the camera positioned to capture the dramatic lighting effect",
    },
    "floating": {
        "E": "a zero-gravity environment with subtle, abstract light refractions in the background",
        "A": "The product floats weightlessly in the center of the frame, rotating slowly.",
        "L": "diffuse, ethereal lighting that seems to emanate from all around, eliminating harsh shadows",
        "Ca": "straight-on, eye-level shot, capturing the product as if suspended in mid-air",
    },
    "lifestyle": {
        "E": "a realistic, high-end bathroom counter with marble surfaces and other subtle, elegant props",
        "A": "The product is placed naturally amongst other bathroom items, ready for use.",
        "L": "soft, natural window light, as if from a large bathroom window in the morning",
        "Ca": "shot from a natural, slightly high angle, as if someone is about to pick it up and use it",
    },
    "silhouette": {
        "E": "a bright, glowing sunrise seen through a large window",
        "A": "The product is placed on a windowsill, its shape perfectly outlined by the light from behind.",
        "L": "strong backlighting that throws the subject entirely into shadow, creating a crisp silhouette",
        "Ca": "eye-level shot, directly facing the light source with the product as the central dark shape",
    },
    "overhead": {
        "E": "a clean, single-color surface like a marble countertop or a wooden table",
        "A": "The product is laid flat in the center of the frame, with other small, related items arranged neatly around it (a flat lay composition).",
        "L": "bright, even, shadowless lighting from directly above, creating a clean, graphic look",
        "Ca": "90-degree overhead shot, camera pointing straight down (top-down perspective)",
    },
}


def build_sealcam_prompt(shot_type: str, product: dict) -> str:
    """Builds a SEALCaM prompt for a given shot type and product."""
    if shot_type not in SHOT_TYPE_PROMPTS:
        raise ValueError(f"Invalid shot_type: {shot_type}. Valid types: {list(SHOT_TYPE_PROMPTS.keys())}")

    prompt_data = SHOT_TYPE_PROMPTS[shot_type]
    va = product.get("visual_description") or {}
    if isinstance(va, str):
        product_desc = va
    else:
        product_desc = va.get("visual_description", product.get("name", "the product"))

    # SEALCaM Framework
    S = f"A cinematic product hero shot of {product_desc}."
    E = prompt_data["E"]
    A = prompt_data["A"]
    L = prompt_data["L"]
    Ca = prompt_data["Ca"]
    M = "photorealistic, hyper-detailed, 8K, octane render, trending on ArtStation, professional product photography"

    # Stringified YAML format
    return (
        f"S: {S}\n"
        f"E: {E}\n"
        f"A: {A}\n"
        f"L: {L}\n"
        f"Ca: {Ca}\n"
        f"M: {M}"
    )


# ---------------------------------------------------------------------------
# Workflow B: Context-Aware Transition Prompt Builder
# ---------------------------------------------------------------------------

# Environment presets for the "Target Style" UI control
TARGET_STYLE_ENVIRONMENTS = {
    "studio_white": "a clean, bright, all-white studio environment",
    "natural_setting": "a realistic, natural outdoor setting with soft sunlight",
    "moody": "a dark, atmospheric environment with dramatic shadows",
}

# Camera angle mapping from analysis values to prompt fragments
_CAMERA_ANGLE_MAP = {
    "eye_level": "eye-level, straight-on composition",
    "low_angle": "low-angle shot, looking slightly upward",
    "high_angle": "slightly elevated angle, looking down at the product",
}

# Framing style mapping from analysis values to prompt fragments
_FRAMING_MAP = {
    "close_up": "close-up",
    "medium_shot": "medium shot",
    "wide_shot": "wide shot",
}


def build_transition_prompt(
    product: dict,
    analysis: dict,
    transition_type: str,
    target_style: str = None,
) -> tuple:
    """
    Builds context-aware image and animation prompts for a transition shot,
    using the visual analysis of the preceding UGC scene's final frame.

    Args:
        product: Product dict with 'name' and/or 'visual_description'.
        analysis: Output from analyze_ugc_frame() with keys:
            product_framing_style, camera_angle, lighting_description.
        transition_type: One of 'match_cut', 'whip_pan', 'focus_pull'.
        target_style: Optional target environment style key.

    Returns:
        (image_prompt, animation_prompt) tuple of strings.
    """
    # Extract product description (same logic as build_sealcam_prompt)
    va = product.get("visual_description") or {}
    if isinstance(va, str):
        product_desc = va
    else:
        product_desc = va.get("visual_description", product.get("name", "the product"))

    # Extract analysis fields with safe defaults
    framing = analysis.get("product_framing_style", "medium_shot")
    camera_angle = analysis.get("camera_angle", "eye_level")
    lighting = analysis.get("lighting_description", "soft natural light")

    # Derive Ca and L from analysis to match the UGC scene's visual context
    ca_from_analysis = _CAMERA_ANGLE_MAP.get(camera_angle, "eye-level, centered composition")
    framing_label = _FRAMING_MAP.get(framing, "medium shot")

    # Select environment based on target_style or default
    if target_style and target_style in TARGET_STYLE_ENVIRONMENTS:
        environment = TARGET_STYLE_ENVIRONMENTS[target_style]
    else:
        environment = "a clean, minimalist studio setting"

    # Build SEALCaM image prompt with context-aware Ca and L
    S = f"A cinematic product shot of {product_desc}."
    M = "photorealistic, hyper-detailed, 8K, octane render, professional product photography"

    if transition_type == "match_cut":
        E = environment
        A = "The product sits centered, presented cleanly and prominently."
        L = f"{lighting}, maintaining consistent color temperature and direction"
        Ca = f"{ca_from_analysis}, matching the preceding scene's perspective"

        animation_prompt = (
            f"Animate a seamless, continuous dolly-in, starting from a {framing_label} "
            f"of the product and ending on an extreme close-up, maintaining the {lighting}."
        )

    elif transition_type == "whip_pan":
        E = environment
        A = "The product appears sharply in frame after a fast motion blur clears."
        L = "bright, clean studio lighting with soft highlights"
        Ca = "eye-level, centered composition, as if the camera just arrived on the product"

        animation_prompt = (
            "A fast whip-pan motion blur clears to reveal the product in sharp focus, "
            "camera settling smoothly with a subtle push-in on the product."
        )

    elif transition_type == "focus_pull":
        E = environment
        A = "The product is positioned on a surface, snapping into sharp focus from a blurred state."
        L = f"{lighting}, with a shallow depth of field isolating the product"
        Ca = f"{ca_from_analysis}, with a very shallow depth of field"

        animation_prompt = (
            "The background and foreground blur dissolve as the product racks into "
            f"crisp focus, maintaining the {lighting}. Subtle, slow push-in."
        )

    else:
        # Fallback to match_cut behavior for unknown types
        E = environment
        A = "The product sits centered, presented cleanly and prominently."
        L = f"{lighting}"
        Ca = ca_from_analysis

        animation_prompt = (
            f"Subtle, slow camera movement with a gentle push-in on the product, "
            f"maintaining the {lighting}."
        )

    image_prompt = (
        f"S: {S}\n"
        f"E: {E}\n"
        f"A: {A}\n"
        f"L: {L}\n"
        f"Ca: {Ca}\n"
        f"M: {M}"
    )

    return image_prompt, animation_prompt
