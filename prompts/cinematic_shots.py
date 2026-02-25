"""
SEALCaM Prompt builder for Cinematic Product Shots (Still Images).
Generates structured prompts for Nano Banana Pro.
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
    "pedestal": {
        "E": "a simple, elegant pedestal or block that elevates the product",
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
