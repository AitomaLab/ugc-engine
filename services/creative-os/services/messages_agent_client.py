"""
Creative OS — Messages API Agent Client (failover path)

Async wrapper around Anthropic's regular Messages API (`client.messages.stream()`).
Drives the same Studio creative-director agent as ManagedAgentClient using the
same SYSTEM_PROMPT and TOOL_DISPATCH, but routes through the standard chat
completions endpoint instead of beta.sessions.events.

Used by AgentClientRouter when Managed Agents (beta) is degraded. Yields the
same SSE event shape so routers/agent.py and AgentPanel.tsx are agnostic to
which client is active.

Differences vs. ManagedAgentClient (all transparent to the user):
  - Conversation history is sent in full every turn (Messages API has no
    server-side session). Mitigated by `cache_control: ephemeral` on system
    + tools, which keeps the bulk of the input cached for ~5 min idle windows.
  - Memory tool works identically because it's a custom Supabase-backed
    tool, not a Managed Agents built-in.
  - `agent_toolset_20260401` is omitted; it's unreferenced by the system
    prompt and unused by the agent in practice.
  - Tool history (tool_use/tool_result blocks from prior turns) is NOT
    replayed. Persisted turn text is enough to maintain conversational
    coherence; the agent doesn't need to "remember" exact tool_use_ids.
    Modal/Supabase rows are the source of truth for what actually shipped.
"""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from anthropic import AsyncAnthropic, APIStatusError

from env_loader import load_env
_repo_root = load_env(Path(__file__))

import sys as _sys
if _repo_root and str(_repo_root) not in _sys.path:
    _sys.path.insert(0, str(_repo_root))

# Reuse everything from the managed client. Zero duplication of tool logic,
# system prompt, or schema construction. If the managed client is updated
# (new tool, prompt tweak, etc.) the fallback inherits it for free.
from services.managed_agent_client import (
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    TOOL_DISPATCH,
    ToolContext,
    _custom_tools_for_agent,
    _summarize_input,
    _summarize_result,
    _user_id_from_jwt,
)
from services import agent_memory as _agent_memory


# ── Tunables ─────────────────────────────────────────────────────────────
_MAX_TOKENS = 8192
_MAX_TOOL_ROUNDS = 24             # safety net against runaway tool-call loops
_MAX_HISTORY_TURNS = 24           # cap replayed turns to keep request size sane
_REQUEST_TIMEOUT_S = 90           # per-request timeout (mirrors managed client)
_TOOL_KEEPALIVE_INTERVAL_S = 15
_HEARTBEAT_INTERVAL_S = 10


# ── Client wrapper ──────────────────────────────────────────────────────
class MessagesAgentClient:
    """Async Anthropic Messages API client.

    Mirrors ManagedAgentClient.run_stream() shape so the router and frontend
    can switch between paths without seeing any structural difference.
    """

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in env.saas / .env")
        # No beta header — this client uses the regular Messages API on purpose.
        self._client = AsyncAnthropic(api_key=self._api_key)

    # ── Streaming entry point ──────────────────────────────────────────
    async def run_stream(
        self,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str] = None,
        stored_agent_id: Optional[str] = None,
        max_tool_calls: int = _MAX_TOOL_ROUNDS,
        prior_turns: Optional[list[dict]] = None,
        lang: Optional[str] = None,
        image_urls: Optional[list[str]] = None,
    ) -> AsyncIterator[dict]:
        """Wrap the inner implementation with a persistent heartbeat task.

        Same pattern as ManagedAgentClient.run_stream — long quiet windows
        during tool execution will time out idle SSE connections without
        these keepalives.
        """
        queue: asyncio.Queue = asyncio.Queue()
        DONE = object()

        async def producer():
            try:
                async for ev in self._run_stream_impl(
                    brief=brief,
                    user_token=user_token,
                    project_id=project_id,
                    session_id=session_id,
                    max_tool_rounds=max_tool_calls,
                    prior_turns=prior_turns,
                    lang=lang,
                    image_urls=image_urls,
                ):
                    await queue.put(ev)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                await queue.put({
                    "type": "error",
                    "message": f"messages-api agent run failed: {e}",
                    "_provider": "messages",
                })
            finally:
                await queue.put(DONE)

        async def heartbeat():
            try:
                while True:
                    await asyncio.sleep(_HEARTBEAT_INTERVAL_S)
                    await queue.put({
                        "type": "keepalive",
                        "elapsed_seconds": 0,
                        "phase": "idle",
                        "_provider": "messages",
                    })
            except asyncio.CancelledError:
                pass

        prod_task = asyncio.create_task(producer())
        hb_task = asyncio.create_task(heartbeat())
        try:
            while True:
                ev = await queue.get()
                if ev is DONE:
                    break
                yield ev
        finally:
            hb_task.cancel()
            prod_task.cancel()
            with suppress(BaseException):
                await hb_task
            with suppress(BaseException):
                await prod_task

    # ── Inner implementation ───────────────────────────────────────────
    async def _run_stream_impl(
        self,
        brief: str,
        user_token: str,
        project_id: Optional[str],
        session_id: Optional[str],
        max_tool_rounds: int,
        prior_turns: Optional[list[dict]],
        lang: Optional[str],
        image_urls: Optional[list[str]],
    ) -> AsyncIterator[dict]:
        # Synthesize a session id so the frontend persists it in agent_threads,
        # marking this thread as "owned by the messages-api client". The router
        # can recognise the prefix on subsequent turns if it wants.
        synth_session = session_id if (session_id or "").startswith("messages-") else f"messages-{uuid.uuid4().hex[:24]}"
        yield {
            "type": "session",
            "session_id": synth_session,
            "agent_id": "messages-api",
            "_provider": "messages",
        }

        ctx = ToolContext(user_token=user_token, project_id=project_id)

        # Build the system block. cache_control on the system prompt + tools
        # is the bulk of input-token cost — caching saves ~90% per turn.
        # Using 1-hour TTL (2× write cost) because SaaS users often idle
        # 5-30 min between turns; the 5-min default would miss too often.
        system_blocks = [
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            },
        ]
        # Optionally inject a brief language steer.
        if lang:
            system_blocks.append({
                "type": "text",
                "text": f"Reply in {'Spanish' if lang.lower().startswith('es') else 'English'}.",
            })

        # Tools: reuse the exact custom-tool definitions the managed client
        # registers. Cache_control on the LAST tool entry caches the whole
        # tools array as a single prefix. 1h TTL matches the system block.
        tools = list(_custom_tools_for_agent())
        if tools:
            tools[-1] = {**tools[-1], "cache_control": {"type": "ephemeral", "ttl": "1h"}}

        # Project prior turns into Messages API history (text only — see file
        # docstring for why tool_use blocks are not replayed).
        messages = self._project_history_to_messages(prior_turns or [])

        # On the first turn of a fresh session, prepend the memory snapshot
        # so the agent doesn't need a silent `memory view` round-trip.
        first_turn = not messages
        if first_turn:
            try:
                uid = _user_id_from_jwt(user_token)
                if uid:
                    snapshot = await _agent_memory.read_snapshot(user_token, uid)
                    brief = (
                        "[Memory snapshot — your persistent notes about this user. "
                        "Apply what's relevant; do NOT call the `memory` tool just to read.]\n"
                        f"{snapshot}\n\n" + brief
                    )
            except Exception as e:
                print(f"[MessagesAgent] memory snapshot preface failed: {e}")

        # Append the user brief.
        user_content: list[dict] | str
        if image_urls:
            # Multi-modal user message. Each image becomes an image block.
            blocks: list[dict] = []
            for url in image_urls:
                blocks.append({
                    "type": "image",
                    "source": {"type": "url", "url": url},
                })
            blocks.append({"type": "text", "text": brief})
            user_content = blocks
        else:
            user_content = brief
        messages.append({"role": "user", "content": user_content})

        # ── Tool-use loop ──────────────────────────────────────────────
        pending_confirmation: Optional[dict] = None
        for _round in range(max_tool_rounds):
            # Per-call event buffer — using a module-level sink would race
            # across concurrent users sharing this singleton client.
            turn_events: list[dict] = []
            (
                assistant_blocks,
                emitted_text,
                tool_uses,
                _stop_reason,
            ) = await self._stream_one_turn(
                messages=messages,
                system_blocks=system_blocks,
                tools=tools,
                event_sink=turn_events.append,
            )
            for ev in turn_events:
                yield ev

            # No tool calls — assistant turn is done.
            if not tool_uses:
                # Safety-net cost-prompt synthesis matches managed client
                # behavior at managed_agent_client.py:5240-5250: if the agent
                # ended a turn after a confirmation_required result without
                # writing user-facing text, surface a fallback message.
                if pending_confirmation and not emitted_text:
                    credits = pending_confirmation.get("credits") or 0
                    summaries = pending_confirmation.get("summaries") or []
                    label = summaries[0] if len(summaries) == 1 else "this batch"
                    fallback = (
                        f"This will cost {credits} credits ({label}). Want me to proceed?"
                        if credits
                        else "Ready when you are — confirm to proceed?"
                    )
                    yield {"type": "agent_message", "text": fallback, "_provider": "messages"}
                break

            # Append assistant message (with tool_use blocks) to history.
            messages.append({"role": "assistant", "content": assistant_blocks})

            # Execute all tool calls concurrently.
            tasks = [
                asyncio.create_task(self._execute_tool_block(tu, ctx, brief=brief))
                for tu in tool_uses
            ]

            # Yield keepalives every 15s while tools are running.
            elapsed = 0
            while any(not t.done() for t in tasks):
                _done, pending = await asyncio.wait(
                    tasks,
                    timeout=_TOOL_KEEPALIVE_INTERVAL_S,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if pending:
                    elapsed += _TOOL_KEEPALIVE_INTERVAL_S
                    yield {
                        "type": "keepalive",
                        "elapsed_seconds": elapsed,
                        "pending_tools": len(pending),
                        "_provider": "messages",
                    }

            results: list[tuple[str, str, bool]] = []
            for t in tasks:
                try:
                    results.append(t.result())
                except Exception as e:
                    results.append(("", json.dumps({"error": str(e)}), True))

            # Emit tool_result events + aggregate confirmations.
            confirm_total_credits = 0
            confirm_summaries: list[str] = []
            for tool_use_id, result_text, is_error in results:
                yield {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "summary": _summarize_result(result_text),
                    "is_error": is_error,
                    "_provider": "messages",
                }
                if not is_error:
                    try:
                        parsed = json.loads(result_text)
                    except Exception:
                        parsed = None
                    if isinstance(parsed, dict):
                        if parsed.get("action") == "confirmation_required":
                            c = parsed.get("credits")
                            s = parsed.get("summary") or parsed.get("operation")
                            if isinstance(c, (int, float)):
                                confirm_total_credits += int(c)
                            if s:
                                confirm_summaries.append(str(s))
                        elif "total_credits" in parsed and "line_items" in parsed:
                            c = parsed.get("total_credits")
                            if isinstance(c, (int, float)):
                                confirm_total_credits += int(c)
                            confirm_summaries.append("estimated bundle")

            if confirm_total_credits > 0:
                yield {
                    "type": "confirmation_pending",
                    "credits": confirm_total_credits,
                    "summaries": confirm_summaries,
                    "_provider": "messages",
                }

            # Drain new artifacts produced by tools in this round.
            if ctx.new_artifacts:
                for art in ctx.new_artifacts:
                    yield {"type": "artifact", "artifact": art, "_provider": "messages"}
                ctx.new_artifacts.clear()

            # Append tool results as the next user message.
            tool_result_blocks = [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_use_id,
                    "content": result_text,
                    "is_error": is_error,
                }
                for tool_use_id, result_text, is_error in results
            ]
            messages.append({"role": "user", "content": tool_result_blocks})

            # Loop and let the model respond to the tool results.

        yield {"type": "done", "session_id": synth_session, "_provider": "messages"}

    # ── Streaming a single assistant turn ──────────────────────────────
    async def _stream_one_turn(
        self,
        messages: list[dict],
        system_blocks: list[dict],
        tools: list[dict],
        event_sink,  # callable that appends emitted events to a buffer
    ) -> tuple[list[dict], str, list[Any], Optional[str]]:
        """Run one round of messages.stream() and emit text/tool_call events
        as they arrive. Returns the full assistant content blocks plus the
        list of tool_use blocks for execution.
        """
        accumulated_text = ""
        tool_uses: list[Any] = []
        assistant_blocks: list[dict] = []

        # Track the in-flight content block per index so we can flush text
        # and detect tool_use boundaries.
        active_text_idx: Optional[int] = None

        try:
            stream_ctx = self._client.messages.stream(
                model=DEFAULT_MODEL,
                system=system_blocks,
                tools=tools,
                messages=messages,
                max_tokens=_MAX_TOKENS,
                timeout=_REQUEST_TIMEOUT_S,
            )
        except APIStatusError:
            raise

        async with stream_ctx as stream:
            async for event in stream:
                t = getattr(event, "type", None)
                if t == "content_block_start":
                    block = getattr(event, "content_block", None)
                    if block is not None and getattr(block, "type", None) == "tool_use":
                        # Tool use block — input arrives as JSON deltas; the
                        # SDK aggregates it for us in the final message. Don't
                        # emit a `tool_call` event yet — wait until we have
                        # the complete input from the final message.
                        pass
                    elif block is not None and getattr(block, "type", None) == "text":
                        active_text_idx = getattr(event, "index", None)
                elif t == "content_block_delta":
                    delta = getattr(event, "delta", None)
                    if delta is not None and getattr(delta, "type", None) == "text_delta":
                        text = getattr(delta, "text", "") or ""
                        accumulated_text += text
                elif t == "content_block_stop":
                    # If a text block just finished, emit it as agent_message.
                    if active_text_idx is not None:
                        if accumulated_text.strip():
                            event_sink({
                                "type": "agent_message",
                                "text": accumulated_text,
                                "_provider": "messages",
                            })
                        accumulated_text = ""
                        active_text_idx = None

            final = await stream.get_final_message()

        # Walk the final message's content blocks to extract tool_use blocks
        # with fully-aggregated input dicts and to capture the assistant's
        # canonical content payload for history replay.
        for block in (final.content or []):
            btype = getattr(block, "type", None)
            if btype == "text":
                txt = getattr(block, "text", "") or ""
                assistant_blocks.append({"type": "text", "text": txt})
            elif btype == "tool_use":
                tool_uses.append(block)
                assistant_blocks.append({
                    "type": "tool_use",
                    "id": getattr(block, "id", ""),
                    "name": getattr(block, "name", ""),
                    "input": getattr(block, "input", {}) or {},
                })
                # Now that we have the complete input dict, emit tool_call.
                event_sink({
                    "type": "tool_call",
                    "name": getattr(block, "name", ""),
                    "input_summary": _summarize_input(getattr(block, "input", {}) or {}, 80),
                    "mode": (getattr(block, "input", {}) or {}).get("mode"),
                    "tool_use_id": getattr(block, "id", ""),
                    "_provider": "messages",
                })

        emitted_text = "".join(b.get("text", "") for b in assistant_blocks if b.get("type") == "text")
        return (
            assistant_blocks,
            emitted_text,
            tool_uses,
            getattr(final, "stop_reason", None),
        )

    # ── Tool execution (parallel to managed client's _execute_tool) ────
    async def _execute_tool_block(self, tool_use_block: Any, ctx: ToolContext, *, brief: str) -> tuple[str, str, bool]:
        """Execute a single Messages-API tool_use block.

        Mirrors ManagedAgentClient._execute_tool (managed_agent_client.py:5417)
        including the [QUICK_MODE=on] auto-confirm logic. Returns the
        (tool_use_id, result_text, is_error) triple expected by the caller.
        """
        tool_use_id = getattr(tool_use_block, "id", "") or ""
        name = getattr(tool_use_block, "name", "") or ""
        tool_input = dict(getattr(tool_use_block, "input", {}) or {})
        fn = TOOL_DISPATCH.get(name)
        if fn is None:
            return tool_use_id, json.dumps({"error": f"unknown tool: {name}"}), True
        try:
            print(f"[MessagesAgent] tool {name}({_summarize_input(tool_input, 120)})")
            result_text = await fn(ctx, **tool_input)

            # Quick Mode auto-confirm parity with managed client.
            if "[QUICK_MODE=on]" in brief:
                try:
                    parsed = json.loads(result_text)
                    if isinstance(parsed, dict) and parsed.get("action") == "confirmation_required":
                        credits = parsed.get("credits", 0)
                        if isinstance(credits, (int, float)) and credits <= 100:
                            print(f"[MessagesAgent] Auto-confirming Quick Mode tool {name} (Cost: {credits})")
                            tool_input["confirmed"] = True
                            echo = parsed.get("echo", {})
                            tool_input.update(echo)
                            result_text = await fn(ctx, **tool_input)
                except Exception as inner_e:
                    print(f"[MessagesAgent] Quick mode auto-confirm parse error: {inner_e}")

            return tool_use_id, result_text, False
        except Exception as e:
            return tool_use_id, json.dumps({"error": str(e)}), True

    # ── History projection ─────────────────────────────────────────────
    @staticmethod
    def _project_history_to_messages(prior_turns: list[dict]) -> list[dict]:
        """Convert agent_threads.turns into a Messages API messages list.

        Strips tool_use/tool_result history (we only have summaries, not the
        full original payloads) and keeps text-only turns. The agent doesn't
        need to "remember" exact tool_use_ids — Modal/Supabase rows hold the
        ground truth for any artifact it produced earlier. Truncated to
        _MAX_HISTORY_TURNS most-recent entries to keep request size sane.
        """
        out: list[dict] = []
        # Take only the tail of the conversation.
        recent = prior_turns[-_MAX_HISTORY_TURNS:] if len(prior_turns) > _MAX_HISTORY_TURNS else list(prior_turns)
        for turn in recent:
            role = turn.get("role")
            text = (turn.get("text") or "").strip()
            if not text:
                # Skip empty agent stubs (the panel sometimes appends an
                # empty placeholder turn before the SSE stream fills it).
                continue
            if role == "user":
                out.append({"role": "user", "content": text})
            elif role == "agent":
                out.append({"role": "assistant", "content": text})
            # Ignore other roles defensively.
        # Messages API requires the conversation to start with a user turn.
        # Drop any leading assistant entries.
        while out and out[0]["role"] != "user":
            out.pop(0)
        return out


# ── Singleton accessor (mirrors managed client pattern) ─────────────────
_singleton: Optional[MessagesAgentClient] = None


def get_messages_agent_client() -> MessagesAgentClient:
    global _singleton
    if _singleton is None:
        _singleton = MessagesAgentClient()
    return _singleton
