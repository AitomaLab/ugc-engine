"""
Creative OS — Agent memory store

Backs the custom `memory` tool exposed to the creative-director agent.
Implements the six command surface documented by Anthropic's Memory Tool
(view / create / str_replace / insert / delete / rename) against the
Supabase `agent_memories` table.

Scope is per-user (cross-project, cross-session). RLS on the table enforces
ownership server-side; we still pass the user's JWT on every request so
Supabase fills `auth.uid()` correctly.

Paths are always normalized to POSIX form under `/memories/`. Directory
traversal (`..`, absolute overrides) is rejected before any DB call.
"""
from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath
from typing import Optional

import httpx

from env_loader import load_env
load_env(Path(__file__))

_TIMEOUT = 15.0
_MEM_ROOT = "/memories"
_MAX_CONTENT_BYTES = 200_000   # ~200 KB per file
_MAX_TOTAL_BYTES = 2_000_000   # ~2 MB per user
_LINE_LIMIT = 999_999
_VIEW_MAX_LINES = 2000


def _supabase_creds() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL")
    anon = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
    if not url or not anon:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY for agent_memory")
    return url, anon


def _headers(user_token: str, anon: str, *, prefer_repr: bool = False) -> dict:
    h = {
        "apikey": anon,
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json",
    }
    if prefer_repr:
        h["Prefer"] = "return=representation"
    return h


def _normalize_path(raw: str) -> str:
    """Normalize an agent-supplied path into a safe `/memories/...` string.

    Raises ValueError if traversal escapes the root, or if the path is empty
    after normalization (i.e. resolves to `/memories` itself when a file was
    required — caller decides whether that's allowed).
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("path must be a non-empty string")
    s = raw.strip()
    # Reject URL-encoded traversal up front.
    if "%2e" in s.lower() or "%2f" in s.lower():
        raise ValueError("path contains encoded traversal sequences")
    # Require absolute-looking path; allow `memories/...` shorthand too.
    if not s.startswith("/"):
        s = "/" + s
    p = PurePosixPath(s)
    # Resolve `.` / `..` segments manually — PurePosixPath doesn't resolve them.
    parts: list[str] = []
    for part in p.parts:
        if part in ("", "/"):
            continue
        if part == ".":
            continue
        if part == "..":
            if not parts or parts[0] != "memories":
                raise ValueError("path traversal out of /memories is forbidden")
            if len(parts) == 1:  # trying to escape /memories
                raise ValueError("path traversal out of /memories is forbidden")
            parts.pop()
            continue
        if "\x00" in part:
            raise ValueError("path contains null byte")
        parts.append(part)
    if not parts or parts[0] != "memories":
        # Accept "/memories" or "memories/..." — prepend if user gave a bare path
        parts = ["memories", *parts] if parts and parts[0] != "memories" else ["memories", *parts]
    normalized = "/" + "/".join(parts)
    if not normalized.startswith(_MEM_ROOT):
        raise ValueError("path must be under /memories")
    return normalized


def _is_dir_path(normalized: str) -> bool:
    """A path is treated as a directory if it ends with `/` OR if it has no
    file-like tail (we keep this simple: callers pass explicit file paths for
    files and `/memories` or `/memories/subdir` for directories)."""
    return normalized == _MEM_ROOT or normalized.endswith("/")


def _human_size(n: int) -> str:
    if n < 1024:
        return f"{n}B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f}K"
    return f"{n / (1024 * 1024):.1f}M"


def _format_file(path: str, content: str, view_range: Optional[list[int]] = None) -> str:
    lines = content.splitlines()
    if len(lines) > _LINE_LIMIT:
        return f"File {path} exceeds maximum line limit of {_LINE_LIMIT} lines."
    start = 1
    end = len(lines)
    if view_range and isinstance(view_range, list) and len(view_range) == 2:
        try:
            start = max(1, int(view_range[0]))
            end = int(view_range[1])
            if end < 0:
                end = len(lines)
            end = min(end, len(lines))
        except Exception:
            start, end = 1, len(lines)
    sliced = lines[start - 1:end]
    if len(sliced) > _VIEW_MAX_LINES:
        sliced = sliced[:_VIEW_MAX_LINES]
        end = start + _VIEW_MAX_LINES - 1
    body = "\n".join(f"{i + start:>6}\t{line}" for i, line in enumerate(sliced))
    return f"Here's the content of {path} with line numbers:\n{body}"


# ─── Low-level DB helpers ──────────────────────────────────────────────

async def _get_file(user_token: str, user_id: str, path: str) -> Optional[dict]:
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/agent_memories",
            headers=_headers(user_token, anon),
            params={
                "user_id": f"eq.{user_id}",
                "path": f"eq.{path}",
                "select": "id,path,content,updated_at",
                "limit": 1,
            },
        )
        if resp.status_code != 200:
            print(f"[agent_memory] get_file error {resp.status_code}: {resp.text}")
            return None
        rows = resp.json()
        return rows[0] if rows else None


async def _list_under(user_token: str, user_id: str, prefix: str) -> list[dict]:
    """List files whose path starts with `prefix`. Pass the directory form
    (trailing `/`) to avoid matching sibling files with longer names."""
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/agent_memories",
            headers=_headers(user_token, anon),
            params={
                "user_id": f"eq.{user_id}",
                "path": f"like.{prefix}%",
                "select": "path,content",
                "order": "path.asc",
                "limit": 500,
            },
        )
        if resp.status_code != 200:
            print(f"[agent_memory] list error {resp.status_code}: {resp.text}")
            return []
        return resp.json()


async def _total_size(user_token: str, user_id: str) -> int:
    url, anon = _supabase_creds()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(
            f"{url}/rest/v1/agent_memories",
            headers=_headers(user_token, anon),
            params={
                "user_id": f"eq.{user_id}",
                "select": "content",
                "limit": 500,
            },
        )
        if resp.status_code != 200:
            return 0
        return sum(len(r.get("content") or "") for r in resp.json())


async def _upsert_file(user_token: str, user_id: str, path: str, content: str) -> bool:
    url, anon = _supabase_creds()
    from datetime import datetime, timezone
    headers = _headers(user_token, anon, prefer_repr=True)
    headers["Prefer"] = "resolution=merge-duplicates,return=representation"
    payload = {
        "user_id": user_id,
        "path": path,
        "content": content,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            f"{url}/rest/v1/agent_memories",
            headers=headers,
            params={"on_conflict": "user_id,path"},
            json=payload,
        )
        if resp.status_code not in (200, 201):
            print(f"[agent_memory] upsert error {resp.status_code}: {resp.text}")
            return False
        return True


async def _delete_exact(user_token: str, user_id: str, path: str) -> int:
    url, anon = _supabase_creds()
    headers = _headers(user_token, anon, prefer_repr=True)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(
            f"{url}/rest/v1/agent_memories",
            headers=headers,
            params={
                "user_id": f"eq.{user_id}",
                "path": f"eq.{path}",
            },
        )
        if resp.status_code not in (200, 204):
            print(f"[agent_memory] delete error {resp.status_code}: {resp.text}")
            return 0
        # When Prefer=return=representation, 200 returns the deleted rows.
        try:
            return len(resp.json())
        except Exception:
            return 1 if resp.status_code in (200, 204) else 0


async def _delete_prefix(user_token: str, user_id: str, prefix: str) -> int:
    url, anon = _supabase_creds()
    headers = _headers(user_token, anon, prefer_repr=True)
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.delete(
            f"{url}/rest/v1/agent_memories",
            headers=headers,
            params={
                "user_id": f"eq.{user_id}",
                "path": f"like.{prefix}%",
            },
        )
        if resp.status_code not in (200, 204):
            print(f"[agent_memory] delete_prefix error {resp.status_code}: {resp.text}")
            return 0
        try:
            return len(resp.json())
        except Exception:
            return 0


# ─── Command handlers ──────────────────────────────────────────────────

async def view(user_token: str, user_id: str, *, path: str, view_range: Optional[list[int]] = None) -> str:
    try:
        norm = _normalize_path(path)
    except ValueError as e:
        return f"Error: {e}"

    # Directory listing: look for any file whose path starts with `norm + "/"`,
    # OR if `norm` itself exists as a file, show it.
    file_row = await _get_file(user_token, user_id, norm)
    if file_row is not None:
        return _format_file(norm, file_row["content"] or "", view_range)

    prefix = norm if norm.endswith("/") else norm + "/"
    rows = await _list_under(user_token, user_id, prefix)
    if not rows and norm != _MEM_ROOT:
        return f"The path {norm} does not exist. Please provide a valid path."

    # Build a 2-level tree view mimicking the Anthropic sample output.
    shown_prefix_len = len(prefix)
    subdirs: dict[str, int] = {}
    files: list[tuple[str, int]] = []
    for r in rows:
        full = r["path"]
        size = len(r.get("content") or "")
        tail = full[shown_prefix_len:]
        depth_parts = tail.split("/")
        if len(depth_parts) == 1:
            files.append((full, size))
        else:
            sub = depth_parts[0]
            subdirs[sub] = subdirs.get(sub, 0) + size

    lines = [
        f"Here're the files and directories up to 2 levels deep in {norm}, "
        f"excluding hidden items and node_modules:"
    ]
    total_here = sum(sz for _, sz in files) + sum(subdirs.values())
    lines.append(f"{_human_size(total_here)}\t{norm}")
    for name, sz in sorted(subdirs.items()):
        lines.append(f"{_human_size(sz)}\t{prefix}{name}")
    for full, sz in sorted(files):
        lines.append(f"{_human_size(sz)}\t{full}")
    return "\n".join(lines)


async def create(user_token: str, user_id: str, *, path: str, file_text: str) -> str:
    try:
        norm = _normalize_path(path)
    except ValueError as e:
        return f"Error: {e}"
    if norm == _MEM_ROOT or norm.endswith("/"):
        return f"Error: {norm} is a directory path. Please provide a file path."
    if not isinstance(file_text, str):
        return "Error: file_text must be a string."
    if len(file_text.encode("utf-8")) > _MAX_CONTENT_BYTES:
        return f"Error: file exceeds per-file limit ({_MAX_CONTENT_BYTES} bytes)."
    existing = await _get_file(user_token, user_id, norm)
    if existing is not None:
        return f"Error: File {norm} already exists"
    total = await _total_size(user_token, user_id)
    if total + len(file_text) > _MAX_TOTAL_BYTES:
        return "Error: user memory quota exceeded — delete older files first."
    ok = await _upsert_file(user_token, user_id, norm, file_text)
    if not ok:
        return f"Error: could not create {norm}"
    return f"File created successfully at: {norm}"


async def str_replace(user_token: str, user_id: str, *, path: str, old_str: str, new_str: str) -> str:
    try:
        norm = _normalize_path(path)
    except ValueError as e:
        return f"Error: {e}"
    if norm == _MEM_ROOT or norm.endswith("/"):
        return f"Error: The path {norm} does not exist. Please provide a valid path."
    row = await _get_file(user_token, user_id, norm)
    if row is None:
        return f"Error: The path {norm} does not exist. Please provide a valid path."
    content = row["content"] or ""
    if not isinstance(old_str, str) or not isinstance(new_str, str):
        return "Error: old_str and new_str must be strings."
    occurrences = content.count(old_str)
    if occurrences == 0:
        return f"No replacement was performed, old_str `{old_str}` did not appear verbatim in {norm}."
    if occurrences > 1:
        line_nums = [str(i + 1) for i, line in enumerate(content.splitlines()) if old_str in line]
        return (
            f"No replacement was performed. Multiple occurrences of old_str `{old_str}` "
            f"in lines: {', '.join(line_nums)}. Please ensure it is unique"
        )
    updated = content.replace(old_str, new_str, 1)
    if len(updated.encode("utf-8")) > _MAX_CONTENT_BYTES:
        return f"Error: edit would exceed per-file limit ({_MAX_CONTENT_BYTES} bytes)."
    if not await _upsert_file(user_token, user_id, norm, updated):
        return f"Error: could not update {norm}"
    # Snippet: show the changed area with ±3 lines of context.
    idx = updated.find(new_str)
    before = updated.count("\n", 0, idx)
    lines = updated.splitlines()
    s = max(0, before - 3)
    e = min(len(lines), before + new_str.count("\n") + 4)
    snippet = "\n".join(f"{i + 1:>6}\t{ln}" for i, ln in enumerate(lines[s:e], start=s))
    return f"The memory file has been edited.\n{snippet}"


async def insert(user_token: str, user_id: str, *, path: str, insert_line: int, insert_text: str) -> str:
    try:
        norm = _normalize_path(path)
    except ValueError as e:
        return f"Error: {e}"
    if norm == _MEM_ROOT or norm.endswith("/"):
        return f"Error: The path {norm} does not exist"
    row = await _get_file(user_token, user_id, norm)
    if row is None:
        return f"Error: The path {norm} does not exist"
    if not isinstance(insert_text, str):
        return "Error: insert_text must be a string."
    try:
        n = int(insert_line)
    except Exception:
        return "Error: insert_line must be an integer."
    content = row["content"] or ""
    lines = content.splitlines()
    if n < 0 or n > len(lines):
        return (
            f"Error: Invalid `insert_line` parameter: {n}. "
            f"It should be within the range of lines of the file: [0, {len(lines)}]"
        )
    new_lines = lines[:n] + insert_text.splitlines() + lines[n:]
    updated = "\n".join(new_lines)
    if len(updated.encode("utf-8")) > _MAX_CONTENT_BYTES:
        return f"Error: edit would exceed per-file limit ({_MAX_CONTENT_BYTES} bytes)."
    if not await _upsert_file(user_token, user_id, norm, updated):
        return f"Error: could not update {norm}"
    return f"The file {norm} has been edited."


async def delete(user_token: str, user_id: str, *, path: str) -> str:
    try:
        norm = _normalize_path(path)
    except ValueError as e:
        return f"Error: {e}"
    # Directory delete — recursive.
    if norm == _MEM_ROOT:
        return "Error: refusing to delete the entire /memories root."
    if norm.endswith("/"):
        removed = await _delete_prefix(user_token, user_id, norm)
        if removed == 0:
            return f"Error: The path {norm} does not exist"
        return f"Successfully deleted {norm}"
    row = await _get_file(user_token, user_id, norm)
    if row is None:
        # Maybe it's a directory supplied without the trailing slash.
        listing = await _list_under(user_token, user_id, norm + "/")
        if listing:
            removed = await _delete_prefix(user_token, user_id, norm + "/")
            return f"Successfully deleted {norm}" if removed else f"Error: The path {norm} does not exist"
        return f"Error: The path {norm} does not exist"
    ok = await _delete_exact(user_token, user_id, norm)
    if not ok:
        return f"Error: could not delete {norm}"
    return f"Successfully deleted {norm}"


async def rename(user_token: str, user_id: str, *, old_path: str, new_path: str) -> str:
    try:
        old_norm = _normalize_path(old_path)
        new_norm = _normalize_path(new_path)
    except ValueError as e:
        return f"Error: {e}"
    if old_norm == new_norm:
        return f"Error: The destination {new_norm} already exists"

    # Directory rename: move every row whose path starts with old prefix.
    old_prefix = old_norm if old_norm.endswith("/") else old_norm + "/"
    rows_under = await _list_under(user_token, user_id, old_prefix)
    if rows_under:
        new_prefix = new_norm if new_norm.endswith("/") else new_norm + "/"
        # Reject if destination already has any content.
        existing_dest = await _list_under(user_token, user_id, new_prefix)
        if existing_dest:
            return f"Error: The destination {new_norm} already exists"
        for r in rows_under:
            src = r["path"]
            dst = new_prefix + src[len(old_prefix):]
            content = r.get("content") or ""
            if not await _upsert_file(user_token, user_id, dst, content):
                return f"Error: failed to rename {old_norm} → {new_norm}"
        await _delete_prefix(user_token, user_id, old_prefix)
        return f"Successfully renamed {old_norm} to {new_norm}"

    # File rename.
    src_row = await _get_file(user_token, user_id, old_norm)
    if src_row is None:
        return f"Error: The path {old_norm} does not exist"
    dst_row = await _get_file(user_token, user_id, new_norm)
    if dst_row is not None:
        return f"Error: The destination {new_norm} already exists"
    if not await _upsert_file(user_token, user_id, new_norm, src_row.get("content") or ""):
        return f"Error: failed to rename {old_norm} → {new_norm}"
    await _delete_exact(user_token, user_id, old_norm)
    return f"Successfully renamed {old_norm} to {new_norm}"


__all__ = ["view", "create", "str_replace", "insert", "delete", "rename"]
