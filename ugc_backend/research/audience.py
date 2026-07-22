"""Audience language mining + persona synthesis (Slice 2).

Pipeline per user: brand strategy -> language-aware sources (named
subreddits for EN, locale-scoped Google PAA for every language) ->
OBSERVATION records with mandatory provenance -> LLM persona synthesis
whose every claim is an INTERPRETATION backed by >= MIN_SUPPORT observation
refs, with vocabulary phrases verified VERBATIM against observation text
(a phrase the model "remembers" but no observation contains is dropped).

Thin coverage stays thin: a language below the coverage floor produces no
personas and is reported low-confidence; the brief simply omits that tier.
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from urllib.parse import quote_plus

from ugc_backend.research import audience_sources, records
from ugc_backend.research.apify_client import ApifyError, run_actor
from ugc_backend.research.brief_composer import _effective_strategy, refresh_brand_brief

logger = logging.getLogger("research.audience")

_REDDIT_ACTOR = "trudax~reddit-scraper-lite"
_GOOGLE_ACTOR = "apify~google-search-scraper"
_MAX_SUBS = 3
# Tuned down from 20 after the first live run: reddit-lite on listing pages
# produced 0 items in 420s at 60 requested; smaller asks finish.
_POSTS_PER_SUB = 10
_COVERAGE_FLOOR = 8          # usable observations per language, else low-confidence
_PERSONA_COUNT = 2


def _model() -> str:
    return os.environ.get("ANALYTICS_STRATEGY_MODEL", "gpt-4o-mini")


def _llm():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    return OpenAI(api_key=api_key, base_url=os.environ.get("OPENAI_API_BASE") or None)


def _sb():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("missing SUPABASE_URL or service key")
    return create_client(url, key)


# ── collection ──────────────────────────────────────────────────────────────

def _collect_reddit(industry: str | None, lang: str, dataset_note: list) -> list[dict]:
    subs = audience_sources.subreddits_for(industry, lang)[:_MAX_SUBS]
    if not subs:
        return []
    start_urls = [{"url": f"https://www.reddit.com/r/{s}/top/?t=month"} for s in subs]
    try:
        meta, items = run_actor(
            _REDDIT_ACTOR,
            {
                "startUrls": start_urls,
                "maxItems": _POSTS_PER_SUB * len(subs),
                "maxPostCount": _POSTS_PER_SUB * len(subs),
                "skipComments": True,
            },
            timeout_s=600,
            max_items=_POSTS_PER_SUB * len(subs) + 10,
            max_cost_usd=1.0,
        )
    except ApifyError as exc:
        logger.warning("[audience] reddit collection failed (%s): %s", lang, exc)
        return []
    dataset_note.append({"source": "reddit", "lang": lang, **meta})
    out = []
    for it in items:
        title = (it.get("title") or "").strip()
        url = it.get("url") or it.get("link")
        if not title or not url or len(title) < 12:
            continue
        body = (it.get("body") or "").strip()[:280]
        itype = "audience_question" if title.rstrip().endswith("?") else "audience_phrase"
        out.append(
            {
                "insight_type": itype,
                "subject_text": title,
                "language": lang,
                "source": "reddit",
                "source_url": url,
                "dataset_id": meta["run_id"],
                "payload": {
                    "text": title,
                    "body": body,
                    "upvotes": it.get("upVotes") or it.get("score"),
                    "community": it.get("communityName") or it.get("parsedCommunityName"),
                },
            }
        )
    return out


def _collect_paa(strategy: dict, lang: str, dataset_note: list) -> list[dict]:
    queries = audience_sources.paa_queries_for(strategy, lang)
    if not queries:
        return []
    gl, hl = audience_sources.paa_locale(lang)
    try:
        meta, items = run_actor(
            _GOOGLE_ACTOR,
            {
                "queries": "\n".join(queries),
                "countryCode": gl,
                "languageCode": hl,
                "resultsPerPage": 10,
                "maxPagesPerQuery": 1,
            },
            timeout_s=240,
            max_cost_usd=0.25,
        )
    except ApifyError as exc:
        logger.warning("[audience] PAA collection failed (%s): %s", lang, exc)
        return []
    dataset_note.append({"source": "google_paa", "lang": lang, **meta})
    out = []
    for it in items:
        query = (it.get("searchQuery") or {}).get("term") if isinstance(it.get("searchQuery"), dict) else it.get("searchQuery")
        serp_url = it.get("url") or f"https://www.google.com/search?q={quote_plus(str(query or ''))}"
        for q in it.get("peopleAlsoAsk") or []:
            question = (q.get("question") or "").strip() if isinstance(q, dict) else ""
            if not question:
                continue
            out.append(
                {
                    "insight_type": "audience_question",
                    "subject_text": question,
                    "language": lang,
                    "source": "google_paa",
                    "source_url": serp_url,
                    "dataset_id": meta["run_id"],
                    "payload": {"text": question, "query": query},
                }
            )
    return out


# ── persona synthesis (interpretations) ─────────────────────────────────────

_PERSONA_SYSTEM = (
    "You build audience personas STRICTLY from the observation list given. "
    "Output ONLY valid JSON, no prose.\n\n"
    "DATA INTEGRITY (overrides everything): every pain and vocabulary item must be "
    "grounded in the observations. `vocabulary` entries must be VERBATIM substrings "
    "copied exactly from observation texts — never paraphrase them. Never introduce "
    "numbers, statistics, or facts that are not in the observations. Each persona "
    "must list the observation ids it is built from in `observation_ids`.\n\n"
    "Schema: {\"personas\": [{\"archetype\": \"<=8 words\", \"pains\": [\"<=3 short items\"], "
    "\"vocabulary\": [\"<=4 verbatim phrases\"], \"triggers\": [\"<=2 short items\"], "
    "\"observation_ids\": [\"id\", ...]}]}"
)


def _synthesize_personas(strategy: dict, obs_rows: list[dict], lang: str) -> list[dict]:
    """Returns validated persona dicts (with refs) ready for insertion."""
    listing = [
        {"id": r["id"], "text": (r.get("payload") or {}).get("text") or r.get("subject")}
        for r in obs_rows
    ]
    user = (
        f"Brand industry: {strategy.get('industry')}\n"
        f"Value prop: {strategy.get('value_prop')}\n"
        f"Audience hypothesis: {strategy.get('audience_hypothesis')}\n"
        f"Language: {lang}\n\n"
        f"Observations (id + text):\n{json.dumps(listing, ensure_ascii=False)}\n\n"
        f"Build {_PERSONA_COUNT} distinct personas."
    )
    resp = _llm().chat.completions.create(
        model=_model(),
        messages=[
            {"role": "system", "content": _PERSONA_SYSTEM},
            {"role": "user", "content": user},
        ],
        max_tokens=900,
        temperature=0.2,
    )
    raw = resp.choices[0].message.content or ""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(0))
    except ValueError:
        return []

    by_id = {r["id"]: ((r.get("payload") or {}).get("text") or r.get("subject") or "") for r in obs_rows}
    all_texts_lower = {i: t.lower() for i, t in by_id.items()}
    validated = []
    for p in (data.get("personas") or [])[:_PERSONA_COUNT]:
        if not isinstance(p, dict):
            continue
        refs = [i for i in (p.get("observation_ids") or []) if i in by_id]
        # verbatim check: a vocabulary phrase must exist inside some observation
        vocab = []
        for ph in (p.get("vocabulary") or [])[:4]:
            if isinstance(ph, str) and any(ph.lower() in t for t in all_texts_lower.values()):
                vocab.append(ph)
        pains = [x for x in (p.get("pains") or [])[:3] if isinstance(x, str)]
        triggers = [x for x in (p.get("triggers") or [])[:2] if isinstance(x, str)]
        archetype = str(p.get("archetype") or "").strip()[:80]
        if not archetype or len(refs) < records.MIN_SUPPORT:
            continue
        validated.append(
            {
                "archetype": archetype,
                "pains": pains,
                "vocabulary": vocab,
                "triggers": triggers,
                "refs": refs,
                "supporting_texts": [by_id[i] for i in refs],
                "language": lang,
            }
        )
    return validated


# ── orchestration ───────────────────────────────────────────────────────────

def run_audience_research(user_id: str) -> dict:
    """Full audience pass for one user. Returns a summary (also stored)."""
    sb = _sb()
    rows = (
        sb.table("brand_profiles").select("brand_state").eq("user_id", user_id).limit(1).execute()
    ).data or []
    brand = (rows[0].get("brand_state") if rows else None) or {}
    strategy = _effective_strategy(brand) or {}
    industry = strategy.get("industry")
    langs = []
    for l in (strategy.get("language_primary"), strategy.get("language_secondary")):
        if l and l not in langs:
            langs.append(l)
    langs = langs or ["en"]

    dataset_note: list[dict] = []
    coverage: dict[str, dict] = {}
    inserted_by_lang: dict[str, list[dict]] = {}

    # replace-on-refresh for the audience pass
    for itype in ("audience_phrase", "audience_question", "persona"):
        records.delete_records(user_id, insight_type=itype)

    for lang in langs[:2]:
        obs = _collect_reddit(industry, lang, dataset_note) + _collect_paa(strategy, lang, dataset_note)
        for o in obs:
            o["industry"] = industry
        ids = records.insert_observations(user_id, obs)
        stored = records.list_records(user_id, kind="observation", limit=400)
        stored_lang = [r for r in stored if r.get("language") == lang and r["id"] in set(ids)]
        inserted_by_lang[lang] = stored_lang
        coverage[lang] = {
            "observations": len(stored_lang),
            "low_confidence": len(stored_lang) < _COVERAGE_FLOOR,
        }

    personas_out = []
    for lang, obs_rows in inserted_by_lang.items():
        if coverage[lang]["low_confidence"]:
            logger.info("[audience] %s below coverage floor (%d) — no personas", lang, len(obs_rows))
            continue
        for p in _synthesize_personas(strategy, obs_rows, lang):
            pid = records.insert_interpretation(
                user_id,
                insight_type="persona",
                subject_text=p["archetype"],
                payload={
                    "archetype": p["archetype"],
                    "pains": p["pains"],
                    "vocabulary": p["vocabulary"],
                    "triggers": p["triggers"],
                },
                refs=p["refs"],
                supporting_texts=p["supporting_texts"],
                language=lang,
                industry=industry,
            )
            if pid:
                personas_out.append({k: p[k] for k in ("archetype", "pains", "vocabulary", "triggers", "language")})

    audience_doc = {
        "personas": personas_out,
        "top_pains": [x for p in personas_out for x in p["pains"]][:3],
        "vocabulary": [x for p in personas_out for x in p["vocabulary"]][:4],
        "coverage": coverage,
        "runs": dataset_note,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    sb.table("brand_profiles").update({"audience": audience_doc}).eq("user_id", user_id).execute()

    try:
        refresh_brand_brief(user_id)
    except Exception as exc:  # brief refresh must never sink the research result
        logger.warning("[audience] brief refresh failed: %s", exc)

    # Hook suggestions chain off fresh audience data + fresh brief — the
    # system picks candidates, production engagement judges them later.
    try:
        from ugc_backend.research.hooks import generate_hook_suggestions

        hooks_out = generate_hook_suggestions(user_id)
        logger.info("[audience] hook suggestions: %s", hooks_out)
    except Exception as exc:
        logger.warning("[audience] hook suggestions failed (non-fatal): %s", exc)

    total_cost = sum(float(n.get("usage_usd") or 0) for n in dataset_note)
    return {
        "personas": len(personas_out),
        "coverage": coverage,
        "cost_usd": round(total_cost, 3),
        "runs": len(dataset_note),
    }


_inflight: set[str] = set()
_inflight_lock = None


def enqueue_audience_research(user_id: str) -> bool:
    """Start a background pass unless one is already running for this user.
    Two concurrent passes race through delete-then-insert and duplicate every
    record (observed live) — the lock makes refresh idempotent."""
    import threading

    global _inflight_lock
    if _inflight_lock is None:
        _inflight_lock = threading.Lock()
    with _inflight_lock:
        if user_id in _inflight:
            logger.info("[audience] research already running for %s — skipped", user_id)
            return False
        _inflight.add(user_id)

    threading.Thread(
        target=lambda: _safe_run(user_id), name=f"audience-research-{user_id[:8]}", daemon=True
    ).start()
    return True


def _safe_run(user_id: str) -> None:
    try:
        out = run_audience_research(user_id)
        logger.info("[audience] research complete for %s: %s", user_id, out)
    except Exception:
        logger.exception("[audience] research failed for %s", user_id)
    finally:
        with _inflight_lock:
            _inflight.discard(user_id)
