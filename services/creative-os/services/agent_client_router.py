"""
Creative OS — Agent Client Router (failover dispatcher)

Single entry point that the FastAPI route at routers/agent.py calls.
Decides per-request whether to use the existing Managed Agents client
(primary) or the new Messages API client (fallback). The user never sees
a difference: same SSE event shape, same tools, same Claude model, same
agent personality.

Routing rules in priority order:
  1. Manual override via AGENT_PROVIDER env var:
       managed   → always use ManagedAgentClient
       messages  → always use MessagesAgentClient
       auto      → managed first, fall back to messages on transient errors
                   (default)
  2. Circuit breaker: after _BREAKER_THRESHOLD transient managed-client
     failures within _BREAKER_WINDOW_S seconds, open the breaker for
     _BREAKER_OPEN_S seconds. While open, route directly to messages
     without trying managed first (avoids the ~14s retry-then-fail
     latency during sustained Anthropic outages).
  3. Per-request fallback: if managed fails after its internal retries,
     log + transparently re-issue the same brief through messages. The
     client sees one continuous response.

The router is purely additive. With AGENT_PROVIDER unset (or =managed),
behavior is identical to calling ManagedAgentClient directly. Existing
sync agent flow is byte-for-byte the same.
"""
from __future__ import annotations

import asyncio
import os
import time
from typing import Any, AsyncIterator, Optional

from anthropic import APIStatusError


# ── Tunables ────────────────────────────────────────────────────────────
_BREAKER_THRESHOLD = 5         # consecutive transient failures to trip
_BREAKER_WINDOW_S = 60         # within this rolling window
_BREAKER_OPEN_S = 300          # stay open for 5 minutes once tripped

_TRANSIENT_MARKERS = (
    "overloaded", "rate limit", "rate_limit",
    "internal server error", "500", "529",
    "timeout", "timed out", "temporarily unavailable",
    "service unavailable", "503", "502",
)


def _is_transient_error(exc: BaseException) -> bool:
    """Same heuristic the managed client already uses internally."""
    if isinstance(exc, asyncio.TimeoutError):
        return True
    if isinstance(exc, APIStatusError):
        msg = (str(exc) or "").lower()
        return any(m in msg for m in _TRANSIENT_MARKERS)
    msg = (str(exc) or "").lower()
    return any(m in msg for m in _TRANSIENT_MARKERS)


# ── Circuit breaker state (in-process, per worker) ──────────────────────
class _CircuitBreaker:
    """Simple sliding-window failure counter with timed open state.

    Not perfect across multiple workers (each has its own state), but
    that's fine: each worker independently learns the upstream is sad
    and routes around it for 5 min.
    """

    def __init__(self) -> None:
        self._failures: list[float] = []   # unix timestamps of recent failures
        self._opened_at: Optional[float] = None

    def record_failure(self) -> None:
        now = time.time()
        self._failures.append(now)
        # Drop entries older than the window
        cutoff = now - _BREAKER_WINDOW_S
        self._failures = [t for t in self._failures if t >= cutoff]
        if len(self._failures) >= _BREAKER_THRESHOLD and self._opened_at is None:
            self._opened_at = now
            print(f"[agent_router] circuit_breaker OPEN (>= {_BREAKER_THRESHOLD} failures in {_BREAKER_WINDOW_S}s)")

    def record_success(self) -> None:
        # A success closes a half-open breaker.
        if self._opened_at is not None:
            print("[agent_router] circuit_breaker CLOSED (probe succeeded)")
        self._opened_at = None
        self._failures.clear()

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.time() - self._opened_at >= _BREAKER_OPEN_S:
            # Half-open: let the next call test the upstream.
            self._opened_at = None
            print("[agent_router] circuit_breaker HALF-OPEN (cooldown elapsed)")
            return False
        return True


_breaker = _CircuitBreaker()


# ── Provider selection ──────────────────────────────────────────────────
def _provider_override() -> str:
    """Return 'managed' | 'messages' | 'auto' (default)."""
    val = (os.getenv("AGENT_PROVIDER") or "managed").strip().lower()
    if val not in {"managed", "messages", "auto"}:
        print(f"[agent_router] unknown AGENT_PROVIDER={val!r}, defaulting to managed")
        return "managed"
    return val


# ── Router ──────────────────────────────────────────────────────────────
class AgentClientRouter:
    """Façade exposing the same `run_stream(...)` signature as the two
    underlying clients. Picks one per call based on env var + breaker
    state, with silent failover on transient errors.
    """

    async def run_stream(
        self,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str] = None,
        stored_agent_id: Optional[str] = None,
        max_tool_calls: int = 24,
        prior_turns: Optional[list[dict]] = None,
        lang: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        provider = _provider_override()

        if provider == "messages":
            async for ev in self._stream_messages(
                brief=brief, user_token=user_token, project_id=project_id,
                session_id=session_id, stored_agent_id=stored_agent_id,
                max_tool_calls=max_tool_calls, prior_turns=prior_turns,
                lang=lang, image_urls=image_urls,
            ):
                yield ev
            return

        if provider == "auto" and _breaker.is_open():
            # Skip the failed managed probe entirely.
            print(
                f"[agent_router] failover from=managed to=messages reason=breaker_open "
                f"project_id={project_id}"
            )
            async for ev in self._stream_messages(
                brief=brief, user_token=user_token, project_id=project_id,
                session_id=session_id, stored_agent_id=stored_agent_id,
                max_tool_calls=max_tool_calls, prior_turns=prior_turns,
                lang=lang, image_urls=image_urls,
            ):
                yield ev
            return

        # Default: try managed. On transient failure (and only when in auto
        # mode) fail over to messages with the same brief.
        managed_failed_transient = False
        try:
            async for ev in self._stream_managed(
                brief=brief, user_token=user_token, project_id=project_id,
                session_id=session_id, stored_agent_id=stored_agent_id,
                max_tool_calls=max_tool_calls, prior_turns=prior_turns,
                lang=lang, image_urls=image_urls,
            ):
                yield ev
            _breaker.record_success()
            return
        except BaseException as e:  # noqa: BLE001 — we re-raise non-transient below
            if _is_transient_error(e):
                _breaker.record_failure()
                managed_failed_transient = True
                # Don't surface this error to the user yet — try the fallback.
                if provider != "auto":
                    # Hard-managed mode: no fallback. Re-raise.
                    raise
                print(
                    f"[agent_router] failover from=managed to=messages reason=transient "
                    f"error={type(e).__name__}:{str(e)[:120]} project_id={project_id}"
                )
            else:
                # Non-transient (auth error, bad request, etc.) — re-raise.
                raise

        if managed_failed_transient:
            # Synthetic keepalive so the SSE doesn't time out on the client
            # during the brief gap between managed failure and messages start.
            yield {
                "type": "keepalive",
                "elapsed_seconds": 0,
                "phase": "failover",
                "_provider": "router",
            }
            async for ev in self._stream_messages(
                brief=brief, user_token=user_token, project_id=project_id,
                session_id=session_id, stored_agent_id=stored_agent_id,
                max_tool_calls=max_tool_calls, prior_turns=prior_turns,
                lang=lang, image_urls=image_urls,
            ):
                yield ev

    # ── Per-provider thin wrappers ─────────────────────────────────────
    async def _stream_managed(
        self,
        *,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str],
        stored_agent_id: Optional[str],
        max_tool_calls: int,
        prior_turns: Optional[list[dict]],
        lang: Optional[str],
        image_urls: Optional[list[str]],
    ) -> AsyncIterator[dict]:
        # Imported lazily so a missing optional dep on the messages side
        # never breaks the managed path.
        from services.managed_agent_client import get_managed_agent_client
        client = get_managed_agent_client()
        async for ev in client.run_stream(
            brief=brief,
            user_token=user_token,
            project_id=project_id,
            session_id=session_id,
            stored_agent_id=stored_agent_id,
            max_tool_calls=max_tool_calls,
            prior_turns=prior_turns,
            lang=lang,
            image_urls=image_urls,
        ):
            # Tag for observability without mutating existing fields.
            if isinstance(ev, dict) and "_provider" not in ev:
                ev["_provider"] = "managed"
            yield ev

    async def _stream_messages(
        self,
        *,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str],
        stored_agent_id: Optional[str],
        max_tool_calls: int,
        prior_turns: Optional[list[dict]],
        lang: Optional[str],
        image_urls: Optional[list[str]],
    ) -> AsyncIterator[dict]:
        from services.messages_agent_client import get_messages_agent_client
        client = get_messages_agent_client()
        async for ev in client.run_stream(
            brief=brief,
            user_token=user_token,
            project_id=project_id,
            session_id=session_id,
            stored_agent_id=stored_agent_id,
            max_tool_calls=max_tool_calls,
            prior_turns=prior_turns,
            lang=lang,
            image_urls=image_urls,
        ):
            yield ev


# ── Singleton accessor ──────────────────────────────────────────────────
_singleton: Optional[AgentClientRouter] = None


def get_agent_client_router() -> AgentClientRouter:
    global _singleton
    if _singleton is None:
        _singleton = AgentClientRouter()
    return _singleton
