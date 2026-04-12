"""
Creative OS — Model Router

Maps user-facing modes to internal model identifiers and API endpoints.
This is the single source of truth for all model routing decisions.
"""

# ── Image Generation ────────────────────────────────────────────────────
IMAGE_MODES = {
    "cinematic": {
        "model": "nano-banana-pro",
        "system_prompt": "cinematic",
        "description": "Cinematic style — hyper-detailed, professional color grading",
    },
    "iphone_look": {
        "model": "nano-banana-pro",
        "system_prompt": "iphone_look",
        "description": "iPhone Look — realistic, casual, premium lifestyle",
    },
    "luxury": {
        "model": "nano-banana-pro",
        "system_prompt": "luxury",
        "description": "Luxury — high-fashion editorial, Vogue-level photography",
    },
    "ugc": {
        "model": "nano-banana-pro",
        "system_prompt": "ugc_composite",
        "description": "UGC — realistic influencer + product composite, social media ready",
    },
}

# ── Video Generation ────────────────────────────────────────────────────
VIDEO_MODES = {
    "ugc": {
        "model": "veo-3.1-fast",
        "system_prompt": None,
        "clip_lengths": [5, 8, 10],
        "description": "UGC style — authentic, social media ready",
    },
    "cinematic_video": {
        "model": "kling-3.0/video",
        "system_prompt": "kling_director",
        "clip_lengths": [5, 10],
        "description": "Cinematic Video — directed, multi-shot capable",
    },
    "ai_clone": {
        "model": "infinitalk",
        "system_prompt": None,
        "clip_lengths": [],  # Duration controlled by script length
        "description": "AI Clone — lip-synced talking head",
    },
}

# ── Animation (Image → Video) ──────────────────────────────────────────
DIRECTOR_STYLES = {
    "dolly_in", "dolly_out", "orbit", "tracking",
    "pan", "tilt", "crane", "static",
}

UGC_STYLES = {
    "handheld", "reveal", "float", "drift",
}

ANIMATION_ROUTING = {
    # All animation styles → Kling 3.0 (no speech needed for image animations)
    **{style: "kling-3.0/video" for style in DIRECTOR_STYLES},
    **{style: "kling-3.0/video" for style in UGC_STYLES},
}


def get_image_mode(mode: str) -> dict:
    """Get image generation config for a mode."""
    if mode not in IMAGE_MODES:
        raise ValueError(f"Unknown image mode: {mode}. Available: {list(IMAGE_MODES.keys())}")
    return IMAGE_MODES[mode]


def get_video_mode(mode: str) -> dict:
    """Get video generation config for a mode."""
    if mode not in VIDEO_MODES:
        raise ValueError(f"Unknown video mode: {mode}. Available: {list(VIDEO_MODES.keys())}")
    return VIDEO_MODES[mode]


def get_animation_model(style: str) -> str:
    """Get the model to use for an animation style."""
    if style not in ANIMATION_ROUTING:
        raise ValueError(
            f"Unknown animation style: {style}. "
            f"Director styles: {DIRECTOR_STYLES}. UGC styles: {UGC_STYLES}."
        )
    return ANIMATION_ROUTING[style]


def get_clip_lengths(mode: str) -> list[int]:
    """Get available clip lengths for a video mode."""
    config = get_video_mode(mode)
    return config["clip_lengths"]
