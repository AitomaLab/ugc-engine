"""
Creative OS — Credit Cost Service (bundled copy)

Standalone copy of ugc_backend.credit_cost_service for Railway deployment
where ugc_backend is not available. Keep in sync with the original.
"""

CREDIT_COSTS = {
    ("digital", 15): 39,
    ("digital", 30): 77,
    ("physical", 15): 100,
    ("physical", 30): 199,
    "cinematic_image_1k": 13,
    "cinematic_image_2k": 13,
    "cinematic_image_4k": 16,
    "cinematic_video_8s": 51,
    "creative_os_image": 5,
    "animate_image_5s": 25,
    "video_clip_ugc_per_s": 6,
    "video_clip_cinematic_per_s": 5,
    "video_clip_clone_per_s": 8,
    ("clone", 15): 90,
    ("clone", 30): 180,
    "editor_render": 10,
}


def get_creative_os_image_credit_cost() -> int:
    return CREDIT_COSTS["creative_os_image"]


def get_animate_image_credit_cost(duration: int = 5) -> int:
    return CREDIT_COSTS["animate_image_5s"] * max(1, round(duration / 5))


def get_clone_video_credit_cost(duration: int) -> int:
    key = ("clone", int(duration))
    cost = CREDIT_COSTS.get(key)
    if cost is None:
        raise ValueError(f"No credit cost defined for clone {duration}s video")
    return cost


def get_editor_render_credit_cost() -> int:
    return CREDIT_COSTS["editor_render"]


def get_video_clip_credit_cost(mode: str, clip_length: int) -> int:
    per_s_key = {
        "ugc": "video_clip_ugc_per_s",
        "cinematic_video": "video_clip_cinematic_per_s",
        "ai_clone": "video_clip_clone_per_s",
    }.get(mode)
    if not per_s_key:
        raise ValueError(f"No credit cost defined for video clip mode: {mode}")
    return int(CREDIT_COSTS[per_s_key] * max(1, int(clip_length)))


def get_video_credit_cost(product_type: str, duration: int) -> int:
    key = (product_type.lower(), int(duration))
    cost = CREDIT_COSTS.get(key)
    if cost is None:
        raise ValueError(f"No credit cost defined for {product_type} {duration}s video")
    return cost
