"""Per-user self-improvement reflection loop for the Analytics module.

Distills the "Do More / Do Less" strategy report plus the raw 30-day post
data (live metrics + one-time AI content breakdowns + generation-model
attribution) into a living per-account rulebook at
``/memories/creative_guidelines.md``, and keeps an audit trail at
``/memories/reflection_log.md``.

Pipeline placement
------------------
Chained after every successful **user-level** strategy report:
``ai_analyzer.generate_strategy_report`` calls
``enqueue_reflection_session(user_id)`` right after the report is saved.
The nightly sweep (``studio_service.run_nightly_analytics_sweep``) drives
the same pipeline for users who never open the app.

Why a single structured LLM call
--------------------------------
The reflection deliberately has no tools and no agent loop: it receives the
current memory files + posts JSON, and must return the COMPLETE updated
guidelines file plus one log line. That makes it tool-safe by construction,
provider-agnostic (works with the same OpenAI-compatible client as
``ai_analyzer``), and naturally idempotent — running twice regenerates the
same file instead of appending duplicates. All writes go through the
service-role upsert helpers in ``db.py``, scoped to one ``user_id``.

Token-cost gates (all deterministic, zero tokens)
-------------------------------------------------
1. ``REFLECTION_ENABLED`` kill switch.
2. Per-user debounce: skip when the guidelines were refreshed within
   ``REFLECTION_MIN_INTERVAL_HOURS`` (default 20h).
3. Signal fingerprint: one machine-readable comment at the top of
   ``reflection_log.md`` records the data state of the previous run;
   ``has_new_signal`` compares against it so the nightly sweep only pays
   for the LLM when a new post / new breakdown appeared or engagement
   moved by ``NIGHTLY_MIN_ENGAGEMENT_DELTA_PCT`` (default 5%).
4. Report-sha gate: skip when the strategy report text is byte-identical
   to the one already reflected on.

Delivery mechanism
------------------
No wiring on the creative-os side: ``read_snapshot`` already inlines every
``/memories/*`` file into the agent's first-turn brief, so the updated
guidelines reach the live agent automatically on the user's next session.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import db as analytics_db
from .ai_analyzer import MEMORY_PATH as STRATEGY_PATH, _get_llm_client

logger = logging.getLogger(__name__)

GUIDELINES_PATH = "/memories/creative_guidelines.md"
REFLECTION_LOG_PATH = "/memories/reflection_log.md"
ACCOUNT_PROFILE_PATH = "/memories/account_profile.md"

_SKILL_PATH = Path(__file__).resolve().parent / "skills" / "analytics_improvement.md"

_MAX_LOG_ENTRIES = 30
_LOG_HEADER = "# Reflection Log"
_FINGERPRINT_RE = re.compile(
    r"<!--\s*signal:v1\s+posts=(?P<posts>\d+)\s+eng=(?P<eng>\d+)\s+"
    r"latest=(?P<latest>\S*)\s+breakdowns=(?P<breakdowns>\d+)\s+"
    r"report_sha=(?P<report_sha>\S*)\s*-->"
)
_GUIDELINES_BLOCK_RE = re.compile(r"<guidelines>(.*?)</guidelines>", re.DOTALL)
_LOG_BLOCK_RE = re.compile(r"<log>(.*?)</log>", re.DOTALL)

_REFLECTION_SYSTEM_PROMPT = """You are the self-improvement reflection engine for Aitoma Studio.
You are in ANALYSIS MODE for one specific user account: you do not create content,
you do not interact with users, and analytics_strategy.md is read-only input.
Follow the skill procedure exactly as written.

Output exactly one <guidelines>...</guidelines> block containing the COMPLETE
updated creative_guidelines.md file, followed by one <log>...</log> block
containing a single log line. No text outside these two blocks."""


# ── Env knobs ────────────────────────────────────────────────────────────────

def _reflection_enabled() -> bool:
    raw = os.environ.get("REFLECTION_ENABLED", "1").strip().lower()
    return raw not in ("0", "false", "off", "no")


def _reflection_model() -> str:
    return (
        os.environ.get("REFLECTION_MODEL")
        or os.environ.get("ANALYTICS_STRATEGY_MODEL")
        or "gpt-4o-mini"
    )


def _min_interval_hours() -> float:
    try:
        return float(os.environ.get("REFLECTION_MIN_INTERVAL_HOURS", "20"))
    except (TypeError, ValueError):
        return 20.0


def _min_engagement_delta_pct() -> float:
    try:
        return float(os.environ.get("NIGHTLY_MIN_ENGAGEMENT_DELTA_PCT", "5"))
    except (TypeError, ValueError):
        return 5.0


def _max_posts() -> int:
    try:
        return max(5, int(os.environ.get("REFLECTION_MAX_POSTS", "40")))
    except (TypeError, ValueError):
        return 40


def load_skill_text() -> str:
    """Read the repo-versioned skill procedure. Raises when missing so the
    caller logs a loud, actionable error instead of running an empty prompt."""
    if not _SKILL_PATH.is_file():
        raise RuntimeError(f"reflection skill file missing: {_SKILL_PATH}")
    return _SKILL_PATH.read_text(encoding="utf-8")


# ── Pure helpers (no I/O) ────────────────────────────────────────────────────

def should_run_reflection(
    guidelines_row: Optional[dict],
    *,
    now: datetime,
    min_interval_hours: float,
) -> bool:
    """Debounce: run when the guidelines are missing, still a bootstrap stub,
    carry an unusable timestamp, or are older than the interval."""
    if not guidelines_row:
        return True
    content = str(guidelines_row.get("content") or "")
    # Late import keeps the two modules import-cycle-free.
    from .memory_bootstrapper import BOOTSTRAP_MARKER

    if BOOTSTRAP_MARKER in content:
        return True
    raw_ts = guidelines_row.get("updated_at")
    if not raw_ts:
        return True
    try:
        updated_at = datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
    except Exception:
        return True
    age_hours = (now - updated_at).total_seconds() / 3600.0
    return age_hours >= min_interval_hours


def compute_signal_fingerprint(posts: list[dict], breakdowns: dict[str, dict]) -> dict:
    """Deterministic snapshot of the 30-day window used to decide whether the
    LLM stages have anything new to look at."""
    latest = ""
    for p in posts:
        ts = str(p.get("posted_at") or p.get("scraped_at") or "")
        if ts > latest:
            latest = ts
    return {
        "posts": len(posts),
        "eng": sum(analytics_db.post_engagement(p) for p in posts),
        "latest": latest,
        "breakdowns": len(breakdowns),
    }


def serialize_fingerprint(fp: dict, report_sha: str) -> str:
    return (
        f"<!-- signal:v1 posts={int(fp.get('posts') or 0)} "
        f"eng={int(fp.get('eng') or 0)} "
        f"latest={fp.get('latest') or '-'} "
        f"breakdowns={int(fp.get('breakdowns') or 0)} "
        f"report_sha={report_sha or '-'} -->"
    )


def parse_fingerprint(log_content: Optional[str]) -> Optional[dict]:
    if not log_content:
        return None
    m = _FINGERPRINT_RE.search(log_content)
    if not m:
        return None
    return {
        "posts": int(m.group("posts")),
        "eng": int(m.group("eng")),
        "latest": "" if m.group("latest") == "-" else m.group("latest"),
        "breakdowns": int(m.group("breakdowns")),
        "report_sha": "" if m.group("report_sha") == "-" else m.group("report_sha"),
    }


def fingerprint_indicates_new_signal(
    old_fp: Optional[dict],
    new_fp: dict,
    *,
    min_delta_pct: float,
) -> bool:
    """True when the data moved enough since the last reflection to be worth
    paying LLM tokens for: any new post, any newly completed breakdown, or a
    total-engagement swing at or above the threshold."""
    if not old_fp:
        return True
    if new_fp.get("posts") != old_fp.get("posts"):
        return True
    if (new_fp.get("latest") or "") != (old_fp.get("latest") or ""):
        return True
    if new_fp.get("breakdowns") != old_fp.get("breakdowns"):
        return True
    old_eng = int(old_fp.get("eng") or 0)
    new_eng = int(new_fp.get("eng") or 0)
    if old_eng <= 0:
        return new_eng > 0
    delta_pct = abs(new_eng - old_eng) / old_eng * 100.0
    return delta_pct >= min_delta_pct


def build_posts_payload(
    posts: list[dict],
    breakdowns: dict[str, dict],
    job_models: dict[str, str],
    follower_counts: dict[tuple[str, str], int],
) -> dict:
    """Compact JSON the reflection LLM reasons over.

    Joins the three data sources per post: live engagement metrics
    (refreshed every pipeline run), the once-per-video content breakdown,
    and the generation-model attribution from ``video_jobs.model_api``.
    """
    rows: list[dict] = []
    model_stats: dict[str, dict] = {}

    for p in posts:
        pid = str(p.get("id") or "")
        plat = (p.get("platform") or "").strip().lower()
        nick = (p.get("username") or "").strip().lower().lstrip("@")
        views = int(p.get("views") or 0)
        eng = analytics_db.post_engagement(p)
        fc = int(follower_counts.get((plat, nick)) or 0)
        if views > 0:
            er = round(eng / views * 100.0, 2)
        elif fc > 0:
            er = round(eng / fc * 100.0, 2)
        else:
            er = None

        model = job_models.get(pid)
        bd = breakdowns.get(pid)
        caption = str(p.get("caption") or "")[:120]

        rows.append(
            {
                "platform": plat,
                "account": nick,
                "posted_at": p.get("posted_at"),
                "media_type": p.get("media_type"),
                "duration_seconds": p.get("duration_seconds"),
                "caption": caption,
                "views": views,
                "likes": int(p.get("likes") or 0),
                "comments": int(p.get("comments") or 0),
                "shares": int(p.get("shares") or 0),
                "saves": int(p.get("saves") or 0),
                "er_pct": er,
                "generation_model": model,
                "breakdown": (
                    {
                        "summary": bd.get("summary"),
                        "hook": bd.get("hook"),
                        "takeaways": bd.get("takeaways"),
                    }
                    if bd
                    else None
                ),
            }
        )

        if model and er is not None:
            stats = model_stats.setdefault(model, {"posts": 0, "_er_sum": 0.0})
            stats["posts"] += 1
            stats["_er_sum"] += er

    by_model = {
        model: {
            "posts": stats["posts"],
            "avg_er_pct": round(stats["_er_sum"] / stats["posts"], 2),
        }
        for model, stats in model_stats.items()
        if stats["posts"]
    }

    return {
        "baseline_er_pct": analytics_db.period_engagement_rate(posts),
        "total_posts": len(rows),
        "by_generation_model": by_model,
        "posts": rows,
    }


def validate_reflection_output(
    raw: str,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract and sanity-check the LLM output.

    Returns ``(guidelines_md, log_line, None)`` on success or
    ``(None, None, reject_reason)`` when the output must not be persisted.
    """
    text = (raw or "").strip()
    if not text:
        return None, None, "empty response"

    g_match = _GUIDELINES_BLOCK_RE.search(text)
    if not g_match:
        return None, None, "missing <guidelines> block"
    l_match = _LOG_BLOCK_RE.search(text)
    if not l_match:
        return None, None, "missing <log> block"

    guidelines = g_match.group(1).strip()
    # Unwrap a full markdown fence if the model wrapped the file in one.
    fence = re.match(r"^```[a-zA-Z]*\n(.*)\n```$", guidelines, re.DOTALL)
    if fence:
        guidelines = fence.group(1).strip()

    if "<guidelines>" in guidelines or "<log>" in guidelines:
        return None, None, "nested output tags (prompt echo)"
    if len(guidelines) < 200:
        return None, None, f"guidelines too short ({len(guidelines)} chars)"
    if len(guidelines) > 12_000:
        return None, None, f"guidelines too long ({len(guidelines)} chars)"
    if len(guidelines.splitlines()) > 120:
        return None, None, "guidelines exceed 120 lines"
    if "# Creative Guidelines" not in guidelines:
        return None, None, "missing '# Creative Guidelines' heading"
    if "Model Routing Reference" not in guidelines:
        return None, None, "missing 'Model Routing Reference' section"

    from .memory_bootstrapper import BOOTSTRAP_MARKER

    if BOOTSTRAP_MARKER in guidelines and "|" not in guidelines:
        return None, None, "still a bootstrap stub"

    log_line = l_match.group(1).strip()
    if not log_line:
        return None, None, "empty log line"
    if "\n" in log_line:
        return None, None, "log entry spans multiple lines"
    if len(log_line) > 200:
        return None, None, "log entry too long"

    return guidelines, log_line, None


def normalize_last_updated(guidelines: str, *, today: str) -> str:
    """Belt-and-braces: stamp today's date on the ``Last updated:`` line, or
    insert one under the H1 when the model dropped it."""
    lines = guidelines.splitlines()
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("last updated:"):
            lines[i] = f"Last updated: {today}"
            return "\n".join(lines)
    for i, line in enumerate(lines):
        if line.startswith("# "):
            lines.insert(i + 1, f"Last updated: {today}")
            return "\n".join(lines)
    return f"Last updated: {today}\n" + guidelines


def append_log_entry(
    existing_log: Optional[str],
    entry: str,
    *,
    fingerprint_comment: Optional[str] = None,
    max_entries: int = _MAX_LOG_ENTRIES,
) -> str:
    """Newest-first log under a fixed header, capped at ``max_entries``.

    The fingerprint comment (when given) replaces any previous one and sits
    on the first line so ``parse_fingerprint`` finds it cheaply.
    """
    old_entries: list[str] = []
    for line in (existing_log or "").splitlines():
        stripped = line.strip()
        if re.match(r"^\d{4}-\d{2}-\d{2}\s*\|", stripped):
            old_entries.append(stripped)

    entries = [entry.strip()] + old_entries
    entries = entries[:max_entries]

    parts: list[str] = []
    if fingerprint_comment:
        parts.append(fingerprint_comment)
    parts.append(_LOG_HEADER)
    parts.append("")
    parts.extend(entries)
    return "\n".join(parts) + "\n"


# ── I/O ──────────────────────────────────────────────────────────────────────

def _follower_counts_for_posts(user_id: str, posts: list[dict]) -> dict[tuple[str, str], int]:
    """One `list_tracked_accounts` call → {(platform, username): follower_count}."""
    counts: dict[tuple[str, str], int] = {}
    try:
        for acct in analytics_db.list_tracked_accounts(user_id):
            plat = (acct.get("platform") or "").strip().lower()
            nick = (acct.get("username") or "").strip().lower().lstrip("@")
            if plat and nick:
                counts[(plat, nick)] = int(
                    acct.get("follower_count") or acct.get("followers") or 0
                )
    except Exception as exc:
        logger.warning(
            "[reflection] follower lookup failed for %s: %s", user_id, exc
        )
    return counts


def _collect_context(user_id: str) -> Optional[dict]:
    """Gather everything the reflection prompt needs. None ⇒ nothing to do."""
    strategy_row = analytics_db.get_agent_memory(user_id, STRATEGY_PATH)
    if not strategy_row or not str(strategy_row.get("content") or "").strip():
        logger.info("[reflection] no strategy report for %s — skipping", user_id)
        return None

    posts = analytics_db.list_posts(
        user_id, period_days=30, sort="recent", limit=_max_posts()
    )
    if not posts:
        logger.info("[reflection] no recent posts for %s — skipping", user_id)
        return None

    breakdowns = analytics_db.list_breakdowns_for_posts(user_id, posts)
    job_models = analytics_db.list_job_models_for_posts(user_id, posts)
    follower_counts = _follower_counts_for_posts(user_id, posts)

    return {
        "strategy": str(strategy_row["content"]),
        "guidelines_row": analytics_db.get_agent_memory(user_id, GUIDELINES_PATH),
        "profile_row": analytics_db.get_agent_memory(user_id, ACCOUNT_PROFILE_PATH),
        "log_row": analytics_db.get_agent_memory(user_id, REFLECTION_LOG_PATH),
        "posts": posts,
        "breakdowns": breakdowns,
        "job_models": job_models,
        "follower_counts": follower_counts,
    }


def has_new_signal(user_id: str) -> bool:
    """Zero-token gate for the nightly sweep: compare the current 30-day data
    fingerprint against the one recorded on the previous reflection. Fails
    open (True) so a broken gate can never silently starve the loop."""
    try:
        posts = analytics_db.list_posts(
            user_id, period_days=30, sort="recent", limit=_max_posts()
        )
        if not posts:
            return False
        breakdowns = analytics_db.list_breakdowns_for_posts(user_id, posts)
        log_row = analytics_db.get_agent_memory(user_id, REFLECTION_LOG_PATH)
        old_fp = parse_fingerprint((log_row or {}).get("content"))
        new_fp = compute_signal_fingerprint(posts, breakdowns)
        return fingerprint_indicates_new_signal(
            old_fp, new_fp, min_delta_pct=_min_engagement_delta_pct()
        )
    except Exception as exc:
        logger.warning("[reflection] signal check failed for %s: %s", user_id, exc)
        return True


def _build_user_prompt(context: dict, payload: dict, *, today: str) -> str:
    guidelines_row = context.get("guidelines_row")
    profile_row = context.get("profile_row")
    guidelines_text = (
        str(guidelines_row.get("content"))
        if guidelines_row and guidelines_row.get("content")
        else "(missing — treat as first run)"
    )
    profile_text = (
        str(profile_row.get("content"))
        if profile_row and profile_row.get("content")
        else "(missing)"
    )
    return (
        "## Skill procedure\n\n"
        f"{load_skill_text()}\n\n"
        "## /memories/analytics_strategy.md (READ-ONLY)\n\n"
        f"{context['strategy']}\n\n"
        "## /memories/creative_guidelines.md (current)\n\n"
        f"{guidelines_text}\n\n"
        "## /memories/account_profile.md\n\n"
        f"{profile_text}\n\n"
        "## Recent posts (last 30 days, compact JSON)\n\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        f"## Today: {today}\n\n"
        "Follow the skill procedure now. Output exactly one <guidelines> block "
        "with the complete updated file, then one <log> block with a single line."
    )


def run_reflection_session(user_id: str) -> Optional[str]:
    """Run one reflection for one user. Returns the new guidelines markdown,
    or None when skipped/failed. Never raises — safe on a daemon thread."""
    try:
        if not user_id:
            return None
        if not _reflection_enabled():
            logger.info("[reflection] disabled via REFLECTION_ENABLED — skipping")
            return None

        now = datetime.now(timezone.utc)
        guidelines_row = analytics_db.get_agent_memory(user_id, GUIDELINES_PATH)
        if not should_run_reflection(
            guidelines_row, now=now, min_interval_hours=_min_interval_hours()
        ):
            logger.info(
                "[reflection] guidelines fresh for %s — debounced", user_id
            )
            return None

        context = _collect_context(user_id)
        if context is None:
            return None
        # Re-use the row fetched for the debounce so both checks agree.
        context["guidelines_row"] = guidelines_row

        report_sha = hashlib.sha1(context["strategy"].encode("utf-8")).hexdigest()[:12]
        old_fp = parse_fingerprint((context.get("log_row") or {}).get("content"))
        if old_fp and old_fp.get("report_sha") == report_sha:
            logger.info(
                "[reflection] strategy report unchanged for %s — skipping LLM",
                user_id,
            )
            return None

        payload = build_posts_payload(
            context["posts"],
            context["breakdowns"],
            context["job_models"],
            context["follower_counts"],
        )
        today = now.date().isoformat()
        user_prompt = _build_user_prompt(context, payload, today=today)

        client = _get_llm_client()
        response = client.chat.completions.create(
            model=_reflection_model(),
            messages=[
                {"role": "system", "content": _REFLECTION_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2500,
            temperature=0.2,
        )
        raw = (response.choices[0].message.content or "").strip()

        guidelines, log_line, reject_reason = validate_reflection_output(raw)
        if reject_reason:
            logger.warning(
                "[reflection] output rejected for %s: %s", user_id, reject_reason
            )
            return None

        guidelines = normalize_last_updated(guidelines, today=today)
        analytics_db.upsert_agent_memory(user_id, GUIDELINES_PATH, guidelines)
        logger.info("[reflection] guidelines updated for user %s", user_id)

        # Log write is best-effort — never roll back the guidelines.
        try:
            new_fp = compute_signal_fingerprint(
                context["posts"], context["breakdowns"]
            )
            log_content = append_log_entry(
                (context.get("log_row") or {}).get("content"),
                log_line,
                fingerprint_comment=serialize_fingerprint(new_fp, report_sha),
            )
            analytics_db.upsert_agent_memory(
                user_id, REFLECTION_LOG_PATH, log_content
            )
        except Exception as exc:
            logger.warning(
                "[reflection] log write failed for %s: %s", user_id, exc
            )

        return guidelines

    except Exception as exc:
        logger.warning(
            "[reflection] session failed for user %s: %s", user_id, exc
        )
        return None


def enqueue_reflection_session(user_id: str) -> None:
    """Fire-and-forget daemon thread, mirroring ``enqueue_strategy_report``."""
    if not user_id or not _reflection_enabled():
        return
    t = threading.Thread(
        target=run_reflection_session,
        args=(user_id,),
        daemon=True,
        name=f"analytics-reflection-{user_id[:8]}",
    )
    t.start()
    logger.info("[reflection] session enqueued for user %s", user_id)
