"""Brand brief composer (Slice 1) — the always-on ~2KB agent context.

Composes /memories/brand_brief.md from the brand profile + confirmed
performance rules. Design rules (from the plan, all deliberate):

- **Built small, never cut small**: assembled from bounded slots (fixed item
  counts, per-item char ceilings). If the result would exceed budget, whole
  lowest-priority items are dropped — never partial sentences.
- **Budget ~2KB**, sized to match creative_guidelines.md (the most valuable
  memory file), so adding the brief while excluding reflection_log.md makes
  the first-turn snapshot smaller than before, not larger.
- **Fingerprinted**: an input fingerprint is stamped into the brief; when
  inputs are unchanged the rewrite is skipped (same pattern as
  reflection_runner's signal fingerprint).
- **Standalone on purpose**: this file exists twice — canonical at
  ugc_backend/research/brief_composer.py, byte-identical shadow at
  services/creative-os/services/brief_composer.py — because the creative-os
  Railway container deploys WITHOUT ugc_backend (see managed_agent_client's
  repo-root note). Same convention as the prompts/config shadow copies; a
  test asserts the two files stay identical. Only stdlib + supabase here;
  the memory upsert mirrors analytics_db.upsert_agent_memory.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone

BRIEF_PATH = "/memories/brand_brief.md"
BRIEF_BUDGET_BYTES = 2048
_MARKER_RE = re.compile(r"<!-- brief:v1 fp=([0-9a-f]+) composed=([^ ]+) -->")

# priority: lower number = dropped LAST (plan precedence: own confirmed
# performance strongest, then identity, then audience hypothesis, then extras)
_P_RULES, _P_IDENTITY, _P_AUDIENCE, _P_EXTRA = 0, 1, 2, 3


def _s(v, cap: int) -> str | None:
    if not isinstance(v, str) or not v.strip():
        return None
    return v.strip()[:cap]


def confirmed_rules_from_guidelines(guidelines_md: str | None, limit: int = 3) -> list[str]:
    """Top confirmed rules from creative_guidelines.md — bullets under a
    'Confirmed' heading; falls back to the first bullets anywhere."""
    if not guidelines_md:
        return []
    lines = guidelines_md.splitlines()
    out: list[str] = []
    in_confirmed = False
    for ln in lines:
        if re.match(r"^#{1,6}\s", ln):
            in_confirmed = "confirmed" in ln.lower()
            continue
        m = re.match(r"^\s*[-*]\s+(.*\S)", ln)
        if m and in_confirmed:
            out.append(m.group(1)[:160])
            if len(out) >= limit:
                return out
    if out:
        return out
    for ln in lines:  # fallback: first bullets anywhere
        m = re.match(r"^\s*[-*]\s+(.*\S)", ln)
        if m:
            out.append(m.group(1)[:160])
            if len(out) >= limit:
                break
    return out


def compose_brand_brief(
    brand: dict,
    *,
    guidelines_md: str | None = None,
    audience: dict | None = None,
) -> str | None:
    """Pure composition. Returns None when there is nothing worth writing
    (no strategy and no rules) — an empty brief must not occupy the snapshot."""
    strategy = _effective_strategy(brand)
    rules = confirmed_rules_from_guidelines(guidelines_md)
    if not strategy and not rules:
        return None

    name = _s(brand.get("name"), 60) or "this brand"
    strategy = strategy or {}

    items: list[tuple[int, str]] = []
    if strategy.get("industry"):
        line = f"Industry: {strategy['industry']}"
        if strategy.get("industry_secondary"):
            line += f" (also {strategy['industry_secondary']})"
        if strategy.get("industry_needs_confirmation"):
            line += " — unconfirmed, low confidence"
        items.append((_P_IDENTITY, line))
    lang = strategy.get("language_primary")
    if lang:
        line = f"Content language: {lang}"
        if strategy.get("language_secondary"):
            line += f" + {strategy['language_secondary']}"
        if strategy.get("region"):
            line += f" · region {strategy['region']}"
        items.append((_P_IDENTITY, line))
    if strategy.get("value_prop"):
        items.append((_P_IDENTITY, f"Value prop: {strategy['value_prop']}"))
    tone = [t for t in (strategy.get("tone_of_voice") or [])[:4] if isinstance(t, str)]
    if tone:
        items.append((_P_IDENTITY, f"Tone: {', '.join(tone)}"))
    if strategy.get("price_positioning"):
        items.append((_P_IDENTITY, f"Price positioning: {strategy['price_positioning']}"))
    for d in (strategy.get("differentiators") or [])[:3]:
        items.append((_P_EXTRA, f"Differentiator: {d[:80]}"))
    cats = [c for c in (strategy.get("product_categories") or [])[:4] if isinstance(c, str)]
    if cats:
        items.append((_P_EXTRA, f"Product categories: {', '.join(cats)}"))
    if strategy.get("audience_hypothesis"):
        items.append((_P_AUDIENCE, f"Audience: {strategy['audience_hypothesis']}"))
    for pain in (audience or {}).get("top_pains", [])[:3]:
        items.append((_P_AUDIENCE, f"Audience pain: {_s(pain, 120)}"))
    for phrase in (audience or {}).get("vocabulary", [])[:4]:
        items.append((_P_AUDIENCE, f'Audience phrase: "{_s(phrase, 90)}"'))
    for r in rules:
        items.append((_P_RULES, f"Confirmed (from this account's real performance): {r}"))

    header = f"# Brand brief — {name}\n"
    footer_hint = (
        "\n_Apply this alongside creative_guidelines.md; "
        "the account's own confirmed performance always wins on conflict._\n"
    )
    fp = compute_fingerprint(brand, guidelines_md, audience)
    marker = f"<!-- brief:v1 fp={fp} composed={datetime.now(timezone.utc).strftime('%Y-%m-%d')} -->\n"

    # whole-item assembly inside the budget, strongest priorities first
    budget = BRIEF_BUDGET_BYTES - len((header + footer_hint + marker).encode("utf-8"))
    chosen: list[tuple[int, int, str]] = []  # (orig_idx, prio, line)
    used = 0
    for prio in (_P_RULES, _P_IDENTITY, _P_AUDIENCE, _P_EXTRA):
        for idx, (p, line) in enumerate(items):
            if p != prio:
                continue
            cost = len(f"- {line}\n".encode("utf-8"))
            if used + cost > budget:
                continue  # whole-item drop
            chosen.append((idx, p, line))
            used += cost
    chosen.sort(key=lambda t: t[0])  # restore natural reading order
    body = "".join(f"- {line}\n" for _, _, line in chosen)
    return header + body + footer_hint + marker


def compute_fingerprint(brand: dict, guidelines_md: str | None, audience: dict | None) -> str:
    payload = json.dumps(
        {
            "strategy": brand.get("strategy"),
            "strategy_manual": brand.get("strategy_manual"),
            "name": brand.get("name"),
            "guidelines": guidelines_md or "",
            "audience": audience or {},
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def parse_fingerprint(brief_md: str | None) -> str | None:
    m = _MARKER_RE.search(brief_md or "")
    return m.group(1) if m else None


def _effective_strategy(brand: dict) -> dict | None:
    """Manual outranks scraped, per-field (mirrors brand_studio.effective_strategy;
    duplicated here to keep this module importable without creative-os code)."""
    scraped = brand.get("strategy") if isinstance(brand.get("strategy"), dict) else None
    manual = brand.get("strategy_manual") if isinstance(brand.get("strategy_manual"), dict) else None
    if not manual:
        return scraped
    if not scraped:
        return manual
    merged = dict(scraped)
    for k, v in manual.items():
        if v not in (None, "", []):
            merged[k] = v
    return merged


# ── persistence (service-role; mirrors analytics_db.upsert_agent_memory) ────

def _sb():
    """Own service-role client — no ugc_db import, so the standalone
    creative-os container can run this file unchanged."""
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("missing SUPABASE_URL or service key")
    return create_client(url, key)


def refresh_brand_brief(user_id: str, brand: dict | None = None) -> dict:
    """Recompose and store the brief; skips the write when the input
    fingerprint is unchanged. Returns {written, reason}."""
    sb = _sb()
    rows = (
        sb.table("brand_profiles")
        .select("brand_state,audience")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    ).data or []
    row = rows[0] if rows else {}
    if brand is None:
        brand = row.get("brand_state") or {}
    audience_doc = row.get("audience") if isinstance(row.get("audience"), dict) else None
    audience = None
    if audience_doc:
        audience = {
            "top_pains": audience_doc.get("top_pains") or [],
            "vocabulary": audience_doc.get("vocabulary") or [],
        }

    def _read_memory(path: str) -> str | None:
        rows = (
            sb.table("agent_memories")
            .select("content")
            .eq("user_id", user_id)
            .eq("path", path)
            .limit(1)
            .execute()
        ).data or []
        return rows[0].get("content") if rows else None

    guidelines = _read_memory("/memories/creative_guidelines.md")
    new_fp = compute_fingerprint(brand, guidelines, audience)
    current = _read_memory(BRIEF_PATH)
    if current is not None and parse_fingerprint(current) == new_fp:
        return {"written": False, "reason": "fingerprint unchanged"}

    brief = compose_brand_brief(brand, guidelines_md=guidelines, audience=audience)
    if brief is None:
        return {"written": False, "reason": "nothing to write"}
    assert len(brief.encode("utf-8")) <= BRIEF_BUDGET_BYTES + 64, "brief over budget"
    now = datetime.now(timezone.utc).isoformat()
    sb.table("agent_memories").upsert(
        {
            "user_id": user_id,
            "path": BRIEF_PATH,
            "content": brief,
            "updated_at": now,
        },
        on_conflict="user_id,path",
    ).execute()
    return {"written": True, "reason": "composed", "bytes": len(brief.encode("utf-8"))}
