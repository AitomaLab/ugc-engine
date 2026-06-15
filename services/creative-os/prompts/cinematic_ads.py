# Canonical cinematic_ads module — imported by Creative OS via repo-root sys.path.
"""
Cinematic-ads prompt builders + direction proposer.

Pure functions, no I/O. Mirrors the .claude/skills/cinematic-ads/SKILL.md
playbook so the SaaS agent's output is identical to what Claude Code does.

Public API:
    propose_directions(product_meta) -> list[dict]
        Three category-aware directions (A/B/C) per the skill's category
        cheat sheet. Each: {key, name, vibe, hero_moment, model_or_product_only}.

    build_storyboard_prompt(
        brand, product, direction, tagline, domain, *,
        category, num_panels=6, duration_s=15,
    ) -> str
        Full GPT Image 2 prompt — applies all 8 storyboard rules,
        safer beauty wording, mannequin/soft-blur face when humans appear.

    build_seedance_prompt(
        brand, product, direction, *,
        duration_s=15, has_humans, has_storyboard=True,
    ) -> str
        1–3 sentence simple Seedance prompt (A/B winner). Always names
        @Image1 + @Image2 explicitly. Word-bleed-trap-safe.

    build_seedance_broll_prompt(brand, product, panel_meta) -> str
        Single-beat 5s prompt from one storyboard panel's metadata.

    build_seedance_product_macro_prompt(brand, product, *, category) -> str
        Product-only 5s beauty macro shot — no humans, no environment
        beyond the product backdrop.

    panel_beats_for(direction_key) -> list[dict]
        The 6 panel beats used by the storyboard prompt builder. Returned
        in structured form so the agent's chat narration can describe the
        beats to the user once the storyboard renders.
"""
from __future__ import annotations

import asyncio
import json as _json
import os
import re as _re
from typing import Any, Optional


# ── Category routing per skill cheat sheet ────────────────────────────
_BEAUTY_CATS = {"beauty", "skincare", "cosmetics", "makeup", "personal_care"}
_AUDIO_CATS = {"audio", "headphones", "earbuds", "speakers"}
_FOOTWEAR_CATS = {"footwear", "sneakers", "shoes"}
_APPAREL_CATS = {"apparel", "fashion", "clothing"}
_DRINK_CATS = {"drink", "beverage", "packaged_goods", "food"}


# Keyword fallback for image-upload propose (no product_id, so no stored
# category metadata). Buckets line up 1:1 with the _category_key router.
# Order matters when terms could match more than one bucket — most specific
# / consumer-facing terms first.
_CATEGORY_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("drink",    ("coffee", "espresso", "latte", "cappuccino", "tea", "matcha",
                  "starbucks", "soda", "cola", "juice", "smoothie", "kombucha",
                  "beer", "wine", "cocktail", "whiskey", "vodka", "water",
                  "drink", "beverage", "snack", "protein bar")),
    ("beauty",   ("cream", "serum", "lipstick", "lipgloss", "lip gloss",
                  "gloss", "lip oil", "lip tint", "lip stain", "lip balm",
                  "mascara", "foundation", "concealer", "blush", "bronzer",
                  "highlighter", "eyeliner", "eyeshadow", "eyebrow", "brow",
                  "moisturizer", "skincare", "perfume", "fragrance", "cologne",
                  "lotion", "shampoo", "conditioner", "makeup", "cosmetic",
                  "scar stick", "cleanser", "balm", "nail polish", "beauty")),
    ("audio",    ("headphone", "earbud", "earphone", "speaker", "soundbar",
                  "airpods", "airpod", "beats", "sonos")),
    ("footwear", ("sneaker", "shoe", "runner", "trainer", "boot", "sandal",
                  "loafer", "heel")),
    ("apparel",  ("shirt", "tshirt", "t-shirt", "dress", "jacket", "coat",
                  "pant", "jean", "hoodie", "sweater", "blazer", "skirt",
                  "outfit")),
]


def infer_category_from_text(text: str) -> str:
    """Return a category bucket if any keyword matches in the text, else ''.

    Used when the agent gets an image upload with no product_id (so category
    metadata is empty). Matches feed straight into _category_key() to reach
    the per-category direction tables; otherwise the default gadget trilogy
    is returned.
    """
    if not text:
        return ""
    t = text.lower()
    for bucket, kws in _CATEGORY_KEYWORDS:
        if any(kw in t for kw in kws):
            return bucket
    return ""


def _category_key(meta: dict) -> str:
    cat = (meta.get("category") or meta.get("product_category") or "").lower().strip()
    if cat in _BEAUTY_CATS:
        return "beauty"
    if cat in _AUDIO_CATS:
        return "audio"
    if cat in _FOOTWEAR_CATS:
        return "footwear"
    if cat in _APPAREL_CATS:
        return "apparel"
    if cat in _DRINK_CATS:
        return "drink"
    return "gadget"  # default — product-only motion-graphic fits most things


# ── Step 2: propose 3 directions ──────────────────────────────────────
def _enrich_directions(dirs: list[dict]) -> list[dict]:
    """Inject pro-cinematic defaults into directions missing the enriched fields.

    Keeps the static fallback compatible with the Haiku-generated shape so
    downstream builders (storyboard / seedance prompts, negative_prompt
    synthesis) can rely on the fields always being present.
    """
    _defaults = [
        ("camera_signature",   "ARRI Alexa Mini LF, Cooke S7/i, 35-85mm, f/2.0"),
        ("lighting_signature", "single motivated key + soft fill, neutral 5600K"),
        ("style_grade",        "Kodak Vision3 250D cinematic grade, balanced contrast"),
    ]
    for d in dirs:
        for k, v in _defaults:
            d.setdefault(k, v)
        d.setdefault("negative_traits", [
            "soft fades", "dissolves", "calm composed coverage", "eye-level standard framing",
        ])
    return dirs


def propose_directions(product_meta: dict, *, brief: str = "", category: str = "") -> list[dict]:
    """Return 3 storyboard directions enriched with pro-cinematic fields.

    Each direction has:
        key, name, vibe, hero_moment, model_or_product_only, recommended,
        camera_signature, lighting_signature, style_grade, negative_traits,
        requires_lip_application.
    Pro fields are injected from defaults if the static table doesn't define
    them, so downstream builders can rely on the full shape always being set.
    """
    cat = category or _category_key(product_meta)
    dirs = _enrich_directions(_propose_directions_static(product_meta))
    return tag_direction_lip_intents(
        dirs,
        product_name=product_meta.get("name") or "",
        category=cat,
        brief=brief,
        product_description=product_meta.get("description") or "",
        product_form=product_meta.get("product_form") or "",
    )


def _propose_directions_static(product_meta: dict) -> list[dict]:
    """Category-aware hand-authored directions (legacy fallback)."""
    cat = _category_key(product_meta)
    brand = product_meta.get("brand") or product_meta.get("name") or "Brand"

    if cat == "beauty":
        return [
            {
                "key": "A",
                "name": "Soft Morning Ritual",
                "vibe": "Warm domestic light, soft cream-and-blush palette, 50mm lens, shallow DOF. Sofia Coppola-soft, not clinical.",
                "hero_moment": "Single fluid glide of the product across soft skin in close-up — a settled stillness as the formula catches morning light.",
                "model_or_product_only": "model",
                "recommended": True,
            },
            {
                "key": "B",
                "name": "Soft Sculpture",
                "vibe": "Studio motion-graphic, suspended in space, blush gradient backdrop, 100mm macro lens.",
                "hero_moment": "Product floats and rotates in slow motion while a 'second skin' film morphs over an abstract blush sphere (no body shown).",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
            {
                "key": "C",
                "name": "Quiet Confidence",
                "vibe": "Documentary-warm, soft natural window light, muted blush + sand palette, 35mm slight handheld.",
                "hero_moment": "Brief moment of the product being used in a real lived-in setting — narrative pull, never clinical.",
                "model_or_product_only": "model",
                "recommended": False,
            },
        ]

    if cat == "footwear":
        return [
            {
                "key": "A",
                "name": f"{brand} Motion Streaks",
                "vibe": "Studio motion-graphic, dynamic abstract terrain blur, wind-streak particles, sweeping color gradients.",
                "hero_moment": "Top-down hero of the shoe through the sole grid, undulating cushioning catching key light.",
                "model_or_product_only": "product_only",
                "recommended": True,
            },
            {
                "key": "B",
                "name": "Runner POV",
                "vibe": "First-person fly-by, golden-hour light, cinematic depth.",
                "hero_moment": "Toe-off slow-mo from low angle with terrain rushing past.",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
            {
                "key": "C",
                "name": "Urban Drift",
                "vibe": "Editorial city evening, soft neon reflections, 35mm street-photography lens.",
                "hero_moment": "Pristine pair on wet pavement reflecting brand colors.",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
        ]

    if cat == "audio":
        # Skill flags audio as likeness-rejection risk on Seedance —
        # all three are product-only.
        return [
            {
                "key": "A",
                "name": "Sound in Space",
                "vibe": "Studio motion-graphic, sound-wave particles, deep matte backdrop, 100mm macro.",
                "hero_moment": "Headphones rotate in slow motion as bass-shockwave particles ripple outward.",
                "model_or_product_only": "product_only",
                "recommended": True,
            },
            {
                "key": "B",
                "name": "Material Macro",
                "vibe": "Ultra-tight product macros — material, mesh, metal, leather.",
                "hero_moment": "Light catches the brand mark in razor-thin DOF.",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
            {
                "key": "C",
                "name": "Listening Room",
                "vibe": "Architectural interior, single key light, the product as the only object on a plinth.",
                "hero_moment": "Camera dolly past empty room walls landing on the product.",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
        ]

    if cat == "drink":
        return [
            {
                "key": "A",
                "name": "Pristine Pour",
                "vibe": "Slow-mo bottle macro, cold condensation, golden-hour ambient.",
                "hero_moment": "Cold liquid catches light through the bottle silhouette — pristine, no splashes.",
                "model_or_product_only": "product_only",
                "recommended": True,
            },
            {
                "key": "B",
                "name": "Lifestyle Beat",
                "vibe": "Warm cafe / kitchen interior, model holding the can/bottle, soft natural light.",
                "hero_moment": "Eye-level beat as the model raises the product, brand-forward.",
                "model_or_product_only": "model",
                "recommended": False,
            },
            {
                "key": "C",
                "name": "Hero on Color",
                "vibe": "Studio motion-graphic, brand-color gradient backdrop, slow rotation.",
                "hero_moment": "Single revolving hero shot building anticipation to the end card.",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
        ]

    if cat == "apparel":
        return [
            {
                "key": "A",
                "name": "Editorial Walk",
                "vibe": "Lunarcore / techwear, soft architectural light, 50mm cinema lens.",
                "hero_moment": "Model walks through the frame, fabric catches light, silhouette holds.",
                "model_or_product_only": "model",
                "recommended": True,
            },
            {
                "key": "B",
                "name": "Material Studio",
                "vibe": "Macro studio shoot — weave, stitching, hardware.",
                "hero_moment": "Single garment hero shot on minimal background.",
                "model_or_product_only": "product_only",
                "recommended": False,
            },
            {
                "key": "C",
                "name": "Daily Life",
                "vibe": "Documentary-warm interior, model wearing the garment in real-feeling moments.",
                "hero_moment": "Quiet beat that makes the garment feel inhabitable, not styled.",
                "model_or_product_only": "model",
                "recommended": False,
            },
        ]

    # default gadget / hardware
    return [
        {
            "key": "A",
            "name": f"{brand} Suspended",
            "vibe": "Studio motion-graphic, suspended in space, soft motion-streak gradients, 100mm macro.",
            "hero_moment": "Product floats and rotates while light catches its primary details.",
            "model_or_product_only": "product_only",
            "recommended": True,
        },
        {
            "key": "B",
            "name": "Hand-In",
            "vibe": "Single hand presents the product against a clean backdrop, 50mm lens.",
            "hero_moment": "Hand reveals the product silhouette and brand mark in one motion.",
            "model_or_product_only": "model",
            "recommended": False,
        },
        {
            "key": "C",
            "name": "Material Study",
            "vibe": "Ultra-close macros of the product's primary materials, brand-color lighting.",
            "hero_moment": "Razor-thin DOF beat on a single design detail.",
            "model_or_product_only": "product_only",
            "recommended": False,
        },
    ]


# ── Panel beats (6 panels @ 2.5s each = 15s) ─────────────────────────
# These are the canonical 6 beats for each direction. The storyboard
# prompt builder embeds them inline; the agent narrates them in chat
# once the storyboard renders.
def _enrich_beats(beats: list[dict]) -> list[dict]:
    """Inject camera/lens/lighting/motion defaults into fallback beats so
    downstream builders (storyboard caption block, seedance prompt pillar
    structure) can rely on the enriched shape always being present.
    """
    _defaults_by_scene = {
        # scene-label keyword → (camera, lens, lighting, motion)
        "STILLNESS":  ("slow push-in (8%)",      "85mm, f/2.0, shallow DOF",  "single warm key from upper-right, golden-amber",      "imperceptible drift over the full beat"),
        "TURN":       ("slow 180° arc",          "50mm, f/2.8, medium DOF",   "rim light from back-right, neutral 5600K",            "one full rotation across the beat"),
        "DETAIL":     ("anamorphic ECU off-axis","100mm macro, f/2.8, shallow DOF","hard key 80°, soft fill, color-temp matches grade","camera glides 6 deg/sec across surface"),
        "FEATURE":    ("locked-off stable medium","50mm, f/2.0, medium DOF",  "motivated key + bounce, balanced",                    "subject holds, micro-particle drift"),
        "HERO":       ("crash zoom",             "35mm, f/2.0, deep DOF",     "hard backlight + warm fill",                          "240fps slo-mo punch over 1s"),
        "END CARD":   ("locked-off stable medium","50mm, f/4.0, deep DOF",    "even soft light, balanced 5600K",                     "static held for the full beat"),
    }
    for b in beats:
        scene = str(b.get("scene", "")).upper()
        cam, lens, lighting, motion = _defaults_by_scene.get(scene, _defaults_by_scene["FEATURE"])
        b.setdefault("camera", cam)
        b.setdefault("lens", lens)
        b.setdefault("lighting", lighting)
        b.setdefault("motion", motion)
    return beats


def panel_beats_for(direction_key: str, *, category: str) -> list[dict]:
    """Hand-authored fallback beats, enriched with camera/lens/lighting/motion
    defaults so downstream builders can rely on the full shape.
    """
    return _enrich_beats(_panel_beats_for_static(direction_key, category=category))


def _panel_beats_for_static(direction_key: str, *, category: str) -> list[dict]:
    if category == "beauty" and direction_key == "A":
        return [
            {"n": 1, "ts": "[0:00–0:02.5]", "scene": "STILLNESS",
             "action": "slow push-in on the product standing on a cream ceramic dish next to a folded linen square, morning light catching it, no hands, no face",
             "sound": "soft morning ambience, gentle piano note"},
            {"n": 2, "ts": "[0:02.5–0:05.0]", "scene": "PICK UP",
             "action": "a woman's hand (soft warm-toned blur face just visible at top edge, no features) lifts the product, slow 50mm close-up",
             "sound": "soft cap-click, warm pad swell"},
            {"n": 3, "ts": "[0:05.0–0:07.5]", "scene": "GLIDE",
             "action": "extreme close-up of the formula gliding smoothly across soft skin (forearm or shoulder, NOT clinical), single fluid horizontal motion",
             "sound": "silk-on-skin whisper, music continues"},
            {"n": 4, "ts": "[0:07.5–0:10.0]", "scene": "SETTLE",
             "action": "macro-close on the treated skin catching warm light, soft natural texture, completely calm and still",
             "sound": "held warm chord, ambient room tone"},
            {"n": 5, "ts": "[0:10.0–0:12.5]", "scene": "REPLACE",
             "action": "she returns the product to the ceramic dish (face still soft warm-toned blur, hair and jawline crisp), hand exits frame, sun slowly brightens",
             "sound": "soft cap-click, music gentle rise"},
            {"n": 6, "ts": "[0:12.5–0:15.0]", "scene": "END CARD",
             "action": "clean hero shot of the product on cream linen, warm morning light, centered composition with brand wordmark + tagline + domain",
             "sound": "final warm chord, soft music tail"},
        ]

    if category == "beauty" and direction_key == "B":
        return [
            {"n": 1, "ts": "[0:00–0:02.5]", "scene": "REVEAL",
             "action": "single product floats into frame against a soft blush gradient, slow rotation, no humans",
             "sound": "low ambient pad, soft riser"},
            {"n": 2, "ts": "[0:02.5–0:05.0]", "scene": "ROTATE",
             "action": "100mm macro orbit around the product, light catches the cap and body",
             "sound": "rising synth, gentle chime"},
            {"n": 3, "ts": "[0:05.0–0:07.5]", "scene": "FORMULA MORPH",
             "action": "abstract blush sphere takes on a 'second skin' silicone-film morph, never literally skin",
             "sound": "warm pad swell"},
            {"n": 4, "ts": "[0:07.5–0:10.0]", "scene": "DETAIL",
             "action": "razor-thin DOF macro of the product wordmark, soft light playing across",
             "sound": "soft chime, ambient room tone"},
            {"n": 5, "ts": "[0:10.0–0:12.5]", "scene": "HERO",
             "action": "product holds in mid-air against the gradient, soft particles drift past",
             "sound": "held warm chord"},
            {"n": 6, "ts": "[0:12.5–0:15.0]", "scene": "END CARD",
             "action": "clean hero with brand wordmark + tagline + domain centered",
             "sound": "final warm chord, music tail"},
        ]

    if category == "footwear" and direction_key == "A":
        return [
            {"n": 1, "ts": "[0:00–0:02.5]", "scene": "REVEAL",
             "action": "shoe drifts into frame against an alpine-horizon color field, soft horizon glow behind",
             "sound": "low ambient pad, soft riser"},
            {"n": 2, "ts": "[0:02.5–0:05.0]", "scene": "KINETIC TURN",
             "action": "three-quarter front view, shoe levitates in slow rotation against motion-streak gradient",
             "sound": "rising synth, shoe whoosh"},
            {"n": 3, "ts": "[0:05.0–0:07.5]", "scene": "SOLE GRID",
             "action": "top-down macro under the outsole, cushioning catches key light",
             "sound": "deep bass hit, soft chime"},
            {"n": 4, "ts": "[0:07.5–0:10.0]", "scene": "TERRAIN FLY-BY",
             "action": "profile of the shoe suspended over alpine horizon, wind-streak particles rush past",
             "sound": "wind rush, percussive build"},
            {"n": 5, "ts": "[0:10.0–0:12.5]", "scene": "TOE-OFF",
             "action": "slow-mo profile of the shoe at full toe-flex, foam compressing along the wave edge",
             "sound": "bass kick, bright high"},
            {"n": 6, "ts": "[0:12.5–0:15.0]", "scene": "END CARD",
             "action": "studio hero of the pair levitating side by side on a clean ivory plinth",
             "sound": "final bass swell, music tail"},
        ]

    # Generic fallback — works for any product, direction-agnostic.
    return [
        {"n": 1, "ts": "[0:00–0:02.5]", "scene": "STILLNESS",
         "action": "slow push-in on the product against a soft brand-colored backdrop",
         "sound": "low ambient pad, soft riser"},
        {"n": 2, "ts": "[0:02.5–0:05.0]", "scene": "TURN",
         "action": "product rotates slowly, key light catching primary surface",
         "sound": "rising synth, gentle whoosh"},
        {"n": 3, "ts": "[0:05.0–0:07.5]", "scene": "DETAIL",
         "action": "ultra-tight macro on the brand mark / hero detail",
         "sound": "soft chime, ambient room tone"},
        {"n": 4, "ts": "[0:07.5–0:10.0]", "scene": "FEATURE",
         "action": "highlight beat showing the product's signature feature",
         "sound": "held warm chord"},
        {"n": 5, "ts": "[0:10.0–0:12.5]", "scene": "HERO",
         "action": "product holds in clean composition with brand-color light wash",
         "sound": "bright bass kick, soft high"},
        {"n": 6, "ts": "[0:12.5–0:15.0]", "scene": "END CARD",
         "action": "clean hero with brand wordmark + tagline + domain centered",
         "sound": "final warm chord, music tail"},
    ]


# ── LLM-generated directions (brief-aware, falls back to propose_directions) ──
#
# Module-level cache so the storyboard stage can resolve the same direction
# object the propose stage generated, without needing to plumb session_id
# through ToolContext. Keyed by (brief_hash, product_id_or_image_url).
# Keyed by session_id (Anthropic Managed Agent session) — stable across
# propose→storyboard→animate within one flow. Was previously keyed by
# sha1(brief)|product_id but the agent sometimes drops the brief on
# follow-up calls, causing silent fallback to static directions.
_LAST_DIRECTIONS_CACHE: dict[str, list[dict]] = {}


def cache_directions(session_id: Optional[str], directions: list[dict]) -> None:
    if not session_id:
        return
    _LAST_DIRECTIONS_CACHE[session_id] = directions
    if len(_LAST_DIRECTIONS_CACHE) > 128:
        for k in list(_LAST_DIRECTIONS_CACHE.keys())[:-128]:
            _LAST_DIRECTIONS_CACHE.pop(k, None)


def get_cached_directions(session_id: Optional[str]) -> Optional[list[dict]]:
    if not session_id:
        return None
    return _LAST_DIRECTIONS_CACHE.get(session_id)


# Beats keyed by (session_id, direction_key) so animate stage gets the
# same beats the storyboard was rendered with.
_LAST_BEATS_CACHE: dict[str, list[dict]] = {}


def cache_beats(session_id: Optional[str], direction_key: str, beats: list[dict]) -> None:
    if not session_id:
        return
    _LAST_BEATS_CACHE[f"{session_id}|d={direction_key}"] = beats
    if len(_LAST_BEATS_CACHE) > 128:
        for k in list(_LAST_BEATS_CACHE.keys())[:-128]:
            _LAST_BEATS_CACHE.pop(k, None)


def get_cached_beats(session_id: Optional[str], direction_key: str) -> Optional[list[dict]]:
    if not session_id:
        return None
    return _LAST_BEATS_CACHE.get(f"{session_id}|d={direction_key}")


# Session influencer stash — survives across turns when the user generates/saves
# a character but does not @-mention them on the next message.
_SESSION_INFLUENCER_CACHE: dict[str, dict] = {}


def cache_session_influencer(session_id: Optional[str], data: dict) -> None:
    if not session_id or not data.get("image_url"):
        return
    _SESSION_INFLUENCER_CACHE[session_id] = dict(data)
    if len(_SESSION_INFLUENCER_CACHE) > 128:
        for k in list(_SESSION_INFLUENCER_CACHE.keys())[:-128]:
            _SESSION_INFLUENCER_CACHE.pop(k, None)


def get_session_influencer(session_id: Optional[str]) -> Optional[dict]:
    if not session_id:
        return None
    return _SESSION_INFLUENCER_CACHE.get(session_id)


# Cinematic flow params carried across propose → storyboard → animate so a
# failed storyboard (e.g. missing influencer) still preserves direction/format.
_CINEMATIC_FLOW_CACHE: dict[str, dict] = {}

_FLOW_KEYS = (
    "direction", "aspect_ratio", "duration_seconds", "product_id",
    "image_url", "brief", "tagline", "domain", "lip_application_intents",
)


def merge_cinematic_flow(session_id: Optional[str], kwargs: dict) -> None:
    if not session_id:
        return
    prev = dict(_CINEMATIC_FLOW_CACHE.get(session_id) or {})
    for k in _FLOW_KEYS:
        v = kwargs.get(k)
        if v is not None and v != "":
            prev[k] = v
    if prev:
        _CINEMATIC_FLOW_CACHE[session_id] = prev
        if len(_CINEMATIC_FLOW_CACHE) > 128:
            for k in list(_CINEMATIC_FLOW_CACHE.keys())[:-128]:
                _CINEMATIC_FLOW_CACHE.pop(k, None)


def get_cinematic_flow(session_id: Optional[str]) -> Optional[dict]:
    if not session_id:
        return None
    return _CINEMATIC_FLOW_CACHE.get(session_id)


async def generate_directions_from_brief(
    *,
    brief: str,
    product_meta: dict,
    category: str,
    aspect_ratio: str = "16:9",
    duration_seconds: int = 15,
    user_lang: str = "en",
    anthropic_client: Optional[Any] = None,
) -> list[dict]:
    """Generate 3 cinematic directions tailored to the user's brief + product,
    via a small Haiku call. Falls back to propose_directions(product_meta) on
    any failure so propose never blocks.

    Returns the same shape as propose_directions: list of 3 dicts with
    {key: 'A'|'B'|'C', name, vibe, hero_moment, model_or_product_only, recommended}.
    """
    client = anthropic_client
    if client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[cinematic_propose] LLM directions skipped: ANTHROPIC_API_KEY not set")
            return propose_directions(product_meta, brief=brief, category=category)
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic()
        except Exception as e:
            print(f"[cinematic_propose] LLM directions skipped: anthropic client init failed: {e}")
            return propose_directions(product_meta, brief=brief, category=category)

    brand = product_meta.get("brand") or product_meta.get("name") or "Brand"
    product = product_meta.get("name") or "Product"
    product_description = (product_meta.get("description") or "").strip()

    system = (
        "You generate 3 cinematic-ad creative directions for a product. "
        "Output STRICT JSON: a single array of 3 objects, each with EXACT keys "
        '{"key": "A"|"B"|"C", '
        '"name": "2-4 word concept name", '
        '"vibe": "ONE sentence palette + lens + mood (max 140 chars)", '
        '"hero_moment": "ONE sentence describing the single beat the viewer remembers (max 160 chars)", '
        '"model_or_product_only": "model"|"product_only", '
        '"recommended": true|false, '
        '"camera_signature": "concrete camera body + lens system + focal range + aperture (e.g. \\"ARRI Alexa 35, Cooke S7/i, 24-85mm, f/1.8-2.8\\") (max 120 chars)", '
        '"lighting_signature": "ONE specific light setup with angle + quality + color temperature (e.g. \\"hard overhead midday 80°, warm amber bounce off concrete\\") (max 140 chars)", '
        '"style_grade": "ONE film stock + grade descriptor (e.g. \\"Kodak Vision3 500T pushed-cinematic, deep cool blues + warm amber\\") (max 140 chars)", '
        '"negative_traits": ["array of 3-5 short phrases naming what this direction must AVOID — e.g. \\"soft fades\\", \\"eye-level standard framing\\", \\"calm composed coverage\\""]}. '
        "EXACTLY ONE direction has recommended=true — the one that BEST fits the user's brief. "
        "Make the directions DISTINCT (not three flavors of the same thing). Each direction's camera_signature, "
        "lighting_signature, style_grade, and negative_traits MUST be unique to that direction's aesthetic intent. "
        "NARRATIVE LOCK: if the brief describes a specific action sequence (e.g. 'person puts on the headphones', "
        "'barista pours coffee', 'runner sprints'), the RECOMMENDED direction MUST reproduce that exact arc as its "
        "hero_moment — including any people, settings, or transitions the user named. At least 2 of the 3 directions "
        "must respect the brief's explicit story; the 3rd may diverge as a counter-option. If the brief explicitly "
        "names a person doing an action, NEVER make all 3 directions product_only — at least the recommended one "
        "MUST be model-led. "
        "REGISTER LOCK: if the brief uses energy words (aggressive, dynamic, fast cuts, techno, kinetic, chaos, drop, "
        "intense, hyper, frenetic, kinetic, energetic), the directions' style_grade and negative_traits MUST reflect "
        "that — high-contrast pushed grades, kinetic camera signatures, glitch-cut transitions, and negative_traits "
        "like 'calm coverage', 'soft fades', 'slow contemplative pacing'. Do NOT propose 'minimal architectural' or "
        "'quiet sculpture' directions when the brief asks for 'dynamic aggressive cuts'. "
        "If the brief is product-only and contains NO action sequence, all three may be product_only. "
        "USAGE PLAUSIBILITY (critical): every direction's `hero_moment` MUST depict the product used the way it "
        "ACTUALLY works in the real world — reason from the PRODUCT USAGE FACTS / description. NEVER invent a "
        "physically impossible interaction or an end-state the product cannot directly produce. For example, a bag "
        "of coffee BEANS or GROUNDS is opened and the grounds/beans are loaded into a grinder or coffee machine to "
        "BREW a cup — you canNOT pour ready-made liquid coffee out of the bag; the brewed cup comes from the machine, "
        "not the bag. Apply the same real-usage logic to any product (e.g. a capsule goes into its machine, a powder "
        "is scooped and mixed, a supplement is taken). If unsure how the product is used, keep the hero_moment to "
        "handling/presenting the product rather than guessing an impossible use. "
        + (
            "OUTPUT LANGUAGE: write the `name`, `vibe`, and `hero_moment` fields in Spanish (es-ES). "
            "Keep `camera_signature` / `lighting_signature` / `style_grade` in English (cinematography vocabulary). "
            if user_lang == "es" else
            "OUTPUT LANGUAGE: write all human-readable fields in English. "
        )
        + "No prose, no markdown, no preamble."
    )
    _aspect_hint = {
        "9:16": (
            "VERTICAL (9:16, TikTok/Reels) — frame for vertical screens: subject fills frame top-to-bottom; "
            "people, environments, and narrative arcs are ENCOURAGED but composed vertically (head-to-toe portrait "
            "shots, low-angle hero shots up the body, single-subject framing of the action). AVOID 16:9 letterbox "
            "compositions and very-wide establishing horizons — but DO include people, settings, and story beats "
            "if the brief calls for them."
        ),
        "4:3":  "CLASSIC (4:3) — boxier classical framing, balanced negative space; works for documentary / vintage moods.",
        "16:9": "HORIZONTAL (16:9, YouTube/landscape) — favor wide establishing shots and cinematic letterbox framing.",
    }.get(aspect_ratio, "")
    user = (
        f"BRIEF:\n{(brief or '').strip()[:1400]}\n\n"
        f"BRAND: {brand}\n"
        f"PRODUCT: {product}\n"
        f"CATEGORY: {category or 'general'}\n"
        + (f"PRODUCT USAGE FACTS (how this product is really used — directions MUST respect this; do NOT invent impossible usage): {product_description[:240]}\n" if product_description else "")
        + f"FORMAT: {aspect_ratio} ({_aspect_hint})\n"
        f"DURATION: {duration_seconds}s\n\n"
        "Write 3 creative directions tailored to the BRIEF and the FORMAT. The recommended one MUST be the one "
        "whose hero_moment best matches the narrative the user described. If the BRIEF or USAGE FACTS describe a "
        "real action (e.g. grinding, steaming, loading a machine, brewing), prefer model-led / action-led "
        "directions that show the product used CORRECTLY — do not default to 'pouring' unless the product is "
        "genuinely poured. "
        "Tailor each hero_moment to fit the specified DURATION (a 5s ad has time for one beat, a 15s ad has 6)."
    )

    try:
        resp = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            ),
            timeout=45.0,
        )
        text = "".join(getattr(block, "text", "") for block in resp.content).strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()
        raw = _json.loads(text)
        if not isinstance(raw, list) or len(raw) != 3:
            raise ValueError(f"expected 3 directions, got {type(raw).__name__}")
        out: list[dict] = []
        keys_seen = set()
        recs = 0
        for i, d in enumerate(raw):
            k = str(d.get("key", "")).upper().strip()
            if k not in ("A", "B", "C") or k in keys_seen:
                k = ["A", "B", "C"][i]
            keys_seen.add(k)
            mode = d.get("model_or_product_only")
            if mode not in ("model", "product_only"):
                mode = "product_only"
            rec = bool(d.get("recommended"))
            if rec:
                recs += 1
            _neg = d.get("negative_traits") or []
            if not isinstance(_neg, list):
                _neg = []
            _neg = [str(x)[:60] for x in _neg[:6]]
            if not _neg:
                _neg = ["soft fades", "dissolves", "calm composed coverage", "eye-level standard framing"]
            out.append({
                "key": k,
                "name": str(d.get("name", f"Direction {k}"))[:60],
                "vibe": str(d.get("vibe", ""))[:200],
                "hero_moment": str(d.get("hero_moment", ""))[:240],
                "model_or_product_only": mode,
                "recommended": rec,
                "camera_signature":   str(d.get("camera_signature", "") or "ARRI Alexa Mini LF, Cooke S7/i, 35-85mm, f/2.0")[:160],
                "lighting_signature": str(d.get("lighting_signature", "") or "single motivated key + soft fill, neutral 5600K")[:180],
                "style_grade":        str(d.get("style_grade", "") or "Kodak Vision3 250D cinematic grade, balanced contrast")[:180],
                "negative_traits":    _neg,
            })
        # Ensure exactly one recommended.
        if recs == 0:
            out[0]["recommended"] = True
        elif recs > 1:
            for d in out[1:]:
                d["recommended"] = False
        print(f"[cinematic_propose] LLM directions generated: {[d['name'] for d in out]}")
        return tag_direction_lip_intents(
            out,
            product_name=product_meta.get("name") or "",
            category=category,
            brief=brief,
            product_description=product_meta.get("description") or "",
            product_form=product_meta.get("product_form") or "",
        )
    except Exception as e:
        print(
            f"[cinematic_propose] LLM directions failed ({type(e).__name__}: {e}) — "
            f"falling back to static propose_directions"
        )
        return propose_directions(product_meta, brief=brief, category=category)


# Library of pro shot types — fed to Haiku so it picks from a known
# vocabulary instead of inventing fuzzy descriptions. Buckets are loose
# groupings (Haiku can pick any value, not just from its own bucket).
_SHOT_VOCAB: dict[str, list[str]] = {
    "static":   ["locked-off", "stable wide", "stable medium", "static low-angle"],
    "push":     ["slow push-in (8%)", "crash zoom", "dolly-in", "vertigo dolly-zoom"],
    "pull":     ["slow pull-out", "reveal pullback", "crane reveal"],
    "orbit":    ["360° orbit", "180° arc", "arc dolly", "circle-track"],
    "extreme":  ["worm's-eye low angle", "bird's-eye top-down", "Dutch tilt 20°", "inverted 180° roll"],
    "subject":  ["snorricam body-mount", "object-POV", "first-person handheld", "shoulder-mount tracking"],
    "macro":    ["anamorphic ECU off-axis", "240fps slo-mo macro", "phantom-macro stable", "lens-plane crossing"],
    "crane":    ["crane-down from high", "crane-up reveal", "jib swing"],
}


# ── LLM-generated beats (brief-aware, falls back to panel_beats_for) ──
async def generate_beats_from_brief(
    *,
    brief: str,
    direction: dict,
    category: str,
    num_panels: int = 6,
    duration_s: int = 15,
    aspect_ratio: str = "16:9",
    user_lang: str = "en",
    product_form: str = "",
    product_name: str = "",
    product_description: str = "",
    application_geometry_hint: str = "",
    allow_lip_application: bool = False,
    anthropic_client: Optional[Any] = None,
) -> list[dict]:
    """Generate num_panels storyboard beats tailored to the user's brief +
    chosen direction, via a small Haiku call.

    On ANY failure (no API key, parse error, timeout, rate limit) returns
    panel_beats_for(...) so the storyboard render is never blocked.
    """
    beat_s = duration_s / num_panels
    has_humans = direction.get("model_or_product_only") == "model"

    # Build a fresh client if caller didn't pass one — keeps callers from
    # needing to thread the singleton through ctx.
    client = anthropic_client
    if client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            print("[cinematic_storyboard] LLM beats skipped: ANTHROPIC_API_KEY not set")
            return panel_beats_for(direction["key"], category=category)
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic()
        except Exception as e:
            print(f"[cinematic_storyboard] LLM beats skipped: anthropic client init failed: {e}")
            return panel_beats_for(direction["key"], category=category)

    _shot_vocab_lines = "\n".join(f"  - {cat.upper()}: {', '.join(opts)}" for cat, opts in _SHOT_VOCAB.items())
    system = (
        "You write cinematic-ad storyboard panel beats with pro-cinematic specificity. "
        "Output STRICT JSON: a single array of objects, each with EXACT keys "
        "{\"scene\": \"2-3 WORD UPPERCASE LABEL\", "
        "\"action\": \"ONE concrete sentence describing what happens in frame (max 140 chars)\", "
        "\"sound\": \"SHORT music/SFX cue (max 60 chars)\", "
        "\"camera\": \"ONE camera move from the SHOT VOCAB list + degree/angle modifier (max 90 chars)\", "
        "\"lens\": \"focal length + aperture + DOF (e.g. '85mm anamorphic, f/2.0, shallow DOF') (max 60 chars)\", "
        "\"lighting\": \"ONE concrete lighting cue with angle + color/temp (max 90 chars)\", "
        "\"motion\": \"TIME-anchored motion physics — NEVER 'slow/fast/gentle' alone (e.g. 'hand rises over 2.5s', '240fps slo-mo', '6 deg/sec orbit') (max 90 chars)\"}. "
        "RULES: pick `camera` from the SHOT VOCAB below — do NOT invent fuzzy descriptions. "
        "Replace every adjective like 'slow / fast / gentle / subtle' with time/physics anchors. "
        "Each beat MUST be a HARD CUT — visually distinct shot, no smooth transitions. "
        "Beats together form a coherent narrative arc. "
        "PRODUCT FORM LOCK (critical): NEVER invent or rename the product's applicator or dispensing "
        "mechanism. Do NOT write 'twist cap off', 'wand', 'doe-foot', 'brush', 'bullet', 'pump', 'dropper', "
        "'reveals interior', 'unscrew', or any form/mechanic that is NOT stated in PRODUCT FORM. If PRODUCT "
        "FORM is given, every `action` must be consistent with that exact form. If PRODUCT FORM is empty, "
        "refer to it generically as 'the product' and keep its physical form abstract — the reference image "
        "defines the exact shape, cap, and applicator. The product is IDENTICAL in every beat; never morph it. "
        "PHYSICS PLAUSIBILITY (critical): every `action` must be physically possible — objects are solid and "
        "NEVER pass through skin, fingers, or flesh; hands keep correct anatomy (five fingers, natural proportions). "
        "Jewelry is worn by ENCIRCLING the finger or wrist (the finger passes through the ring band) — never push a "
        "ring through a finger or describe it intersecting the body. "
        "USAGE PLAUSIBILITY (critical): every `action` must match how the product is REALLY used (see PRODUCT USAGE "
        "FACTS). NEVER depict an end-state the product cannot directly produce. Example: a bag of coffee beans/grounds "
        "is opened and the grounds/beans are loaded into a grinder or coffee machine to BREW — you canNOT pour "
        "ready-made liquid coffee out of the bag; a finished cup is poured by the MACHINE, not the bag. Reason the "
        "same way for any product (capsule into its machine, powder scooped and mixed, etc.). If usage is unknown, "
        "show the product being handled/presented rather than inventing an impossible action. "
        + (
            "APPLICATION GEOMETRY (critical): on the application beat, lipstick/lip product is held upright; "
            "ONLY the bullet tip contacts the lower lip in a single stroke; flat base points away from the face; "
            "never apply to cheek, forearm, or hand; never press base-first. "
            if allow_lip_application else
            "APPLICATION GEOMETRY (critical): on any beat where the product touches skin, the product is held upright "
            "and gripped by the body; ONLY the dispensing/applying end contacts skin in a single stroke; the flat "
            "base/bottom/heel of the container NEVER touches skin and must point away from the body. Never depict "
            "the product inverted or pressed base-first against skin. "
        )
        + (
            "OUTPUT LANGUAGE: write `scene`, `action`, and `sound` in Spanish (es-ES). "
            "Keep `camera`, `lens`, `lighting`, and `motion` in English (cinematography terminology). "
            if user_lang == "es" else
            "OUTPUT LANGUAGE: write all human-readable fields in English. "
        )
        + "No prose, no markdown, no preamble.\n\n"
        f"SHOT VOCAB (pick `camera` from these per beat):\n{_shot_vocab_lines}"
    )
    if is_beauty_category(category):
        if allow_lip_application:
            system += (
                "\n\nLIP APPLICATION MODE (mandatory — direction requires on-lip use): "
                "The application beat MUST depict the lip product applied to the LOWER LIP in one fluid stroke — "
                "this is the hero moment. Professional beauty-ad ECU framing (mouth partial in frame). "
                "State upright product grip: bullet tip on lower lip, flat base away from face. "
                "NEVER apply to cheek, forearm, or back of hand. NEVER kiss, pout, tongue, or sexual framing. "
                "PANEL FRAMING: beat 1 = medium establishing shot with face visible and product nearby. "
                "Application beat = lip ECU with product stroke on lower lip. Final beat = product hero shot."
            )
        else:
            system += (
                "\n\nBEAUTY FAL SAFETY (mandatory when CATEGORY is beauty/skincare): "
                "NEVER mention lip, lips, mouth, kiss, pout, or tongue in any `action`. "
                "Product application MUST be on forearm, back of hand, or cheek — never on lips. "
                "On application beats, state explicit upright grip: dispensing tip toward skin, flat base away. "
                "No lip ECU, no mouth close-up, no product touching lips. "
                "PANEL FRAMING: beat 1 = medium establishing shot with face visible and product "
                "on a surface nearby (not at lips). Beats 2 through N-1 = hands/forearm/product "
                "macro only — explicitly state 'no face in frame'. Final beat = product hero or "
                "relaxed medium shot (face optional, never lip ECU)."
            )
    if is_jewelry_product(product_name, product_form, brief):
        # Structural avoidance of GPT Image 2's worst anatomy cases: a frozen
        # mid-insertion frame is visually identical to a ring clipping through
        # the finger, and interlaced hands produce extra/fused digits. Negative
        # instructions alone don't fix this — the beats must not REQUEST those
        # shots in the first place.
        system += (
            "\n\nJEWELRY SHOT SAFETY (mandatory — the product is jewelry): "
            "NEVER write a beat depicting the jewelry mid-slide, partially on, or in the act of "
            "being put onto a finger/wrist/neck — the put-on moment happens BETWEEN panels (hard "
            "cut). In each beat the jewelry is either (a) clearly separated from the body — held "
            "up between fingertips, resting in its box, or on a surface — or (b) already FULLY "
            "seated and worn. "
            "NEVER write interlaced, interlocked, entwined, intertwined, or clasped fingers/hands. "
            "At most ONE beat may show two hands, and they must be side by side with fingers "
            "relaxed and separated. "
            "Choose ONE wearing position (default: the left ring finger), name it explicitly, and "
            "reuse the IDENTICAL phrase in every beat where the jewelry is worn — it never moves "
            "to a different finger or hand. "
            "Prefer product-only macro beats for detail shots (jewelry on velvet, in its box, "
            "360-degree macro, light sweep) — at most 3 beats may include hands or skin."
        )
    _aspect_hint = {
        "9:16": "VERTICAL (9:16) — frame for vertical screens, close-ups + single-subject framing, avoid wide horizon shots",
        "4:3":  "CLASSIC (4:3) — boxier frame, works for documentary / vintage",
        "16:9": "HORIZONTAL (16:9) — wide cinematic framing, letterbox-friendly",
    }.get(aspect_ratio, "")
    user = (
        f"BRIEF:\n{(brief or '').strip()[:1200]}\n\n"
        f"DIRECTION: {direction.get('name','')} — {direction.get('vibe','')}\n"
        f"HERO MOMENT: {direction.get('hero_moment','')}\n"
        f"DIRECTION CAMERA SIG: {direction.get('camera_signature','')}\n"
        f"DIRECTION LIGHTING SIG: {direction.get('lighting_signature','')}\n"
        f"DIRECTION STYLE GRADE: {direction.get('style_grade','')}\n"
        f"CATEGORY: {category}\n"
        + (f"PRODUCT USAGE FACTS (how this product is really used — every action MUST respect this; do NOT depict an impossible use or end-state): {product_description.strip()[:240]}\n" if (product_description or "").strip() else "")
        + (f"PRODUCT FORM (the product's exact physical form — actions MUST match this, never invent a different applicator): {product_form.strip()[:240]}\n" if (product_form or "").strip() else "PRODUCT FORM: (unspecified — refer to it as 'the product' and keep its form abstract; the reference image defines the exact form)\n")
        + (f"APPLICATION GEOMETRY (mandatory on any beat where product touches skin): {application_geometry_hint.strip()[:240]}\n" if (application_geometry_hint or "").strip() else "")
        + (
            f"NARRATIVE ANCHOR: the application beat MUST realize this HERO MOMENT on the lips: "
            f"{direction.get('hero_moment', '')[:200]}\n"
            if allow_lip_application else ""
        )
        + f"HUMANS ALLOWED: {has_humans}\n"
        f"FORMAT: {aspect_ratio} ({_aspect_hint})\n"
        f"DURATION: {duration_s}s across {num_panels} beats (~{beat_s:.1f}s each)\n\n"
        f"Write the {num_panels} beats so the storyboard tells the story in the BRIEF using the "
        f"DIRECTION's aesthetic AND fits the FORMAT. Beat {num_panels} MUST be a clean cinematic HERO SHOT "
        f"of the product (or product+character) — no text, no typography, no logo lockup, no 'buy now', "
        f"no domain. Treat it as the final pure-image frame of the ad. "
        "If HUMANS ALLOWED is False, do NOT include people in any beat. Concrete actions only — no abstract metaphors. "
        "Lean on the DIRECTION's camera_signature / lighting_signature when picking per-beat camera + lens + lighting."
    )

    try:
        resp = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2000,
                system=system,
                messages=[{"role": "user", "content": user}],
            ),
            timeout=45.0,
        )
        text = "".join(getattr(block, "text", "") for block in resp.content).strip()
        # Strip ```json fences if Haiku adds them despite the instruction.
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0].strip()
        beats_raw = _json.loads(text)
        if not isinstance(beats_raw, list) or len(beats_raw) != num_panels:
            raise ValueError(
                f"expected {num_panels} beats, got "
                f"{len(beats_raw) if isinstance(beats_raw, list) else type(beats_raw).__name__}"
            )
        beats = []
        for i, b in enumerate(beats_raw, start=1):
            start = (i - 1) * beat_s
            end = i * beat_s
            beats.append({
                "n": i,
                "ts": f"[0:{start:04.1f}-0:{end:04.1f}]",
                "scene":    str(b.get("scene", "BEAT")).upper()[:30],
                "action":   str(b.get("action", ""))[:240],
                "sound":    str(b.get("sound", ""))[:100],
                "camera":   str(b.get("camera", "") or "locked-off stable medium")[:120],
                "lens":     str(b.get("lens", "") or "50mm, f/2.8, medium DOF")[:80],
                "lighting": str(b.get("lighting", "") or "single motivated key, neutral 5600K")[:120],
                "motion":   str(b.get("motion", "") or "continuous fluid arc over the full beat")[:120],
            })
        print(
            f"[cinematic_storyboard] LLM beats generated for direction={direction.get('key')} "
            f"brief_len={len(brief or '')}"
        )
        return beats
    except Exception as e:
        print(
            f"[cinematic_storyboard] LLM beats failed ({type(e).__name__}: {e}) — "
            f"falling back to hand-authored panel_beats_for"
        )
        return panel_beats_for(direction["key"], category=category)


# ── Storyboard prompt ─────────────────────────────────────────────────
_DURATION_TO_PANELS: dict[int, int] = {5: 3, 10: 4, 15: 6}


def panels_for_duration(duration_seconds: int) -> int:
    """Map allowed cinematic-ad durations to storyboard panel counts."""
    return _DURATION_TO_PANELS.get(int(duration_seconds), 6)


def is_beauty_category(category: str) -> bool:
    return (category or "").lower() in _BEAUTY_CATS


_LIP_APPLICABLE_KEYWORDS = (
    "lipstick", "lipgloss", "lip gloss", "lip stain", "lip tint", "lip balm",
    "lip oil", "lip color", "lip colour", "lip product", "rouge",
)


_LIP_USE_SIGNALS = (
    "lip application", "across her lips", "across lips", "across the lips",
    "on lips", "on her lips", "on the lip", "lip stroke", "lip moment",
    "lip application moment", "lip swipe",
)


def _direction_lip_blob(direction: dict) -> str:
    return (
        f"{direction.get('name', '')} {direction.get('hero_moment', '')} "
        f"{direction.get('vibe', '')}"
    ).lower()


def _blob_implies_lip_application(blob: str) -> bool:
    """True when direction text explicitly describes on-lip application."""
    if any(s in blob for s in _LIP_USE_SIGNALS):
        return True
    if _re.search(
        r"\b(lip application|across (?:her )?lips|on (?:her )?lips|on the lip|lip moment|lip swipe)\b",
        blob,
    ):
        return True
    return bool(
        _re.search(r"\blips?\b", blob) and _re.search(r"\b(apply|appli|glide|stroke|swipe)\b", blob)
    )


def is_lip_applicable_product(
    product_name: str,
    category: str,
    brief: str = "",
    *,
    product_description: str = "",
    product_form: str = "",
) -> bool:
    """True when the product is a lip color product (lipstick, gloss, tint, etc.)."""
    text = (
        f"{product_name} {brief} {product_description} {product_form} {category}"
    ).lower()
    keyword_hit = any(kw in text for kw in _LIP_APPLICABLE_KEYWORDS)
    beauty_rouge = bool(_re.search(r"\brouge\b", text)) and is_beauty_category(category)
    beauty_lip_token = bool(_re.search(r"\blip\b", text)) and is_beauty_category(category)
    if not (keyword_hit or beauty_rouge or beauty_lip_token):
        return False
    if is_beauty_category(category) or category == "beauty":
        return True
    return infer_category_from_text(text) == "beauty"


def direction_implies_lip_scene(
    direction: dict,
    category: str,
    *,
    has_humans: Optional[bool] = None,
) -> bool:
    """True when a model-led beauty direction's name/hero explicitly calls for lips.

    Does NOT require the product display name to contain 'lipstick' — a direction
    like 'Lip Swipe Moment' on Guerlain Rouge G still qualifies.
    """
    if has_humans is None:
        has_humans = direction.get("model_or_product_only") == "model"
    if not has_humans or not is_beauty_category(category):
        return False
    return _blob_implies_lip_application(_direction_lip_blob(direction))


def direction_requires_lip_application(
    direction: dict,
    product_name: str,
    category: str,
    brief: str = "",
    *,
    product_description: str = "",
    product_form: str = "",
) -> bool:
    """True when the chosen direction calls for on-lip application."""
    has_humans = direction.get("model_or_product_only") == "model"
    if direction_implies_lip_scene(direction, category, has_humans=has_humans):
        return True
    if not is_lip_applicable_product(
        product_name,
        category,
        brief,
        product_description=product_description,
        product_form=product_form,
    ):
        return False
    return _blob_implies_lip_application(_direction_lip_blob(direction))


def tag_direction_lip_intents(
    directions: list[dict],
    *,
    product_name: str,
    category: str,
    brief: str = "",
    product_description: str = "",
    product_form: str = "",
) -> list[dict]:
    """Embed requires_lip_application on each direction at propose time."""
    for d in directions:
        d["requires_lip_application"] = direction_requires_lip_application(
            d,
            product_name,
            category,
            brief,
            product_description=product_description,
            product_form=product_form,
        )
    return directions


def resolve_lip_application_intent(
    direction: dict,
    product_meta: dict,
    category: str,
    brief: str = "",
    *,
    cached_intents: Optional[dict] = None,
    direction_key: str = "",
) -> bool:
    """Resolve lip bypass intent: embedded direction flag > session cache > recompute."""
    if direction.get("requires_lip_application"):
        return True
    dk = (direction_key or direction.get("key") or "").upper()
    if cached_intents and dk in cached_intents:
        return bool(cached_intents[dk])
    return direction_requires_lip_application(
        direction,
        product_meta.get("name") or "",
        category,
        brief,
        product_description=product_meta.get("description") or "",
        product_form=product_meta.get("product_form") or "",
    )


_PRODUCT_FORM_PHYSICAL_KEYWORDS = (
    "cap", "tube", "wand", "bullet", "applicator", "dispens", "packag",
    "container", "bottle", "jar", "pump", "dropper", "cylind", "hexagon",
    "glass", "plastic", "label", "matte", "texture", "shape", "material",
)

_APPLICATION_GEOMETRY_CLAUSE = (
    "hold product upright; only the dispensing/applying end contacts skin in one stroke; "
    "flat base/bottom never touches skin"
)

_LIP_APPLICATION_GEOMETRY_CLAUSE = (
    "hold lipstick upright; bullet tip glides across lower lip in one stroke; "
    "flat base away from face; professional cosmetic ad framing"
)

_JEWELRY_GEOMETRY_CLAUSE = (
    "the band encircles the finger and slides fully onto it (the finger passes through "
    "the ring hole); the ring never intersects, clips, or passes through flesh; preserve "
    "natural hand anatomy with five fingers"
)

_JEWELRY_KEYWORDS = (
    "ring", "engagement ring", "wedding band", "wedding ring", "bracelet",
    "necklace", "earring", "pendant", "bangle", "anklet", "watch", "cufflink",
    "brooch", "tiara",
)

_APPLICATION_ACTION_RE = _re.compile(
    r"\b(apply|appli|glide|stroke|swipe|dispens)\b",
    _re.I,
)
_GEOMETRY_KEYWORDS_RE = _re.compile(
    r"\b(upright|dispens|tip|base|bottom|heel|invert|lower lip)\b",
    _re.I,
)

_FORBIDDEN_SEXUAL_FRAMING_RE = _re.compile(r"\b(kiss|pout|tongue)\b", _re.I)


def is_substantive_product_form(product_form: str, product_name: str = "") -> bool:
    """True when product_form carries real physical structure, not just the product name."""
    pf = (product_form or "").strip()
    if not pf or pf.lower() == "the product":
        return False
    if product_name and pf.strip().lower() == product_name.strip().lower():
        return False
    if len(pf) < 30:
        low = pf.lower()
        if not any(kw in low for kw in _PRODUCT_FORM_PHYSICAL_KEYWORDS):
            return False
    return True


def sanitize_product_form(
    product_form: str,
    *,
    product_name: str = "",
    description: str = "",
) -> str:
    """Drop name-only fallbacks so beats don't treat 'lipgloss' as physical form."""
    pf = str(product_form or "").strip()
    if is_substantive_product_form(pf, product_name):
        return pf[:240]
    desc = str(description or "").strip()
    if is_substantive_product_form(desc, product_name):
        return desc[:240]
    return ""


def resolve_sanitized_product_form(product: dict) -> str:
    """Resolve visual_description/description into a substantive product_form string."""
    name = product.get("name") or ""
    raw = ""
    try:
        from prompts.product_refs import resolve_product_visual_description
        raw = resolve_product_visual_description(product) or ""
    except Exception as e:
        print(f"[cinematic_ad] product form resolve failed: {e}")
    return sanitize_product_form(raw, product_name=name, description=product.get("description") or "")


def is_jewelry_product(product_name: str, product_form: str = "", brief: str = "") -> bool:
    """True when the product is jewelry (ring, bracelet, etc.).

    Used only for usage-geometry/anatomy guidance — does NOT add a direction-table
    category, so propose/direction routing is unaffected.
    """
    text = f"{product_name} {product_form} {brief}".lower()
    return any(_re.search(rf"\b{_re.escape(kw)}\b", text) for kw in _JEWELRY_KEYWORDS)


def infer_application_geometry_hint(
    product_form: str,
    product_name: str,
    category: str,
    *,
    has_humans: bool = True,
    allow_lip_application: bool = False,
    brief: str = "",
) -> str:
    """Short orientation hint for beats/storyboard application panels."""
    if not has_humans:
        return ""
    if allow_lip_application:
        if is_substantive_product_form(product_form, product_name):
            return f"{product_form.strip()[:180]}. {_LIP_APPLICATION_GEOMETRY_CLAUSE}"
        return _LIP_APPLICATION_GEOMETRY_CLAUSE
    # Jewelry is worn (encircles finger/wrist) — the beauty "dispensing end"
    # clause is nonsensical and causes through-finger deformation.
    if is_jewelry_product(product_name, product_form, brief):
        if is_substantive_product_form(product_form, product_name):
            return f"{product_form.strip()[:180]}. {_JEWELRY_GEOMETRY_CLAUSE}"
        return _JEWELRY_GEOMETRY_CLAUSE
    if is_beauty_category(category):
        if is_substantive_product_form(product_form, product_name):
            return f"{product_form.strip()[:180]}. {_APPLICATION_GEOMETRY_CLAUSE}"
        return _APPLICATION_GEOMETRY_CLAUSE
    # Non-beauty, non-jewelry: don't emit the beauty dispensing clause. The
    # ANATOMY & PHYSICS LOCK in the storyboard prompt covers solidity.
    if is_substantive_product_form(product_form, product_name):
        return product_form.strip()[:180]
    return ""


# Lip/mouth wording that triggers Fal GPT Image 2 content checkers on beauty ads.
_LIP_MOUTH_RE = _re.compile(
    r"\b(lower lip|upper lip|lips?|mouth|kiss|pout|tongue|balm[\s-]glossed|lip[\s-]rests?)\b",
    _re.I,
)
_ECU_LIP_CAMERA_RE = _re.compile(r"anamorphic\s+ECU|ECU\s+off[\s-]axis", _re.I)


_FACE_IN_FRAME_RE = _re.compile(
    r"\b(face|portrait|profile|head|woman|man|person|model|she|he|her|his)\b",
    _re.I,
)


def sanitize_beats_for_fal(
    beats: list[dict],
    *,
    category: str,
    has_humans: bool,
    aggressive: bool = False,
    hands_only: bool = False,
    allow_lip_application: bool = False,
) -> list[dict]:
    """Rewrite beauty panel beats to pass Fal content moderation.

    Standard mode fixes obvious lip/mouth ECU language. Aggressive mode (retry
    path) forces forearm/hand application on any beat that still looks risky.
    hands_only mode crops application panels to hands/product with no face in frame
    (panel 1 may keep an establishing medium shot with face visible).
    """
    if not is_beauty_category(category) or not has_humans:
        return beats

    _safe_apply = (
        "hand holds product upright; dispensing tip glides across forearm in one stroke; "
        "flat base points away from skin, never contacts skin (no mouth contact)"
    )
    _safe_hold = (
        "product held gently in hand near the cheek, warm window light, no lip or mouth contact"
    )
    _hands_only_action = (
        "tight crop on hands and product only, no face visible in frame, "
        "warm natural light on skin and packaging"
    )
    out: list[dict] = []
    changed = False
    for b in beats:
        beat = dict(b)
        action = str(beat.get("action") or "")
        camera = str(beat.get("camera") or "")
        orig_action, orig_camera = action, camera
        panel_n = int(beat.get("n") or 0)
        risky = bool(_LIP_MOUTH_RE.search(action)) or bool(_ECU_LIP_CAMERA_RE.search(camera))

        if hands_only and panel_n > 1:
            if _FACE_IN_FRAME_RE.search(action) or "face" in action.lower():
                action = _hands_only_action
                camera = "50mm close-up, hands and product in frame"
                changed = True
            elif "hand" not in action.lower() and "forearm" not in action.lower():
                action = f"{_hands_only_action}, {action[:120]}"
                camera = camera or "50mm close-up, hands and product in frame"
                changed = True

        if allow_lip_application:
            if _FORBIDDEN_SEXUAL_FRAMING_RE.search(action):
                action = _FORBIDDEN_SEXUAL_FRAMING_RE.sub("", action).strip()
                changed = True
        elif aggressive or risky:
            if aggressive and (_LIP_MOUTH_RE.search(action) or "lip" in action.lower() or "mouth" in action.lower()):
                action = _safe_apply if "glide" in action.lower() or "apply" in action.lower() or "stroke" in action.lower() else _safe_hold
            else:
                action = _LIP_MOUTH_RE.sub("soft skin", action)
                action = action.replace("lower lip", "forearm")
                action = action.replace("across lips", "across forearm")
                action = action.replace("lip rests", "hand rests product nearby")
            if _ECU_LIP_CAMERA_RE.search(camera):
                camera = "50mm close-up, product in hand"
            changed = True

        geometry_clause = _LIP_APPLICATION_GEOMETRY_CLAUSE if allow_lip_application else _APPLICATION_GEOMETRY_CLAUSE
        if _APPLICATION_ACTION_RE.search(action) and not _GEOMETRY_KEYWORDS_RE.search(action):
            action = f"{action.rstrip('.')}; {geometry_clause}"
            changed = True

        beat["action"] = action[:240]
        beat["camera"] = camera[:120]
        out.append(beat)
    if changed or aggressive or hands_only:
        print(
            f"[cinematic_storyboard] beats sanitized for Fal "
            f"(aggressive={aggressive}, hands_only={hands_only})"
        )
    return out


# Jewelry beat hazards: a frozen mid-insertion frame renders as the ring
# clipping through the finger, and interlaced hands produce extra/fused digits.
_JEWELRY_MID_INSERTION_RE = _re.compile(
    r"\b(slid(?:e|es|ing)\s+(?:fully\s+)?onto|begins?\s+to\s+slide|"
    r"lowers?\s+.{0,30}?\btoward|push(?:es|ed)?\s+onto|glid(?:e|es|ing)\s+onto|"
    r"slips?\s+(?:the\s+\w+\s+)?onto|placing\s+.{0,20}?\bonto\s+.{0,20}?\bfinger|"
    r"halfway\s+(?:on|onto)|partially\s+(?:on|onto|worn))\b",
    _re.I,
)
_JEWELRY_INTERLOCK_RE = _re.compile(
    r"\b(interlaced?|interlock(?:ed|ing)?|entwin(?:e|es|ed|ing)|"
    r"intertwin(?:e|es|ed|ing)|clasp(?:ed|ing)?)\b",
    _re.I,
)
_JEWELRY_FINGER_REF_RE = _re.compile(
    r"\b(?:receiving|her|his|the)\s+(?:ring\s+)?finger\b",
    _re.I,
)

_JEWELRY_SEATED_ACTION = (
    "ring fully seated on the left ring finger, hand at rest, diamonds catching light"
)
_JEWELRY_HANDS_SAFE_ACTION = (
    "two hands rest side by side, fingers relaxed and separated, "
    "ring visible on the left ring finger"
)


def sanitize_beats_for_jewelry(
    beats: list[dict],
    *,
    product_name: str = "",
    product_form: str = "",
    brief: str = "",
) -> list[dict]:
    """Deterministic post-pass for jewelry beats — the LLM beat generator can
    still emit mid-insertion or interlocked-hands shots despite the JEWELRY
    SHOT SAFETY system rules. Rewrites those actions into safe equivalents and
    normalizes the wearing finger so the ring never jumps fingers across panels.

    No-op when the product isn't jewelry.
    """
    if not is_jewelry_product(product_name, product_form, brief):
        return beats

    out: list[dict] = []
    changed = False
    for b in beats:
        beat = dict(b)
        action = str(beat.get("action") or "")
        orig = action

        if _JEWELRY_MID_INSERTION_RE.search(action):
            action = _JEWELRY_SEATED_ACTION
        if _JEWELRY_INTERLOCK_RE.search(action):
            action = _JEWELRY_HANDS_SAFE_ACTION
        action = _JEWELRY_FINGER_REF_RE.sub("left ring finger", action)

        if action != orig:
            changed = True
        beat["action"] = action[:240]
        out.append(beat)

    if changed:
        print("[cinematic_storyboard] beats sanitized for jewelry (mid-insertion/interlock/finger-lock)")
    return out


def _grid_for(num_panels: int, aspect_ratio: str) -> tuple[int, int]:
    """Return (cols, rows) for a storyboard sheet given panel count + aspect.

    The grid is chosen so each panel CELL matches the target video aspect, not
    the whole sheet. A vertical (9:16) video needs TALL/vertical cells, so we lay
    panels out WIDE (more columns). A horizontal (16:9 / 4:3) video needs WIDE
    cells, so we lay panels out TALL (more rows).
    """
    vertical = aspect_ratio == "9:16"
    if num_panels == 3:
        return (3, 1) if vertical else (1, 3)
    if num_panels == 4:
        return (2, 2)
    return (3, 2) if vertical else (2, 3)


def _panel_orientation_label(aspect_ratio: str) -> str:
    if aspect_ratio == "9:16":
        return "9:16 vertical orientation"
    if aspect_ratio == "4:3":
        return "4:3 standard orientation"
    return "16:9 landscape orientation"


# Per-panel base cell sized to the TARGET video aspect ratio. The storyboard
# sheet is built from these cells so every panel keeps the video's orientation.
_STORYBOARD_PANEL_CELL = {
    "9:16": (720, 1280),
    "4:3": (1024, 768),
    "16:9": (1280, 720),
}
_STORYBOARD_HEADER_PX = 140      # mono header band above the grid
_STORYBOARD_CAPTION_PX = 280     # 4-line caption block beneath each panel row
_STORYBOARD_MAX_SIDE = 2560      # GPT Image 2 longest-side cap
_STORYBOARD_MIN_SIDE = 512


def _round16(v: float) -> int:
    return max(_STORYBOARD_MIN_SIDE, int(round(v / 16.0)) * 16)


def storyboard_sheet_size(num_panels: int, aspect_ratio: str) -> tuple[int, int]:
    """Compute (width, height) for a storyboard sheet whose per-panel CELLS match
    the target video aspect ratio.

    The grid (from `_grid_for`) lays vertical (9:16) ads out wide and horizontal
    ads out tall, so each cell carries the video orientation. Sheet width is the
    columns times the panel cell width; height adds a header band plus a caption
    band per row. The longest side is clamped to 2560 (scaling both dims), and
    both dims are rounded to multiples of 16 (floor 512).
    """
    cols, rows = _grid_for(num_panels, aspect_ratio)
    panel_w, panel_h = _STORYBOARD_PANEL_CELL.get(aspect_ratio, _STORYBOARD_PANEL_CELL["16:9"])

    width = cols * panel_w
    height = _STORYBOARD_HEADER_PX + rows * (panel_h + _STORYBOARD_CAPTION_PX)

    longest = max(width, height)
    if longest > _STORYBOARD_MAX_SIDE:
        scale = _STORYBOARD_MAX_SIDE / float(longest)
        width *= scale
        height *= scale

    return (_round16(width), _round16(height))


def build_storyboard_prompt(
    *,
    brand: str,
    product: str,
    direction: dict,
    tagline: str,
    domain: str,
    category: str,
    num_panels: int = 6,
    duration_s: int = 15,
    aspect_ratio: str = "16:9",
    beats: Optional[list[dict]] = None,
    has_influencer_ref: bool = False,
    moderation_profile: str = "sharp",
    product_form: str = "",
    product_description: str = "",
    application_geometry_hint: str = "",
    allow_lip_application: bool = False,
    brief: str = "",
) -> str:
    has_humans = direction.get("model_or_product_only") == "model"
    is_jewelry = is_jewelry_product(product, product_form, brief)
    beat_s = duration_s / num_panels

    # Anatomy + physics guardrail — only meaningful when a person/hands appear.
    # GPT Image 2 otherwise renders rings through fingers and warps hands on the
    # tight usage/macro panels. No negative-prompt support, so it lives in-prompt.
    anatomy_lock = (
        "ANATOMY & PHYSICS LOCK: render all hands, fingers, and bodies with correct human "
        "anatomy — exactly five fingers per hand, natural joints and proportions, no fused, "
        "extra, missing, or warped digits. Objects are solid and obey physics: the product "
        "NEVER passes through skin, fingers, or flesh. A ring/band encircles the finger with "
        "the finger through the hole; a bracelet encircles the wrist — jewelry never clips "
        "through or merges with the body. On macro and close-up usage panels keep all limbs "
        "and contact points anatomically correct and physically plausible."
        + (
            " FINGER LOCK: the ring is worn on the LEFT RING FINGER in every panel where it "
            "is worn — never a different finger or hand across panels. NEVER depict the ring "
            "mid-slide or partially on a finger: in each panel it is either clearly separated "
            "from the hand or fully seated at the finger base. NEVER render interlaced or "
            "interlocked fingers; when two hands appear they are side by side with all "
            "fingers separated and visible."
            if is_jewelry else ""
        )
        + "\n\n"
    ) if has_humans else ""
    if beats is None:
        beats = panel_beats_for(direction["key"], category=category)
    cols, rows = _grid_for(num_panels, aspect_ratio)
    panel_orient = _panel_orientation_label(aspect_ratio)
    grid_text = f"{cols} columns by {rows} rows"
    # Describe the OVERALL sheet shape from the computed dimensions, not the video
    # aspect — a 9:16 ad now lays panels out wide, so the sheet itself is landscape
    # even though each panel cell is vertical.
    _sheet_w, _sheet_h = storyboard_sheet_size(num_panels, aspect_ratio)
    if _sheet_w > _sheet_h * 1.05:
        sheet_orient = "in landscape (wider than tall)"
    elif _sheet_h > _sheet_w * 1.05:
        sheet_orient = "in portrait (taller than wide)"
    else:
        sheet_orient = "roughly square"

    if allow_lip_application:
        _fal_safety = (
            "LIP APPLICATION MODE — on the application panel, product contacts LIPS ONLY "
            "(lower lip stroke, professional beauty ECU). Professional cosmetic ad framing. "
            "NEVER kiss, pout, tongue, or sexual framing. NEVER apply to cheek or forearm.\n\n"
        )
    else:
        _fal_safety = (
            "FAL SAFETY — product application on forearm, back of hand, or "
            "cheek only. NEVER lip/mouth ECU, NEVER product touching lips.\n\n"
        )

    # Beauty uses progressive moderation profiles (lips_allowed → sharp → hands_only →
    # product_ref_only → blur_fallback). Non-beauty always sharp @Image2.
    if has_humans and is_beauty_category(category):
        profile = moderation_profile if moderation_profile in (
            "sharp", "hands_only", "product_ref_only", "blur_fallback", "lips_allowed",
        ) else "sharp"
        use_image2 = has_influencer_ref and profile != "product_ref_only"

        if profile == "blur_fallback":
            if use_image2:
                character_lock = (
                    "CRITICAL — CHARACTER LOCK (for panels with a person): @Image2 "
                    "anchors hair, jawline, skin tone, and clothing. Render the face "
                    "center as SOFT WARM-TONED DIFFUSED BLUR (Sofia Coppola-style) — "
                    "hair edges and jawline crisp, no discernible eyes/nose/mouth in "
                    "storyboard panels.\n\n"
                    + _fal_safety
                )
            else:
                character_lock = (
                    "CRITICAL — CHARACTER LOCK (for panels with a person): a woman in "
                    "her late twenties, soft natural beauty. Render the FACE as SOFT "
                    "WARM-TONED DIFFUSED BLUR — hair edges and jawline crisp, no "
                    "discernible eyes/nose/mouth.\n\n"
                    + _fal_safety
                )
        elif profile == "hands_only":
            if use_image2:
                character_lock = (
                    "CRITICAL — CHARACTER LOCK: @Image2 anchors identity. Panel 01 ONLY "
                    "may show a medium establishing shot with face FULLY SHARP and IN FOCUS "
                    "(product on surface nearby, not at lips). Panels 02–"
                    f"{num_panels:02d} are tight crops on hands/forearm/product ONLY — "
                    "NO face visible in frame.\n\n"
                    + _fal_safety
                )
            else:
                character_lock = (
                    "CRITICAL — CHARACTER LOCK: a single consistent woman in her late "
                    "twenties. Panel 01 ONLY may show a medium establishing shot with face "
                    "FULLY SHARP. Panels 02–"
                    f"{num_panels:02d} are hands/forearm/product crops ONLY — NO face in frame.\n\n"
                    + _fal_safety
                )
        elif profile == "product_ref_only" or not use_image2:
            character_lock = (
                "CRITICAL — CHARACTER LOCK (for panels with a person): a single "
                "consistent woman in her late twenties, natural lived-in appearance. "
                "Render the FACE FULLY, SHARP, IN FOCUS in panel 01 only; application "
                "panels are hands-only crops with no face in frame. Same person across "
                "every panel where she appears.\n\n"
                + _fal_safety
            )
        elif profile == "lips_allowed" or profile == "sharp":
            if use_image2:
                character_lock = (
                    "CRITICAL — CHARACTER LOCK (for panels with a person): locked to "
                    "@Image2 — preserve exact face geometry, hair color/style, skin tone, "
                    "and clothing. Render the FACE FULLY, SHARP, IN FOCUS — same person "
                    "across every panel. Eyes, nose, mouth all clearly drawn. "
                    "@Image2 is the identity anchor; do not invent a different face.\n\n"
                    + _fal_safety
                )
            else:
                character_lock = (
                    "CRITICAL — CHARACTER LOCK (for panels with a person): a single "
                    "consistent individual in their late twenties, natural lived-in "
                    "appearance. Render the FACE FULLY, SHARP, IN FOCUS — same person "
                    "across every panel.\n\n"
                    + _fal_safety
                )
    elif has_humans and has_influencer_ref:
        character_lock = (
            "CRITICAL — CHARACTER LOCK (for panels with a person): locked to "
            "@Image2 — preserve exact face geometry, hair color/style, skin tone, "
            "and clothing. Render the FACE FULLY, SHARP, IN FOCUS — same person "
            "across every panel. Eyes, nose, mouth all clearly drawn. "
            "@Image2 is the identity anchor for the character; do not invent a "
            "different face.\n\n"
        )
    elif has_humans:
        character_lock = (
            "CRITICAL — CHARACTER LOCK (for panels with a person): a single "
            "consistent individual in their late twenties, natural lived-in "
            "appearance. Render the FACE FULLY, SHARP, IN FOCUS — same person "
            "across every panel (same face geometry, hair, skin tone, clothing). "
            "Eyes, nose, mouth all clearly drawn.\n\n"
        )
    else:
        character_lock = ""

    # 4-line caption per panel (SCENE / CAMERA / ACTION / SOUND) so the sheet
    # reads as a pro shot list rather than generic action descriptions.
    beats_block = "\n".join(
        f"{b['n']:02d} {b['ts']} SCENE: {b['scene']} | CAMERA: {b.get('camera','')} | ACTION: {b['action']} | SOUND: {b['sound']}"
        for b in beats
    )

    # Aspect-specific composition note — what framing rules each ratio expects.
    aspect_note = {
        "9:16": "Composition: vertical center-frame, subject fills ~60% of frame height, avoid wide horizon shots — every panel works for TikTok/Reels.",
        "4:3":  "Composition: classical centered framing, balanced negative space, documentary-leaning.",
        "16:9": "Composition: cinematic letterbox framing, wide establishing shots welcome.",
    }.get(aspect_ratio, "")

    # Direction signatures roll up into a single AESTHETIC block — gives GPT
    # Image 2 the specific grade + lighting + camera intent in one go.
    aesthetic_block = (
        f"AESTHETIC — STYLE GRADE: {direction.get('style_grade', direction['vibe'])}\n"
        f"AESTHETIC — LIGHTING: {direction.get('lighting_signature', 'natural motivated light')}\n"
        f"AESTHETIC — CAMERA SIG: {direction.get('camera_signature', '50mm cinematic')}\n"
        f"AESTHETIC — VIBE: {direction['vibe']} Lived-in, intimate, never sterile.\n"
    )

    return (
        f"A single image: a {num_panels}-panel cinematic ad storyboard sheet, "
        f"{grid_text}, on an off-white paper background with a thin black "
        f"border. Each panel is a cinematic film still in {panel_orient}. "
        + (
            "EVERY panel image is a TALL VERTICAL 9:16 still — taller than it is wide. Do NOT render wide, "
            "landscape, or 16:9-cropped panels; compose each shot for a vertical phone screen. "
            if aspect_ratio == "9:16" else ""
        )
        + f"Above the grid, a bold mono header reads:\n\n"
        f"STORYBOARD: {direction['name'].upper()} — {duration_s}s SPOT — "
        f"BRAND: {brand}     PRODUCT: {product}\n\n"
        f"Each panel has a small \"01\"–\"{num_panels:02d}\" number top-left AND a "
        f"clean monospace timestamp badge top-right (e.g. [0:00–0:02.5]). Beneath "
        f"each panel sits a 4-line monospace caption block:\n"
        f"  SCENE: <label>\n"
        f"  CAMERA: <camera move + lens>\n"
        f"  ACTION: <what happens in frame>\n"
        f"  SOUND: <music or SFX cue>\n\n"
        f"PRODUCT LOCK: subject is locked to @Image1 — preserve exact shape, color, materials, "
        f"and surface texture across every panel. The product never deforms, never changes color, "
        f"never appears in degraded form. THIS REFERENCE IS THE IDENTITY ANCHOR. "
        f"@Image1 is the SOLE authority on the product's physical form, applicator, cap, and packaging. "
        f"If any ACTION caption below implies a different applicator or mechanic (wand, doe-foot, brush, "
        f"bullet, pump, dropper, 'twist cap off', 'reveals interior'), IGNORE the caption's form and render "
        f"the product EXACTLY as @Image1. Caption text NEVER overrides the reference image's form. "
        + (f"CONFIRMED PRODUCT FORM (matches @Image1): {product_form.strip()[:240]}. " if (product_form or "").strip() else "")
        + f"EVERY panel MUST show the IDENTICAL product from @Image1 — same silhouette, cap, "
        f"applicator, color, and label in all {num_panels} panels. NEVER substitute a different "
        f"item: no lipstick bullet, no doe-foot wand, no sponge, no brush, no alternate bottle or "
        f"tube. The product's form, cap, and applicator are identical in all panels; never morph it, "
        f"never open it into a different object, never swap applicator type. On any application or "
        f"usage beat, the SAME @Image1 product is the ONLY applicator shown — do not invent a second product. "
        f"On macro, ECU, slow-motion, or in-use panels the product is a 1:1 faithful copy of @Image1 — "
        f"identical proportions, label/text placement, color, and materials. Do NOT simplify, restyle, or "
        f"re-proportion it because it is in motion, partially framed, or close to camera; product fidelity is "
        f"HIGHEST on the usage/action panel. "
        + (
            f"USAGE TRUTH (how this product is really used — every panel MUST respect this; NEVER depict an "
            f"impossible use or an end-state the product cannot directly produce, e.g. coffee beans/grounds are "
            f"loaded into a grinder/machine to brew, NOT poured as liquid from the bag): {product_description.strip()[:240]}. "
            if (product_description or "").strip() else ""
        )
        + (
            "APPLICATION GEOMETRY: on the application panel, product contacts LIPS ONLY (lower lip stroke); "
            "bullet tip on lower lip, flat base away from face; never cheek, forearm, or base-first. "
            if allow_lip_application else
            "USAGE GEOMETRY: the product is worn by encircling the finger/wrist; the finger passes through "
            "the band; never render the ring intersecting, clipping, or passing through flesh; preserve "
            "natural hand anatomy. "
            if is_jewelry else
            "APPLICATION GEOMETRY: when a panel shows the product touching skin, only the dispensing/applying end "
            "may contact skin; product held upright, gripped by the body; flat base/bottom/heel NEVER pressed "
            "against skin; never invert the product or apply base-first. "
            if is_beauty_category(category) else
            ""
        )
        + (f"{application_geometry_hint.strip()[:240]}. " if (application_geometry_hint or "").strip() else "")
        + f"CAP STATE LOCK: @Image1 cap open/closed state is canonical. Non-application panels match @Image1 "
        f"exactly — if @Image1 shows the cap on, every reveal/spin/hero panel keeps the cap on. Never remove "
        f"the cap in reveal or spin panels unless @Image1 is already open. Application panels may show the "
        f"product in use only at the dispensing end without morphing the tube body. "
        f"Render ALL text that exists on the product itself (brand name, product name, labels, "
        f"packaging copy, nutritional info, ingredient lists) crisply, sharply, and FULLY READABLE "
        f"at 100% — match the typography, color, and placement from @Image1 exactly. Product-native "
        f"text is part of the product identity and must look professional, not blurred or smudged.\n\n"
        f"NO ADDED TEXT OVERLAYS INSIDE ANY PANEL. Do NOT add any tagline, headline, CTA, website "
        f"domain, 'buy now' button, lower-third caption, or any typographic element that isn't ALREADY "
        f"printed on the product itself. Panel {num_panels:02d} must be a clean cinematic hero shot "
        f"with NO end-card text overlay, NO logo lockup graphic, NO promotional copy — just the "
        f"product (with its own native packaging text intact) in the scene. The header above the "
        f"grid and the caption blocks below each panel are the ONLY non-product text in this image.\n\n"
        f"{anatomy_lock}"
        f"{character_lock}"
        f"{aesthetic_block}"
        f"{aspect_note}\n\n"
        f"PANELS (timestamped for a {duration_s}-second spot @ {beat_s:.1f}s per beat — HARD CUTS between every panel):\n"
        f"{beats_block}\n\n"
        # No end-card text overlay — panel N is a pure hero image (see "NO TEXT OVERLAYS" rule above).

        f"Render the full storyboard as ONE single image, {cols}×{rows} grid {sheet_orient}. "
        f"Captions legible in monospace. No watermarks. No extra text beyond what is "
        f"specified. Same product silhouette every panel."
    )


# ── Seedance prompts ──────────────────────────────────────────────────
def _aspect_composition_rule(aspect_ratio: str) -> str:
    return {
        "9:16": "Vertical center-frame compositions, subject fills ~60% of frame height, avoid wide horizon shots",
        "4:3":  "Classical centered framing, balanced negative space",
        "16:9": "Cinematic letterbox framing, wide establishing shots welcome",
    }.get(aspect_ratio, "Cinematic framing")


def build_seedance_prompt(
    *,
    brand: str,
    product: str,
    direction: dict,
    duration_s: int = 15,
    has_humans: bool,
    has_storyboard: bool = True,
    beats: Optional[list[dict]] = None,
    aspect_ratio: str = "16:9",
    has_influencer_ref: bool = False,
) -> str:
    """"Animate this storyboard" prompt. The storyboard image (Image1) anchors
    composition / product / character per panel; when beats are available a
    compact time-blocked "shot direction" block (action + camera + motion, one
    line per panel) gives Seedance explicit cinematography so the motion isn't
    generic. Beats omit lens/lighting/sound — those are baked into the panels,
    and the full pillar-structured prompts over-constrained Seedance and
    caused stuttery motion / hallucinations in the 9:16 regression. When beats
    are missing (cache miss after restart) we fall back to the prior short
    40-70 word prompt so animation is never blocked.
    """
    if has_storyboard:
        panel_count = len(beats) if beats else 6
        if has_humans and has_influencer_ref:
            human_line = (
                " @Image3 is the character — preserve exact face, hair, and skin tone "
                "in every shot where a person appears."
            )
        elif has_humans:
            human_line = (
                " Keep the character consistent across all shots — same person, same face."
            )
        else:
            human_line = ""
        base = (
            f"Animate the {panel_count}-panel storyboard in @Image1 in order as a continuous "
            f"{duration_s}s {aspect_ratio} cinematic ad with hard cuts between panels"
            f"{' — panel N drives shot N' if beats else ''}. "
            f"@Image2 is the {brand} {product} — preserve its exact shape, color, materials, "
            f"and surface texture in every shot; it never deforms.{human_line} "
            f"Mood: {direction.get('vibe', 'cinematic')}. "
            f"Music and ambient sound design, no dialogue."
        )
        if not beats:
            return base
        # Time-blocked shot direction — one compact line per panel, boundaries
        # split proportionally across the spot (same convention as the
        # direct-Seedance prompt, which empirically produces stronger motion).
        beat_s = duration_s / panel_count
        shot_lines: list[str] = []
        for i, b in enumerate(beats):
            start = round(i * beat_s, 1)
            end = float(duration_s) if i == panel_count - 1 else round((i + 1) * beat_s, 1)
            start_s = int(start) if float(start).is_integer() else start
            end_s = int(end) if float(end).is_integer() else end
            action = (b.get("action") or b.get("scene") or "").strip().rstrip(".")
            if not action:
                continue
            extras = ", ".join(
                p for p in ((b.get("camera") or "").strip(), (b.get("motion") or "").strip()) if p
            )
            line = f"[{start_s}-{end_s}s] {action}"
            if extras:
                line += f" — {extras}"
            shot_lines.append(line)
        if not shot_lines:
            return base
        return base + "\n\nShot direction (match each panel):\n" + "\n".join(shot_lines)
    return (
        f"A {duration_s}s {aspect_ratio} cinematic product ad. "
        f"@Image1 is the {brand} {product} — preserve exact shape, color, materials. "
        f"Mood: {direction.get('vibe', 'cinematic')}. Music + ambient sound, no dialogue."
    )


def build_seedance_direct_prompt(
    *,
    brand: str,
    product: str,
    direction: dict,
    beats: Optional[list[dict]] = None,
    duration_s: int = 15,
    has_humans: bool = True,
    has_influencer_ref: bool = False,
    aspect_ratio: str = "16:9",
    application_geometry_hint: str = "",
    allow_lip_application: bool = False,
) -> str:
    """Storyboard-FREE Seedance 2.0 prompt for Fal-bypassed (lip / sensitive)
    directions.

    Instead of animating a Fal storyboard sheet, the shot sequence is written
    out scene-by-scene as time-blocked direction (the seedance_director.txt
    convention) so Kie Seedance renders the whole spot from the product shot
    (@Image1) + character (@Image2) alone — GPT Image 2 never sees it.
    """
    direction = direction or {}
    beats = beats or []
    panel_count = len(beats) or 1
    vibe = direction.get("vibe", "cinematic")

    # Reference bindings: product is always @Image1; the character (when the
    # direction is model-led and an influencer ref exists) is @Image2.
    refs = [
        f"@Image1 is the {brand} {product} — preserve its exact shape, color, "
        f"materials, surface texture, and any printed label; it never deforms."
    ]
    if has_humans and has_influencer_ref:
        refs.append(
            "@Image2 is the character — preserve exact face, hair, and skin tone "
            "in every shot where a person appears; same person throughout."
        )
    elif has_humans:
        refs.append("Keep the character consistent across all shots — same person, same face.")
    refs_block = " ".join(refs)

    # Time-blocked scene direction — one block per beat, proportionally split
    # across the spot duration (hard cuts between blocks).
    beat_s = max(1.0, duration_s / panel_count)
    lines: list[str] = []
    for i, b in enumerate(beats):
        start = round(i * beat_s)
        end = duration_s if i == panel_count - 1 else round((i + 1) * beat_s)
        action = (b.get("action") or b.get("scene") or "product beat").strip()
        lines.append(f"[{start}-{end}s] {action}")
    if not lines:
        lines.append(f"[0-{duration_s}s] cinematic hero shot of the {brand} {product}")
    scene_block = "\n".join(lines)

    geometry_line = ""
    if has_humans and application_geometry_hint:
        geometry_line = f"Application geometry: {application_geometry_hint.strip()}. "
    elif has_humans and allow_lip_application:
        geometry_line = f"Application geometry: {_LIP_APPLICATION_GEOMETRY_CLAUSE}. "

    return (
        f"References: {refs_block}\n\n"
        f"Style: {duration_s}s {aspect_ratio} cinematic product ad. Mood: {vibe}. "
        f"{_aspect_composition_rule(aspect_ratio)}. Hard cuts between shots, "
        f"product stays identical in every shot. {geometry_line}"
        f"No on-screen text, titles, or captions — only text physically printed "
        f"on the product packaging, 100% faithful to the original.\n\n"
        f"{scene_block}\n\n"
        f"Ambient sound design and light music, no dialogue."
    )


def build_seedance_broll_prompt(
    *,
    brand: str,
    product: str,
    panel: dict,
    has_humans: bool,
    direction: Optional[dict] = None,
    aspect_ratio: str = "16:9",
    has_influencer_ref: bool = False,
) -> str:
    """Single-beat 5s pillar-structured b-roll prompt from one panel + the
    parent direction's signatures (so b-roll inherits the same look as the
    main ad).
    """
    direction = direction or {}
    action = panel.get("action") or panel.get("scene", "single product beat")
    if has_humans and has_influencer_ref:
        human_line = (
            " @Image3 is the character — preserve exact face, hair, and skin tone."
        )
    elif has_humans:
        human_line = " Keep the character consistent and in focus."
    else:
        human_line = " No people."
    return (
        f"Animate @Image1 as a 5s {aspect_ratio} cinematic b-roll beat: {action}. "
        f"@Image2 is the {brand} {product} — preserve exact shape, color, materials; "
        f"it never deforms.{human_line} "
        f"Mood: {direction.get('vibe', 'cinematic')}. Ambient sound + music, no dialogue."
    )


def build_seedance_product_macro_prompt(
    *,
    brand: str,
    product: str,
    category: str,
    direction: Optional[dict] = None,
    aspect_ratio: str = "16:9",
) -> str:
    """Pure product-only 5s macro beauty shot — pillar-structured, no humans,
    soft brand-colored backdrop. Cleanest Seedance path."""
    direction = direction or {}
    backdrop = "soft blush gradient" if category == "beauty" else "soft brand-colored gradient"
    return (
        f"A 5s {aspect_ratio} cinematic macro product shot. @Image1 is the {brand} {product} — "
        f"preserve exact shape, color, materials; it never deforms. "
        f"Slow product rotation against a {backdrop} backdrop, soft key light, macro 100mm, "
        f"shallow depth of field. No people. Subtle ambient foley, no dialogue."
    )
