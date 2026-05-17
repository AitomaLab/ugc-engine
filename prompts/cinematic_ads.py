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
    ("beauty",   ("cream", "serum", "lipstick", "mascara", "foundation",
                  "moisturizer", "skincare", "perfume", "cologne", "lotion",
                  "shampoo", "conditioner", "makeup", "cosmetic", "scar stick",
                  "cleanser", "balm")),
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


def propose_directions(product_meta: dict) -> list[dict]:
    """Return 3 storyboard directions enriched with pro-cinematic fields.

    Each direction has:
        key, name, vibe, hero_moment, model_or_product_only, recommended,
        camera_signature, lighting_signature, style_grade, negative_traits.
    Pro fields are injected from defaults if the static table doesn't define
    them, so downstream builders can rely on the full shape always being set.
    """
    return _enrich_directions(_propose_directions_static(product_meta))


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
            return propose_directions(product_meta)
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic()
        except Exception as e:
            print(f"[cinematic_propose] LLM directions skipped: anthropic client init failed: {e}")
            return propose_directions(product_meta)

    brand = product_meta.get("brand") or product_meta.get("name") or "Brand"
    product = product_meta.get("name") or "Product"

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
        f"FORMAT: {aspect_ratio} ({_aspect_hint})\n"
        f"DURATION: {duration_seconds}s\n\n"
        "Write 3 creative directions tailored to the BRIEF and the FORMAT. The recommended one MUST be the one "
        "whose hero_moment best matches the narrative the user described. If the user described "
        "actions (e.g. grinding, steaming, pouring), prefer model-led / action-led directions. "
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
        return out
    except Exception as e:
        print(
            f"[cinematic_propose] LLM directions failed ({type(e).__name__}: {e}) — "
            f"falling back to static propose_directions"
        )
        return propose_directions(product_meta)


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
        + (
            "OUTPUT LANGUAGE: write `scene`, `action`, and `sound` in Spanish (es-ES). "
            "Keep `camera`, `lens`, `lighting`, and `motion` in English (cinematography terminology). "
            if user_lang == "es" else
            "OUTPUT LANGUAGE: write all human-readable fields in English. "
        )
        + "No prose, no markdown, no preamble.\n\n"
        f"SHOT VOCAB (pick `camera` from these per beat):\n{_shot_vocab_lines}"
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
        f"HUMANS ALLOWED: {has_humans}\n"
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


def _grid_for(num_panels: int, aspect_ratio: str) -> tuple[int, int]:
    """Return (cols, rows) for a storyboard sheet given panel count + aspect.

    Vertical sheets use taller grids (more rows) so panels stay readable on a
    9:16 PNG. Horizontal sheets use wider grids.
    """
    vertical = aspect_ratio == "9:16"
    if num_panels == 3:
        return (1, 3) if vertical else (3, 1)
    if num_panels == 4:
        return (2, 2)
    return (2, 3) if vertical else (3, 2)


def _panel_orientation_label(aspect_ratio: str) -> str:
    if aspect_ratio == "9:16":
        return "9:16 vertical orientation"
    if aspect_ratio == "4:3":
        return "4:3 standard orientation"
    return "16:9 landscape orientation"


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
) -> str:
    has_humans = direction.get("model_or_product_only") == "model"
    beat_s = duration_s / num_panels
    if beats is None:
        beats = panel_beats_for(direction["key"], category=category)
    cols, rows = _grid_for(num_panels, aspect_ratio)
    panel_orient = _panel_orientation_label(aspect_ratio)
    grid_text = f"{cols} columns by {rows} rows"
    sheet_orient = "vertical" if aspect_ratio == "9:16" else ("standard" if aspect_ratio == "4:3" else "landscape")

    # Character lock — sharp, consistent face across panels. Soft-blur was a
    # legacy beauty-safety rule but it broke Seedance face propagation
    # (downstream i2v can't inpaint a blurred reference → blurred video faces).
    if has_humans:
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
        f"Above the grid, a bold mono header reads:\n\n"
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
        f"never appears in degraded form. THIS REFERENCE IS THE IDENTITY ANCHOR. Keep small text "
        f"on packaging as illegible texture, not readable type.\n\n"
        f"NO TEXT OVERLAYS INSIDE ANY PANEL. Do NOT render any tagline, brand name, product name, "
        f"website domain, CTA, or any other typographic element INSIDE the panel frames. Panel "
        f"{num_panels:02d} must be a pure cinematic hero image (clean product/scene shot) with NO "
        f"end-card text, NO logo lockup, NO 'buy now', NO domain. The header above the grid + the "
        f"caption blocks below each panel are the ONLY text in this image.\n\n"
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
) -> str:
    """Short 40-70 word "animate this storyboard" prompt — matches the prior
    working 16:9 shape. All cinematic complexity lives in the storyboard image
    (Image1); Seedance just animates the panels in sequence and holds the
    product lock. Long pillar-structured prompts over-constrained Seedance and
    caused stuttery motion / hallucinations in the 9:16 regression.
    """
    if has_storyboard:
        panel_count = len(beats) if beats else 6
        human_line = (
            " Keep the character consistent across all shots — same person, same face."
            if has_humans else ""
        )
        return (
            f"Animate the {panel_count}-panel storyboard in @Image1 in order as a continuous "
            f"{duration_s}s {aspect_ratio} cinematic ad with hard cuts between panels. "
            f"@Image2 is the {brand} {product} — preserve its exact shape, color, materials, "
            f"and surface texture in every shot; it never deforms.{human_line} "
            f"Mood: {direction.get('vibe', 'cinematic')}. "
            f"Music and ambient sound design, no dialogue."
        )
    return (
        f"A {duration_s}s {aspect_ratio} cinematic product ad. "
        f"@Image1 is the {brand} {product} — preserve exact shape, color, materials. "
        f"Mood: {direction.get('vibe', 'cinematic')}. Music + ambient sound, no dialogue."
    )


def build_seedance_broll_prompt(
    *,
    brand: str,
    product: str,
    panel: dict,
    has_humans: bool,
    direction: Optional[dict] = None,
    aspect_ratio: str = "16:9",
) -> str:
    """Single-beat 5s pillar-structured b-roll prompt from one panel + the
    parent direction's signatures (so b-roll inherits the same look as the
    main ad).
    """
    direction = direction or {}
    action = panel.get("action") or panel.get("scene", "single product beat")
    human_line = " Keep the character consistent and in focus." if has_humans else " No people."
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
