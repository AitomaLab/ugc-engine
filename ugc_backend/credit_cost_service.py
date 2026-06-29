"""
UGC Engine SaaS — Credit Cost Service

User-facing credit costs per generation type.
This is SEPARATE from cost_service.py which calculates internal COGS/API costs.

Pricing model (Model A):
  Revenue per credit (RPC) = $0.03
  Target gross margin = 70%
  credits = ceil(COGS_USD / ((1 - 0.70) * RPC)) = ceil(COGS / 0.009)

Model B ($0.01/credit): multiply all Model A values by ~3.33 (divisor 0.003).
"""
from __future__ import annotations

import math

# (1 - TARGET_GROSS_MARGIN) * REVENUE_PER_CREDIT  —  Model A @ $0.03/credit, 70% margin
_MARGIN_DIVISOR = 0.009
REVENUE_PER_CREDIT = 0.03
TARGET_GROSS_MARGIN = 0.70


def credits_for_cogs(cogs_usd: float) -> int:
    """Convert a dollar COGS amount to credits at 70% gross margin."""
    return max(1, math.ceil(float(cogs_usd) / _MARGIN_DIVISOR))


def _is_seedance_model(model_api: str | None) -> bool:
    return bool(model_api and "seedance" in str(model_api).lower())


# Fixed credit costs — aligned to cost_config.json COGS @ 70% margin (Model A)
CREDIT_COSTS = {
    # Full UGC pipeline bundles (Veo production path + agent + script)
    ("digital", 15): 67,
    ("digital", 30): 134,
    ("physical", 15): 101,
    ("physical", 30): 202,
    # Seedance premium bundles (when model_api contains "seedance")
    ("digital_seedance", 15): 145,
    ("digital_seedance", 30): 290,
    ("physical_seedance", 15): 288,
    ("physical_seedance", 30): 576,
    # Cinematic product shots (Nano + Veo)
    "cinematic_image_1k": 10,
    "cinematic_image_2k": 10,
    "cinematic_image_4k": 14,
    "cinematic_video_8s": 44,
    # Creative OS — single image generation (nano-banana-pro)
    "creative_os_image": 10,
    # Creative OS — animate still → 5s clip (Kling 3.0)
    "animate_image_5s": 56,
    # Video clips — Veo is flat per clip; others are per-second
    "video_clip_ugc_per_s": 34,
    "video_clip_veo_fast_720p": 34,
    "video_clip_veo_fast_1080p": 37,
    "video_clip_cinematic_per_s": 12,
    "video_clip_clone_per_s": 3,
    "video_clip_seedance_with_ref_per_s": 14,
    "video_clip_seedance_no_ref_per_s": 23,
    # AI Clone full videos
    ("clone", 15): 53,
    ("clone", 30): 106,
    # Editor render
    "editor_render": 2,
    # Cinematic Ads — storyboard via Fal GPT Image 2; Seedance 2.0 video via Kie @ \.125/s
    "cinematic_storyboard": 20,
    "cinematic_animate_720p_5s": 70,
    "cinematic_animate_720p_10s": 140,
    "cinematic_animate_720p_15s": 210,
    "cinematic_broll_720p_5s": 70,
    "cinematic_product_macro_720p_5s": 70,
    # Gemini Omni Video edit (flat per generation)
    "gemini_omni_edit_720p": 134,
    "gemini_omni_edit_4k": 200,
    "gemini_omni_edit_multipass": 268,
    # 4-view sheets (4× Nano Banana)
    "creative_os_identity_4view": 40,
    "creative_os_product_4view": 40,
    "wavespeed_alt_versions_pair": 20,
    # Flat Kling cinematic clip rates (5/8/10s)
    "cinematic_clip_5s": 60,
    "cinematic_clip_8s": 96,
    "cinematic_clip_10s": 120,
    # Overhead add-ons (when itemized)
    "agent_session_ugc": 13,
    "script_generation": 2,
    "music_per_video": 6,
    "processing_per_video": 2,
    "elevenlabs_per_1k_chars": 20,
}


def get_creative_os_image_credit_cost() -> int:
    """Credits for one Creative OS still image generation."""
    return CREDIT_COSTS["creative_os_image"]


def get_animate_image_credit_cost(duration: int = 5) -> int:
    """Credits for animating a still image into a Kling 3.0 clip."""
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

    Note: Veo 3.1 Fast is flat per video — ugc mode returns a flat rate,
    not clip_length × per_second.
    """
    if mode == "ugc":
        return CREDIT_COSTS["video_clip_veo_fast_720p"]
    if mode in ("seedance_2_ugc", "seedance_2_cinematic", "seedance_2_product"):
        per_s_key = (
            "video_clip_seedance_with_ref_per_s" if has_reference
            else "video_clip_seedance_no_ref_per_s"
        )
        return int(CREDIT_COSTS[per_s_key] * max(1, int(clip_length)))
    per_s_key = {
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
    """Credits for one Gemini Omni Video edit (with-video-input, flat per gen)."""
    key = "gemini_omni_edit_4k" if str(resolution).lower() == "4k" else "gemini_omni_edit_720p"
    return CREDIT_COSTS[key]


def get_video_extend_credit_cost() -> int:
    """Credits for one Veo 3.1 Fast extend operation (flat per extend)."""
    return CREDIT_COSTS["video_clip_veo_fast_720p"]


def get_video_credit_cost(
    product_type: str,
    duration: int,
    model_api: str | None = None,
) -> int:
    """Get the credit cost for a full UGC video generation.

    Args:
        product_type: 'digital' or 'physical'
        duration: 15 or 30 seconds
        model_api: when it contains 'seedance', uses premium Seedance bundle pricing

    Returns:
        Credit cost as integer.
    """
    ptype = product_type.lower()
    dur = int(duration)
    if _is_seedance_model(model_api):
        key = (f"{ptype}_seedance", dur)
    else:
        key = (ptype, dur)
    cost = CREDIT_COSTS.get(key)
    if cost is None:
        raise ValueError(f"No credit cost defined for {product_type} {duration}s video")
    return cost


def get_shot_credit_cost(shot_type: str = "image", resolution: str = "2k") -> int:
    """Get the credit cost for a cinematic product shot."""
    if shot_type == "video":
        return CREDIT_COSTS["cinematic_video_8s"]
    key = f"cinematic_image_{resolution.lower()}"
    return CREDIT_COSTS.get(key, CREDIT_COSTS["cinematic_image_2k"])


def get_identity_sheet_credit_cost() -> int:
    """Credits for a 4-view character identity sheet."""
    return CREDIT_COSTS["creative_os_identity_4view"]


def get_product_shots_credit_cost() -> int:
    """Credits for a 4-view product shot sheet."""
    return CREDIT_COSTS["creative_os_product_4view"]


def get_alt_versions_credit_cost() -> int:
    """Credits for a pair of alternative image variations (edit-multi)."""
    return CREDIT_COSTS["wavespeed_alt_versions_pair"]


def _is_kling_model(model_api: str | None) -> bool:
    return bool(model_api and "kling" in str(model_api).lower())


def _is_veo_model(model_api: str | None) -> bool:
    return bool(model_api and "veo" in str(model_api).lower())


def resolve_job_credit_cost(
    product_type: str,
    length: int,
    model_api: str | None = None,
    *,
    has_reference: bool = True,
) -> int:
    """Resolve credit cost for POST /jobs from length + model_api.

    Full UGC bundles: length 15 or 30.
    Short clips: length <= 15 with model-specific clip pricing.
    """
    dur = int(length)
    api = (model_api or "veo-3.1-fast").lower()

    if dur in (15, 30):
        return get_video_credit_cost(product_type, dur, model_api=model_api)

    if dur < 1 or dur > 15:
        raise ValueError(f"Unsupported job length: {dur}s")

    if _is_veo_model(api):
        return get_video_clip_credit_cost("ugc", dur)
    if _is_kling_model(api):
        flat_key = f"cinematic_clip_{dur}s"
        if flat_key in CREDIT_COSTS:
            return CREDIT_COSTS[flat_key]
        return get_video_clip_credit_cost("cinematic_video", dur)
    if _is_seedance_model(api):
        mode = "seedance_2_ugc"
        return get_video_clip_credit_cost(mode, dur, has_reference=has_reference)

    raise ValueError(
        f"No credit cost for {product_type} {dur}s job with model_api={model_api!r}"
    )


def credits_deducted_for_job_row(job: dict) -> int | None:
    """Read persisted credits from job metadata, or resolve from row fields."""
    meta = job.get("metadata") or {}
    if meta.get("credits_deducted") is not None:
        return int(meta["credits_deducted"])
    try:
        return resolve_job_credit_cost(
            job.get("product_type") or "digital",
            int(job.get("length") or 15),
            model_api=job.get("model_api"),
            has_reference=bool(meta.get("has_reference", True)),
        )
    except (ValueError, TypeError):
        return None


def export_credit_cost_table() -> dict:
    """Serialize CREDIT_COSTS for API responses (tuple keys → strings)."""
    out: dict = {}
    for key, value in CREDIT_COSTS.items():
        if isinstance(key, tuple):
            out[f"{key[0]}_{key[1]}s"] = value
        else:
            out[str(key)] = value
    return out


def build_credit_cost_catalog(lang: str = "en") -> dict:
    """Human-readable credit catalog for agent pricing FAQ and support UI."""
    es = str(lang or "en").lower().startswith("es")

    def _row(key: str, en: str, es_label: str, credits: int) -> dict:
        return {"key": key, "label": es_label if es else en, "credits": int(credits)}

    sections: list[dict] = []

    img_cr = get_creative_os_image_credit_cost()
    sections.append({
        "id": "images",
        "title": "Imágenes" if es else "Images",
        "items": [
            _row("image_standard", "Static image (lifestyle, UGC, product, cinematic)", "Imagen estática (lifestyle, UGC, producto, cinemática)", img_cr),
            _row("influencer_random", "Random AI influencer (photo included)", "Influencer IA generado al azar (foto incluida)", img_cr),
            _row("identity_4view", "Influencer identity sheet — 4 views", "Hoja de identidad del influencer — 4 vistas", get_identity_sheet_credit_cost()),
            _row("product_4view", "Professional product sheet — 4 angles", "Hoja de fotos profesionales del producto — 4 ángulos", get_product_shots_credit_cost()),
            _row("alt_versions", "Alternative image versions (pair)", "Versiones alternativas de imagen (par)", get_alt_versions_credit_cost()),
            _row("cinematic_image_4k", "Cinematic still image — 4K", "Imagen cinemática — 4K", CREDIT_COSTS["cinematic_image_4k"]),
        ],
    })

    sections.append({
        "id": "short_clips",
        "title": "Videos cortos (clips individuales)" if es else "Short video clips",
        "items": [
            _row("veo_ugc_clip", "UGC talking-head clip — Veo 3.1 Fast (flat per clip)", "Clip UGC con persona hablando — Veo 3.1 Fast", get_video_clip_credit_cost("ugc", 8)),
            _row("kling_5s", "Cinematic product/scene clip — Kling 5s", "Clip cinemático de producto/escena — 5 segundos", CREDIT_COSTS["cinematic_clip_5s"]),
            _row("kling_8s", "Cinematic product/scene clip — Kling 8s", "Clip cinemático de producto/escena — 8 segundos", CREDIT_COSTS["cinematic_clip_8s"]),
            _row("kling_10s", "Cinematic product/scene clip — Kling 10s", "Clip cinemático de producto/escena — 10 segundos", CREDIT_COSTS["cinematic_clip_10s"]),
            _row("animate_image_5s", "Animate existing image — 5s Kling", "Animar una imagen existente — 5 segundos", get_animate_image_credit_cost(5)),
            _row("animate_image_10s", "Animate existing image — 10s Kling", "Animar una imagen existente — 10 segundos", get_animate_image_credit_cost(10)),
            _row("seedance_i2v_5s", "Seedance clip with reference — 5s", "Clip Seedance con referencia — 5 segundos", get_video_clip_credit_cost("seedance_2_ugc", 5, has_reference=True)),
            _row("seedance_t2v_5s", "Seedance clip text-only — 5s", "Clip Seedance solo texto — 5 segundos", get_video_clip_credit_cost("seedance_2_ugc", 5, has_reference=False)),
            _row("extend_veo", "Extend existing Veo clip", "Extender clip Veo existente", get_video_extend_credit_cost()),
        ],
    })

    sections.append({
        "id": "full_ugc",
        "title": "Videos UGC completos (15s / 30s)" if es else "Full UGC videos (15s / 30s)",
        "items": [
            _row("digital_15_veo", "Digital 15s — Veo 3.1", "Digital 15s — Veo 3.1", get_video_credit_cost("digital", 15)),
            _row("digital_30_veo", "Digital 30s — Veo 3.1", "Digital 30s — Veo 3.1", get_video_credit_cost("digital", 30)),
            _row("physical_15_veo", "Physical 15s — Veo 3.1", "Físico 15s — Veo 3.1", get_video_credit_cost("physical", 15)),
            _row("physical_30_veo", "Physical 30s — Veo 3.1", "Físico 30s — Veo 3.1", get_video_credit_cost("physical", 30)),
            _row("digital_15_seedance", "Digital 15s — Seedance 2.0", "Digital 15s — Seedance 2.0", get_video_credit_cost("digital", 15, model_api="seedance-2.0")),
            _row("digital_30_seedance", "Digital 30s — Seedance 2.0", "Digital 30s — Seedance 2.0", get_video_credit_cost("digital", 30, model_api="seedance-2.0")),
            _row("physical_15_seedance", "Physical 15s — Seedance 2.0", "Físico 15s — Seedance 2.0", get_video_credit_cost("physical", 15, model_api="seedance-2.0")),
            _row("physical_30_seedance", "Physical 30s — Seedance 2.0", "Físico 30s — Seedance 2.0", get_video_credit_cost("physical", 30, model_api="seedance-2.0")),
        ],
    })

    sections.append({
        "id": "clone",
        "title": "Videos AI Clone" if es else "AI Clone videos",
        "items": [
            _row("clone_15", "AI Clone lip-sync video — 15s", "Video AI Clone con lip-sync — 15s", get_clone_video_credit_cost(15)),
            _row("clone_30", "AI Clone lip-sync video — 30s", "Video AI Clone con lip-sync — 30s", get_clone_video_credit_cost(30)),
        ],
    })

    sections.append({
        "id": "cinematic_ads",
        "title": "Anuncios cinematográficos" if es else "Cinematic ads",
        "items": [
            _row("cinematic_storyboard", "Storyboard sheet (1 image)", "Storyboard (1 imagen)", get_cinematic_ad_credit_cost("storyboard")),
            _row("cinematic_animate_5s", "Animate cinematic ad — 5s", "Animación anuncio cinemático — 5s", get_cinematic_ad_credit_cost("animate", 5)),
            _row("cinematic_animate_10s", "Animate cinematic ad — 10s", "Animación anuncio cinemático — 10s", get_cinematic_ad_credit_cost("animate", 10)),
            _row("cinematic_animate_15s", "Animate cinematic ad — 15s", "Animación anuncio cinemático — 15s", get_cinematic_ad_credit_cost("animate", 15)),
            _row("cinematic_broll", "B-roll clip from storyboard panel — 5s", "Clip B-roll desde panel — 5s", get_cinematic_ad_credit_cost("broll")),
            _row("cinematic_macro", "Product macro clip — 5s", "Macro de producto — 5s", get_cinematic_ad_credit_cost("product_macro")),
        ],
    })

    sections.append({
        "id": "video_editing",
        "title": "Edición de video (Gemini Omni)" if es else "Video editing (Gemini Omni)",
        "items": [
            _row("gemini_720p", "Edit video — 720p (single pass)", "Editar video — 720p (un pase)", get_gemini_omni_edit_credit_cost("720p")),
            _row("gemini_4k", "Edit video — 4K (single pass)", "Editar video — 4K (un pase)", get_gemini_omni_edit_credit_cost("4k")),
            _row("gemini_multipass", "Edit video — multi-pass (>10s full clip)", "Editar video — multipase (>10s)", CREDIT_COSTS["gemini_omni_edit_multipass"]),
        ],
    })

    free_title = "Gratis (sin costo)" if es else "Free (no credit cost)"
    sections.append({
        "id": "free",
        "title": free_title,
        "items": [
            _row("discovery", "Discovery tools (list assets, wallet, scripts, jobs)", "Herramientas de descubrimiento", 0),
            _row("cinematic_propose", "Cinematic ad — propose 3 directions", "Anuncio cinemático — proponer 3 direcciones", 0),
            _row("captions", "Captions / subtitles on finished video", "Subtítulos en video terminado", 0),
            _row("combine", "Combine videos / editor save", "Combinar videos / guardar editor", 0),
        ],
    })

    return {
        "lang": "es" if es else "en",
        "sections": sections,
        "message": (
            "Presenta estos números exactos al usuario. No redondees ni fusiones variantes "
            "(p. ej. digital vs físico, Veo vs Seedance)."
            if es
            else "Present these exact numbers to the user. Do not round or merge variants "
            "(e.g. digital vs physical, Veo vs Seedance)."
        ),
    }
