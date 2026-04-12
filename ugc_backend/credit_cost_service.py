"""
UGC Engine SaaS — Credit Cost Service

User-facing credit costs per generation type.
This is SEPARATE from cost_service.py which calculates internal COGS/API costs.
"""


# Fixed credit costs — from the Aitoma Studio pricing document
CREDIT_COSTS = {
    # Video generation
    ("digital", 15): 39,
    ("digital", 30): 77,
    ("physical", 15): 100,
    ("physical", 30): 199,
    # Cinematic product shots
    "cinematic_image_1k": 13,
    "cinematic_image_2k": 13,
    "cinematic_image_4k": 16,
    "cinematic_video_8s": 51,
    # Creative OS — single image generation (nano-banana-pro)
    "creative_os_image": 5,
    # Creative OS — animate still → 5s clip (Kling 3.0)
    "animate_image_5s": 25,
    # Creative OS — text-to-video clips (per-second pricing)
    "video_clip_ugc_per_s": 6,           # Veo 3.1 Fast (UGC mode)
    "video_clip_cinematic_per_s": 5,     # Kling 3.0 (cinematic_video mode)
    "video_clip_clone_per_s": 8,         # InfiniTalk (ai_clone mode, lip-sync)
    # AI Clone full videos (lip-synced talking head, separate pipeline)
    ("clone", 15): 90,
    ("clone", 30): 180,
    # Editor render (re-encoding edited timeline — fixed flat fee)
    "editor_render": 10,
}


def get_creative_os_image_credit_cost() -> int:
    """Credits for one Creative OS still image generation."""
    return CREDIT_COSTS["creative_os_image"]


def get_animate_image_credit_cost(duration: int = 5) -> int:
    """Credits for animating a still image into a Kling 3.0 clip."""
    # Kling 3.0 image animation is fixed at 5s. Round up for safety.
    return CREDIT_COSTS["animate_image_5s"] * max(1, round(duration / 5))


def get_clone_video_credit_cost(duration: int) -> int:
    """Credits for one full AI Clone video (lip-synced talking head)."""
    key = ("clone", int(duration))
    cost = CREDIT_COSTS.get(key)
    if cost is None:
        raise ValueError(f"No credit cost defined for clone {duration}s video")
    return cost


def get_editor_render_credit_cost() -> int:
    """Credits for one Remotion editor render (flat fee)."""
    return CREDIT_COSTS["editor_render"]


def get_video_clip_credit_cost(mode: str, clip_length: int) -> int:
    """Credits for a Creative OS text-to-video clip generation.

    mode: 'ugc' | 'cinematic_video' | 'ai_clone'
    clip_length: seconds (5/8/10 typically)
    """
    per_s_key = {
        "ugc": "video_clip_ugc_per_s",
        "cinematic_video": "video_clip_cinematic_per_s",
        "ai_clone": "video_clip_clone_per_s",
    }.get(mode)
    if not per_s_key:
        raise ValueError(f"No credit cost defined for video clip mode: {mode}")
    return int(CREDIT_COSTS[per_s_key] * max(1, int(clip_length)))


def get_video_credit_cost(product_type: str, duration: int) -> int:
    """Get the credit cost for a video generation.

    Args:
        product_type: 'digital' or 'physical'
        duration: 15 or 30 seconds

    Returns:
        Credit cost as integer.

    Raises:
        ValueError if the combination is not recognized.
    """
    key = (product_type.lower(), int(duration))
    cost = CREDIT_COSTS.get(key)
    if cost is None:
        raise ValueError(f"No credit cost defined for {product_type} {duration}s video")
    return cost


def get_shot_credit_cost(shot_type: str = "image", resolution: str = "2k") -> int:
    """Get the credit cost for a cinematic product shot.

    Args:
        shot_type: 'image' or 'video'
        resolution: '1k', '2k', or '4k' (for images) — ignored for video

    Returns:
        Credit cost as integer.
    """
    if shot_type == "video":
        return CREDIT_COSTS["cinematic_video_8s"]
    key = f"cinematic_image_{resolution.lower()}"
    return CREDIT_COSTS.get(key, 13)  # Default to 1k/2k cost
