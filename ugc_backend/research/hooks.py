"""Hook suggestion engine (Slice 2.5) — the system picks, production judges.

Replaces the human A/B gate at the user's direction: candidates are
generated WITH the brand brief, then scored DETERMINISTICALLY in code
against the intelligence we actually hold. The model writes creative text;
it never scores itself and never produces a number.

Score components (all computed, stored transparently in the payload):
- audience_echo  : how many audience observations the hook verbatim-echoes
                   (canonical containment / 3+ word overlap — string math)
- brand_terms    : overlap with the brand's own value-prop/differentiator
                   terms (string math)
- type_prior     : +1 when the classified hook type is `claim` — the weak,
                   explicitly-labelled prior from the external G0 study
                   (claim vs demo median plays 2.91x, study niche, n=118)

Each stored suggestion is an interpretation whose refs are the observation
rows it echoes (direct-echo floor: 1). The digit-containment guard applies:
a hook naming a number absent from its sources is refused — this catches
exactly the "40 grams" class of plausible invention.

The loop closes downstream: published posts' extracted hooks are matched
back to suggestions, engagement flows through the existing per-user
reflection loop, and confirmed hook patterns land in creative_guidelines.md
→ the brief → future suggestions. Per-user, additive, no pipeline changes.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone

from ugc_backend.research import records
from ugc_backend.research.brief_composer import BRIEF_PATH, _effective_strategy

logger = logging.getLogger("research.hooks")

_N_CANDIDATES = 12
_KEEP = 6
_HOOK_TYPES = ("question", "claim", "pattern-interrupt", "demo", "stat", "pov")

_GEN_SYSTEM = (
    "You write opening hooks (max 2 sentences each, spoken style) for short-form "
    "vertical videos. Use the audience's own words from the context where natural. "
    "NEVER include a number, statistic, or named fact that is not present in the "
    "provided context. Output ONLY a JSON array of strings."
)

_CLASSIFY_SYSTEM = (
    "Classify the opening style of each short-video hook. Inputs may be the hook's "
    "spoken/on-screen text OR a description of its opening visuals — a purely visual "
    "opening still has a style (typically demo, pattern-interrupt, or pov). "
    "Output ONLY a JSON array of strings, exactly one per input, never empty, each "
    "exactly one of: question | claim | pattern-interrupt | demo | stat | pov."
)


def _llm():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_API_BASE") or None)


def _model() -> str:
    return os.environ.get("ANALYTICS_STRATEGY_MODEL", "gpt-4o-mini")


def _sb():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("missing SUPABASE_URL or service key")
    return create_client(url, key)


def _json_array(raw: str) -> list:
    m = re.search(r"\[.*\]", raw or "", re.S)
    if not m:
        return []
    try:
        out = json.loads(m.group(0))
        return out if isinstance(out, list) else []
    except ValueError:
        return []


# ── deterministic scoring ───────────────────────────────────────────────────

_STOP = set("the a an and or but for with your you to of in on is are what how why i my it this that".split())


def _terms(text: str) -> set[str]:
    return {
        w for w in records.canonical_subject(text).split() if w not in _STOP and len(w) > 2
    }


def score_hook(hook: str, observations: list[dict], brand_terms: set[str], hook_type: str) -> dict:
    """Pure, deterministic scoring. Returns the full transparent breakdown."""
    h_terms = _terms(hook)
    h_canon = records.canonical_subject(hook)
    matched: list[dict] = []
    for o in observations:
        text = (o.get("payload") or {}).get("text") or o.get("subject") or ""
        o_canon = records.canonical_subject(text)
        overlap = _terms(text) & h_terms
        if (o_canon and o_canon in h_canon) or len(overlap) >= 3:
            matched.append({"id": o["id"], "text": text})
    brand_overlap = brand_terms & h_terms
    type_prior = 1 if hook_type == "claim" else 0
    score = 2 * len(matched) + len(brand_overlap) + type_prior
    return {
        "score": score,
        "audience_echo": len(matched),
        "matched": matched,
        "brand_terms": sorted(brand_overlap),
        "type_prior": type_prior,
        "hook_type": hook_type,
    }


# ── orchestration ───────────────────────────────────────────────────────────

def classify_hook_type(hook_text: str) -> str | None:
    """Classify one hook's opening style into the fixed 6-type enum.
    Used by the breakdown pipeline so every analyzed post carries a
    hook_type the reflection loop can group on. Returns None on any
    failure — the label is an enrichment, never a blocker."""
    text = (hook_text or "").strip()
    if len(text) < 8:
        return None
    try:
        resp = _llm().chat.completions.create(
            model=_model(),
            messages=[
                {"role": "system", "content": _CLASSIFY_SYSTEM},
                {"role": "user", "content": json.dumps([text], ensure_ascii=False)},
            ],
            max_tokens=20,
            temperature=0.0,
        )
        out = _json_array(resp.choices[0].message.content)
        return out[0] if out and out[0] in _HOOK_TYPES else None
    except Exception as exc:
        logger.warning("[hooks] classify failed: %s", exc)
        return None


def generate_hook_suggestions(user_id: str) -> dict:
    sb = _sb()
    prow = (
        sb.table("brand_profiles").select("brand_state,audience").eq("user_id", user_id).limit(1).execute()
    ).data or []
    brand = (prow[0].get("brand_state") if prow else None) or {}
    strategy = _effective_strategy(brand) or {}
    brief_rows = (
        sb.table("agent_memories").select("content").eq("user_id", user_id)
        .eq("path", BRIEF_PATH).limit(1).execute()
    ).data or []
    brief = brief_rows[0]["content"] if brief_rows else None
    if not brief:
        return {"suggestions": 0, "reason": "no brand brief yet"}

    observations = records.list_records(user_id, kind="observation", limit=120)
    if not observations:
        return {"suggestions": 0, "reason": "no audience observations yet"}

    # 1) generate candidates WITH the brief
    gen = _llm().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": _GEN_SYSTEM},
            {
                "role": "user",
                "content": f"Brand context:\n{brief}\n\nWrite {_N_CANDIDATES} distinct hooks "
                f"for {brand.get('name') or 'this brand'} short-form videos.",
            },
        ],
        max_tokens=900,
        temperature=0.9,
    )
    hooks = [h.strip().strip('"') for h in _json_array(gen.choices[0].message.content) if isinstance(h, str)]
    hooks = [h for h in hooks if 15 <= len(h) <= 220][:_N_CANDIDATES]
    if not hooks:
        return {"suggestions": 0, "reason": "generation returned nothing usable"}

    # 2) classify types (one batched call)
    cls = _llm().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM},
            {"role": "user", "content": json.dumps(hooks, ensure_ascii=False)},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    types = [t if t in _HOOK_TYPES else "claim" for t in _json_array(cls.choices[0].message.content)]
    types += ["claim"] * (len(hooks) - len(types))

    # 3) deterministic scoring + brand terms from the brand's own copy
    brand_terms = _terms(
        " ".join(
            filter(
                None,
                [strategy.get("value_prop") or "", " ".join(strategy.get("differentiators") or [])],
            )
        )
    )
    scored = [
        {"hook": h, **score_hook(h, observations, brand_terms, t)}
        for h, t in zip(hooks, types)
    ]
    scored.sort(key=lambda s: -s["score"])

    # 4) store top suggestions; digit containment guarded by insert
    records.delete_records(user_id, insight_type="hook_suggestion")
    sources_for_digits = [
        (o.get("payload") or {}).get("text") or o.get("subject") or "" for o in observations
    ] + [brief]
    kept = 0
    for s in scored[:_KEEP]:
        refs = [m["id"] for m in s["matched"]]
        if not refs:
            continue  # a suggestion that echoes nothing is not grounded — skip
        out = records.insert_interpretation(
            user_id,
            insight_type="hook_suggestion",
            subject_text=s["hook"],
            payload={
                "hook": s["hook"],
                "hook_type": s["hook_type"],
                "score": s["score"],
                "audience_echo": s["audience_echo"],
                "brand_terms": s["brand_terms"],
                "type_prior": s["type_prior"],
                "echoes": [m["text"] for m in s["matched"]][:3],
                "status": "suggested",  # -> published/confirmed via the loop
            },
            refs=refs,
            supporting_texts=[m["text"] for m in s["matched"]] + sources_for_digits,
            language=strategy.get("language_primary"),
            industry=strategy.get("industry"),
            min_support=records.MIN_SUPPORT_DIRECT,
        )
        if out:
            kept += 1

    return {
        "suggestions": kept,
        "candidates": len(hooks),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
