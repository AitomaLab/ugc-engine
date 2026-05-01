"""
Creative OS — Campaign Planner

Uses GPT-4o to convert a brief + branding notes + product context into a
structured multi-asset campaign plan. Output is a list of plan items
ready to insert into `campaign_plan_items`.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from env_loader import load_env
from openai import AsyncOpenAI

load_env(Path(__file__))

_openai_client: Optional[AsyncOpenAI] = None


def _openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError("OPENAI_API_KEY not set")
        _openai_client = AsyncOpenAI(api_key=key)
    return _openai_client


VALID_ASSET_TYPES = [
    "ugc_video",
    "clone_video",
    "product_shot",
    "generated_image",
    "animated_image",
]


SYSTEM_PROMPT = """You are the creative director of Studio. You design multi-asset content campaigns for brands.

Your job: given a product, a brief, branding notes, and a cadence, produce a JSON plan with N assets spread across the campaign window. Each asset is distinct — different angle, hook, or visual treatment — and cumulatively tells the brand's story.

Asset types you can pick from:
- ugc_video: a 15s or 30s full UGC video with an influencer performing a script. Use for hook-driven short-form that drives engagement. Brief must include: hook (one short punchy line), duration (15 or 30).
- clone_video: lip-synced talking-head (requires a saved clone). Use for direct-to-camera pitches. Brief: script_text, duration.
- product_shot: static professional product photograph. Use for polished hero shots, lifestyle stills. Brief: shot_type ("hero"|"lifestyle"|"detail"|"alternate"), prompt (one sentence).
- generated_image: stylized still image (cinematic / iphone_look / luxury / ugc). Use for cinematic moods, stylized compositions. Brief: mode, prompt.
- animated_image: 5-10s subtle animation of a product shot or image. Use for moody, subtle motion content. Brief: style, duration (5 or 10).

Output STRICT JSON with this shape — nothing else:
{
  "campaign_name": "<short punchy name>",
  "items": [
    {
      "slot_index": 0,
      "day_offset": 0,
      "asset_type": "ugc_video",
      "brief": { ... per-asset args ... },
      "platforms": ["tiktok", "instagram"],
      "caption": "<ready-to-post caption, 1-2 sentences + 3-5 relevant hashtags>"
    },
    ...
  ]
}

Rules:
- slot_index starts at 0 and increments by 1 per item.
- day_offset is the 0-based day within the campaign window (0 = first day, N-1 = last day). Spread items evenly across the window unless the cadence suggests otherwise.
- platforms: subset of ["tiktok","instagram","youtube","facebook","twitter","linkedin"] — pick per the user's request or default to ["tiktok","instagram"].
- caption: align with the branding voice. Include relevant hashtags.
- Vary asset_type across the plan when the user asked for a mix. When they asked for one type, keep it homogeneous.
- Keep briefs minimal — only fields the generator needs. No extra commentary.
- The total number of items must equal exactly the requested count.
"""


def _slot_time(
    start_date: datetime,
    day_offset: int,
    cadence: dict,
) -> datetime:
    time_utc = (cadence or {}).get("time_utc", "15:00")
    try:
        hour, minute = (int(x) for x in time_utc.split(":"))
    except Exception:
        hour, minute = 15, 0
    dt = start_date + timedelta(days=day_offset)
    return dt.replace(hour=hour, minute=minute, second=0, microsecond=0)


async def generate_plan(
    *,
    product: Optional[dict],
    brief: str,
    branding_notes: dict,
    target_asset_count: int,
    asset_mix: Optional[dict],
    days: int,
    cadence: dict,
    platforms: list[str],
    influencer_id: Optional[str],
    product_id: Optional[str],
    app_clip_id: Optional[str],
    default_duration: int = 15,
) -> dict:
    """Call GPT-4o to produce a plan, then post-process: compute scheduled_at,
    validate asset_type, slot_index, etc.

    Returns: {"campaign_name": str, "items": [plan_item_row, ...]}
    """
    user_msg = {
        "brief": brief,
        "product": product or {},
        "branding_notes": branding_notes or {},
        "target_asset_count": target_asset_count,
        "asset_mix": asset_mix or {},
        "days": days,
        "cadence": cadence,
        "platforms": platforms or ["tiktok", "instagram"],
        "influencer_id": influencer_id,
        "product_id": product_id,
        "app_clip_id": app_clip_id,
        "default_duration": default_duration,
    }

    resp = await _openai().chat.completions.create(
        model="gpt-4o",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_msg, ensure_ascii=False)},
        ],
        temperature=0.75,
    )

    raw = resp.choices[0].message.content or "{}"
    plan = json.loads(raw)

    name = (plan.get("campaign_name") or brief[:60] or "Untitled Campaign").strip()
    raw_items = plan.get("items") or []
    if not isinstance(raw_items, list) or not raw_items:
        raise ValueError("planner returned no items")

    # Normalize: enforce asset_type enum, slot_index, scheduled_at, brief shape.
    start_date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    items: list[dict] = []
    for idx, it in enumerate(raw_items[:target_asset_count]):
        if not isinstance(it, dict):
            continue
        asset_type = it.get("asset_type")
        if asset_type not in VALID_ASSET_TYPES:
            continue
        day_offset = int(it.get("day_offset", idx))
        day_offset = max(0, min(day_offset, max(days - 1, 0)))
        scheduled_at = _slot_time(start_date, day_offset, cadence)

        brief_dict = it.get("brief") or {}
        if not isinstance(brief_dict, dict):
            brief_dict = {}

        # Forward context IDs into the brief so the dispatcher can pick them up.
        if asset_type in ("ugc_video", "animated_image") and influencer_id:
            brief_dict.setdefault("influencer_id", influencer_id)
        if product_id:
            brief_dict.setdefault("product_id", product_id)
        if app_clip_id and asset_type in ("ugc_video",):
            brief_dict.setdefault("app_clip_id", app_clip_id)

        items.append({
            "slot_index": idx,
            "scheduled_at": scheduled_at.isoformat(),
            "asset_type": asset_type,
            "brief": brief_dict,
            "platforms": it.get("platforms") or platforms or ["tiktok", "instagram"],
            "caption": it.get("caption"),
            "status": "pending",
        })

    if len(items) != target_asset_count:
        # The planner produced the wrong count. Fail loudly so the agent can retry.
        raise ValueError(
            f"planner returned {len(items)} valid items, expected {target_asset_count}"
        )

    return {"campaign_name": name, "items": items}
