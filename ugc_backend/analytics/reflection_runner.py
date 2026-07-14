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


def _comparison_days() -> int:
    """Lookback for the content-type performance comparison. Wider than the
    30-day posts window because model attribution only exists on
    Studio-published posts — a longer window is what gets content types past
    the >=5-post confirm threshold."""
    try:
        return max(30, int(os.environ.get("REFLECTION_COMPARISON_DAYS", "90")))
    except (TypeError, ValueError):
        return 90


# Users never pick generation models — the agent routes by content type. All
# user-visible learnings therefore speak in content types; the raw model_api
# is translated here and never reaches the reflection prompt.
_MODEL_CONTENT_TYPES = (
    ("kling", "cinematic video (no speech)"),
    ("veo", "UGC video (spoken)"),
    ("seedance", "animated app-promo video"),
    ("infinitalk", "AI clone video"),
    ("banana", "image"),
    ("nano", "image"),
)


def content_type_for_model(model_api: Optional[str]) -> Optional[str]:
    """Translate an internal model id ("kling-3.0/video", "seedance-2.0-pro")
    into the user-facing content type. None for unattributed posts; falls back
    to the raw id for unknown engines so new models never silently vanish."""
    if not model_api:
        return None
    lowered = str(model_api).lower()
    for needle, label in _MODEL_CONTENT_TYPES:
        if needle in lowered:
            return label
    return str(model_api)


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

        content_type = content_type_for_model(job_models.get(pid))
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
                "content_type": content_type,
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

    by_type = aggregate_by_content_type(posts, job_models, follower_counts)

    return {
        "baseline_er_pct": analytics_db.period_engagement_rate(posts),
        "total_posts": len(rows),
        "by_content_type": by_type,
        "content_type_comparison": compute_content_type_comparison(by_type),
        "posts": rows,
    }


def aggregate_by_content_type(
    posts: list[dict],
    job_models: dict[str, str],
    follower_counts: dict[tuple[str, str], int],
) -> dict[str, dict]:
    """{content_type: {posts, avg_er_pct}} over attributed posts only.

    Buckets by user-facing content type, which also merges engine variants
    ("seedance-2.0" + "seedance-2.0-pro" → one animated-app-promo bucket).
    """
    stats: dict[str, dict] = {}
    for p in posts:
        pid = str(p.get("id") or "")
        ctype = content_type_for_model(job_models.get(pid))
        if not ctype:
            continue
        views = int(p.get("views") or 0)
        eng = analytics_db.post_engagement(p)
        plat = (p.get("platform") or "").strip().lower()
        nick = (p.get("username") or "").strip().lower().lstrip("@")
        fc = int(follower_counts.get((plat, nick)) or 0)
        if views > 0:
            er = eng / views * 100.0
        elif fc > 0:
            er = eng / fc * 100.0
        else:
            continue
        bucket = stats.setdefault(ctype, {"posts": 0, "_er_sum": 0.0})
        bucket["posts"] += 1
        bucket["_er_sum"] += er
    return {
        ctype: {
            "posts": b["posts"],
            "avg_er_pct": round(b["_er_sum"] / b["posts"], 2),
        }
        for ctype, b in stats.items()
        if b["posts"]
    }


_GROWTH_DELTA_KEYS = ("views_delta_pct", "engagement_delta_pct", "posts_delta_pct")


_GROWTH_SIGNIFICANT_PCT = 25.0  # |delta| at/above this is a headline swing
_GROWTH_TOP_POSTS = 3


def _top_current_posts(
    rows: list[dict],
    period_days: int,
    follower_counts: dict[tuple[str, str], int],
    *,
    n: int = _GROWTH_TOP_POSTS,
) -> list[dict]:
    """The highest-engagement posts of the CURRENT period — i.e. the posts
    that drove this window's numbers — so the reflection can attribute a
    growth swing to specific content instead of asserting it abstractly."""
    current = analytics_db._filter_posts_by_period(rows, period_days)
    ranked = sorted(current, key=analytics_db.post_engagement, reverse=True)[:n]
    out: list[dict] = []
    for p in ranked:
        eng = analytics_db.post_engagement(p)
        views = int(p.get("views") or 0)
        plat = (p.get("platform") or "").strip().lower()
        nick = (p.get("username") or "").strip().lower().lstrip("@")
        fc = int((follower_counts or {}).get((plat, nick)) or 0)
        if views > 0:
            er = round(eng / views * 100.0, 2)
        elif fc > 0:
            er = round(eng / fc * 100.0, 2)
        else:
            er = None
        out.append(
            {
                "caption": str(p.get("caption") or "")[:80],
                "posted_at": p.get("posted_at"),
                "engagement": eng,
                "views": views,
                "er_pct": er,
            }
        )
    return out


def compute_growth_block(
    comparison_posts: list[dict],
    *,
    period_days: int = 30,
    follower_counts: Optional[dict[tuple[str, str], int]] = None,
) -> dict:
    """Period-over-period growth deltas, overall and per account, plus the
    specific current-period posts that drove the numbers.

    Reuses the already-fetched wide (90d) post slice — zero extra queries.
    Delegates the delta math to ``stats_extras_from_rows`` (the same helper
    behind the dashboard sparklines) and keeps only the three delta
    percentages; the daily series would bloat the prompt without adding
    decision value. ``significant_pct`` tells the reflection the threshold at
    which a swing is worth surfacing as a headline learning.
    """

    def _deltas(rows: list[dict]) -> dict:
        period_rows = analytics_db._filter_posts_by_period(rows, period_days)
        extras = analytics_db.stats_extras_from_rows(
            period_rows, rows, period_days=period_days
        )
        return {k: extras.get(k) for k in _GROWTH_DELTA_KEYS}

    by_account: dict[str, dict] = {}
    grouped: dict[str, list[dict]] = {}
    for p in comparison_posts:
        plat = (p.get("platform") or "").strip().lower()
        nick = (p.get("username") or "").strip().lower().lstrip("@")
        if plat and nick:
            grouped.setdefault(f"{plat} @{nick}", []).append(p)
    for label, rows in grouped.items():
        by_account[label] = _deltas(rows)

    overall = _deltas(comparison_posts)
    overall["top_current_posts"] = _top_current_posts(
        comparison_posts, period_days, follower_counts or {}
    )

    return {
        "window_days": period_days,
        "vs": f"previous {period_days} days",
        "significant_pct": _GROWTH_SIGNIFICANT_PCT,
        "overall": overall,
        "by_account": by_account,
    }


def compute_content_type_comparison(by_type: dict[str, dict]) -> Optional[dict]:
    """Pre-compute the content-type ranking + leader delta deterministically.

    The reflection LLM has repeatedly bungled this arithmetic (comparing the
    top performer to the overall baseline instead of to its rivals, producing
    incoherent "outperforms with a below-baseline number" claims). So we hand
    it the finished comparison to transcribe rather than recompute:
    ``leader`` beats ``runner_up`` by ``leader_vs_runner_up_pct`` percent, on
    ``posts`` posts. ``leader_meets_confirm_threshold`` states plainly whether
    the leader has the >=5 posts required for a Confirmed Rule.
    """
    ranked = sorted(
        (
            {"content_type": t, "avg_er_pct": v["avg_er_pct"], "posts": v["posts"]}
            for t, v in by_type.items()
        ),
        key=lambda r: r["avg_er_pct"],
        reverse=True,
    )
    if len(ranked) < 2:
        return {"ranked": ranked, "leader": None, "best_confirmable": None}
    leader, runner_up = ranked[0], ranked[1]
    delta = None
    if runner_up["avg_er_pct"] > 0:
        delta = round(
            (leader["avg_er_pct"] - runner_up["avg_er_pct"])
            / runner_up["avg_er_pct"]
            * 100.0,
            1,
        )

    # The raw leader can be a 1-post fluke that outranks a well-evidenced
    # type. best_confirmable is the top type that actually clears the
    # >=5-post gate, with its delta vs the best of the OTHER types — and a
    # plain `confirmable` verdict so the LLM never has to do the math.
    # best_confirmable: the top type that clears the >=5-post gate, judged
    # against the POOLED (post-weighted) ER of all other attributed types —
    # NOT the single best-of-others, which lets a 1-post fluke suppress a
    # well-evidenced workhorse and produces incoherent verdicts.
    _MIN_COMPARATOR_POSTS = 3
    best_confirmable = None
    eligible = [r for r in ranked if r["posts"] >= 5]
    if eligible:
        cand = eligible[0]
        others = [r for r in ranked if r["content_type"] != cand["content_type"]]
        other_posts = sum(r["posts"] for r in others)
        pooled_er = None
        if other_posts >= _MIN_COMPARATOR_POSTS:
            pooled_er = round(
                sum(r["avg_er_pct"] * r["posts"] for r in others) / other_posts, 2
            )
        cand_delta = None
        if pooled_er and pooled_er > 0:
            cand_delta = round(
                (cand["avg_er_pct"] - pooled_er) / pooled_er * 100.0, 1
            )
        best_confirmable = {
            "content_type": cand["content_type"],
            "avg_er_pct": cand["avg_er_pct"],
            "posts": cand["posts"],
            "comparator": "all other content types (pooled)",
            "comparator_avg_er_pct": pooled_er,
            "comparator_posts": other_posts,
            "delta_vs_others_pct": cand_delta,
            "confirmable": cand_delta is not None and cand_delta > 20.0,
        }

    return {
        "ranked": ranked,
        "leader": {
            "content_type": leader["content_type"],
            "avg_er_pct": leader["avg_er_pct"],
            "posts": leader["posts"],
            "runner_up_content_type": runner_up["content_type"],
            "runner_up_avg_er_pct": runner_up["avg_er_pct"],
            "leader_vs_runner_up_pct": delta,
            "leader_meets_confirm_threshold": leader["posts"] >= 5,
        },
        "best_confirmable": best_confirmable,
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
    # Tolerate title-wording variation ("## Creative Guidelines for @x",
    # "# Content Guidelines", …) — require only that it's recognizably a
    # guidelines document, not an exact heading string.
    if "guideline" not in guidelines.lower():
        return None, None, "not a guidelines document"

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


_STATIC_SECTION_NEEDLES = ("model routing reference", "how to apply")


def _remove_sections(text: str, needles: tuple[str, ...]) -> str:
    """Drop every markdown section whose heading contains one of the needles.

    Level-aware: a skipped section ends only at the next heading of the SAME
    or higher level, so a sub-heading inside the section (e.g. a `### Examples`
    under a skipped `##`) cannot flip skipping off and leak the remainder.
    """
    out: list[str] = []
    skip_level: Optional[int] = None
    for line in text.splitlines():
        stripped = line.strip()
        heading_match = re.match(r"(#{1,6})\s+(.*)", stripped)
        if heading_match:
            level = len(heading_match.group(1))
            heading_text = heading_match.group(2).lower()
            if skip_level is not None and level > skip_level:
                continue  # sub-heading inside the skipped section
            if any(n in heading_text for n in needles):
                skip_level = level
                continue
            skip_level = None
        elif skip_level is not None:
            continue
        out.append(line)
    return "\n".join(out)


def apply_static_sections(guidelines: str) -> str:
    """Replace the boilerplate sections with their canonical versions.

    The LLM has produced scrambled model mappings when left to write these
    itself (e.g. "UGC video: seedance") — and the generation agent reads this
    file, so a wrong mapping is actively harmful. Whatever the model wrote
    under "How to apply" or "Model Routing Reference" is discarded and the
    canonical blocks from the bootstrapper are appended instead.
    """
    from .memory_bootstrapper import _AGENT_GUIDANCE, _MODEL_ROUTING_REFERENCE

    body = _remove_sections(guidelines, _STATIC_SECTION_NEEDLES).rstrip()
    return body + "\n\n" + _AGENT_GUIDANCE + "\n\n" + _MODEL_ROUTING_REFERENCE + "\n"


def strip_guidelines_for_display(markdown: Optional[str]) -> Optional[str]:
    """Clean the raw guidelines file for the read-only frontend panel.

    Returns None when there is nothing worth showing yet (missing, empty, or a
    bootstrap stub with no learned rules) so the UI can render a "still
    learning" state. Otherwise drops the internal ``## Model Routing
    Reference`` section (a static model-name table, too technical for end
    users — the *learned* model rules live under Confirmed Rules), strips HTML
    comment markers, and collapses the duplicate ``Last updated:`` line the LLM
    occasionally emits.
    """
    if not markdown or not markdown.strip():
        return None

    from .memory_bootstrapper import BOOTSTRAP_MARKER

    # A bootstrap stub carries the marker and no confirmed-rule table rows
    # (real reflections cite data with "|"-delimited or bulleted rules).
    if BOOTSTRAP_MARKER in markdown and "No confirmed rules yet" in markdown:
        return None

    # Remove HTML comments (bootstrap/signal markers) anywhere in the file,
    # then the internal sections (model routing table, agent guidance).
    text = re.sub(r"<!--.*?-->", "", markdown, flags=re.DOTALL)
    text = _remove_sections(text, _STATIC_SECTION_NEEDLES)

    out: list[str] = []
    seen_last_updated = False
    for line in text.splitlines():
        stripped = line.strip()
        heading_match = re.match(r"#{1,6}\s+(.*)", stripped)
        heading_text = heading_match.group(1).lower() if heading_match else None
        # Collapse a stray "Last updated:" line/heading (LLM sometimes emits two).
        is_last_updated = stripped.lower().startswith("last updated:") or (
            heading_text is not None and heading_text.startswith("last updated:")
        )
        if is_last_updated:
            if seen_last_updated:
                continue
            seen_last_updated = True
        out.append(line)

    cleaned = "\n".join(out).strip()
    return cleaned or None


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


def build_outcome_log(
    existing_log: Optional[str],
    *,
    today: str,
    status: str,
    detail: str,
    max_entries: int = _MAX_LOG_ENTRIES,
) -> Optional[str]:
    """Prepend a per-run outcome line `YYYY-MM-DD | <status> | <detail>` to the
    log body, preserving the fingerprint comment. Pure.

    Returns None (meaning "no write needed") when the newest existing entry is
    already an identical `status | detail` on the same date — so repeated
    same-day dashboard-visit skips don't spam the log.
    """
    line = f"{today} | {status} | {detail}".strip()

    fingerprint = None
    body: list[str] = []
    for raw in (existing_log or "").splitlines():
        stripped = raw.strip()
        if stripped.startswith("<!--") and fingerprint is None:
            fingerprint = stripped
        elif re.match(r"^\d{4}-\d{2}-\d{2}\b", stripped):
            body.append(stripped)

    if body and body[0] == line:
        return None  # exact duplicate of the newest entry — skip the write

    entries = ([line] + body)[:max_entries]
    parts: list[str] = []
    if fingerprint:
        parts.append(fingerprint)
    parts.append(_LOG_HEADER)
    parts.append("")
    parts.extend(entries)
    return "\n".join(parts) + "\n"


def _record_outcome(user_id: str, existing_log: Optional[str], *, status: str, detail: str) -> None:
    """Best-effort durable trace of what the reflection decided this run —
    including skips, so the admin per-user view always shows the last outcome.
    Never raises."""
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        content = build_outcome_log(existing_log, today=today, status=status, detail=detail)
        if content is not None:
            analytics_db.upsert_agent_memory(user_id, REFLECTION_LOG_PATH, content)
    except Exception as exc:
        logger.warning("[reflection] outcome log failed for %s: %s", user_id, exc)


# ── I/O ──────────────────────────────────────────────────────────────────────

def _follower_counts_for_posts(user_id: str, posts: list[dict]) -> dict[tuple[str, str], int]:
    """One `list_tracked_accounts` call → {(platform, username): follower_count}."""
    try:
        accounts = analytics_db.list_tracked_accounts(user_id)
    except Exception as exc:
        logger.warning(
            "[reflection] follower lookup failed for %s: %s", user_id, exc
        )
        accounts = []
    return _follower_counts_from_accounts(accounts)


def _follower_counts_from_accounts(accounts: list[dict]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for acct in accounts:
        plat = (acct.get("platform") or "").strip().lower()
        nick = (acct.get("username") or "").strip().lower().lstrip("@")
        if plat and nick:
            counts[(plat, nick)] = int(
                acct.get("follower_count") or acct.get("followers") or 0
            )
    return counts


_MAX_ACCOUNT_REPORTS = 3
_ACCOUNT_REPORT_CHARS = 2500


def _account_reports_for_context(user_id: str, accounts: list[dict]) -> list[dict]:
    """Latest per-account strategy reports (secondary prose input). Capped to
    the first few active accounts and truncated per report — prompt budget."""
    reports: list[dict] = []
    for acct in accounts:
        if acct.get("is_active") is False or not acct.get("id"):
            continue
        try:
            data = analytics_db.get_account_strategy_report(
                user_id, str(acct["id"])
            )
        except Exception as exc:
            logger.warning(
                "[reflection] account report fetch failed for %s/%s: %s",
                user_id,
                acct.get("id"),
                exc,
            )
            continue
        report = str((data or {}).get("report") or "").strip()
        if not report:
            continue
        plat = (acct.get("platform") or "").strip().lower()
        nick = (acct.get("username") or "").strip().lower().lstrip("@")
        reports.append(
            {
                "account": f"{plat} @{nick}",
                "report": report[:_ACCOUNT_REPORT_CHARS],
                "generated_at": (data or {}).get("generated_at"),
            }
        )
        if len(reports) >= _MAX_ACCOUNT_REPORTS:
            break
    return reports


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

    # Back-fill memory files for accounts that predate the connect-time
    # bootstrap (never overwrites existing rows) so profile/guidelines exist.
    try:
        from . import memory_bootstrapper

        memory_bootstrapper.bootstrap_user_memories(user_id)
    except Exception as exc:
        logger.warning(
            "[reflection] bootstrap back-fill failed for %s: %s", user_id, exc
        )

    try:
        accounts = analytics_db.list_tracked_accounts(user_id)
    except Exception as exc:
        logger.warning(
            "[reflection] account lookup failed for %s: %s", user_id, exc
        )
        accounts = []
    follower_counts = _follower_counts_from_accounts(accounts)
    account_reports = _account_reports_for_context(user_id, accounts)

    # Wider slice for the content-type comparison only — attribution exists
    # solely on Studio posts, so 30 days is often too thin to clear the
    # >=5-post confirm gate while 90 days is not. Metrics are live either way.
    comparison_posts = analytics_db.list_posts(
        user_id, period_days=_comparison_days(), sort="recent", limit=200
    )
    comparison_job_models = analytics_db.list_job_models_for_posts(
        user_id, comparison_posts
    )

    return {
        "strategy": str(strategy_row["content"]),
        "guidelines_row": analytics_db.get_agent_memory(user_id, GUIDELINES_PATH),
        "profile_row": analytics_db.get_agent_memory(user_id, ACCOUNT_PROFILE_PATH),
        "log_row": analytics_db.get_agent_memory(user_id, REFLECTION_LOG_PATH),
        "posts": posts,
        "breakdowns": breakdowns,
        "job_models": job_models,
        "follower_counts": follower_counts,
        "account_reports": account_reports,
        "comparison_posts": comparison_posts,
        "comparison_job_models": comparison_job_models,
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
    account_reports = context.get("account_reports") or []
    if account_reports:
        report_chunks = [
            f"### {r['account']} (generated {r.get('generated_at') or 'unknown'})\n\n{r['report']}"
            for r in account_reports
        ]
        account_reports_text = "\n\n".join(report_chunks)
    else:
        account_reports_text = "(none yet)"

    return (
        "## Skill procedure\n\n"
        f"{load_skill_text()}\n\n"
        "## /memories/analytics_strategy.md (READ-ONLY)\n\n"
        f"{context['strategy']}\n\n"
        "## Account-level strategy reports (READ-ONLY, secondary)\n\n"
        f"{account_reports_text}\n\n"
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
    log_content: Optional[str] = None
    try:
        if not user_id:
            return None
        if not _reflection_enabled():
            logger.info("[reflection] disabled via REFLECTION_ENABLED — skipping")
            return None

        now = datetime.now(timezone.utc)
        guidelines_row = analytics_db.get_agent_memory(user_id, GUIDELINES_PATH)
        log_row = analytics_db.get_agent_memory(user_id, REFLECTION_LOG_PATH)
        log_content = (log_row or {}).get("content")

        if not should_run_reflection(
            guidelines_row, now=now, min_interval_hours=_min_interval_hours()
        ):
            g_at = (guidelines_row or {}).get("updated_at") or "?"
            logger.info(
                "[reflection] guidelines fresh for %s — debounced", user_id
            )
            _record_outcome(
                user_id, log_content,
                status="skipped", detail=f"debounced (guidelines fresh, last run {g_at})",
            )
            return None

        context = _collect_context(user_id)
        if context is None:
            _record_outcome(
                user_id, log_content,
                status="skipped", detail="no strategy report or no recent posts",
            )
            return None
        # Re-use the rows fetched above so all checks agree.
        context["guidelines_row"] = guidelines_row

        report_sha = hashlib.sha1(context["strategy"].encode("utf-8")).hexdigest()[:12]
        old_fp = parse_fingerprint((context.get("log_row") or {}).get("content"))
        if old_fp and old_fp.get("report_sha") == report_sha:
            logger.info(
                "[reflection] strategy report unchanged for %s — skipping LLM",
                user_id,
            )
            _record_outcome(
                user_id, log_content,
                status="no-change", detail="strategy report unchanged since last run",
            )
            return None

        payload = build_posts_payload(
            context["posts"],
            context["breakdowns"],
            context["job_models"],
            context["follower_counts"],
        )
        # Content-type comparison comes from the wider window (default 90d)
        # so Studio content types can actually reach the >=5-post gate.
        wide_by_type = aggregate_by_content_type(
            context["comparison_posts"],
            context["comparison_job_models"],
            context["follower_counts"],
        )
        if wide_by_type:
            payload["by_content_type"] = wide_by_type
            payload["content_type_comparison"] = compute_content_type_comparison(
                wide_by_type
            )
            payload["content_type_window_days"] = _comparison_days()
        payload["growth"] = compute_growth_block(
            context["comparison_posts"],
            follower_counts=context["follower_counts"],
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
            _record_outcome(
                user_id, log_content,
                status="skipped", detail=f"LLM output rejected ({reject_reason})",
            )
            return None

        guidelines = normalize_last_updated(guidelines, today=today)
        guidelines = apply_static_sections(guidelines)
        analytics_db.upsert_agent_memory(user_id, GUIDELINES_PATH, guidelines)
        logger.info("[reflection] guidelines updated for user %s", user_id)

        # Log write is best-effort — never roll back the guidelines.
        try:
            new_fp = compute_signal_fingerprint(
                context["posts"], context["breakdowns"]
            )
            new_log = append_log_entry(
                log_content,
                log_line,
                fingerprint_comment=serialize_fingerprint(new_fp, report_sha),
            )
            analytics_db.upsert_agent_memory(
                user_id, REFLECTION_LOG_PATH, new_log
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
        _record_outcome(
            user_id, log_content,
            status="failed", detail=f"error: {str(exc)[:120]}",
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
