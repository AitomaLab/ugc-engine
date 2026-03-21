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
}


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
