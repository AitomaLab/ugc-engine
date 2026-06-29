"""Locale resolution and translate-on-read caching for Analytics AI content."""

from __future__ import annotations

import copy
import json
import logging
import os
import threading
from typing import Any, Optional

from fastapi import Request

from ugc_db.db_manager import get_supabase

logger = logging.getLogger(__name__)

SUPPORTED_LOCALES = frozenset({"en", "es"})
_DEFAULT_LOCALE = "en"
_TRANSLATE_MODEL = os.environ.get("ANALYTICS_STRATEGY_MODEL", "gpt-4o-mini")
_breakdown_translate_inflight: set[str] = set()
_strategy_translate_inflight: set[str] = set()
_inflight_lock = threading.Lock()

_SPANISH_OUTPUT_RULE = (
    "\n\nLANGUAGE: Write all user-facing text values in Spanish (es). "
    "Keep JSON keys, timestamps (MM:SS), and structural field names in English."
)

_SPANISH_MARKDOWN_RULE = (
    "\n\nLANGUAGE: Write the entire report in Spanish (es), including all headings and bullet text."
)


def normalize_locale(value: Optional[str]) -> str:
    if not value:
        return _DEFAULT_LOCALE
    loc = str(value).strip().lower()[:2]
    return loc if loc in SUPPORTED_LOCALES else _DEFAULT_LOCALE


def locale_prompt_suffix(locale: str) -> str:
    return _SPANISH_OUTPUT_RULE if normalize_locale(locale) == "es" else ""


def markdown_prompt_suffix(locale: str) -> str:
    return _SPANISH_MARKDOWN_RULE if normalize_locale(locale) == "es" else ""


def get_profile_ui_language(user_id: str) -> str:
    try:
        sb = get_supabase()
        res = (
            sb.table("profiles")
            .select("ui_language")
            .eq("id", user_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0]
        return normalize_locale(row.get("ui_language") if row else None)
    except Exception:
        return _DEFAULT_LOCALE


def set_profile_ui_language(user_id: str, locale: str) -> None:
    loc = normalize_locale(locale)
    try:
        sb = get_supabase()
        sb.table("profiles").upsert(
            {"id": user_id, "ui_language": loc},
            on_conflict="id",
        ).execute()
    except Exception as exc:
        logger.warning("[locale] failed to save ui_language for %s: %s", user_id[:8], exc)


def resolve_request_locale(request: Optional[Request], user_id: str) -> str:
    if request is not None:
        header = request.headers.get("X-Ui-Language") or request.headers.get("x-ui-language")
        if header:
            return normalize_locale(header)
    return get_profile_ui_language(user_id)


def request_wants_sync_locale(request: Optional[Request]) -> bool:
    """True when the client asks for inline translation (e.g. language toggle)."""
    if request is None:
        return False
    raw = request.headers.get("X-Ui-Language-Sync") or request.headers.get("x-ui-language-sync")
    return str(raw or "").strip().lower() in ("1", "true", "yes")


def _get_llm_client():
    from openai import OpenAI

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    base_url = os.environ.get("OPENAI_API_BASE") or None
    return OpenAI(api_key=api_key, base_url=base_url)


def _translate_breakdown_payload(payload: dict, target_locale: str) -> dict:
    client = _get_llm_client()
    target = normalize_locale(target_locale)
    prompt = (
        "Translate the following JSON object to "
        f"{'Spanish' if target == 'es' else 'English'}. "
        "Preserve JSON structure and keys exactly. "
        "Translate only string values (including nested strings in arrays/objects). "
        "Do not translate timestamps like 00:03 or MM:SS values.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )
    response = client.chat.completions.create(
        model=_TRANSLATE_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You translate analytics video breakdown JSON. Output ONLY valid JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        max_tokens=4000,
        temperature=0.2,
    )
    text = (response.choices[0].message.content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        text = text.strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Translation did not return a JSON object")
    return parsed


def _translate_markdown(text: str, target_locale: str) -> str:
    client = _get_llm_client()
    target = normalize_locale(target_locale)
    lang_name = "Spanish" if target == "es" else "English"
    response = client.chat.completions.create(
        model=_TRANSLATE_MODEL,
        messages=[
            {
                "role": "system",
                "content": f"Translate Markdown social-media strategy reports to {lang_name}. Preserve Markdown structure.",
            },
            {"role": "user", "content": text},
        ],
        max_tokens=2500,
        temperature=0.2,
    )
    return (response.choices[0].message.content or "").strip()


def _extract_translatable_breakdown(row: dict) -> dict:
    return {
        "summary": row.get("summary"),
        "hook": row.get("hook"),
        "scenes": row.get("scenes"),
        "audio": row.get("audio"),
        "visual_details": row.get("visual_details"),
        "key_moments": row.get("key_moments"),
        "takeaways": row.get("takeaways"),
    }


def _merge_breakdown_translation(row: dict, translated: dict) -> dict:
    out = copy.deepcopy(row)
    for key in (
        "summary", "hook", "scenes", "audio",
        "visual_details", "key_moments", "takeaways",
    ):
        if key in translated and translated[key] is not None:
            out[key] = translated[key]
    return out


def _save_breakdown_variant(breakdown_id: str, locale: str, variant: dict) -> None:
    try:
        sb = get_supabase()
        res = (
            sb.table("analytics_video_breakdowns")
            .select("locale_variants")
            .eq("id", breakdown_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        variants = dict(row.get("locale_variants") or {})
        variants[normalize_locale(locale)] = variant
        sb.table("analytics_video_breakdowns").update(
            {"locale_variants": variants},
        ).eq("id", breakdown_id).execute()
    except Exception as exc:
        logger.warning("[locale] failed to cache breakdown variant %s: %s", breakdown_id[:8], exc)


def _enqueue_breakdown_translation(breakdown_id: str, source: dict, target_locale: str) -> None:
    key = f"{breakdown_id}:{normalize_locale(target_locale)}"
    with _inflight_lock:
        if key in _breakdown_translate_inflight:
            return
        _breakdown_translate_inflight.add(key)

    def _runner() -> None:
        try:
            translated = _translate_breakdown_payload(source, target_locale)
            _save_breakdown_variant(breakdown_id, target_locale, translated)
        except Exception as exc:
            logger.warning("[locale] background breakdown translation failed: %s", exc)
        finally:
            with _inflight_lock:
                _breakdown_translate_inflight.discard(key)

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"locale-breakdown-{breakdown_id[:8]}",
    ).start()


def _enqueue_strategy_translation(
    user_id: str,
    account_id: str,
    report: str,
    target_locale: str,
) -> None:
    key = f"{account_id}:{normalize_locale(target_locale)}"
    with _inflight_lock:
        if key in _strategy_translate_inflight:
            return
        _strategy_translate_inflight.add(key)

    def _runner() -> None:
        try:
            translated = _translate_markdown(report, target_locale)
            if translated:
                _save_strategy_variant(user_id, account_id, target_locale, translated)
        except Exception as exc:
            logger.warning("[locale] background strategy translation failed: %s", exc)
        finally:
            with _inflight_lock:
                _strategy_translate_inflight.discard(key)

    threading.Thread(
        target=_runner,
        daemon=True,
        name=f"locale-strategy-{account_id[:8]}",
    ).start()


def _locale_error_message(exc: BaseException) -> str:
    text = str(exc).lower()
    if "openai_api_key" in text or "not configured" in text:
        return "AI translation is not configured (OPENAI_API_KEY missing)."
    return "Translation unavailable — please try again."


def _with_locale_meta(
    row: dict,
    *,
    content_locale: str,
    locale_pending: bool = False,
    locale_error: Optional[str] = None,
) -> dict:
    out = copy.deepcopy(row)
    out["content_locale"] = normalize_locale(content_locale)
    out["locale_pending"] = locale_pending
    if locale_error:
        out["locale_error"] = locale_error
    else:
        out.pop("locale_error", None)
    return out


def localize_breakdown(
    row: Optional[dict],
    locale: str,
    *,
    sync: bool = False,
) -> Optional[dict]:
    if not row:
        return row
    loc = normalize_locale(locale)
    output_locale = normalize_locale(row.get("output_locale") or "en")

    if row.get("status") != "completed":
        return _with_locale_meta(row, content_locale=output_locale, locale_pending=False)

    if loc == output_locale:
        return _with_locale_meta(row, content_locale=loc, locale_pending=False)

    variants = row.get("locale_variants") or {}
    if isinstance(variants, dict) and loc in variants:
        merged = _merge_breakdown_translation(row, variants[loc])
        return _with_locale_meta(merged, content_locale=loc, locale_pending=False)

    source = _extract_translatable_breakdown(row)
    if not any(source.values()):
        return _with_locale_meta(row, content_locale=output_locale, locale_pending=False)

    breakdown_id = str(row["id"])

    if sync:
        try:
            translated = _translate_breakdown_payload(source, loc)
            _save_breakdown_variant(breakdown_id, loc, translated)
            merged = _merge_breakdown_translation(row, translated)
            return _with_locale_meta(merged, content_locale=loc, locale_pending=False)
        except Exception as exc:
            logger.warning("[locale] sync breakdown translation failed: %s", exc)
            return _with_locale_meta(
                row,
                content_locale=output_locale,
                locale_pending=True,
                locale_error=_locale_error_message(exc),
            )

    _enqueue_breakdown_translation(breakdown_id, source, loc)
    return _with_locale_meta(row, content_locale=output_locale, locale_pending=True)


def _save_strategy_variant(user_id: str, account_id: str, locale: str, report: str) -> None:
    try:
        sb = get_supabase()
        res = (
            sb.table("analytics_tracked_accounts")
            .select("ai_strategy_report_i18n")
            .eq("user_id", user_id)
            .eq("id", account_id)
            .limit(1)
            .execute()
        )
        row = (res.data or [None])[0] or {}
        i18n = dict(row.get("ai_strategy_report_i18n") or {})
        i18n[normalize_locale(locale)] = report
        sb.table("analytics_tracked_accounts").update(
            {"ai_strategy_report_i18n": i18n},
        ).eq("user_id", user_id).eq("id", account_id).execute()
    except Exception as exc:
        logger.warning("[locale] failed to cache strategy variant: %s", exc)


def localize_strategy_report(
    *,
    report: Optional[str],
    report_locale: Optional[str],
    i18n_cache: Optional[dict],
    target_locale: str,
    user_id: str,
    account_id: str,
    sync: bool = False,
) -> Optional[str]:
    if not report:
        return report
    loc = normalize_locale(target_locale)
    source_locale = normalize_locale(report_locale or "en")
    if loc == source_locale:
        return report

    cache = i18n_cache if isinstance(i18n_cache, dict) else {}
    if loc in cache and cache[loc]:
        return str(cache[loc])

    if sync:
        try:
            translated = _translate_markdown(report, loc)
            if translated:
                _save_strategy_variant(user_id, account_id, loc, translated)
                return translated
        except Exception as exc:
            logger.warning("[locale] sync strategy translation failed: %s", exc)

    _enqueue_strategy_translation(user_id, account_id, report, loc)
    return report
