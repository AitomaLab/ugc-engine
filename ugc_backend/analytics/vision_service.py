"""Gemini-powered video breakdown service for the Analytics module.

Architecture
------------
Single ``analyze_video()`` coroutine that:

1. Downloads the input video to a temp file (Supabase Storage URL or external).
2. Runs **Pass 1** — structured JSON analysis matching the columns of
   ``analytics_video_breakdowns`` (summary, hook, scenes, audio,
   visual_details, key_moments). Retries once on invalid JSON.
3. Runs **Pass 2** — text-only call that feeds the Pass 1 output + the post's
   metrics into Gemini and returns three strategic takeaways
   (what worked / didn't / next test).
4. Persists the structured result + the raw markdown to the breakdown row.

Provider routing
----------------
The two passes have very different requirements, so they use **separate**
provider chains:

* **Pass 1 (video upload)** — `_detect_video_provider`:
    1. ``GEMINI_API_KEY`` → direct ``google-genai`` client (Files API).
    2. ``FAL_KEY``        → FAL's Gemini app.

  KIE is intentionally excluded here: KIE's Gemini proxy is OpenAI-compatible
  and exposes only chat completions. It has no ``/v1/files`` upload endpoint,
  and Gemini videos cannot be base64-inlined through OpenAI's ``video_url``
  shape (which requires a ``file_id`` from ``/v1/files``). Calling KIE for
  video uploads 404s every time — see the attached ``claude-vision`` skill
  for the canonical Gemini-direct pattern.

* **Pass 2 (text-only takeaways)** — `_detect_text_provider`:
    1. ``KIE_API_KEY``    → OpenAI-compatible chat completions.
    2. ``FAL_KEY``        → FAL's text endpoint.
    3. ``GEMINI_API_KEY`` → google-genai text call.

  All 3 work fine for text-only prompts.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


# MIME types per video extension — matches the claude-vision skill so the
# Content-Type we hand Gemini's Files API is always accurate. ``video/mp4``
# is the fallback for unknown extensions (Gemini will reject anything truly
# unsupported on its end).
_MIME_TYPES = {
    ".mp4":  "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg":  "video/mpg",
    ".mov":  "video/quicktime",
    ".avi":  "video/avi",
    ".flv":  "video/x-flv",
    ".webm": "video/webm",
    ".wmv":  "video/wmv",
    ".3gpp": "video/3gpp",
    ".3gp":  "video/3gpp",
    ".m4v":  "video/mp4",
    ".mkv":  "video/x-matroska",
}


def _mime_for(path: Path) -> str:
    return _MIME_TYPES.get(path.suffix.lower(), "video/mp4")


# ── Prompts ────────────────────────────────────────────────────────────────

# Pass 1 — strict JSON. Preserves the anti-hallucination rules from the
# original analyze_video.py prompt verbatim, but adds a JSON-schema-style
# contract so we can map results 1:1 to the breakdown columns.
PASS1_SYSTEM = """You are a careful video analyst. Output ONLY valid JSON matching the schema below — no prose, no markdown, no code fences.

CRITICAL ACCURACY RULES — follow these before anything else:
1. Only report what is ACTUALLY in the video. Do not infer, guess, or fill in plausible-sounding content. Many videos have silent audio tracks, no narration, no on-screen speaker, or no branding — this is NORMAL and you must report it accurately.
2. NEVER invent a presenter, creator, narrator, or speaker name. If no name is shown on screen or clearly spoken aloud, the video has no identified creator — say so.
3. NEVER fabricate a voiceover, dialogue, or transcript. If the audio track is silent, near-silent, or contains no speech, set audio.has_audio=false and explain in audio.notes.
4. Distinguish between what you SEE (high confidence) and what you INFER (lower confidence). If you must infer, label it: "(inferred)".
5. Screen recordings often have no audio at all. This is the default expectation, not an anomaly.

OUTPUT SCHEMA (return JSON exactly matching this shape — extra keys are dropped):
{
  "summary": "2-3 sentences of what actually happens in the video.",
  "hook": {
    "timestamp": "00:00-00:03",
    "on_screen_text": "verbatim text visible during the hook window, or null",
    "visual": "what is happening visually in the first 3s",
    "why_it_works": "1 sentence on the hook's pattern-interrupt / curiosity gap / payoff promise — or why it falls flat"
  },
  "scenes": [
    { "start": "MM:SS", "end": "MM:SS", "description": "what is on screen", "on_screen_text": "verbatim, or null" }
  ],
  "audio": {
    "has_audio": true,
    "transcript": [ { "ts": "MM:SS", "text": "verbatim line" } ],
    "notes": "describe music/SFX/ambient noise, or note 'silent track' if nothing relevant"
  },
  "visual_details": [ "string", "string" ],
  "key_moments": [ { "ts": "MM:SS", "description": "memorable moment" } ]
}

If a section has no content, return an empty array / empty string / has_audio=false rather than inventing content."""


PASS2_SYSTEM = """You are a creative strategist analyzing how a single short-form video performed. You will receive (1) a structured breakdown of the video and (2) its performance metrics. Return ONLY a JSON array of exactly 3 short strings — no prose, no markdown.

The three strings, in order, should answer:
1. What worked (concrete element + why metrics suggest it landed)
2. What didn't work (concrete weakness + why metrics suggest it underperformed)
3. What to test next (one specific, testable change for the next iteration)

Keep each string under 200 characters. Be concrete and specific to this video — do not give generic advice."""


# ── Public types ───────────────────────────────────────────────────────────

@dataclass
class VisionResult:
    summary: Optional[str] = None
    hook: Optional[dict] = None
    scenes: Optional[list[dict]] = None
    audio: Optional[dict] = None
    visual_details: Optional[list[str]] = None
    key_moments: Optional[list[dict]] = None
    takeaways: Optional[list[str]] = None
    raw_markdown: Optional[str] = None
    model: Optional[str] = None
    provider: Optional[str] = None
    error_message: Optional[str] = None

    def as_db_updates(self) -> dict:
        return {
            "summary": self.summary,
            "hook": self.hook,
            "scenes": self.scenes,
            "audio": self.audio,
            "visual_details": self.visual_details,
            "key_moments": self.key_moments,
            "takeaways": self.takeaways,
            "raw_markdown": self.raw_markdown,
            "model": self.model,
            "provider": self.provider,
            "error_message": self.error_message,
        }


# ── Helpers ────────────────────────────────────────────────────────────────

_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_MAX_VIDEO_BYTES = int(os.getenv("ANALYTICS_MAX_VIDEO_BYTES", str(150 * 1024 * 1024)))


def _detect_video_provider() -> str:
    """Pick the provider that can actually upload a video to Gemini.

    Order matters: Gemini-direct first (uses the official Files API per the
    claude-vision skill), FAL second (hosts Gemini behind its own upload
    pipeline). KIE is **deliberately excluded** — its OpenAI-compatible
    proxy doesn't expose ``/v1/files`` for Gemini, so video uploads 404.
    """
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if os.getenv("FAL_KEY"):
        return "fal"
    raise RuntimeError(
        "No video-capable provider configured. Set GEMINI_API_KEY in .env.saas "
        "(get one at https://aistudio.google.com/apikey) to enable AI breakdowns. "
        "KIE_API_KEY alone is not sufficient — KIE's Gemini proxy does not "
        "support video file uploads."
    )


def _detect_text_provider() -> str:
    """Pick the provider for the text-only Pass 2 takeaways call.

    All three providers work for plain text, so we keep the original cost-
    ordered chain (KIE first because it's typically the cheapest tier).
    """
    if os.getenv("KIE_API_KEY"):
        return "kie"
    if os.getenv("FAL_KEY"):
        return "fal"
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    raise RuntimeError(
        "No LLM provider configured. Set one of KIE_API_KEY, FAL_KEY, or GEMINI_API_KEY."
    )


def _ext_from_url(url: str) -> str:
    for ext in (".mp4", ".mov", ".webm", ".mkv", ".m4v"):
        if ext in url.lower():
            return ext
    return ".mp4"


def _download_video(url: str) -> Path:
    """Stream a video to a temp file. Raises if size exceeds the cap."""
    ext = _ext_from_url(url)
    fd, tmp_path = tempfile.mkstemp(prefix="analytics_video_", suffix=ext)
    os.close(fd)
    tmp = Path(tmp_path)
    bytes_written = 0
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=120) as resp:
            resp.raise_for_status()
            with open(tmp, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > _MAX_VIDEO_BYTES:
                        raise RuntimeError(
                            f"Video exceeds {_MAX_VIDEO_BYTES // (1024 * 1024)}MB cap"
                        )
                    f.write(chunk)
        return tmp
    except Exception:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass
        raise


_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}", re.MULTILINE)


def _coerce_json(text: str) -> Optional[dict]:
    """Best-effort JSON extraction. Returns None if no valid object found."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        # Strip ```json fences if the model added them despite the instruction.
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = _JSON_BLOCK_RE.search(text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            return None
    return None


# ── Provider implementations ───────────────────────────────────────────────

def _call_gemini_video(prompt: str, video_path: Path, *, model: str) -> str:
    """Direct google-genai call — mirrors the claude-vision skill verbatim.

    Inline path (≤18 MB) uses ``types.Blob``; larger files go through the
    Files API (``client.files.upload`` + poll for ACTIVE). This is the only
    provider chain in this module that can actually upload a video to
    Gemini — see ``_detect_video_provider`` for the rationale.
    """
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError(
            "google-genai is not installed. Add `google-genai>=1.0` to requirements.txt."
        ) from e

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    size = video_path.stat().st_size
    mime = _mime_for(video_path)

    if size <= 18 * 1024 * 1024:
        logger.info(
            "[vision] provider=gemini model=%s size=%.1fMB inline=true",
            model, size / 1024 / 1024,
        )
        part = types.Part(inline_data=types.Blob(data=video_path.read_bytes(), mime_type=mime))
    else:
        logger.info(
            "[vision] provider=gemini model=%s size=%.1fMB inline=false (Files API)",
            model, size / 1024 / 1024,
        )
        uploaded = client.files.upload(file=str(video_path))
        elapsed = 0
        while elapsed < 300:
            refreshed = client.files.get(name=uploaded.name)
            state = getattr(refreshed.state, "name", str(refreshed.state))
            if state == "ACTIVE":
                part = types.Part(
                    file_data=types.FileData(
                        file_uri=refreshed.uri,
                        mime_type=refreshed.mime_type or mime,
                    )
                )
                break
            if state == "FAILED":
                raise RuntimeError("Gemini Files API failed to process upload")
            time.sleep(3)
            elapsed += 3
        else:
            raise RuntimeError("Gemini Files API processing timed out after 300s")

    resp = client.models.generate_content(
        model=model,
        contents=types.Content(parts=[part, types.Part(text=prompt)]),
    )
    return resp.text or ""


def _call_gemini_text(prompt: str, *, model: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    resp = client.models.generate_content(
        model=model,
        contents=types.Content(parts=[types.Part(text=prompt)]),
    )
    return resp.text or ""


def _call_kie_video(prompt: str, video_path: Path, *, model: str) -> str:
    """KIE AI does **not** support video uploads to Gemini.

    KIE's Gemini routing exposes only the OpenAI-compatible chat completions
    endpoint, not ``POST /v1/files``. Calling ``client.files.create`` returns
    a 404 (``{"status":404,"path":"/v1/files"}``). Gemini videos also can't be
    base64-inlined through OpenAI's ``video_url`` shape (it requires a
    ``file_id`` from ``/v1/files``).

    This function is kept as a defensive shim — the dispatcher should never
    reach it now that ``_detect_video_provider`` skips KIE for video — but if
    it ever does, the error message tells the operator exactly what to fix.
    """
    raise RuntimeError(
        "KIE AI does not support video uploads to Gemini (POST /v1/files returns 404). "
        "Set GEMINI_API_KEY in .env.saas (https://aistudio.google.com/apikey) to enable "
        "video breakdowns. See vision_service._detect_video_provider for the provider chain."
    )


def _call_kie_text(prompt: str, *, model: str) -> str:
    from openai import OpenAI

    base_url = os.getenv("KIE_BASE_URL", "https://api.kie.ai/v1")
    client = OpenAI(api_key=os.environ["KIE_API_KEY"], base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    return response.choices[0].message.content or ""


def _call_fal_video(prompt: str, video_path: Path, *, model: str) -> str:
    """FAL AI Gemini endpoint. FAL hosts Gemini behind their `fal-ai/gemini` ID
    family and accepts a video URL or base64-encoded file."""
    try:
        import fal_client  # type: ignore
    except ImportError as e:
        raise RuntimeError(
            "fal_client not installed but FAL_KEY is set. Add `fal_client` to requirements.txt."
        ) from e

    size = video_path.stat().st_size
    logger.info(
        "[vision] provider=fal model=%s size=%.1fMB",
        model, size / 1024 / 1024,
    )

    # fal_client picks up FAL_KEY from env automatically.
    uploaded_url = fal_client.upload_file(str(video_path))
    fal_app = os.getenv("FAL_GEMINI_APP", "fal-ai/gemini-flash-vision")
    result = fal_client.run(
        fal_app,
        arguments={"prompt": prompt, "media_url": uploaded_url, "model": model},
    )
    if isinstance(result, dict):
        return result.get("output") or result.get("text") or json.dumps(result)
    return str(result)


def _call_fal_text(prompt: str, *, model: str) -> str:
    import fal_client  # type: ignore

    fal_app = os.getenv("FAL_GEMINI_TEXT_APP", "fal-ai/gemini-flash")
    result = fal_client.run(fal_app, arguments={"prompt": prompt, "model": model})
    if isinstance(result, dict):
        return result.get("output") or result.get("text") or json.dumps(result)
    return str(result)


# ── Dispatcher ─────────────────────────────────────────────────────────────

# Transient upstream signals we should retry on instead of surfacing to the
# user. Match on substrings so we cover both raw HTTP-status exceptions
# (`503 UNAVAILABLE`) and structured google-genai exceptions whose `repr()`
# embeds the status string.
_TRANSIENT_SIGNALS = (
    "503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED",
    "429", "rate limit", "rate_limit", "high demand", "currently experiencing",
    "Service Unavailable", "Bad Gateway", "502", "504", "Gateway Timeout",
    "Connection reset", "Connection aborted", "Read timed out", "timed out",
)

_RETRY_DELAYS_SEC = (3, 6, 12)


def _is_transient_error(err: BaseException) -> bool:
    text = f"{type(err).__name__}: {err}"
    return any(sig.lower() in text.lower() for sig in _TRANSIENT_SIGNALS)


def _friendly_error(err: BaseException) -> str:
    """Map a raw exception into copy we'd be happy to show in the UI.

    Gemini / OpenAI / FAL upstream errors are often opaque JSON payloads.
    We classify the few we care about and fall back to a generic line for
    the rest. Anything user-facing must NOT include raw provider JSON or
    stack-trace style detail — the `error_message` column ends up rendered
    verbatim by `HookBreakdownPanel`.
    """
    text = f"{type(err).__name__}: {err}"
    low = text.lower()
    if any(sig.lower() in low for sig in ("503", "unavailable", "high demand", "currently experiencing")):
        return ("The AI analysis service is temporarily busy. "
                "We'll retry automatically — or you can try again in a moment.")
    if any(sig.lower() in low for sig in ("429", "rate limit", "resource_exhausted")):
        return ("We've hit the per-minute rate limit on the AI provider. "
                "Try again in a minute.")
    if "deadline_exceeded" in low or "timed out" in low or "504" in low:
        return ("The analysis took too long this time. "
                "We'll keep trying — give it another go in a moment.")
    if "size" in low and "cap" in low:
        return "This video is too large to analyze right now."
    if "no llm provider" in low or "gemini_api_key" in low:
        return "AI analysis is not configured on this environment yet."
    # Generic fallback — never the raw API payload.
    return "AI analysis is temporarily unavailable. Please try again."


def _call_with_retry(label: str, fn, *args, **kwargs):
    """Run `fn(*args, **kwargs)` with bounded exponential backoff on
    transient upstream errors. Non-transient errors raise immediately.

    Total worst-case wait: 3 + 6 + 12 = 21s — well inside the breakdown
    background job's tolerance, and short enough that the user sees a
    spinner rather than a failure card for the common 503-recovery path.
    """
    last_err: Optional[BaseException] = None
    for attempt, delay in enumerate([0, *_RETRY_DELAYS_SEC]):
        if delay:
            time.sleep(delay)
        try:
            return fn(*args, **kwargs)
        except Exception as e:  # noqa: BLE001
            last_err = e
            if not _is_transient_error(e):
                raise
            logger.warning(
                "[vision] transient upstream error on %s (attempt %d/%d): %s",
                label, attempt + 1, len(_RETRY_DELAYS_SEC) + 1, type(e).__name__,
            )
    assert last_err is not None
    raise last_err


def _run_pass1(video_path: Path, *, provider: str, model: str) -> str:
    prompt = PASS1_SYSTEM
    if provider == "fal":
        return _call_with_retry("pass1.fal", _call_fal_video, prompt, video_path, model=model)
    if provider == "kie":
        # Defensive: _detect_video_provider should never return "kie".
        return _call_kie_video(prompt, video_path, model=model)
    return _call_with_retry("pass1.gemini", _call_gemini_video, prompt, video_path, model=model)


def _run_pass2(structured: dict, metrics: dict, *, provider: str, model: str) -> str:
    payload = {"breakdown": structured, "metrics": metrics}
    prompt = PASS2_SYSTEM + "\n\n--- INPUT ---\n" + json.dumps(payload, ensure_ascii=False, indent=2)
    if provider == "kie":
        return _call_with_retry("pass2.kie", _call_kie_text, prompt, model=model)
    if provider == "fal":
        return _call_with_retry("pass2.fal", _call_fal_text, prompt, model=model)
    return _call_with_retry("pass2.gemini", _call_gemini_text, prompt, model=model)


# ── Sanitizers ─────────────────────────────────────────────────────────────

def _sanitize_structured(data: dict) -> dict:
    """Coerce model output into the exact column shapes we persist."""
    out: dict[str, Any] = {}
    if isinstance(data.get("summary"), str):
        out["summary"] = data["summary"].strip()
    if isinstance(data.get("hook"), dict):
        out["hook"] = {
            "timestamp": data["hook"].get("timestamp"),
            "on_screen_text": data["hook"].get("on_screen_text"),
            "visual": data["hook"].get("visual"),
            "why_it_works": data["hook"].get("why_it_works"),
        }
    if isinstance(data.get("scenes"), list):
        out["scenes"] = [
            {
                "start": s.get("start"),
                "end": s.get("end"),
                "description": s.get("description"),
                "on_screen_text": s.get("on_screen_text"),
            }
            for s in data["scenes"]
            if isinstance(s, dict)
        ]
    if isinstance(data.get("audio"), dict):
        a = data["audio"]
        out["audio"] = {
            "has_audio": bool(a.get("has_audio")),
            "transcript": [
                {"ts": t.get("ts"), "text": t.get("text")}
                for t in (a.get("transcript") or [])
                if isinstance(t, dict)
            ],
            "notes": a.get("notes"),
        }
    if isinstance(data.get("visual_details"), list):
        out["visual_details"] = [str(x) for x in data["visual_details"] if x]
    if isinstance(data.get("key_moments"), list):
        out["key_moments"] = [
            {"ts": k.get("ts"), "description": k.get("description")}
            for k in data["key_moments"]
            if isinstance(k, dict)
        ]
    return out


def _sanitize_takeaways(text: str) -> Optional[list[str]]:
    parsed = _coerce_json(text)
    if isinstance(parsed, list):
        result = [str(x).strip() for x in parsed if str(x).strip()][:3]
        return result or None
    # Fallback: split by lines / bullets so we still surface SOMETHING when
    # Gemini disregards the JSON contract.
    lines = [
        l.strip("-• \t").strip()
        for l in (text or "").splitlines()
        if l.strip().strip("-• \t")
    ]
    return lines[:3] or None


# ── Public entry point ─────────────────────────────────────────────────────

def analyze_video(*, video_url: str, metrics: Optional[dict] = None) -> VisionResult:
    """Run the full two-pass analysis. Synchronous — designed to run inside a
    background thread spawned by jobs.run_breakdown_in_background.
    """
    model = _MODEL

    # Detect the video-capable provider up front so a missing GEMINI_API_KEY
    # surfaces as a clean error_message on the breakdown row instead of a
    # generic 500 from a downstream call.
    try:
        video_provider = _detect_video_provider()
    except RuntimeError as e:
        logger.error("[vision] No video provider available: %s", e)
        return VisionResult(model=model, error_message=str(e))

    text_provider = _detect_text_provider()
    logger.info(
        "[vision] starting analyze_video video_provider=%s text_provider=%s model=%s url=%s",
        video_provider, text_provider, model, video_url[:80],
    )

    tmp_path: Optional[Path] = None
    try:
        tmp_path = _download_video(video_url)

        raw_text = _run_pass1(tmp_path, provider=video_provider, model=model)
        parsed = _coerce_json(raw_text)
        if parsed is None:
            # Retry once with an explicit instruction reminder.
            raw_text_retry = _run_pass1(tmp_path, provider=video_provider, model=model)
            parsed = _coerce_json(raw_text_retry)
            if parsed is None:
                return VisionResult(
                    raw_markdown=raw_text,
                    model=model,
                    provider=video_provider,
                    error_message="Pass 1 did not return valid JSON after retry.",
                )
            raw_text = raw_text_retry

        sanitized = _sanitize_structured(parsed)

        # Pass 2 — strategic takeaways (text-only, can use any provider)
        takeaways: Optional[list[str]] = None
        try:
            tk_text = _run_pass2(sanitized, metrics or {}, provider=text_provider, model=model)
            takeaways = _sanitize_takeaways(tk_text)
        except Exception as e:
            # Don't fail the whole breakdown just because takeaways flopped.
            logger.warning("[vision] Pass 2 takeaways failed: %s", e)
            sanitized.setdefault("takeaways_error", str(e)[:300])

        return VisionResult(
            summary=sanitized.get("summary"),
            hook=sanitized.get("hook"),
            scenes=sanitized.get("scenes"),
            audio=sanitized.get("audio"),
            visual_details=sanitized.get("visual_details"),
            key_moments=sanitized.get("key_moments"),
            takeaways=takeaways,
            raw_markdown=raw_text,
            model=model,
            provider=video_provider,
        )
    except Exception as e:
        # Log the raw exception for debugging — never surface it verbatim.
        logger.exception("[vision] analyze_video failed: %s", e)
        return VisionResult(
            model=model,
            provider=video_provider,
            # Friendly, classified copy goes to the breakdown row and into
            # the modal. The raw exception stays in the server log only.
            error_message=_friendly_error(e),
        )
    finally:
        if tmp_path:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
