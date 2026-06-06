"""
UGC Engine SaaS — Credit Cost Service

User-facing credit costs per generation type.
This is SEPARATE from cost_service.py which calculates internal COGS/API costs.
"""


# Fixed credit costs — from the Aitoma Studio pricing document
# Updated 2026-05-07 with real WaveSpeed COGS to ensure positive margins.
CREDIT_COSTS = {
    # Video generation (full UGC pipeline)
    ("digital", 15): 95,     # was 39 — raised to cover Seedance 720P i2v at $0.125/s
    ("digital", 30): 190,    # was 77 — raised proportionally
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
    "video_clip_ugc_per_s": 6,           # Veo 3.1 Fast (UGC mode) — flat $0.325/video
    "video_clip_cinematic_per_s": 8,     # Kling 3.0 Std w/ audio ($0.10/s) — was 5, raised for margin
    "video_clip_clone_per_s": 8,         # InfiniTalk (ai_clone mode, lip-sync)
    "video_clip_seedance_with_ref_per_s": 16,  # Seedance 2.0 Fast 720p i2v ($0.125/s)
    "video_clip_seedance_no_ref_per_s": 27,    # Seedance 2.0 Fast 720p t2v ($0.205/s)
    # AI Clone full videos (lip-synced talking head, separate pipeline)
    ("clone", 15): 90,
    ("clone", 30): 180,
    # Editor render (re-encoding edited timeline — fixed flat fee)
    "editor_render": 10,
    # Cinematic Ads (Fal AI: GPT Image 2 + Seedance 2.0 Pro, always 720p)
    # Margin-aligned with existing video jobs (~21 credits per $1 of COGS).
    "cinematic_storyboard": 4,              # GPT Image 2 high (any aspect, ~$0.18)
    "cinematic_animate_720p_5s":  32,       # Seedance 720p 5s
    "cinematic_animate_720p_10s": 64,       # Seedance 720p 10s
    "cinematic_animate_720p_15s": 96,       # Seedance 720p 15s (anchor)
    "cinematic_broll_720p_5s": 32,          # Seedance 720p 5s broll panel
    "cinematic_product_macro_720p_5s": 32,  # Seedance 720p 5s product macro
    # Gemini Omni Video — generative EDIT of an existing clip (KIE).
    # "With video input" pricing is flat per generation, independent of length.
    # Margin-aligned at ~21 credits per $1 of COGS (same rule as cinematic ads).
    "gemini_omni_edit_720p": 25,            # 720p/1080p with video input ($1.20)
    "gemini_omni_edit_4k": 38,              # 4K with video input ($1.80)
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


def get_video_clip_credit_cost(mode: str, clip_length: int, has_reference: bool = False) -> int:
    """Credits for a Creative OS text-to-video clip generation.

    mode: 'ugc' | 'cinematic_video' | 'ai_clone' | 'seedance_2_ugc'
          | 'seedance_2_cinematic' | 'seedance_2_product'
    clip_length: seconds (5/8/10 typically)
    has_reference: for Seedance modes, True when an image or video reference
        is attached (i2v pricing) vs pure text-to-video (t2v pricing).
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


def get_cinematic_ad_credit_cost(stage: str, duration_seconds: int = 15) -> int:
    """Credits for one Cinematic Ads stage.

    stage: 'storyboard' | 'animate' | 'broll' | 'product_macro'
    duration_seconds: only used for 'animate' — one of 5 / 10 / 15.
    All animation stages are 720p; broll + product_macro are always 5s.
    """
    if stage == "animate":
        key = f"cinematic_animate_720p_{int(duration_seconds)}s"
        return CREDIT_COSTS.get(key, CREDIT_COSTS["cinematic_animate_720p_15s"])
    key = {
        "storyboard": "cinematic_storyboard",
        "broll": "cinematic_broll_720p_5s",
        "product_macro": "cinematic_product_macro_720p_5s",
    }.get(stage)
    if not key:
        raise ValueError(f"No cinematic-ad credit cost defined for stage: {stage}")
    return CREDIT_COSTS[key]


def get_gemini_omni_edit_credit_cost(resolution: str = "720p") -> int:
    """Credits for one Gemini Omni Video edit (with-video-input, flat per gen).

    720p/1080p → 25 credits; 4k → 38 credits. The >10s chunk→edit→stitch flow
    still sends only ONE edit window to the model, so it costs the same flat rate.
    """
    key = "gemini_omni_edit_4k" if str(resolution).lower() == "4k" else "gemini_omni_edit_720p"
    return CREDIT_COSTS[key]


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
