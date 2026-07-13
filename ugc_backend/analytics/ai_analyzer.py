"""AI-powered performance analyzer for the Analytics Feedback Loop.

Reads the user's top and bottom performing posts, calls the LLM to generate
a "Do More / Do Less" strategy report, and persists it to ``agent_memories``
at the stable path ``/memories/analytics_strategy.md`` so the creation agent
can read it on the next video generation request.

Pipeline placement
------------------
This module is invoked at the **end** of
``studio_service.run_connected_accounts_pipeline`` — after the metrics
refresh and breakdown queueing — via the daemon-thread fire-and-forget
helper ``enqueue_strategy_report`` so it never blocks the API response.

Persistence target
------------------
The ``agent_memories`` table (migration 028) is the canonical durable
memory for the creative-director agent. The path is intentionally stable
(``/memories/analytics_strategy.md``) so successive runs upsert in place
and the agent always sees the latest snapshot. The agent's runtime
context-builder (``read_snapshot`` in ``services/creative-os/services/
agent_memory.py``) automatically inlines all ``/memories/*`` files into
the system prompt — no further wiring is required for the feedback loop
to close.

LLM client
----------
Uses the OpenAI-compatible client surface that is already a dependency of
this codebase (``openai`` package). Credentials come from
``OPENAI_API_KEY`` (+ optional ``OPENAI_API_BASE`` for custom endpoints
or proxies). When the key is missing the analyzer logs and returns
``None`` — never raises into the caller's pipeline.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Optional

from ugc_db.db_manager import get_supabase

from . import db as analytics_db

logger = logging.getLogger(__name__)

MEMORY_PATH = "/memories/analytics_strategy.md"

# Tunable via env so ops can swap to a cheaper or higher-quality model
# without a code change. ``gpt-4o-mini`` is the documented default.
_MODEL = os.environ.get("ANALYTICS_STRATEGY_MODEL", "gpt-4o-mini")


# ── LLM client ───────────────────────────────────────────────────────────────

def _get_llm_client():
    """Return an OpenAI-compatible client using the environment credentials.

    Raises ``RuntimeError`` when ``OPENAI_API_KEY`` is unset so callers can
    log and skip cleanly without a misleading import error.
    """
    try:
        from openai import OpenAI
    except ImportError as exc:  # pragma: no cover — package is in requirements
        raise RuntimeError("openai package not installed") from exc

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not configured — analytics strategy report "
            "generation is disabled. Set it in .env.saas to enable the "
            "feedback loop."
        )
    base_url = os.environ.get("OPENAI_API_BASE") or None
    return OpenAI(api_key=api_key, base_url=base_url)


# ── Prompts ──────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are a social media performance analyst for Aitoma Studio.
You analyze a creator's published video posts and identify what is working and what is not.
Your output is a concise, actionable Markdown report that the AI creation agent will read
before generating new content. The agent will use your "Do More" list to replicate
successful patterns and your "Do Less" list to avoid underperforming patterns.

Rules:
- Always benchmark against the user's own averages, never against industry benchmarks.
- Be specific. Reference actual post captions, timing, or format details from the data.
- Keep each section to 3–5 bullet points maximum. Brevity is critical.
- Write in active voice. No filler phrases.
- Output only the Markdown report — no preamble, no explanation outside the report."""

_USER_PROMPT_TEMPLATE = """Here is the performance data for this creator's posts over the last 30 days.

**Baseline Engagement Rate:** {baseline_er:.2f}%
**Total Posts Analyzed:** {total_posts}

---

### Top Performing Posts (highest ER)
{top_posts_text}

---

### Bottom Performing Posts (lowest ER)
{bottom_posts_text}

---

Generate the strategy report now. Use this exact structure:

## Performance Analysis — Last 30 Days
**Baseline ER:** {baseline_er:.2f}%
**Posts analyzed:** {total_posts}

---

### Top Performers — Why They Worked
[3–5 specific observations about what made these posts succeed]

### Bottom Performers — What Went Wrong
[3–5 specific diagnoses of why these posts underperformed]

### Do More
[3–5 concrete patterns to replicate in future videos]

### Do Less
[3–5 concrete patterns to avoid in future videos]

### Your #1 Priority This Week
[One sentence. The single most important change to make right now.]"""


def _format_post_for_prompt(post: dict, rank: int) -> str:
    """Render a single post row as a compact text block for the LLM prompt."""
    caption = (post.get("caption") or "No caption")[:200]
    platform = post.get("platform") or "unknown"
    er = post.get("_er") or 0.0
    views = int(post.get("views") or 0)
    likes = int(post.get("likes") or 0)
    comments = int(post.get("comments") or 0)
    shares = int(post.get("shares") or 0)
    posted_at = (post.get("posted_at") or "unknown date")
    posted_at = str(posted_at)[:10]
    return (
        f"{rank}. Platform: {platform} | Posted: {posted_at} | ER: {er:.2f}%\n"
        f"   Views: {views} | Likes: {likes} | Comments: {comments} | Shares: {shares}\n"
        f"   Caption: {caption}"
    )


# ── Account-level report (surfaced in the Account Detail modal) ───────────────

_ACCOUNT_SYSTEM_PROMPT = """You are a social media performance analyst.
You analyze a single account's published posts and diagnose what is driving \
engagement and what is holding it back. Output a clean, concise Markdown \
report. Be specific and reference the actual post data provided. Do not invent \
metrics that are not in the data."""

# Exact account-level prompt structure requested for the strategy report.
_ACCOUNT_USER_PROMPT_TEMPLATE = """Analyze the following social media performance data and provide a specific, actionable diagnosis.

**Account:** {account_username} on {platform}
**Followers:** {follower_count}
**Baseline Engagement Rate:** {baseline_er:.2f}%

### Top Performers
{top_posts_data_json}
Diagnose why these worked (Hook, Topic, Timing, Format).

### Bottom Performers
{bottom_posts_data_json}
Diagnose what went wrong.

### What to Do Next
Provide 3-5 specific, ranked actions based on these findings. Format the output as clean Markdown."""


def _post_to_json_row(post: dict) -> dict:
    """Compact, JSON-serializable view of a post for the LLM prompt."""
    posted_at = str(post.get("posted_at") or "")[:10] or None
    return {
        "posted_at": posted_at,
        "engagement_rate_pct": round(float(post.get("_er") or 0.0), 2),
        "views": int(post.get("views") or 0),
        "likes": int(post.get("likes") or 0),
        "comments": int(post.get("comments") or 0),
        "shares": int(post.get("shares") or 0),
        "saves": int(post.get("saves") or 0),
        "media_type": post.get("media_type"),
        "caption": (post.get("caption") or "")[:280],
    }


def _generate_account_report(
    user_id: str, account_id: str, locale: str = "en",
) -> Optional[str]:
    """Generate + persist a strategy report scoped to one tracked account."""
    from . import locale_content

    loc = locale_content.normalize_locale(locale)
    account = analytics_db.get_tracked_account(user_id, account_id)
    if not account:
        logger.info(
            "[ai_analyzer] Account %s not found for user %s — skipping",
            account_id, user_id,
        )
        return None

    platform = (account.get("platform") or "").strip().lower()
    username = (account.get("username") or "").strip().lower().lstrip("@")
    follower_count = int(
        account.get("follower_count") or account.get("followers") or 0
    )

    data = analytics_db.get_top_and_bottom_posts(
        user_id, limit=5, platform=platform, username=username,
    )
    top_posts = data.get("top", [])
    bottom_posts = data.get("bottom", [])
    if not top_posts and not bottom_posts:
        logger.info(
            "[ai_analyzer] No scorable posts for account %s — skipping",
            account_id,
        )
        return None

    # Account-level baseline ER over the full post history (same formula the
    # dashboard uses) so the report frames top/bottom against the account's
    # own average rather than an industry benchmark.
    account_posts = analytics_db.list_account_posts(
        user_id, platform=platform, username=username, limit=500,
    )
    baseline_er = analytics_db.compute_engagement_rate(
        account_posts, follower_count,
    )

    top_json = json.dumps(
        [_post_to_json_row(p) for p in top_posts], indent=2, ensure_ascii=False,
    )
    bottom_json = json.dumps(
        [_post_to_json_row(p) for p in bottom_posts], indent=2, ensure_ascii=False,
    )

    user_prompt = _ACCOUNT_USER_PROMPT_TEMPLATE.format(
        account_username=f"@{username}",
        platform=platform or "unknown",
        follower_count=f"{follower_count:,}" if follower_count else "unknown",
        baseline_er=baseline_er,
        top_posts_data_json=top_json,
        bottom_posts_data_json=bottom_json,
    )

    client = _get_llm_client()
    system_prompt = _ACCOUNT_SYSTEM_PROMPT + locale_content.markdown_prompt_suffix(loc)
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1500,
        temperature=0.3,
    )
    report = (response.choices[0].message.content or "").strip()
    if report:
        analytics_db.save_account_strategy_report(user_id, account_id, report, locale=loc)
        logger.info(
            "[ai_analyzer] Account strategy report saved for %s/%s",
            user_id, account_id,
        )
    return report or None


# ── Persistence ──────────────────────────────────────────────────────────────

def _save_strategy_to_memory(user_id: str, report_markdown: str) -> bool:
    """Upsert the strategy report into ``agent_memories`` at ``MEMORY_PATH``.

    Uses the service-role Supabase client (matches every other write in the
    analytics module) and the ``(user_id, path)`` unique index from
    migration 028 so the row is overwritten in place on each run. Returns
    True on success so the caller can chain the reflection session only
    when the report actually landed.
    """
    try:
        sb = get_supabase()
        now = datetime.now(timezone.utc).isoformat()
        sb.table("agent_memories").upsert(
            {
                "user_id": user_id,
                "path": MEMORY_PATH,
                "content": report_markdown,
                "updated_at": now,
            },
            on_conflict="user_id,path",
        ).execute()
        logger.info(
            "[ai_analyzer] Strategy report saved to memory for user %s",
            user_id,
        )
        return True
    except Exception as exc:
        logger.warning(
            "[ai_analyzer] Failed to save strategy to memory: %s", exc
        )
        return False


# ── Core ─────────────────────────────────────────────────────────────────────

def generate_strategy_report(
    user_id: str,
    account_id: Optional[str] = None,
    locale: Optional[str] = None,
) -> Optional[str]:
    """Generate and persist the AI strategy report.

    When ``account_id`` is provided the report is scoped to a single tracked
    account and saved onto its row (surfaced in the Account Detail modal).
    Otherwise it spans every tracked account and is saved to
    ``agent_memories`` for the creative-director feedback loop.

    Returns the generated markdown or ``None`` on any failure (no posts, no
    API key, LLM error). Safe to call from a background thread — every
    exception path is caught and logged.
    """
    from . import locale_content

    loc = locale_content.normalize_locale(
        locale or locale_content.get_profile_ui_language(user_id),
    )
    if account_id:
        try:
            return _generate_account_report(user_id, account_id, locale=loc)
        except Exception as exc:
            logger.warning(
                "[ai_analyzer] Account report failed for %s/%s: %s",
                user_id, account_id, exc,
            )
            return None
    try:
        data = analytics_db.get_top_and_bottom_posts(
            user_id, limit=5, period_days=30
        )
        top_posts = data.get("top", [])
        bottom_posts = data.get("bottom", [])

        if not top_posts and not bottom_posts:
            logger.info(
                "[ai_analyzer] No post data available for user %s — skipping",
                user_id,
            )
            return None

        # Baseline ER across every post-with-views in the same window so the
        # report can frame top/bottom relative to the user's own average.
        all_posts = analytics_db.list_posts(
            user_id, period_days=30, limit=500
        )
        posts_with_views = [
            p for p in all_posts if (p.get("views") or 0) > 0
        ]
        if posts_with_views:
            total_eng = sum(
                int(p.get("total_engagement") or 0)
                for p in posts_with_views
            )
            total_views = sum(
                int(p.get("views") or 1) for p in posts_with_views
            )
            baseline_er = (total_eng / total_views) * 100 if total_views else 0.0
        else:
            baseline_er = 0.0

        top_text = "\n\n".join(
            _format_post_for_prompt(p, i + 1)
            for i, p in enumerate(top_posts)
        ) or "No top performers yet."
        bottom_text = "\n\n".join(
            _format_post_for_prompt(p, i + 1)
            for i, p in enumerate(bottom_posts)
        ) or "No bottom performers yet."

        user_prompt = _USER_PROMPT_TEMPLATE.format(
            baseline_er=baseline_er,
            total_posts=len(posts_with_views),
            top_posts_text=top_text,
            bottom_posts_text=bottom_text,
        )

        client = _get_llm_client()
        system_prompt = _SYSTEM_PROMPT + locale_content.markdown_prompt_suffix(loc)
        response = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1500,
            temperature=0.3,
        )
        report = (response.choices[0].message.content or "").strip()
        if report:
            saved = _save_strategy_to_memory(user_id, report)
            if saved:
                # Chain the self-improvement reflection (daemon thread).
                # Lazy import avoids a module-level cycle; any failure here
                # must never break report generation.
                try:
                    from . import reflection_runner

                    reflection_runner.enqueue_reflection_session(user_id)
                except Exception as exc:
                    logger.warning(
                        "[ai_analyzer] reflection enqueue failed for %s: %s",
                        user_id,
                        exc,
                    )
        return report or None

    except Exception as exc:
        logger.warning(
            "[ai_analyzer] Strategy report generation failed for user %s: %s",
            user_id,
            exc,
        )
        return None


def enqueue_strategy_report(
    user_id: str,
    account_id: Optional[str] = None,
    locale: Optional[str] = None,
) -> None:
    """Spawn a daemon thread to generate the strategy report off the request path.

    Mirrors the fire-and-forget pattern used by
    ``scraper_service._mirror_posts_in_background`` — daemon=True so the
    process can exit cleanly without joining, and a thread name that
    includes a user-id prefix to make logs easier to grep. Pass
    ``account_id`` for a per-account report (Account Detail modal).
    """
    if not user_id:
        return
    from . import locale_content

    loc = locale or locale_content.get_profile_ui_language(user_id)
    t = threading.Thread(
        target=generate_strategy_report,
        args=(user_id, account_id),
        kwargs={"locale": loc},
        daemon=True,
        name=f"ai_analyzer_{user_id[:8]}",
    )
    t.start()
    logger.info(
        "[ai_analyzer] Strategy report enqueued for user %s (account=%s)",
        user_id, account_id or "all",
    )


def enqueue_account_strategy_reports(user_id: str) -> int:
    """Enqueue a per-account strategy report for every active tracked account.

    Returns the number of reports dispatched. Safe/best-effort — never raises
    into the caller's pipeline.
    """
    try:
        accounts = analytics_db.list_tracked_accounts(user_id)
    except Exception:
        return 0
    dispatched = 0
    for acct in accounts:
        if acct.get("is_active") is False:
            continue
        acct_id = acct.get("id")
        if not acct_id:
            continue
        enqueue_strategy_report(user_id, account_id=acct_id)
        dispatched += 1
    return dispatched
