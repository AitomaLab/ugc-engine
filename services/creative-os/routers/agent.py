"""
Creative OS — Managed Agent Router

Endpoints:
  GET  /creative-os/agent/thread?project_id=...   load persisted thread
  POST /creative-os/agent/stream                  SSE stream of one turn
  POST /creative-os/agent/reset                   delete the thread
  POST /creative-os/agent/stop                    interrupt the active run

The frontend talks to this router. The router talks to the
ManagedAgentClient (which talks to Anthropic) and to the agent_threads
Supabase table for persistence. Supabase is the source of truth.
"""
from __future__ import annotations

import asyncio
import json
from time import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user
from services.agent_threads import get_thread, reset_thread, upsert_thread
from services.managed_agent_client import (
    get_managed_agent_client,
    _detect_input_language,
    is_dynamic_speaking_ugc,
    has_routing_character_for_session,
    _recent_agent_turn_text,
    session_has_multi_video_intent,
    CAMPAIGN_INTENT_RE,
)

router = APIRouter(prefix="/agent", tags=["managed-agent"])

# Per-project concurrency guard — prevents duplicate stream requests from
# crashing the active Anthropic session (which rejects user.message while
# tool calls are pending).
_active_streams: dict[str, asyncio.Lock] = {}


# ── Schemas ────────────────────────────────────────────────────────────
class AgentRef(BaseModel):
    type: str  # 'product' | 'influencer' | 'clone' | 'image' | 'video'
    tag: str   # the @-token the user typed, e.g. 'tea_94802f09'
    name: Optional[str] = None
    id: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    shot_id: Optional[str] = None
    job_id: Optional[str] = None
    app_clip_id: Optional[str] = None
    look_id: Optional[str] = None
    product_type: Optional[str] = None  # 'physical' | 'digital'


class AgentRunRequest(BaseModel):
    brief: str
    project_id: str
    refs: Optional[list[AgentRef]] = None
    use_seedance: bool = False
    lang: Optional[str] = None  # 'en' | 'es' — steers conversational reply language
    quick_mode: bool = False


class AgentResetRequest(BaseModel):
    project_id: str


class AgentStopRequest(BaseModel):
    project_id: str


class AgentPrewarmRequest(BaseModel):
    project_id: str


def _now_ms() -> int:
    return int(time() * 1000)


# ── GET /agent/thread ──────────────────────────────────────────────────
@router.get("/thread")
async def get_agent_thread(
    project_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    thread = await get_thread(user["token"], user["id"], project_id)
    if not thread:
        return {"session_id": None, "turns": []}
    return {
        "session_id": thread.get("anthropic_session_id"),
        "turns": thread.get("turns") or [],
    }


# ── POST /agent/reset ──────────────────────────────────────────────────
@router.post("/reset")
async def reset_agent_thread(
    data: AgentResetRequest,
    user: dict = Depends(get_current_user),
):
    ok = await reset_thread(user["token"], user["id"], data.project_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to reset thread")
    return {"ok": True}


# ── POST /agent/stop ───────────────────────────────────────────────────
@router.post("/stop")
async def stop_agent(
    data: AgentStopRequest,
    user: dict = Depends(get_current_user),
):
    # Always clear the project's concurrency lock so the next /stream can start
    # fresh, even if the previous run is wedged (hung SSE, dropped client, etc).
    # A still-running task in the old lock finishes harmlessly into a lock no
    # one is waiting on.
    _active_streams.pop(data.project_id, None)

    thread = await get_thread(user["token"], user["id"], data.project_id)
    session_id = thread.get("anthropic_session_id") if thread else None
    if not session_id:
        return {"ok": True, "lock_cleared": True, "session_interrupted": False}
    try:
        client = get_managed_agent_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    try:
        await client.interrupt_session(session_id)
    except Exception as e:
        return {"ok": True, "lock_cleared": True, "session_interrupted": False, "interrupt_error": str(e)}
    return {"ok": True, "lock_cleared": True, "session_interrupted": True}


# ── POST /agent/session/prewarm ────────────────────────────────────────
@router.post("/session/prewarm")
async def prewarm_agent_session(
    data: AgentPrewarmRequest,
    user: dict = Depends(get_current_user),
):
    """Eagerly create an Anthropic session before the user sends their first
    message. Idempotent at the frontend level: the panel only calls this when
    its hydrated thread has no `session_id`.
    """
    # If a thread already has a stored session, return it — no waste.
    thread = await get_thread(user["token"], user["id"], data.project_id)
    existing = (thread or {}).get("anthropic_session_id")
    if existing:
        return {"session_id": existing, "created": False}

    try:
        client = get_managed_agent_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    try:
        session_id = await client.prewarm_session(data.project_id)
    except Exception as e:
        # Non-fatal — the send path will fall back to creating a session on
        # demand. We just return a 200 with no id so the frontend doesn't
        # surface an error toast.
        print(f"[agent_prewarm] failed: {e}")
        return {"session_id": None, "created": False, "error": str(e)}

    try:
        await upsert_thread(
            user["token"], user["id"], data.project_id,
            anthropic_session_id=session_id,
            turns=(thread or {}).get("turns") or [],
        )
    except Exception as e:
        print(f"[agent_prewarm] upsert failed: {e}")

    return {"session_id": session_id, "created": True}


# ── POST /agent/stream (SSE) ───────────────────────────────────────────
@router.post("/stream")
async def agent_stream(
    data: AgentRunRequest,
    user: dict = Depends(get_current_user),
):
    if not data.brief.strip():
        raise HTTPException(status_code=400, detail="brief is required")

    # Concurrency guard: one stream per project at a time.
    if data.project_id not in _active_streams:
        _active_streams[data.project_id] = asyncio.Lock()
    lock = _active_streams[data.project_id]
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Agent is already running for this project. Wait for it to finish or stop it first.",
        )

    try:
        client = get_managed_agent_client()
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    user_token = user["token"]
    user_id = user["id"]
    project_id = data.project_id
    brief = data.brief
    refs = data.refs or []

    # Build a structured "Referenced assets" preface so the model receives
    # explicit IDs / URLs for everything the user @-mentioned. This is what
    # the agent reads when deciding which tool to call.
    augmented_brief = brief
    seedance_marker = (
        "[ENGINE=seedance — use seedance_2_ugc / seedance_2_cinematic / seedance_2_product "
        "video modes for this turn. Do NOT use ugc or cinematic_video modes.]"
    )
    # Explicit negative marker when the toggle is OFF. Without this, the agent
    # carries Seedance preference over from earlier turns (sessions are
    # persistent) — an absent marker is not a strong enough signal to override
    # prior-turn behavior.
    default_marker = (
        "[ENGINE=default — use Veo 3.1 for `ugc` and Kling 3.0 for `cinematic_video` this turn. "
        "Do NOT use seedance_2_ugc / seedance_2_cinematic / seedance_2_product, regardless of "
        "what was used in earlier turns.]"
    )
    dynamic_speaking_engine_marker = (
        "[ENGINE=dynamic_speaking — walk-and-talk UGC. Use generate_video(mode=seedance_2_ugc, "
        "dynamic_speaking=true). This OVERRIDES the normal ENGINE=default ban on seedance_2_ugc for "
        "this brief only. Do NOT use create_ugc_video or create_bulk_campaign.]"
    )
    engine_marker = seedance_marker if data.use_seedance else default_marker
    quick_mode_marker = (
        "[QUICK_MODE=on]" if data.quick_mode else "[QUICK_MODE=off]"
    )

    # Detect the frontend's literal confirm-button text. When the user
    # clicks "Confirm" on a cost preview card, the frontend sends this
    # exact string as the user's next message. The agent is supposed to
    # immediately re-fire the previously-previewed gated tool with
    # confirmed=true and the same echo args — but Sonnet 4.6 sometimes
    # hallucinates the post-confirm action ("Looks like there was a
    # server-side hiccup on all 3 — want me to retry?") without ever
    # emitting the tool_use. The SYSTEM_PROMPT's anti-hallucination rule
    # (line 167) isn't always followed in practice. Inject a hard
    # per-turn reinforcement when we see the confirm text.
    _CONFIRM_BUTTON_TEXTS = {
        "Confirmed — proceed with the pending generation now.",
        "Confirmed - proceed with the pending generation now.",
    }
    is_post_confirm = brief.strip() in _CONFIRM_BUTTON_TEXTS
    post_confirm_marker = (
        "[POST-CONFIRM TURN — the user just clicked Confirm on the cost "
        "preview card from the prior turn. You MUST emit a tool_use block "
        "for the SAME gated tool you previewed last turn, with "
        "confirmed=true and the SAME echo fields you received in the "
        "confirmation_required payload (prompt, mode, count, "
        "reference_image_urls, product_id, influencer_id, aspect_ratio, "
        "etc. — copy them exactly). Do NOT respond with prose alone. "
        "Do NOT report 'server-side hiccup', 'failure', or 'retry' — you "
        "have not called the tool yet, so you cannot have failures to "
        "report. Do NOT re-quote the cost. Do NOT call the tool again "
        "with confirmed=false. Just fire the tool with confirmed=true.]"
    ) if is_post_confirm else None

    # Edit-intent reminder — Claude has a strong pretrained pattern for emitting
    # `AI_EDIT_OPS` + an ops JSON array when asked to trim/edit/add music. That
    # format belongs to a DIFFERENT subsystem (the in-editor AI panel) and is
    # ignored by the dashboard — the user sees technical text and nothing happens.
    # The system prompt forbids it, but the pretrained pattern is strong enough
    # that per-turn reinforcement is needed when the brief contains edit verbs.
    import re as _re
    _brief_lc = brief.lower()
    # On-screen caption/subtitle requests — route to caption_video, NOT create_ugc_video.
    _caption_intent_re = _re.compile(
        r"\b(?:"
        r"(?:add|put|apply|burn|overlay|include|change|redo|restyle|update|swap|remove)"
        r"(?:\s+\w+){0,8}?\s+(?:captions?|subtitles?|subtitulos?|subtítulos?)"
        r"|"
        r"(?:hormozi|minimal|bold|karaoke)\s+(?:style\s+)?(?:captions?|subtitles?)"
        r"|"
        r"caption\s+this|caption\s+the\s+video"
        r")\b",
        _re.IGNORECASE,
    )
    # Regex: verb-near-noun patterns (add/swap/remove music | voiceover)
    # plus standalone edit verbs (trim / cut / shorten / re-edit).
    # Captions/subtitles are handled separately via _caption_intent_re.
    _edit_intent_re = _re.compile(
        r"\b(?:"
        r"(?:add|swap|replace|remove|change|insert|put|mix|layer|overlay|drop|stick|throw)"
        r"(?:\s+\w+){0,6}?\s+"
        r"(?:music|soundtrack|song|bgm|audio|voice\s?over|vo|narration)"
        r"|"
        r"trim|cut|shorten|re-?edit|edit\s+(?:the\s+)?(?:video|clip|timeline)"
        r")\b"
    )
    is_caption_intent = bool(_caption_intent_re.search(_brief_lc))
    is_edit_intent = bool(_edit_intent_re.search(_brief_lc)) and not is_caption_intent
    caption_reminder = (
        "[CAPTION TURN — the user wants on-screen subtitles burned onto an EXISTING video. "
        "Call `caption_video(job_id=..., style=..., placement=...)` immediately — NOT `create_ugc_video`, "
        "NOT `create_bulk_campaign`, and NOT `apply_editor_ops`. This is a fast overlay (~30s), NOT a "
        "~6 minute full UGC regeneration. If a video ref with `job_id` is in Referenced assets, use THAT "
        "job_id. If the user named a style (hormozi, minimal, bold, karaoke), call `caption_video` directly; "
        "if they did not name a style, call `list_caption_styles()` first. NEVER interpret 'add captions' "
        "as confirmation to fire a pending `create_ugc_video`. NEVER pass `subtitles_enabled=true` to "
        "`create_ugc_video` when a finished video already exists in this thread.]"
    )
    edit_reminder = (
        "[EDIT TURN REMINDER — do NOT respond with `AI_EDIT_OPS` text or any ops-JSON array as chat "
        "prose. That format is ignored by the dashboard and the edit will not apply. "
        "Call the actual tools: for trim / fade / speed / opacity / delete / text overlays / "
        "add music on a single video, call `apply_editor_ops(job_id, ops=[...])` with the same ops you "
        "would have emitted. For on-screen captions/subtitles, call `caption_video` — NEVER "
        "`apply_editor_ops` or `create_ugc_video`. For swap/remove/add-music on a finished COMBINED video, "
        "call combine_videos again with the ORIGINAL per-clip source URLs from earlier in this thread + "
        "`music_prompt` (and `mute_audio_indices` if needed). Never emit ops text without a matching "
        "tool_use block.]"
    )

    # Ref carry-forward: the frontend only re-sends a ref on a follow-up
    # turn when the user re-types the @-tag (AgentPanel.tsx). So follow-up
    # messages like "opcion 1 mejor" or "ok dale" arrive with `refs=[]`
    # even when the user @-mentioned the influencer / product / app_clip
    # earlier in the same conversation. Without this carry-forward, the
    # agent goes to fire `create_ugc_video`, has no IDs, and falls back to
    # fuzzy `list_project_assets` matching that often misses the right
    # asset ("I don't see Lucía or NAIARA in this project's assets").
    #
    # We ONLY carry forward when the current turn has zero refs of its
    # own. If the user explicitly attached or @-mentioned anything this
    # turn, treat it as a fresh task and trust their selection — silently
    # merging in stale state from earlier in the thread otherwise mixes
    # asset types (e.g. CeraVe lotion + a NAIARA app_clip from a prior
    # Lucía-promoting-NAIARA video) and confuses the agent into either
    # hallucinating a response or calling the wrong tool.
    #
    # This subsumes the previous edit-intent-only sticky-video special
    # case ("make it louder" / "try a different bed") — those follow-ups
    # arrive with refs=[] today, so they still benefit; explicit
    # @-mention edits already carry the video URL on the current turn.
    sticky_video_ref: Optional[AgentRef] = None
    has_video_ref = any(r.video_url for r in refs)
    carried_refs: list[AgentRef] = []
    _prior_turns_all: list[dict] = []
    try:
        _prior_thread = await get_thread(user_token, user_id, project_id)
        _prior_turns_all = list((_prior_thread or {}).get("turns") or [])
    except Exception as _e:
        print(f"[agent_stream] prior thread load failed: {_e}")

    _RETRY_BRIEF_RE = _re.compile(
        r"^\s*(?:retry|try\s+again|re-?try|again|once\s+more)\s*[!.?]*\s*$",
        _re.IGNORECASE,
    )
    if _RETRY_BRIEF_RE.match(brief.strip()) and not is_caption_intent:
        for _past in reversed(_prior_turns_all):
            _role = _past.get("role")
            _txt = _past.get("text") or ""
            if _role == "user" and _caption_intent_re.search(_txt.lower()):
                is_caption_intent = True
                brief = "add captions to the video"
                print("[agent_stream] retry-after-caption: rewrote bare retry brief")
                break
            if _role == "agent" and "editing assistant is temporarily unavailable" in _txt.lower():
                is_caption_intent = True
                brief = "add captions to the video"
                print("[agent_stream] retry-after-caption-failure: rewrote bare retry brief")
                break

    if not refs:
        try:
            # Filter to AgentRef's known fields so unknown keys don't break validation.
            _allowed = set(AgentRef.model_fields.keys())
            seen_types: set[str] = set()

            def _has_core(types: set[str]) -> bool:
                # The cinematic / UGC / campaign flows pick the product and the
                # creator in SEPARATE turns (one selector per message). The core
                # set we need carried forward is a product PLUS a creator.
                return "product" in types and ("influencer" in types or "clone" in types)

            # Walk back across MULTIPLE ref-bearing turns — not just the most
            # recent one. When the user selects product then influencer in two
            # separate turns, the gated tool (e.g. create_cinematic_ad) fires on
            # a later ref-less button-click turn (direction pick / Confirm), so
            # only carrying the single most-recent ref turn drops the product
            # (its selected shot URL) and the backend falls back to the default
            # DB profile image. We keep collecting unseen ref types until the
            # core product+creator pair is gathered, a turn adds nothing new, or
            # a small cap of ref-bearing turns is inspected (bounds staleness on
            # long threads / prior unrelated tasks).
            _MAX_REF_TURNS = 3
            _ref_turns_seen = 0
            for _past in reversed(_prior_turns_all):
                if _past.get("role") != "user":
                    continue
                _turn_refs = _past.get("refs") or []
                if not _turn_refs:
                    # Ref-less user turn (e.g. "retry", "Confirmed — proceed
                    # with the pending generation now."). These intermediate
                    # messages must NOT terminate the walk — otherwise the
                    # @-mentioned product/influencer from the original request
                    # are dropped and NanoBanana hallucinates a random
                    # person/product. Skip and keep walking back to the most
                    # recent turn that actually carried refs.
                    continue
                _added_new = False
                for _pr in _turn_refs:
                    t = _pr.get("type")
                    if is_caption_intent and t != "video" and not _pr.get("video_url"):
                        continue
                    if not t or t in seen_types:
                        continue
                    try:
                        resurrected = AgentRef(**{k: v for k, v in _pr.items() if k in _allowed})
                    except Exception:
                        continue
                    carried_refs.append(resurrected)
                    seen_types.add(t)
                    _added_new = True
                    if resurrected.video_url and not has_video_ref:
                        sticky_video_ref = resurrected
                        has_video_ref = True
                _ref_turns_seen += 1
                # Caption turns only need the finished video ref — stop once found.
                if is_caption_intent and sticky_video_ref:
                    break
                # Stop once we have the core product+creator pair, or this
                # ref-bearing turn added nothing new (we've crossed into
                # redundant / older state), or we've inspected the cap.
                if (
                    _has_core(seen_types)
                    or not _added_new
                    or _ref_turns_seen >= _MAX_REF_TURNS
                ):
                    break
        except Exception as _e:
            print(f"[agent_stream] prior-ref carry-forward failed: {_e}")
    if carried_refs:
        refs = list(refs) + carried_refs
        print(f"[agent_stream] prior-ref carry-forward: re-attached {len(carried_refs)} ref(s) ({sorted(set(r.type for r in carried_refs if r.type))}) from prior user turn (current turn had no refs)")

    _ugc_intent_re = _re.compile(
        r"\b(?:"
        r"ugc|create\s+(?:a\s+)?(?:ugc\s+)?ad|product\s+showcase|anuncio\s+ugc|"
        r"video\s+for\s+(?:my\s+)?product|make\s+(?:a\s+)?(?:ugc\s+)?video|"
        r"crear\s+(?:un\s+)?(?:anuncio|video)\s+ugc"
        r")\b",
        _re.IGNORECASE,
    )
    _product_shots_intent_re = _re.compile(
        r"\b(?:"
        r"generate(?:\s+\d+)?\s+product\s+shots|product\s+shots|"
        r"generar(?:\s+\d+)?\s+tomas?\s+de\s+producto|tomas?\s+de\s+producto"
        r")\b",
        _re.IGNORECASE,
    )
    _model_led_ad_images_re = _re.compile(
        r"\b(?:"
        r"commercial\s+ads?\s+images?|ad\s+images?|"
        r"imágenes?\s+(?:de\s+)?anuncios?"
        r")\b",
        _re.IGNORECASE,
    )
    _cinematic_ad_intent_re = _re.compile(
        r"\b(?:"
        r"cinematic\s+ad|cinematic\s+video|cinematic\s+spot|anuncio\s+cinematogr|"
        r"anuncio\s+cinemático|vídeo\s+cinematográfico|spot\s+cinemático|"
        r"commercial\s+ad|anuncio\s+comercial|create\s+a\s+cinematic|"
        r"crear\s+(?:un\s+)?anuncio\s+cinematogr"
        r")\b",
        _re.IGNORECASE,
    )
    _presenter_intent_re = _re.compile(
        r"\b(?:"
        r"with\s+(?:a\s+)?(?:model|influencer|creator|person|presenter|host|spokesperson)|"
        r"model[\s-]led|starring|featuring|who\s+should|"
        r"con\s+(?:un\s+)?(?:modelo|influencer|creador|persona|presentador)|"
        r"protagoniz|presentador"
        r")\b",
        _re.IGNORECASE,
    )
    _product_skip_re = _re.compile(
        r"(?:"
        r"^(?:skip|omitir)\b|"
        r"influencer[\s-]only|creator[\s-]only|"
        r"solo\s+(?:influencer|creador|modelo)|"
        r"sin\s+producto|no\s+product"
        r")",
        _re.IGNORECASE,
    )
    _creator_skip_re = _re.compile(
        r"(?:"
        r"^(?:skip|omitir)\b|"
        r"product[\s-]only|solo\s+producto|"
        r"sin\s+(?:modelo|influencer|creador)|"
        r"no\s+(?:model|influencer|creator)"
        r")",
        _re.IGNORECASE,
    )
    _has_product_ref = any(r.type == "product" for r in refs)
    _has_creator_ref = any(r.type in ("influencer", "clone") for r in refs)

    bulk_reminder: Optional[str] = None
    if session_has_multi_video_intent(brief, _prior_turns_all):
        bulk_reminder = (
            "[MULTI-VIDEO REQUEST — the user wants MORE THAN ONE video. Dispatch via ONE bulk tool, "
            "NEVER N separate single-video calls (the engine de-dupes near-identical single calls, so "
            "only ONE would launch). "
            "UGC -> create_bulk_campaign (scripts[] one per video, or count). If duration is missing, "
            "ask with [[UGC_DURATION_BUTTONS]] (8s/15s/30s) — NEVER [[DURATION_BUTTONS]] for UGC. "
            "AI Clone -> create_bulk_clone (scripts[] or count). "
            "Cinematic -> if the user has NOT specified the format/length in the brief, FIRST confirm aspect ratio "
            "(end the message with [[ASPECT_BUTTONS]]) and, if still missing, duration (end with [[DURATION_BUTTONS]] "
            "for 5/10/15s only) — one marker per message, exactly as for a single cinematic ad — BEFORE "
            "create_cinematic_ad stage='propose'; then ONE create_cinematic_ad stage='bulk' with directions=[...]. "
            "ONE batched cost chip; on Confirm all N jobs launch at once.]"
        )

    def _session_is_product_shots() -> bool:
        if _model_led_ad_images_re.search(brief):
            return False
        if _product_shots_intent_re.search(brief):
            return True
        for _past in _prior_turns_all:
            if _past.get("role") == "user":
                _past_text = _past.get("text") or ""
                if _model_led_ad_images_re.search(_past_text):
                    return False
                if _product_shots_intent_re.search(_past_text):
                    return True
        return False

    _is_product_shots_session = _session_is_product_shots()

    def _session_user_text() -> str:
        parts = [brief or ""]
        for _past in _prior_turns_all:
            if _past.get("role") == "user":
                parts.append(_past.get("text") or "")
        return " ".join(parts)

    def _session_routing_text() -> str:
        """User turns plus recent agent script/visual-direction for routing."""
        parts = [_session_user_text()]
        _agent_tail = _recent_agent_turn_text(_prior_turns_all)
        if _agent_tail:
            parts.append(_agent_tail)
        return " ".join(p for p in parts if p).strip()

    def _session_skipped_product() -> bool:
        return bool(_product_skip_re.search(_session_user_text()))

    def _session_skipped_creator() -> bool:
        return bool(_creator_skip_re.search(_session_user_text()))

    def _session_wants_presenter() -> bool:
        if _session_skipped_creator():
            return False
        text = _session_user_text()
        if _model_led_ad_images_re.search(text):
            return True
        if _presenter_intent_re.search(text):
            return True
        if _has_creator_ref:
            return True
        for _past in _prior_turns_all:
            if _past.get("role") == "user":
                _past_refs = _past.get("refs") or []
                if any(
                    isinstance(r, dict) and r.get("type") in ("influencer", "clone")
                    for r in _past_refs
                ):
                    return True
        return False

    _routing_text = _session_routing_text()
    _refs_as_dicts = [{"type": r.type} for r in refs]
    _has_routing_character = has_routing_character_for_session(
        _routing_text,
        refs=_refs_as_dicts,
    )
    _is_dynamic_speaking = is_dynamic_speaking_ugc(
        _routing_text,
        has_character=_has_routing_character,
    )
    dynamic_speaking_reminder: Optional[str] = None
    if _is_dynamic_speaking:
        dynamic_speaking_reminder = (
            "[DYNAMIC_SPEAKING_UGC — do NOT use create_ugc_video or create_bulk_campaign. "
            "Use generate_video(mode=seedance_2_ugc, dynamic_speaking=true, clip_length=15). "
            "For 30s insistence pass target_duration=30. Pass hook with the script. "
            "After dispatch tell user ~10–12 min ETA (walk-and-talk complexity); watch Videos tab.]"
        )
        engine_marker = dynamic_speaking_engine_marker
    elif data.use_seedance:
        engine_marker = seedance_marker
    else:
        engine_marker = default_marker

    def _session_is_product_only_cinematic() -> bool:
        text = _session_user_text()
        if _model_led_ad_images_re.search(text):
            return False
        if not _cinematic_ad_intent_re.search(text):
            return False
        return not _session_wants_presenter()

    _is_product_only_cinematic = _session_is_product_only_cinematic()
    _reminder_lang = _detect_input_language(brief) or data.lang
    asset_selection_reminder: Optional[str] = None
    if (
        not _has_product_ref
        and not _session_skipped_product()
        and (_ugc_intent_re.search(brief) or _product_shots_intent_re.search(brief) or CAMPAIGN_INTENT_RE.search(brief))
    ):
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[SELECTOR DE ACTIVOS — el usuario aún no ha elegido un producto. Responde con UNA "
                "pregunta corta en español que termine con el marcador literal [[PRODUCT_SELECTOR]] "
                "en la última línea. El frontend muestra una cuadrícula visual de productos — NO "
                "listes nombres de productos en prosa. NO preguntes por influencer, guión o "
                "duración en el mismo mensaje.]"
            )
        else:
            asset_selection_reminder = (
                "[ASSET PICKER — user has not chosen a product yet. Reply with ONE short question "
                "ending with the literal marker [[PRODUCT_SELECTOR]] on the last line. The frontend "
                "renders a visual product grid — do NOT list product names in prose. Do NOT ask about "
                "influencer, script, or duration in the same message.]"
            )
    elif (
        not _has_product_ref
        and _session_skipped_product()
        and not _has_creator_ref
        and not _is_product_shots_session
        and not _is_dynamic_speaking
    ):
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[SOLO INFLUENCER — el usuario omitió el selector de producto. NO uses "
                "[[PRODUCT_SELECTOR]]. Pregunta quién debe presentar con [[CREATOR_SELECTOR]] si "
                "aún no hay creador. UGC → create_ugc_video / create_bulk_campaign solo con "
                "influencer_id, sin product_id. Imágenes → generate_image solo con ref de influencer.]"
            )
        else:
            asset_selection_reminder = (
                "[INFLUENCER-ONLY — user skipped product picker. Do NOT use [[PRODUCT_SELECTOR]]. "
                "Ask who should present with [[CREATOR_SELECTOR]] if creator not yet chosen. "
                "UGC → create_ugc_video / create_bulk_campaign with influencer_id only, no product_id. "
                "Images → generate_image with influencer ref only.]"
            )
    elif _has_creator_ref and not _has_product_ref and _session_skipped_product() and not _is_dynamic_speaking:
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[SOLO INFLUENCER — creador elegido, usuario omitió producto. Continúa sin product_id. "
                "UGC → create_ugc_video (talking-head, product_type=digital). "
                "Imágenes → generate_image solo con ref de influencer. "
                "NO uses [[PRODUCT_SELECTOR]].]"
            )
        else:
            asset_selection_reminder = (
                "[INFLUENCER-ONLY — creator chosen, user skipped product. Proceed without product_id. "
                "UGC → create_ugc_video (talking-head, product_type=digital). "
                "Images → generate_image with influencer ref only. "
                "Do NOT use [[PRODUCT_SELECTOR]].]"
            )
    elif _has_product_ref and not _has_creator_ref and _is_product_shots_session:
        asset_selection_reminder = (
            "[PRODUCT SHOTS — product is chosen (see Referenced assets). Call generate_product_shots "
            "with the product image_url from the preface. Do NOT ask for an influencer. "
            "Do NOT use [[CREATOR_SELECTOR]]. Proceed to the cost confirmation gate.]"
        )
    elif _has_product_ref and not _has_creator_ref and _is_product_only_cinematic:
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[ANUNCIO CINEMATOGRÁFICO DE PRODUCTO — el producto ya está elegido (ver Referenced assets). "
                "NO pidas creador ni uses [[CREATOR_SELECTOR]]. Llama create_cinematic_ad stage='propose' "
                "con el product_id de Referenced assets. Si falta formato o duración, pregunta con "
                "[[ASPECT_BUTTONS]] o [[DURATION_BUTTONS]] (un marcador por mensaje) ANTES de propose.]"
            )
        else:
            asset_selection_reminder = (
                "[CINEMATIC PRODUCT AD — product is chosen (see Referenced assets). Do NOT ask for a "
                "creator or use [[CREATOR_SELECTOR]]. Call create_cinematic_ad stage='propose' with the "
                "product from Referenced assets. If aspect ratio or duration is missing, ask with "
                "[[ASPECT_BUTTONS]] or [[DURATION_BUTTONS]] (one marker per message) BEFORE propose.]"
            )
    elif (
        _has_product_ref
        and not _has_creator_ref
        and _session_skipped_creator()
        and _model_led_ad_images_re.search(_session_user_text())
    ):
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[IMÁGENES DE ANUNCIO SOLO PRODUCTO — el usuario omitió el creador. Llama generate_image "
                "solo con ref de producto (sin influencer_id). Usa count=N del brief. "
                "NO uses [[CREATOR_SELECTOR]]. Pregunta aspecto con [[ASPECT_BUTTONS]] si falta.]"
            )
        else:
            asset_selection_reminder = (
                "[PRODUCT-ONLY COMMERCIAL AD IMAGES — user skipped creator. Call generate_image "
                "with product ref only (no influencer_id). Use count=N from brief. "
                "Do NOT use [[CREATOR_SELECTOR]]. Ask aspect with [[ASPECT_BUTTONS]] if missing.]"
            )
    elif (
        _has_product_ref
        and not _has_creator_ref
        and _session_skipped_creator()
        and not _is_product_shots_session
    ):
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[SOLO PRODUCTO — el usuario omitió el creador. Continúa sin influencer_id. "
                "NO uses [[CREATOR_SELECTOR]]. Imágenes → generate_image con producto. "
                "Cinematográfico → create_cinematic_ad stage='propose' solo producto.]"
            )
        else:
            asset_selection_reminder = (
                "[PRODUCT-ONLY — user skipped creator. Proceed without influencer_id. "
                "Do NOT use [[CREATOR_SELECTOR]]. Images → generate_image with product. "
                "Cinematic → create_cinematic_ad stage='propose' product-only.]"
            )
    elif _has_product_ref and not _has_creator_ref and not _is_product_shots_session:
        if _reminder_lang == "es":
            asset_selection_reminder = (
                "[SELECTOR DE ACTIVOS — el producto ya está elegido (ver Referenced assets). "
                "El usuario aún necesita un creador. Tu respuesta COMPLETA debe ser UNA pregunta "
                "corta en español que termine con el marcador literal [[CREATOR_SELECTOR]] en la "
                "última línea — nada más. Ejemplo: "
                "'¿Quién debería presentarlo? [[CREATOR_SELECTOR]]'. El frontend muestra las "
                "pestañas Modelos + Clones IA con imágenes. NO listes nombres de creadores. "
                "NO preguntes por guión o duración todavía.]"
            )
        else:
            asset_selection_reminder = (
                "[ASSET PICKER — product is chosen (see Referenced assets). User still needs a creator. "
                "Your ENTIRE reply must be ONE short question ending with the literal marker "
                "[[CREATOR_SELECTOR]] on the last line — nothing else. The frontend renders Models + "
                "AI Clones tabs with preview images. Do NOT list creator names. Do NOT ask about script "
                "or duration yet — creator selection comes first.]"
            )

    if not refs:
        prefix_lines = [engine_marker, quick_mode_marker]
        if dynamic_speaking_reminder:
            prefix_lines.append(dynamic_speaking_reminder)
        if is_caption_intent:
            prefix_lines.append(caption_reminder)
        if is_edit_intent:
            prefix_lines.append(edit_reminder)
        if asset_selection_reminder:
            prefix_lines.append(asset_selection_reminder)
        if bulk_reminder:
            prefix_lines.append(bulk_reminder)
        if post_confirm_marker:
            prefix_lines.append(post_confirm_marker)
        augmented_brief = "\n\n".join(prefix_lines + [augmented_brief])
    if refs:
        lines = [engine_marker, quick_mode_marker]
        if dynamic_speaking_reminder:
            lines.append(dynamic_speaking_reminder)
        if is_caption_intent:
            lines.append(caption_reminder)
        if is_edit_intent:
            lines.append(edit_reminder)
        if asset_selection_reminder:
            lines.append(asset_selection_reminder)
        if bulk_reminder:
            lines.append(bulk_reminder)
        if post_confirm_marker:
            lines.append(post_confirm_marker)
        lines.append("")
        lines.append("[Referenced assets — these are the EXACT items the user is talking about]")
        for r in refs:
            parts = [f"@{r.tag} ({r.type})"]
            if r.name:
                parts.append(f"name={r.name!r}")
            if r.id:
                parts.append(f"id={r.id}")
            if r.shot_id:
                parts.append(f"shot_id={r.shot_id}")
            if r.job_id:
                parts.append(f"job_id={r.job_id}")
            if r.image_url:
                parts.append(f"image_url={r.image_url}")
            if r.video_url:
                parts.append(f"video_url={r.video_url}")
            if r.app_clip_id:
                parts.append(f"app_clip_id={r.app_clip_id}")
            if r.look_id:
                parts.append(f"look_id={r.look_id}")
            if r.product_type:
                parts.append(f"product_type={r.product_type}")
            if r in carried_refs:
                # Tagged so the agent knows the user didn't re-type the
                # @-mention this turn; we resurrected it from earlier in
                # the thread.
                parts.append("source=carried_from_prior_turn")
            lines.append("- " + ", ".join(parts))
        lines.append("")
        if sticky_video_ref is not None:
            lines.append(
                "Note: the user did not attach a video this turn, but they uploaded one "
                "earlier in this thread — it is re-included above as `source=carried_from_prior_turn`. "
                "Use that video_url directly for this edit. Do NOT call list_project_assets or list_jobs."
            )
        lines.append(
            "Use these IDs/URLs directly in any tool that takes a product_id / influencer_id / app_clip_id. "
            "Do NOT call list_project_assets, create_product, create_influencer, create_app_clip, or any other "
            "lookup/create tool for these — they already exist in the user's account."
        )
        lines.append("")
        lines.append("User message: " + brief)
        augmented_brief = "\n".join(lines)

    # ── Onboarding first video: special handling ──────────────────────────
    is_onboarding = "ONBOARDING_FIRST_VIDEO" in brief
    if is_onboarding:
        onboarding_instructions = (
            "\n\n[ONBOARDING INSTRUCTIONS — CRITICAL]\n"
            "This is the user's very first video from onboarding. Follow these rules EXACTLY:\n"
            "1. DURATION: Use 5 seconds (duration=5). Do NOT use 10s.\n"
            "2. PRODUCT IMAGE: You MUST include the product's image_url in the `reference_image_urls` "
            "array when calling seedance_2_ugc. The product must be VISIBLE in the video. "
            "Include BOTH the influencer image AND the product image as reference images.\n"
            "3. FREE VIDEO: This video costs 0 credits — it is a free welcome gift. "
            "In your confirmation message to the user, explicitly say this video is FREE "
            "and mention they still have all 100 credits to use afterwards. "
            "Do NOT mention any credit cost number.\n"
            "4. SKIP QUESTIONS: Do NOT ask the user about aspect ratio, duration, or any preferences. "
            "Just start generating immediately with 9:16 vertical, 5s, Seedance 2.0.\n"
            "5. CONFIRMATION: Start your response with a brief, enthusiastic confirmation and "
            "immediately call the generation tool. Keep your message short and action-oriented."
        )
        augmented_brief += onboarding_instructions

    async def gen():
        nonlocal augmented_brief
        async with lock:
            thread = await get_thread(user_token, user_id, project_id)
            session_id: Optional[str] = thread.get("anthropic_session_id") if thread else None
            stored_agent_id: Optional[str] = thread.get("anthropic_agent_id") if thread else None
            turns: list[dict] = list((thread or {}).get("turns") or [])

            # Append user turn immediately so a refresh during the run shows it.
            # We persist the *original* brief (what the user typed) — the augmented
            # version with reference URLs is only sent to the model.
            user_turn: dict = {"role": "user", "text": brief, "ts": _now_ms()}
            if refs:
                user_turn["refs"] = [r.model_dump(exclude_none=True) for r in refs]
            turns.append(user_turn)

            # Fire the initial upsert in the background so it doesn't block
            # client.run_stream from starting. Saves ~300-600ms on first-token
            # latency per turn. A refresh mid-run may briefly miss the new user
            # turn, but the final upsert in `finally` always persists it.
            async def _initial_upsert():
                try:
                    await upsert_thread(
                        user_token, user_id, project_id,
                        anthropic_session_id=session_id,
                        turns=turns,
                        title=(turns[0]["text"][:80] if turns and turns[0].get("role") == "user" else None),
                    )
                except Exception as e:
                    print(f"[agent_stream] initial upsert failed: {e}")

            asyncio.create_task(_initial_upsert())

            interrupted = False
            # `prior_turns` is everything persisted before this run (excluding
            # the user turn we just appended). The client replays this as a
            # context primer if the session has to be reset mid-run, so the
            # agent keeps memory across Anthropic session resets.
            prior_turns = turns[:-1]

            def _ensure_agent_turn() -> dict:
                """Return the current agent turn, appending a new one if needed."""
                if not turns or turns[-1].get("role") != "agent":
                    turns.append({
                        "role": "agent",
                        "text": "",
                        "artifacts": [],
                        "tool_calls": [],
                        "ts": _now_ms(),
                    })
                return turns[-1]

            try:
                dirty = False  # set when turns changed since last persist
                last_persist = 0

                async def _maybe_persist(force: bool = False):
                    """Upsert turns to Supabase. Throttled to at most once per 3s
                    unless forced, so the SSE hot path isn't dominated by I/O."""
                    nonlocal dirty, last_persist
                    if not dirty:
                        return
                    now = _now_ms()
                    if not force and (now - last_persist) < 3000:
                        return
                    try:
                        await upsert_thread(
                            user_token, user_id, project_id,
                            anthropic_session_id=session_id,
                            turns=turns,
                        )
                        dirty = False
                        last_persist = now
                    except Exception as e:
                        print(f"[agent_stream] mid-run upsert failed: {e}")

                # On the FIRST turn of a session, inject a `[Memory snapshot]`
                # preface so the agent can read user preferences without a
                # blocking `memory view` tool round-trip. Saves ~500ms-2s on
                # the first message of every chat.
                if not prior_turns:
                    try:
                        from services import agent_memory as _mem
                        from services.managed_agent_client import _user_id_from_jwt
                        _uid = _user_id_from_jwt(user_token)
                        if _uid:
                            _snap = await _mem.read_snapshot(user_token, _uid)
                            augmented_brief = (
                                "[Memory snapshot — your persistent notes about this user. "
                                "Apply what's relevant; do NOT call the `memory` tool just to read.]\n"
                                f"{_snap}\n\n" + augmented_brief
                            )
                    except Exception as _e:
                        print(f"[agent_stream] memory preface failed: {_e}")

                image_urls = []
                _seen_img_urls: set[str] = set()
                for r in refs:
                    url = r.image_url
                    if url and url not in _seen_img_urls:
                        _seen_img_urls.add(url)
                        image_urls.append(url)
                # Mirror the user's actual input language. The EN/ES dropdown
                # (`data.lang`) becomes a fallback for short or ambiguous
                # input (button clicks, "ok", numbers) — when the user
                # clearly types Spanish in an EN-defaulted session, the
                # agent should still reply in Spanish. We run detection on
                # the original `brief`, not `augmented_brief`, because the
                # augmentation injects English markers (engine, refs preface,
                # etc.) that dilute the language signal.
                _detected_brief_lang = _detect_input_language(brief)
                _effective_lang = _detected_brief_lang or data.lang
                async for ev in client.run_stream(
                    brief=augmented_brief,
                    user_token=user_token,
                    project_id=project_id,
                    session_id=session_id,
                    stored_agent_id=stored_agent_id,
                    prior_turns=prior_turns,
                    lang=_effective_lang,
                    image_urls=image_urls or None,
                    turn_refs=[r.model_dump(exclude_none=True) for r in refs] if refs else None,
                ):
                    t = ev.get("type")
                    if t == "session":
                        session_id = ev["session_id"]
                        stored_agent_id = ev.get("agent_id") or stored_agent_id
                        # Persist new/refreshed session id + agent binding immediately.
                        await upsert_thread(
                            user_token, user_id, project_id,
                            anthropic_session_id=session_id,
                            anthropic_agent_id=stored_agent_id,
                        )
                    elif t == "agent_message":
                        current = _ensure_agent_turn()
                        if not current["text"] and not current["artifacts"] and not current["tool_calls"]:
                            current["text"] = ev["text"]
                        else:
                            turns.append({
                                "role": "agent",
                                "text": ev["text"],
                                "artifacts": [],
                                "tool_calls": [],
                                "ts": _now_ms(),
                            })
                        dirty = True
                    elif t == "tool_call":
                        _ensure_agent_turn()["tool_calls"].append({
                            "name": ev["name"],
                            "input_summary": ev.get("input_summary", ""),
                            "mode": ev.get("mode"),
                        })
                        dirty = True
                    elif t == "artifact":
                        _ensure_agent_turn()["artifacts"].append(ev["artifact"])
                        dirty = True
                    # Persist incrementally so clients that lost the SSE can
                    # recover full state via GET /agent/thread.
                    await _maybe_persist()
                    yield f"data: {json.dumps(ev)}\n\n"

            except asyncio.CancelledError:
                interrupted = True
                yield f"data: {json.dumps({'type': 'interrupted'})}\n\n"
                raise
            finally:
                # Mark interruption on the active agent turn, then persist.
                if interrupted and turns and turns[-1].get("role") == "agent":
                    turns[-1]["interrupted"] = True
                if len(turns) > (len(prior_turns) + 1) or interrupted:
                    try:
                        await upsert_thread(
                            user_token, user_id, project_id,
                            anthropic_session_id=session_id,
                            turns=turns,
                        )
                    except Exception as e:
                        print(f"[agent_stream] final upsert failed: {e}")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
