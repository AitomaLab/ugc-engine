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
    "video_clip_seedance_with_ref_per_s": 16,
    "video_clip_seedance_no_ref_per_s": 27,
    ("clone", 15): 90,
    ("clone", 30): 180,
    "editor_render": 10,
    # WaveSpeed-specific costs. Element register confirmed at $0.01 → 1 credit.
    # Per-mode WS costs not yet supplied; callers fall back to KIE pricing
    # so the WS path matches today's cost until the user provides deltas.
    "wavespeed_kling_element_register": 1,
    "wavespeed_video_extend_per_s": 6,
    "wavespeed_text_to_image": 5,
    "wavespeed_alt_versions_pair": 10,
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


def get_video_clip_credit_cost(
    mode: str,
    clip_length: int,
    has_reference: bool = False,
    provider: str = "kie",
) -> int:
    """Return the credit cost for a single clip generation.

    `provider` is informational for now — WaveSpeed pricing differentials are
    not yet supplied, so both providers map to the same per-second rate.
    Callers may pass provider="wavespeed" today; rates can diverge later
    without touching the call sites.
    """
    if mode in ("seedance_2_ugc", "seedance_2_cinematic", "seedance_2_product"):
        per_s_key = (
            "video_clip_seedance_with_ref_per_s" if has_reference
            else "video_clip_seedance_no_ref_per_s"
        )
        return int(CREDIT_COSTS[per_s_key] * max(1, int(clip_length)))
    per_s_key = {
        "ugc": "video_clip_ugc_per_s",
        "cinematic_video": "video_clip_cinematic_per_s",
        "ai_clone": "video_clip_clone_per_s",
    }.get(mode)
    if not per_s_key:
        raise ValueError(f"No credit cost defined for video clip mode: {mode}")
    return int(CREDIT_COSTS[per_s_key] * max(1, int(clip_length)))


def get_kling_element_register_credit_cost() -> int:
    """One-time charge for registering a Kling element (cached after first call)."""
    return CREDIT_COSTS["wavespeed_kling_element_register"]


def get_video_extend_credit_cost(clip_length: int = 8) -> int:
    """Credit cost for the WaveSpeed Veo extend operation."""
    return int(CREDIT_COSTS["wavespeed_video_extend_per_s"] * max(1, int(clip_length)))


def get_text_to_image_credit_cost() -> int:
    return CREDIT_COSTS["wavespeed_text_to_image"]


def get_alt_versions_credit_cost() -> int:
    """Pair of alt-version outputs from a single edit-multi call."""
    return CREDIT_COSTS["wavespeed_alt_versions_pair"]


def get_video_credit_cost(product_type: str, duration: int) -> int:
    key = (product_type.lower(), int(duration))
    cost = CREDIT_COSTS.get(key)
    if cost is None:
        raise ValueError(f"No credit cost defined for {product_type} {duration}s video")
    return cost
