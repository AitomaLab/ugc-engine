"""BrightData Datasets v3 integration for the Analytics module.

Public entry point::

    result = await scrape(input="https://www.tiktok.com/@nike/video/...",
                          kind=None,
                          user_id=user_id,
                          job_id=job_id)

Returns a list of normalized ``analytics_posts`` row dicts (without ``user_id``;
the router stamps that on before upserting).

Mock mode
---------
Set ``BRIGHTDATA_MOCK=true`` to bypass the network and return canned fixtures
from ``analytics/fixtures/*.json``. Used by unit tests and local development
without a BrightData seat.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx

from . import db as analytics_db
from .url_parser import ParsedInput, detect

BRIGHTDATA_BASE = "https://api.brightdata.com"
BRIGHTDATA_TRIGGER_PATH = "/datasets/v3/trigger"
BRIGHTDATA_SNAPSHOT_PATH = "/datasets/v3/snapshot/{snapshot_id}"

# Conservative defaults — caller can override via env.
_POLL_INTERVAL_SEC = float(os.getenv("BRIGHTDATA_POLL_INTERVAL", "4"))
_MAX_WAIT_SEC = float(os.getenv("BRIGHTDATA_MAX_WAIT", "120"))
_PER_RECORD_COST_USD = float(os.getenv("BRIGHTDATA_PER_RECORD_USD", "0.002"))
_STORAGE_BUCKET = os.getenv("ANALYTICS_STORAGE_BUCKET", "analytics-media")
_MIRROR_MAX_BYTES = int(os.getenv("ANALYTICS_MIRROR_MAX_BYTES", str(150 * 1024 * 1024)))

_FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ── Public types ────────────────────────────────────────────────────────────

@dataclass
class ScrapeResult:
    posts: list[dict]
    brightdata_calls: int
    estimated_cost_usd: float
    snapshot_id: Optional[str] = None
    status: str = "completed"
    error_message: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mock_enabled() -> bool:
    return os.getenv("BRIGHTDATA_MOCK", "false").lower() in ("1", "true", "yes")


def _api_key() -> str:
    key = os.getenv("BRIGHTDATA_API_KEY", "")
    if not key:
        raise RuntimeError(
            "BRIGHTDATA_API_KEY is not set. Add it to .env.saas or run with BRIGHTDATA_MOCK=true."
        )
    return key


def _dataset_id(platform: str, kind: str) -> Optional[str]:
    env_name = {
        ("tiktok", "post"):       "BRIGHTDATA_TIKTOK_POST_DATASET_ID",
        ("tiktok", "account"):    "BRIGHTDATA_TIKTOK_PROFILE_DATASET_ID",
        ("instagram", "post"):    "BRIGHTDATA_INSTAGRAM_POST_DATASET_ID",
        ("instagram", "account"): "BRIGHTDATA_INSTAGRAM_PROFILE_DATASET_ID",
        ("youtube", "post"):      "BRIGHTDATA_YOUTUBE_POST_DATASET_ID",
        ("youtube", "account"):   "BRIGHTDATA_YOUTUBE_PROFILE_DATASET_ID",
        ("facebook", "post"):     "BRIGHTDATA_FACEBOOK_POST_DATASET_ID",
        ("facebook", "account"):  "BRIGHTDATA_FACEBOOK_PROFILE_DATASET_ID",
    }.get((platform, kind))
    return os.getenv(env_name) if env_name else None


def _profile_url_for(platform: Optional[str], username: Optional[str], kind: str) -> Optional[str]:
    """Construct a canonical profile URL so BrightData's profile datasets get
    the `url` field they require when the user only typed an @handle.

    Each social platform has a different profile URL shape — BrightData's
    Instagram/TikTok/YouTube/Facebook profile datasets all accept the
    public-facing profile URL.
    """
    if kind != "account" or not platform or not username:
        return None
    u = username.lstrip("@").lower()
    if platform == "instagram":
        return f"https://www.instagram.com/{u}/"
    if platform == "tiktok":
        return f"https://www.tiktok.com/@{u}"
    if platform == "youtube":
        return f"https://www.youtube.com/@{u}"
    if platform == "facebook":
        return f"https://www.facebook.com/{u}"
    return None


def _coerce_int(v: Any) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


def _coerce_float(v: Any) -> Optional[float]:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ── Normalization ───────────────────────────────────────────────────────────

def _normalize_tiktok(raw: dict, parsed: ParsedInput) -> dict:
    """Map a BrightData TikTok record to an analytics_posts row."""
    url = raw.get("url") or raw.get("video_url") or parsed.normalized_url or ""
    username = (
        raw.get("username")
        or raw.get("profile_username")
        or raw.get("author_username")
        or parsed.username
        or ""
    )
    return {
        "source": "external",
        "platform": "tiktok",
        "username": username.lower() if username else "",
        "post_url": url,
        "external_post_id": str(raw.get("video_id") or raw.get("id") or parsed.post_id or ""),
        "caption": raw.get("description") or raw.get("caption") or raw.get("title"),
        "hashtags": raw.get("hashtags") or [],
        "media_type": "video",
        "media_urls": [{"url": raw.get("video_url"), "type": "video"}] if raw.get("video_url") else [],
        "thumbnail_url": raw.get("cover_url") or raw.get("thumbnail") or raw.get("display_url"),
        "duration_seconds": _coerce_float(raw.get("duration") or raw.get("video_duration")),
        "posted_at": raw.get("created_time") or raw.get("posted_at") or raw.get("date_posted"),
        "views": _coerce_int(
            raw.get("view_count") or raw.get("play_count") or raw.get("playcount")
            or raw.get("video_view_count") or raw.get("plays") or raw.get("views")
        ),
        "likes": _coerce_int(raw.get("like_count") or raw.get("digg_count") or raw.get("likes")),
        "comments": _coerce_int(raw.get("comment_count") or raw.get("comments")),
        "shares": _coerce_int(raw.get("share_count") or raw.get("shares")),
        "saves": _coerce_int(raw.get("save_count") or raw.get("collect_count") or raw.get("saves")),
        # Stripped before upsert. See note in _normalize_instagram.
        "_owner_followers": _coerce_int(
            raw.get("followers") or raw.get("author_followers")
            or raw.get("profile_followers") or raw.get("user_followers")
            or raw.get("followers_count") or raw.get("fans")
        ),
        # Side-channel — same lifecycle as `_owner_followers`. The router
        # peels it off and patches `analytics_tracked_accounts.avatar_url`
        # so the AccountCard / AccountDetailModal can render a real photo
        # instead of a coloured initial. BrightData TikTok post records
        # often include `author.profile_pic_url` even when scraping a
        # single video.
        "_owner_avatar_url": _profile_pic_from_raw(raw),
        "raw_payload": raw,
    }


def _instagram_video_url(raw: dict) -> Optional[str]:
    """Walk every shape BrightData / IG returns the video URL in.

    Real-world responses use any of: top-level ``video_url``, ``videos[0].url``,
    ``video.url``, ``video_versions[0].url`` (the IG-private API shape), or
    nested under ``main_media`` / ``media[*]``.
    """
    for key in ("video_url", "video_play_url", "videoPlayUrl"):
        v = raw.get(key)
        if isinstance(v, str) and v:
            return v
    nested = raw.get("video") or raw.get("main_media") or {}
    if isinstance(nested, dict):
        v = nested.get("url") or nested.get("video_url")
        if isinstance(v, str) and v:
            return v
    for list_key in ("videos", "video_versions", "media"):
        items = raw.get(list_key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    v = item.get("url") or item.get("video_url") or item.get("src")
                    if isinstance(v, str) and v:
                        return v
                elif isinstance(item, str) and item:
                    return item
    return None


def _normalize_instagram(raw: dict, parsed: ParsedInput) -> dict:
    url = raw.get("url") or raw.get("post_url") or parsed.normalized_url or ""
    username = (
        raw.get("user_posted")
        or raw.get("username")
        or raw.get("ownerUsername")
        or parsed.username
        or ""
    )
    media_type = (raw.get("content_type") or raw.get("media_type") or "").lower() or None
    if media_type in ("graphimage", "photo"):
        media_type = "image"
    if media_type in ("graphvideo", "reel", "reels"):
        media_type = "video"
    if media_type in ("graphsidecar", "sidecar"):
        media_type = "carousel"
    video_url = _instagram_video_url(raw)
    thumb_url = (
        raw.get("display_url")
        or raw.get("thumbnail_url")
        or raw.get("image_url")
        or raw.get("display_uri")
    )
    media_urls: list[dict] = []
    if video_url:
        media_urls.append({"url": video_url, "type": "video"})
    elif thumb_url:
        media_urls.append({"url": thumb_url, "type": media_type or "image"})
    return {
        "source": "external",
        "platform": "instagram",
        "username": username.lower() if username else "",
        "post_url": url,
        "external_post_id": str(raw.get("shortcode") or raw.get("post_id") or parsed.post_id or ""),
        "caption": raw.get("description") or raw.get("caption"),
        "hashtags": raw.get("hashtags") or [],
        "media_type": media_type,
        "media_urls": media_urls,
        "thumbnail_url": thumb_url,
        "duration_seconds": _coerce_float(raw.get("video_duration") or raw.get("duration")),
        "posted_at": raw.get("date_posted") or raw.get("posted_at") or raw.get("taken_at"),
        # IG view counts are surfaced under at least four different keys
        # depending on whether BrightData scraped the post via the public
        # web (`video_play_count`), the IG private API mirror
        # (`video_view_count`), or as a Reel listing (`play_count`,
        # `views`). Be maximally permissive — checking each in turn falls
        # through to None rather than 0 so we keep the FE's "—" affordance
        # accurate when no signal exists.
        "views": _coerce_int(
            raw.get("video_play_count") or raw.get("video_view_count")
            or raw.get("play_count") or raw.get("views")
            or raw.get("plays") or raw.get("view_count")
        ),
        "likes": _coerce_int(raw.get("likes") or raw.get("like_count")),
        "comments": _coerce_int(raw.get("num_comments") or raw.get("comment_count")),
        "shares": None,
        "saves": None,
        # `_owner_followers` is stripped before upsert (see _strip_metadata in
        # _scrape_account_for_user). We surface it here so the caller can
        # patch follower_count onto analytics_tracked_accounts without an
        # extra round-trip to BrightData. BrightData's IG posts dataset
        # exposes this on every post row.
        "_owner_followers": _coerce_int(
            raw.get("followers") or raw.get("owner_followers")
            or raw.get("profile_followers") or raw.get("user_followers")
        ),
        # Avatar surfaced from `owner.profile_pic_url` / `user.profile_pic_url`
        # via the recursive `_profile_pic_from_raw` helper. Stripped to
        # `analytics_tracked_accounts.avatar_url` by the router; same
        # lifecycle as `_owner_followers`.
        "_owner_avatar_url": _profile_pic_from_raw(raw),
        "raw_payload": raw,
    }


def _is_error_envelope(raw: dict) -> Optional[str]:
    """BrightData sometimes returns `{error, error_code, input, timestamp}` for
    an individual record when its validator/collector rejects the URL (e.g.
    a profile URL submitted to a post-only dataset). Returns the error
    message if `raw` is an error envelope so callers can surface it on the
    scrape_job row instead of silently persisting a phantom post."""
    if not isinstance(raw, dict):
        return None
    if raw.get("error_code") or raw.get("error"):
        msg = raw.get("error") or raw.get("error_code") or "BrightData record error"
        return str(msg)
    return None


def _profile_pic_from_raw(raw: dict) -> Optional[str]:
    """Best-effort avatar URL from a BrightData profile envelope or post row.

    Walks every shape we've seen across the IG / TikTok / YT / FB datasets,
    plus the IG post-level `owner.profile_pic_url` and TikTok `author.avatar`.
    Returns the first non-empty string under any known alias, or None when
    no avatar is present (e.g. a record that's a pure post payload from a
    dataset that doesn't include owner metadata).
    """
    if not isinstance(raw, dict):
        return None
    for key in (
        # IG: web (`profile_pic_url`, `profile_pic_url_hd`), private API
        # mirror (`profilePic`), BrightData's own naming
        # (`profile_image_link`, `profile_image_link_hd`).
        "profile_pic_url", "profile_pic_url_hd",
        "profile_image_link", "profile_image_link_hd",
        "profilePic",
        # TikTok: `avatar`, `avatar_thumb`, `avatar_larger` (BrightData),
        # plus `avatarThumb`/`avatarLarger` from the IG-style camelcase.
        "avatar", "avatar_url", "avatar_thumb", "avatar_larger",
        "avatarThumb", "avatarLarger",
        # YT / FB / generic — `picture` (FB), `profile_image_url` (YT-ish),
        # `user_profile_pic_url`, `pic`.
        "profile_image_url", "user_profile_pic_url", "picture", "pic",
        # BrightData TikTok profile dataset uses `profile_pic`.
        "profile_pic",
    ):
        val = raw.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()[:8000]
    # Walk nested envelopes — IG post records bury the avatar under
    # `owner.profile_pic_url`, TikTok under `author.avatar`, and some
    # BrightData snapshots wrap the whole thing in `user`.
    for nested_key in ("user", "owner", "author", "channel"):
        nested = raw.get(nested_key)
        if isinstance(nested, dict):
            found = _profile_pic_from_raw(nested)
            if found:
                return found
    return None


def _attach_owner_avatar(rows: list[dict], avatar: Optional[str]) -> None:
    if avatar:
        for row in rows:
            row["_owner_avatar_url"] = avatar


def _explode_tiktok_profile(raw: dict, parsed: ParsedInput) -> list[dict]:
    """A TikTok profile-dataset record is a profile envelope containing
    `top_videos[]` (engagement metrics + cover image) and `top_posts_data[]`
    (post URL, hashtags, caption). Merge them by video_id/post_id into a
    list of normalized analytics_posts rows. Falls back to a single
    pseudo-post if no posts are surfaced (lets the caller still flag the
    scrape as completed-but-empty)."""
    videos = raw.get("top_videos") or []
    posts_meta = raw.get("top_posts_data") or []
    posts_by_id: dict[str, dict] = {}
    for p in posts_meta:
        if isinstance(p, dict):
            pid = str(p.get("post_id") or p.get("id") or "")
            if pid:
                posts_by_id[pid] = p

    profile_followers = _coerce_int(raw.get("followers"))
    username = (
        raw.get("account_id") or raw.get("nickname") or parsed.username or ""
    )
    if isinstance(username, str):
        username = username.lstrip("@").lower()

    out: list[dict] = []
    for v in videos:
        if not isinstance(v, dict):
            continue
        vid = str(v.get("video_id") or v.get("id") or "")
        meta = posts_by_id.get(vid, {})
        post_url = (
            meta.get("post_url")
            or v.get("video_url")
            or (f"https://www.tiktok.com/@{username}/video/{vid}" if username and vid else "")
        )
        if not post_url:
            continue
        out.append({
            "source": "external",
            "platform": "tiktok",
            "username": username,
            "post_url": post_url,
            "external_post_id": vid,
            "caption": meta.get("description"),
            "hashtags": meta.get("hashtags") or [],
            "media_type": "video",
            # The TikTok profile dataset doesn't expose a direct CDN video
            # file URL — only the canonical /video/{id} page URL. Leaving
            # media_urls empty so the lazy video-prep pipeline triggers a
            # per-post scrape (with the post dataset) to fetch the real
            # video bytes when the user opens the modal.
            "media_urls": [],
            "thumbnail_url": v.get("cover_image") or v.get("cover_url"),
            "duration_seconds": None,
            "posted_at": v.get("create_date") or meta.get("create_time"),
            "views": _coerce_int(
                v.get("playcount") or v.get("play_count")
                or v.get("view_count") or v.get("views")
                or v.get("video_view_count")
            ),
            "likes": _coerce_int(v.get("diggcount") or meta.get("likes")),
            "comments": _coerce_int(v.get("commentcount")),
            "shares": _coerce_int(v.get("share_count")),
            "saves": _coerce_int(v.get("favorites_count")),
            "_owner_followers": profile_followers,
            "raw_payload": v,
        })
    _attach_owner_avatar(out, _profile_pic_from_raw(raw))
    return out


def _explode_instagram_profile(raw: dict, parsed: ParsedInput) -> list[dict]:
    """IG profile dataset returns a profile envelope with a nested posts /
    reels array. Mirrors the TikTok exploder for the common keys we know
    BrightData uses."""
    profile_followers = _coerce_int(
        raw.get("followers") or raw.get("followers_count") or raw.get("edge_followed_by")
    )
    username = (
        raw.get("user_name") or raw.get("username")
        or raw.get("account") or parsed.username or ""
    )
    if isinstance(username, str):
        username = username.lstrip("@").lower()

    candidates: list[dict] = []
    for key in ("posts", "recent_posts", "top_posts", "top_posts_data",
                "reels", "videos", "media", "items"):
        items = raw.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict):
                    candidates.append(item)
            if candidates:
                break

    out: list[dict] = []
    for item in candidates:
        post_url = (
            item.get("post_url") or item.get("url")
            or item.get("permalink") or item.get("link")
        )
        shortcode = item.get("shortcode") or item.get("code") or item.get("post_id")
        if not post_url and shortcode:
            post_url = f"https://www.instagram.com/p/{shortcode}/"
        if not post_url:
            continue
        thumb = (
            item.get("display_url") or item.get("thumbnail_url")
            or item.get("image_url") or item.get("cover_image")
            or item.get("display_uri")
        )
        out.append({
            "source": "external",
            "platform": "instagram",
            "username": username,
            "post_url": post_url,
            "external_post_id": str(shortcode or item.get("id") or ""),
            "caption": item.get("description") or item.get("caption"),
            "hashtags": item.get("hashtags") or [],
            "media_type": "video" if item.get("is_video") or item.get("video_url") else None,
            "media_urls": [],
            "thumbnail_url": thumb,
            "duration_seconds": _coerce_float(
                item.get("video_duration") or item.get("duration")
            ),
            "posted_at": item.get("date_posted") or item.get("posted_at")
                         or item.get("taken_at") or item.get("create_time"),
            # IG profile-dataset post sub-shapes use one of several keys for
            # plays — `video_play_count` is the canonical web shape,
            # `video_view_count` is the IG-private mirror, `play_count` /
            # `view_count` show up on Reels listings. Walk each in turn so
            # we capture views whenever BrightData surfaces them.
            "views": _coerce_int(
                item.get("video_play_count") or item.get("video_view_count")
                or item.get("plays") or item.get("play_count")
                or item.get("view_count") or item.get("views")
            ),
            "likes": _coerce_int(item.get("likes") or item.get("like_count")),
            "comments": _coerce_int(item.get("num_comments") or item.get("comment_count")),
            "shares": None,
            "saves": None,
            "_owner_followers": profile_followers,
            "raw_payload": item,
        })
    _attach_owner_avatar(out, _profile_pic_from_raw(raw))
    return out


def _looks_like_profile_envelope(raw: dict) -> bool:
    """A profile envelope contains aggregate account fields (followers etc.)
    plus an array of nested posts — but does NOT itself describe a single
    piece of content. Used to decide whether to explode the record."""
    if not isinstance(raw, dict):
        return False
    has_profile_fields = any(k in raw for k in (
        "followers", "followers_count", "edge_followed_by",
        "biography", "is_verified", "profile_pic_url",
    ))
    has_posts_array = any(
        isinstance(raw.get(k), list) and raw.get(k)
        for k in (
            "top_videos", "top_posts_data", "posts",
            "recent_posts", "reels", "videos",
        )
    )
    # Bare profile rows (no nested posts) — still treat as profile so we
    # don't persist them as a fake post. Caller can then surface the
    # account followers/avatar even when zero posts come back.
    return has_profile_fields and (has_posts_array or "url" in raw or "account_id" in raw or "username" in raw)


def _normalize_record(raw: dict, parsed: ParsedInput) -> Optional[dict]:
    if parsed.platform == "tiktok":
        return _normalize_tiktok(raw, parsed)
    if parsed.platform == "instagram":
        return _normalize_instagram(raw, parsed)
    # Best-effort generic fallback for YouTube / Facebook so the cards still
    # render — partners can refine these mappings later without changing the
    # router contract.
    url = raw.get("url") or raw.get("post_url") or raw.get("video_url") or parsed.normalized_url or ""
    if not parsed.platform or not url:
        return None
    return {
        "source": "external",
        "platform": parsed.platform,
        "username": (raw.get("username") or raw.get("channel_name") or parsed.username or "").lower(),
        "post_url": url,
        "external_post_id": str(raw.get("id") or raw.get("video_id") or parsed.post_id or ""),
        "caption": raw.get("title") or raw.get("description") or raw.get("caption"),
        "hashtags": raw.get("hashtags") or [],
        "media_type": "video",
        "media_urls": [{"url": raw.get("video_url"), "type": "video"}] if raw.get("video_url") else [],
        "thumbnail_url": raw.get("thumbnail") or raw.get("display_url"),
        "duration_seconds": _coerce_float(raw.get("duration")),
        "posted_at": raw.get("published_at") or raw.get("created_time"),
        "views": _coerce_int(raw.get("views") or raw.get("view_count")),
        "likes": _coerce_int(raw.get("likes") or raw.get("like_count")),
        "comments": _coerce_int(raw.get("comments") or raw.get("comment_count")),
        "shares": _coerce_int(raw.get("shares") or raw.get("share_count")),
        "saves": _coerce_int(raw.get("saves")),
        # Same side-channel pattern as the platform-specific normalisers —
        # YouTube's channel-page record exposes `avatar`, FB's profile
        # record `picture`. `_profile_pic_from_raw` handles both.
        "_owner_avatar_url": _profile_pic_from_raw(raw),
        "raw_payload": raw,
    }


# ── Storage mirror (BrightData CDN → Supabase Storage) ─────────────────────

def _first_media_video_url(post: dict) -> Optional[str]:
    media = post.get("media_urls") or []
    if not isinstance(media, list):
        return None
    for entry in media:
        if isinstance(entry, dict) and (entry.get("type") in ("video", None)):
            url = entry.get("url")
            if isinstance(url, str) and url:
                return url
        elif isinstance(entry, str) and entry:
            return entry
    return None


def _ffmpeg_binary() -> Optional[str]:
    """Locate ffmpeg — system PATH first (Homebrew / apt install), then the
    imageio-ffmpeg bundled binary that the creative-os service already pulls
    in via requirements.txt. Returns None if neither is available so callers
    can degrade gracefully (no thumbnail, but mirror still succeeds)."""
    binary = shutil.which("ffmpeg")
    if binary:
        return binary
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def _extract_poster_frame(video_path: Path) -> Optional[Path]:
    """Run ffmpeg to extract a single JPEG poster frame at ~1s into the video.

    Why 1s instead of 0s: many social videos open on a black/blank frame for
    the first ~200ms (platform watermark fade-in), which produces a useless
    thumbnail. 1s lands on actual content for virtually every Reel / TikTok.
    Falls back to the very first frame if the video is shorter than 1s.
    """
    binary = _ffmpeg_binary()
    if not binary:
        return None
    import tempfile
    fd, raw_path = tempfile.mkstemp(prefix="analytics_poster_", suffix=".jpg")
    os.close(fd)
    out_path = Path(raw_path)
    try:
        # -ss 1 (seek to 1s), -vframes 1 (one frame), -q:v 4 (~80% quality).
        # -loglevel error so we don't pollute logs with ffmpeg's progress
        # output on every single mirror.
        proc = subprocess.run(
            [
                binary, "-y",
                "-ss", "1",
                "-i", str(video_path),
                "-vframes", "1",
                "-q:v", "4",
                "-loglevel", "error",
                str(out_path),
            ],
            timeout=20,
            capture_output=True,
        )
        if proc.returncode != 0 or out_path.stat().st_size == 0:
            # Retry from frame 0 — video might be shorter than 1s.
            proc = subprocess.run(
                [
                    binary, "-y",
                    "-i", str(video_path),
                    "-vframes", "1",
                    "-q:v", "4",
                    "-loglevel", "error",
                    str(out_path),
                ],
                timeout=20,
                capture_output=True,
            )
        if proc.returncode != 0 or not out_path.exists() or out_path.stat().st_size == 0:
            try:
                out_path.unlink(missing_ok=True)
            except Exception:
                pass
            return None
        return out_path
    except Exception:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _upload_poster_to_storage(
    *, poster_path: Path, user_id: str, post_id: str
) -> Optional[str]:
    """Upload an already-extracted poster JPEG to the analytics-media bucket.
    Returns the public URL or None on any failure. Idempotent (upsert=true)."""
    try:
        from ugc_db.db_manager import get_supabase
    except Exception:
        return None
    try:
        sb = get_supabase()
        storage_key = f"{user_id}/{post_id}_poster.jpg"
        with open(poster_path, "rb") as f:
            sb.storage.from_(_STORAGE_BUCKET).upload(
                storage_key, f,
                file_options={"content-type": "image/jpeg", "upsert": "true"},
            )
        return sb.storage.from_(_STORAGE_BUCKET).get_public_url(storage_key)
    except Exception:
        return None


def _mirror_thumbnail_to_storage(*, image_url: str, user_id: str, post_id: str) -> Optional[str]:
    """Download a remote image (typically BrightData's IG / TikTok CDN
    `thumbnail_url`) and re-upload to the analytics-media bucket so the
    browser can render it without CORS / signed-URL expiry issues.

    Used by `_mirror_posts_in_background` for posts where we can't extract
    a poster frame ourselves (image posts, carousels, or videos whose
    `video_url` wasn't surfaced from BrightData). Returns the new public
    Supabase URL or None on failure.
    """
    try:
        from ugc_db.db_manager import get_supabase
    except Exception:
        return None
    tmp_path: Optional[Path] = None
    try:
        import tempfile
        # Preserve the extension when we recognise it — keeps Storage's
        # served `Content-Type` correct without us having to sniff bytes.
        ext = ".jpg"
        for candidate in (".jpg", ".jpeg", ".png", ".webp"):
            if candidate in image_url.lower():
                ext = candidate
                break
        fd, raw_path = tempfile.mkstemp(prefix="analytics_thumb_", suffix=ext)
        os.close(fd)
        tmp_path = Path(raw_path)
        bytes_written = 0
        with httpx.stream("GET", image_url, follow_redirects=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    # 10 MB cap — IG/TikTok poster JPEGs are typically <300 KB
                    # so anything larger is almost certainly a wrong content
                    # type and not worth uploading.
                    if bytes_written > 10 * 1024 * 1024:
                        return None
                    f.write(chunk)
        if bytes_written == 0:
            return None
        # Reuse the poster uploader — it already targets the right bucket
        # and path convention; the file just happens to come from the CDN
        # instead of ffmpeg this time.
        return _upload_poster_to_storage(
            poster_path=tmp_path, user_id=user_id, post_id=post_id,
        )
    except Exception:
        return None
    finally:
        if tmp_path is not None:
            try: tmp_path.unlink(missing_ok=True)
            except Exception: pass


def _is_supabase_storage_url(url: Optional[str]) -> bool:
    """True when the URL already points to our analytics bucket — used to
    skip re-mirroring rows that we've previously processed."""
    if not url:
        return False
    return _STORAGE_BUCKET in url and "supabase" in url


_VIDEO_URL_RE = re.compile(r"\.(mp4|webm|mov|avi|mkv|m4v)(\?.*)?$", re.I)


def _looks_like_video_url(url: Optional[str]) -> bool:
    """True when the URL points at video bytes, not a poster JPEG/PNG."""
    if not url:
        return False
    return bool(_VIDEO_URL_RE.search(url))


def _stable_image_thumbnail(url: Optional[str]) -> bool:
    """True when `url` is a Supabase-hosted image we can render in <img>."""
    return bool(
        url
        and _is_supabase_storage_url(url)
        and not _looks_like_video_url(url)
    )


def _download_video_to_temp(video_url: str) -> Optional[Path]:
    """Stream a remote video to a temp file. Returns the path or None."""
    ext = ".mp4"
    for candidate in (".mp4", ".mov", ".webm", ".m4v"):
        if candidate in video_url.lower():
            ext = candidate
            break
    import tempfile
    fd, raw_path = tempfile.mkstemp(prefix="analytics_mirror_", suffix=ext)
    os.close(fd)
    tmp_path = Path(raw_path)
    bytes_written = 0
    try:
        with httpx.stream("GET", video_url, follow_redirects=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=128 * 1024):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > _MIRROR_MAX_BYTES:
                        return None
                    f.write(chunk)
        if bytes_written == 0:
            return None
        return tmp_path
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None


def _extract_and_store_poster_from_video_url(
    *, video_url: str, user_id: str, post_id: str,
) -> Optional[str]:
    """Download a video, extract one JPEG frame, upload to Storage.

    Used when we already have a playable video URL (typically our own
    ``storage_video_url``) but the card still needs a stable poster.
    """
    tmp_path: Optional[Path] = None
    poster_path: Optional[Path] = None
    try:
        tmp_path = _download_video_to_temp(video_url)
        if tmp_path is None:
            return None
        poster_path = _extract_poster_frame(tmp_path)
        if poster_path is None:
            return None
        return _upload_poster_to_storage(
            poster_path=poster_path, user_id=user_id, post_id=post_id,
        )
    finally:
        if poster_path is not None:
            try:
                poster_path.unlink(missing_ok=True)
            except Exception:
                pass
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


def ensure_post_thumbnails_sync(
    posts: list[dict],
    *,
    user_id: str,
) -> list[dict]:
    """Synchronously ensure each post has a Supabase-hosted poster image.

    Called before returning account-detail post lists so cards never render
    the gray placeholder while a background mirror thread is still running.
    Updates the DB and returns post dicts with patched ``thumbnail_url``.
    """
    if not posts or not user_id:
        return posts

    updated: list[dict] = []
    for post in posts:
        post_id = str(post.get("id") or "")
        if not post_id:
            updated.append(post)
            continue

        thumb = post.get("thumbnail_url")
        if _stable_image_thumbnail(thumb):
            updated.append(post)
            continue

        new_thumb: Optional[str] = None
        storage_video = post.get("storage_video_url")
        media_video = _first_media_video_url(post)

        # Prefer poster extraction from an already-mirrored Studio video.
        if storage_video:
            new_thumb = _extract_and_store_poster_from_video_url(
                video_url=storage_video, user_id=user_id, post_id=post_id,
            )
        elif media_video and not post.get("storage_video_url"):
            mirrored = _mirror_video_to_storage(
                video_url=media_video, user_id=user_id, post_id=post_id,
            )
            if mirrored:
                if mirrored.get("video_url"):
                    try:
                        analytics_db.set_post_storage_video_url(
                            post_id, mirrored["video_url"],
                        )
                        post = {**post, "storage_video_url": mirrored["video_url"]}
                    except Exception:
                        pass
                new_thumb = mirrored.get("thumbnail_url")
        elif thumb and _looks_like_video_url(thumb):
            new_thumb = _extract_and_store_poster_from_video_url(
                video_url=thumb, user_id=user_id, post_id=post_id,
            )
        elif thumb and not _is_supabase_storage_url(thumb):
            new_thumb = _mirror_thumbnail_to_storage(
                image_url=thumb, user_id=user_id, post_id=post_id,
            )

        if new_thumb:
            try:
                analytics_db.set_post_thumbnail_url(post_id, new_thumb)
            except Exception:
                pass
            post = {**post, "thumbnail_url": new_thumb}

        updated.append(post)
    return updated


def mirror_avatar_to_storage(
    *, image_url: str, user_id: str, slug: str,
) -> Optional[str]:
    """Download a remote profile photo (IG/TikTok CDN) into analytics-media.

    Browsers often block hot-linked IG avatars (referrer / expiry) even when
    server-side HEAD checks succeed — mirroring gives AccountCard a stable URL.
    """
    if not image_url or _is_supabase_storage_url(image_url):
        return image_url or None
    try:
        from ugc_db.db_manager import get_supabase
    except Exception:
        return None
    tmp_path: Optional[Path] = None
    try:
        import tempfile
        import re
        safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", slug.strip())[:120] or "avatar"
        ext = ".jpg"
        for candidate in (".jpg", ".jpeg", ".png", ".webp"):
            if candidate in image_url.lower():
                ext = candidate
                break
        fd, raw_path = tempfile.mkstemp(prefix="analytics_avatar_", suffix=ext)
        os.close(fd)
        tmp_path = Path(raw_path)
        bytes_written = 0
        with httpx.stream("GET", image_url, follow_redirects=True, timeout=30) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=64 * 1024):
                    if not chunk:
                        continue
                    bytes_written += len(chunk)
                    if bytes_written > 5 * 1024 * 1024:
                        return None
                    f.write(chunk)
        if bytes_written == 0:
            return None
        sb = get_supabase()
        storage_key = f"{user_id}/avatars/{safe}{ext}"
        sb.storage.from_(_STORAGE_BUCKET).upload(
            storage_key,
            tmp_path.read_bytes(),
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        return sb.storage.from_(_STORAGE_BUCKET).get_public_url(storage_key)
    except Exception:
        return None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass


def _mirror_video_to_storage(*, video_url: str, user_id: str, post_id: str) -> Optional[dict]:
    """Download a BrightData/CDN video URL and re-upload to Supabase Storage,
    plus extract a poster frame for use as a stable thumbnail.

    Returns a dict ``{"video_url": str, "thumbnail_url": Optional[str]}`` on
    success, or None on any failure. The thumbnail is best-effort: a missing
    poster doesn't break the mirror (caller still gets the video_url back).

    Intentionally best-effort overall — a failure here just means the user
    falls back to the platform's official embed iframe for playback (and
    AI breakdown won't be available for that post until the next re-scrape).
    """
    try:
        from ugc_db.db_manager import get_supabase
    except Exception:
        return None

    tmp_path: Optional[Path] = None
    poster_path: Optional[Path] = None
    try:
        tmp_path = _download_video_to_temp(video_url)
        if tmp_path is None:
            return None

        ext = tmp_path.suffix or ".mp4"
        sb = get_supabase()
        storage_key = f"{user_id}/{post_id}{ext}"
        try:
            with open(tmp_path, "rb") as f:
                sb.storage.from_(_STORAGE_BUCKET).upload(
                    storage_key, f,
                    file_options={"content-type": f"video/{ext.lstrip('.')}", "upsert": "true"},
                )
        except Exception:
            # Bucket may not exist yet — try to create it (idempotent) then retry once.
            try:
                sb.storage.create_bucket(_STORAGE_BUCKET, options={"public": True})
            except Exception:
                pass
            try:
                with open(tmp_path, "rb") as f:
                    sb.storage.from_(_STORAGE_BUCKET).upload(
                        storage_key, f,
                        file_options={"content-type": f"video/{ext.lstrip('.')}", "upsert": "true"},
                    )
            except Exception:
                return None

        public_url = sb.storage.from_(_STORAGE_BUCKET).get_public_url(storage_key)

        # Best-effort poster frame extraction. Local file is still on disk
        # so we re-read it via ffmpeg. Failure is fine — we just won't have
        # a server-mirrored thumbnail and will fall back to the placeholder.
        thumbnail_url: Optional[str] = None
        poster_path = _extract_poster_frame(tmp_path)
        if poster_path is not None:
            thumbnail_url = _upload_poster_to_storage(
                poster_path=poster_path, user_id=user_id, post_id=post_id,
            )

        return {"video_url": public_url, "thumbnail_url": thumbnail_url}
    except Exception:
        return None
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass
        if poster_path is not None:
            try:
                poster_path.unlink(missing_ok=True)
            except Exception:
                pass


def _queue_breakdown_after_mirror(user_id: str, post_id: str) -> None:
    """Auto-analyze once a mirrored video is ready for Gemini."""
    try:
        from . import studio_service
        post = analytics_db.get_post(user_id, post_id)
        if post:
            studio_service.queue_breakdown_for_post(user_id, post)
    except Exception:
        pass


def _mirror_posts_in_background(saved_posts: list[dict]) -> None:
    """Spawn a daemon thread that mirrors each saved post's video AND/OR
    thumbnail to Supabase Storage so the frontend has stable, CORS-safe
    URLs to render. The frontend polls the post list / detail endpoints,
    so the new URL surfaces on the next refresh.

    Two paths exist:
      * Video posts with a `video_url` from BrightData → full video mirror
        (also extracts a poster frame via ffmpeg → stable thumbnail).
      * Image/carousel posts OR videos whose `video_url` wasn't surfaced →
        thumbnail-only mirror so the card image still loads.

    Posts that already have a Storage-hosted thumbnail are skipped to keep
    background runs idempotent across re-scrapes.
    """
    video_candidates: list[tuple[str, str]] = []
    thumb_candidates: list[tuple[str, str]] = []
    poster_candidates: list[tuple[str, str]] = []
    for post in saved_posts:
        post_id = post.get("id")
        if not post_id:
            continue
        video_url = _first_media_video_url(post)
        if video_url and not post.get("storage_video_url"):
            video_candidates.append((str(post_id), video_url))
            continue
        storage_video = post.get("storage_video_url")
        thumb_url = post.get("thumbnail_url")
        if storage_video and not _stable_image_thumbnail(thumb_url):
            poster_candidates.append((str(post_id), storage_video))
            continue
        # Thumbnail-only fallback path. We re-mirror unless the row already
        # points at our Supabase bucket — IG/TikTok CDN URLs are short-lived
        # and often CORS-blocked, so the cheapest reliable fix is to copy
        # them into our own bucket once per post.
        if thumb_url and not _stable_image_thumbnail(thumb_url):
            if _looks_like_video_url(thumb_url):
                poster_candidates.append((str(post_id), thumb_url))
            else:
                thumb_candidates.append((str(post_id), thumb_url))

    if not video_candidates and not thumb_candidates and not poster_candidates:
        return

    user_id = saved_posts[0].get("user_id")
    if not user_id:
        return

    def _runner() -> None:
        for post_id, video_url in video_candidates:
            _set_prep_state(post_id, "downloading", progress_pct=55)
            mirrored = _mirror_video_to_storage(
                video_url=video_url, user_id=user_id, post_id=post_id
            )
            if mirrored and mirrored.get("video_url"):
                try:
                    analytics_db.set_post_storage_video_url(post_id, mirrored["video_url"])
                    if mirrored.get("thumbnail_url"):
                        analytics_db.set_post_thumbnail_url(
                            post_id, mirrored["thumbnail_url"],
                        )
                    _set_prep_state(post_id, "ready", progress_pct=100)
                    _queue_breakdown_after_mirror(user_id, post_id)
                except Exception:
                    _set_prep_state(post_id, "failed",
                                    error_message="Storage update failed.")
            else:
                _set_prep_state(post_id, "failed",
                                error_message="Could not mirror the video to storage.")

        for post_id, image_url in thumb_candidates:
            # Lightweight path — no prep state to update because these posts
            # never enter the video preparation pipeline. We're only swapping
            # the thumbnail URL for a CORS-safe copy.
            stable = _mirror_thumbnail_to_storage(
                image_url=image_url, user_id=user_id, post_id=post_id,
            )
            if stable:
                try:
                    analytics_db.set_post_thumbnail_url(post_id, stable)
                except Exception:
                    pass  # best-effort; next scrape retries

        for post_id, video_url in poster_candidates:
            stable = _extract_and_store_poster_from_video_url(
                video_url=video_url, user_id=user_id, post_id=post_id,
            )
            if stable:
                try:
                    analytics_db.set_post_thumbnail_url(post_id, stable)
                except Exception:
                    pass

    thread_seed = (video_candidates or thumb_candidates or poster_candidates)[0][0][:8]
    threading.Thread(
        target=_runner, daemon=True, name=f"analytics-mirror-{thread_seed}"
    ).start()


# ── Lazy video-prep pipeline (on-demand mirror for the post detail modal) ──
#
# The post-list scrape only has *thumbnails* for many accounts (BrightData's
# IG / TikTok profile datasets don't include video URLs), so the modal needs a
# way to escalate from "thumbnail-only" → "fully-mirrored" right when the user
# opens it. This pipeline:
#
#   1. Checks the DB for `storage_video_url`. If present → ready, done.
#   2. Checks the DB for a video URL in `media_urls`. If present → mirror it.
#   3. Otherwise triggers a single-post BrightData scrape on `post_url` to
#      *enrich* the row with a video URL, then mirrors that.
#
# Progress is tracked in process memory so the modal can show a real progress
# bar while polling `POST /posts/{id}/prepare-video`.

_VIDEO_PREP_TASKS: dict[str, dict] = {}
_VIDEO_PREP_LOCK = threading.Lock()

# Status values returned to the frontend. Anything in _IN_PROGRESS_STATES
# means the frontend should keep polling.
_IN_PROGRESS_STATES = {"queued", "scraping", "downloading"}
_PREP_STALE_SEC = float(os.getenv("ANALYTICS_PREP_STALE_SEC", "360"))


def _set_prep_state(
    post_id: str,
    status: str,
    *,
    progress_pct: int = 0,
    error_message: Optional[str] = None,
) -> None:
    with _VIDEO_PREP_LOCK:
        _VIDEO_PREP_TASKS[post_id] = {
            "status": status,
            "progress_pct": progress_pct,
            "error_message": error_message,
            "updated_at": time.time(),
        }


def get_video_prep_status(post_id: str) -> dict:
    """Snapshot of the current prep state, or empty dict if no task tracked."""
    with _VIDEO_PREP_LOCK:
        return dict(_VIDEO_PREP_TASKS.get(post_id, {}))


def start_video_prep(user_id: str, post: dict) -> dict:
    """Kick off (or return the existing) prep job for `post`.

    Re-entrant + idempotent: concurrent callers see the same task. Returns the
    current state snapshot so the HTTP handler can respond immediately while
    the heavy lifting continues in a background thread.
    """
    post_id = str(post.get("id") or "")
    if not post_id:
        return {"status": "failed", "progress_pct": 0,
                "error_message": "Post is missing an id."}

    # Fast path: already mirrored.
    if post.get("storage_video_url"):
        _set_prep_state(post_id, "ready", progress_pct=100)
        return get_video_prep_status(post_id)

    with _VIDEO_PREP_LOCK:
        existing = _VIDEO_PREP_TASKS.get(post_id)
        if existing and existing["status"] in _IN_PROGRESS_STATES:
            updated_at = existing.get("updated_at") or 0
            if time.time() - updated_at < _PREP_STALE_SEC:
                return dict(existing)
            # Stale in-progress task — prior thread likely died; restart.
            _VIDEO_PREP_TASKS.pop(post_id, None)
        # Seed the state synchronously so the very first poll already sees
        # "queued" rather than an empty object.
        _VIDEO_PREP_TASKS[post_id] = {
            "status": "queued",
            "progress_pct": 5,
            "error_message": None,
            "updated_at": time.time(),
        }

    def _runner() -> None:
        try:
            fresh = analytics_db.get_post(user_id, post_id) or post
            if fresh.get("storage_video_url"):
                _set_prep_state(post_id, "ready", progress_pct=100)
                return

            video_url = _first_media_video_url(fresh)

            # If the row was created by an account-scrape it usually only has
            # the thumbnail — escalate to a per-post BrightData scrape so we
            # get the real video URL. Cheap (1 credit) and targeted.
            if not video_url and fresh.get("post_url"):
                _set_prep_state(post_id, "scraping", progress_pct=20)
                try:
                    loop = asyncio.new_event_loop()
                    try:
                        result = loop.run_until_complete(scrape(
                            input_value=fresh["post_url"],
                            user_id=user_id,
                            kind_override="post",
                            platform_override=fresh.get("platform"),
                        ))
                    finally:
                        loop.close()
                except Exception as e:
                    _set_prep_state(post_id, "failed",
                                    error_message=f"Per-post scrape failed: {str(e)[:200]}")
                    return

                if result.status == "failed":
                    _set_prep_state(post_id, "failed",
                                    error_message=result.error_message
                                                  or "Per-post scrape failed.")
                    return
                if result.status == "pending":
                    _set_prep_state(
                        post_id,
                        "failed",
                        error_message=(
                            "Video scrape is still running — close and try again in a minute."
                        ),
                    )
                    return

                if result.posts:
                    # Strip the side-channel `_owner_followers` field — it's
                    # not a column on analytics_posts and would 400 the
                    # upsert.
                    for r in result.posts:
                        r.pop("_owner_followers", None)
                    rows = [{**r, "user_id": user_id} for r in result.posts]
                    saved = analytics_db.upsert_posts(rows)
                    if saved:
                        # Prefer the row we just upserted (matches post_url) so
                        # we don't grab the wrong record on a multi-row scrape.
                        match = next(
                            (s for s in saved if s.get("id") == post_id),
                            saved[0],
                        )
                        video_url = _first_media_video_url(match)
                        # Re-read in case the upsert returned partial data.
                        if not video_url:
                            fresh = analytics_db.get_post(user_id, post_id) or fresh
                            video_url = _first_media_video_url(fresh)

            if not video_url:
                _set_prep_state(post_id, "failed",
                                error_message="No downloadable video URL could be obtained for this post.")
                return

            _set_prep_state(post_id, "downloading", progress_pct=55)
            mirrored = _mirror_video_to_storage(
                video_url=video_url, user_id=user_id, post_id=post_id,
            )
            if mirrored and mirrored.get("video_url"):
                try:
                    analytics_db.set_post_storage_video_url(post_id, mirrored["video_url"])
                    if mirrored.get("thumbnail_url"):
                        analytics_db.set_post_thumbnail_url(
                            post_id, mirrored["thumbnail_url"],
                        )
                except Exception as e:
                    _set_prep_state(post_id, "failed",
                                    error_message=f"Storage update failed: {str(e)[:200]}")
                    return
                _set_prep_state(post_id, "ready", progress_pct=100)
            else:
                _set_prep_state(post_id, "failed",
                                error_message="Video download or upload to storage failed.")
        except Exception as e:
            _set_prep_state(post_id, "failed", error_message=str(e)[:200])

    threading.Thread(
        target=_runner, daemon=True, name=f"prep-{post_id[:8]}",
    ).start()
    return get_video_prep_status(post_id)


# ── Mock fixtures ───────────────────────────────────────────────────────────

def _load_fixture(platform: str) -> list[dict]:
    fname = f"{platform}_post.sample.json"
    path = _FIXTURES_DIR / fname
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except Exception:
        return []


# ── BrightData calls ────────────────────────────────────────────────────────

async def _trigger_brightdata(
    dataset_id: str,
    rows: list[dict],
    *,
    client: httpx.AsyncClient,
) -> str:
    """Trigger a Dataset run and return the snapshot id.

    Surfaces BrightData's `validation_error` body in the exception message so
    schema mismatches (e.g. "This input should not contain a username field")
    are visible to the caller / scrape_job row instead of hiding behind a
    generic ``400 Bad Request``.
    """
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    params = {"dataset_id": dataset_id, "format": "json", "include_errors": "true"}
    resp = await client.post(
        BRIGHTDATA_BASE + BRIGHTDATA_TRIGGER_PATH,
        headers=headers,
        params=params,
        json=rows,
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(
            f"BrightData trigger failed: HTTP {resp.status_code} — {resp.text[:500]}"
        )
    data = resp.json()
    snapshot_id = data.get("snapshot_id") or data.get("collection_id") or data.get("id")
    if not snapshot_id:
        raise RuntimeError(f"BrightData trigger returned no snapshot id: {data}")
    return snapshot_id


async def _poll_snapshot(snapshot_id: str, *, client: httpx.AsyncClient) -> Optional[list[dict]]:
    """Poll a snapshot until status=ready or timeout. Returns the records or
    None if the snapshot is still running after _MAX_WAIT_SEC.
    """
    headers = {"Authorization": f"Bearer {_api_key()}"}
    deadline = time.monotonic() + _MAX_WAIT_SEC
    interval = _POLL_INTERVAL_SEC
    while time.monotonic() < deadline:
        resp = await client.get(
            BRIGHTDATA_BASE + BRIGHTDATA_SNAPSHOT_PATH.format(snapshot_id=snapshot_id),
            headers=headers,
            params={"format": "json"},
            timeout=30,
        )
        if resp.status_code == 202:
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, 15)
            continue
        if resp.status_code != 200:
            raise RuntimeError(
                f"BrightData snapshot fetch failed: {resp.status_code} {resp.text[:200]}"
            )
        body = resp.json()
        # Datasets v3 returns either the records directly (200) or a status
        # envelope `{ status: 'running' | 'ready', ... }`.
        if isinstance(body, list):
            return body
        status = (body.get("status") or "").lower()
        if status in ("ready", "completed", "done"):
            return body.get("data") or body.get("records") or []
        if status in ("failed", "error"):
            raise RuntimeError(f"BrightData snapshot failed: {body}")
        await asyncio.sleep(interval)
        interval = min(interval * 1.5, 15)
    return None


# ── Public entry point ─────────────────────────────────────────────────────

async def scrape(
    *,
    input_value: str,
    user_id: str,
    job_id: Optional[str] = None,
    kind_override: Optional[str] = None,
    platform_override: Optional[str] = None,
    top_n: Optional[int] = None,
) -> ScrapeResult:
    """Drive a single BrightData scrape end-to-end.

    `top_n` (v2): when scraping a profile, only return the top-N posts by
    total engagement after normalisation. Saves DB space on accounts with
    hundreds of posts since the dashboard never surfaces the long tail.
    """
    parsed = detect(input_value)
    if platform_override and not parsed.platform:
        parsed.platform = platform_override  # type: ignore[assignment]
    if kind_override:
        parsed.kind = kind_override  # type: ignore[assignment]

    if not parsed.platform:
        return ScrapeResult(
            posts=[],
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status="failed",
            error_message="Could not detect platform — pass platform explicitly when using a bare @handle.",
        )

    # ── Mock path ──────────────────────────────────────────────────────────
    if _mock_enabled():
        raw_records = _load_fixture(parsed.platform)
        normalized = [r for r in (_normalize_record(r, parsed) for r in raw_records) if r]
        return ScrapeResult(
            posts=normalized,
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status="completed",
        )

    dataset_id = _dataset_id(parsed.platform, parsed.kind)
    if not dataset_id:
        return ScrapeResult(
            posts=[],
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status="failed",
            error_message=(
                f"No BrightData dataset id configured for {parsed.platform}/{parsed.kind}. "
                f"Set BRIGHTDATA_{parsed.platform.upper()}_{parsed.kind.upper()}_DATASET_ID."
            ),
        )

    # BrightData v3 datasets validate their input schema strictly: every
    # collector defined by BrightData accepts a `url` field and rejects any
    # extra keys (e.g. `username`) with HTTP 400 + `validation_error`. So we
    # always send exactly one field — the URL — and synthesise a profile URL
    # from a bare @handle when needed.
    trigger_url = parsed.normalized_url or _profile_url_for(parsed.platform, parsed.username, parsed.kind)
    if not trigger_url:
        return ScrapeResult(
            posts=[],
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status="failed",
            error_message="Empty trigger payload — no URL could be derived from input.",
        )
    trigger_row = {"url": trigger_url}

    try:
        async with httpx.AsyncClient() as client:
            snapshot_id = await _trigger_brightdata(dataset_id, [trigger_row], client=client)
            if job_id:
                analytics_db.update_scrape_job(job_id, {"status": "running", "snapshot_id": snapshot_id})
            records = await _poll_snapshot(snapshot_id, client=client)
    except Exception as e:
        return ScrapeResult(
            posts=[],
            brightdata_calls=1,
            estimated_cost_usd=0.0,
            status="failed",
            error_message=str(e)[:500],
        )

    if records is None:
        # Timed out — return pending so the FE can keep polling. The router
        # leaves analytics_scrape_jobs.status='running' for follow-up.
        return ScrapeResult(
            posts=[],
            brightdata_calls=1,
            estimated_cost_usd=0.0,
            snapshot_id=snapshot_id,
            status="pending",
        )

    return _records_to_scrape_result(
        records,
        parsed,
        snapshot_id=snapshot_id,
        top_n=top_n,
    )


def _records_to_scrape_result(
    records: list,
    parsed: ParsedInput,
    *,
    snapshot_id: Optional[str],
    top_n: Optional[int] = None,
) -> ScrapeResult:
    """Normalize BrightData snapshot records into a completed ScrapeResult."""
    error_msgs = [m for m in (_is_error_envelope(r) for r in records) if m]
    if error_msgs and len(error_msgs) == len(records):
        return ScrapeResult(
            posts=[],
            brightdata_calls=1,
            estimated_cost_usd=round(_PER_RECORD_COST_USD * len(records), 4),
            snapshot_id=snapshot_id,
            status="failed",
            error_message=f"BrightData returned: {error_msgs[0][:200]}",
        )

    normalized: list[dict] = []
    for r in records:
        if _is_error_envelope(r):
            continue
        if parsed.kind == "account" and _looks_like_profile_envelope(r):
            if parsed.platform == "tiktok":
                normalized.extend(_explode_tiktok_profile(r, parsed))
                continue
            if parsed.platform == "instagram":
                normalized.extend(_explode_instagram_profile(r, parsed))
                continue
        single = _normalize_record(r, parsed)
        if single:
            normalized.append(single)
    # History preservation: we intentionally keep the FULL normalized set
    # (no top-N truncation) so the dashboard can run accurate long-term
    # trend analysis. The `top_n` arg is retained for signature stability
    # but no longer truncates account scrapes.
    return ScrapeResult(
        posts=normalized,
        brightdata_calls=1,
        estimated_cost_usd=round(_PER_RECORD_COST_USD * len(records), 4),
        snapshot_id=snapshot_id,
        status="completed",
    )


_RESUME_MAX_WAIT_SEC = float(os.getenv("BRIGHTDATA_RESUME_MAX_WAIT", "600"))


async def _poll_snapshot_with_timeout(
    snapshot_id: str,
    *,
    client: httpx.AsyncClient,
    max_wait_sec: float,
) -> Optional[list[dict]]:
    """Poll until ready, failed, or `max_wait_sec` elapses."""
    headers = {"Authorization": f"Bearer {_api_key()}"}
    deadline = time.monotonic() + max_wait_sec
    interval = _POLL_INTERVAL_SEC
    while time.monotonic() < deadline:
        resp = await client.get(
            BRIGHTDATA_BASE + BRIGHTDATA_SNAPSHOT_PATH.format(snapshot_id=snapshot_id),
            headers=headers,
            params={"format": "json"},
            timeout=30,
        )
        if resp.status_code == 202:
            await asyncio.sleep(interval)
            interval = min(interval * 1.5, 15)
            continue
        if resp.status_code != 200:
            raise RuntimeError(
                f"BrightData snapshot fetch failed: {resp.status_code} {resp.text[:200]}"
            )
        body = resp.json()
        if isinstance(body, list):
            return body
        status = (body.get("status") or "").lower()
        if status in ("ready", "completed", "done"):
            return body.get("data") or body.get("records") or []
        if status in ("failed", "error"):
            raise RuntimeError(f"BrightData snapshot failed: {body}")
        await asyncio.sleep(interval)
        interval = min(interval * 1.5, 15)
    return None


async def resume_pending_scrape_job(
    user_id: str,
    job_id: str,
    *,
    top_n: Optional[int] = None,
) -> ScrapeResult:
    """Continue polling a BrightData snapshot that outlived the HTTP timeout."""
    job = analytics_db.get_scrape_job(user_id, job_id)
    if not job:
        return ScrapeResult(
            posts=[],
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status="failed",
            error_message="Scrape job not found.",
        )
    if job.get("status") in ("completed", "failed"):
        return ScrapeResult(
            posts=[],
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status=job["status"],
            error_message=job.get("error_message"),
        )

    snapshot_id = job.get("snapshot_id")
    if not snapshot_id:
        return ScrapeResult(
            posts=[],
            brightdata_calls=0,
            estimated_cost_usd=0.0,
            status="failed",
            error_message="Scrape job has no snapshot id to resume.",
        )

    parsed = detect(job.get("input") or "")
    if job.get("platform") and not parsed.platform:
        parsed.platform = job["platform"]  # type: ignore[assignment]
    if job.get("kind"):
        parsed.kind = job["kind"]  # type: ignore[assignment]

    try:
        async with httpx.AsyncClient() as client:
            records = await _poll_snapshot_with_timeout(
                snapshot_id,
                client=client,
                max_wait_sec=_RESUME_MAX_WAIT_SEC,
            )
    except Exception as e:
        return ScrapeResult(
            posts=[],
            brightdata_calls=1,
            estimated_cost_usd=0.0,
            snapshot_id=snapshot_id,
            status="failed",
            error_message=str(e)[:500],
        )

    if records is None:
        return ScrapeResult(
            posts=[],
            brightdata_calls=1,
            estimated_cost_usd=0.0,
            snapshot_id=snapshot_id,
            status="pending",
            error_message="BrightData snapshot still running.",
        )

    return _records_to_scrape_result(
        records,
        parsed,
        snapshot_id=snapshot_id,
        top_n=top_n,
    )


def persist_scrape_job_result(
    user_id: str,
    job_id: str,
    result: ScrapeResult,
    *,
    kind: str,
    platform: str,
    username: Optional[str] = None,
    top_n: Optional[int] = None,
) -> list[dict]:
    """Upsert posts + finalize the scrape job row. Returns saved post dicts."""
    from datetime import datetime, timezone

    def _iso_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    saved: list[dict] = []
    follower_count: Optional[int] = None
    avatar_url: Optional[str] = None
    if result.posts:
        for row in result.posts:
            fc = row.pop("_owner_followers", None)
            if fc and fc > 0 and (follower_count is None or fc > follower_count):
                follower_count = fc
            av = row.pop("_owner_avatar_url", None)
            if av and not avatar_url:
                avatar_url = str(av)[:8000]
            row = {**row, "user_id": user_id}
            link = analytics_db.find_social_post_by_url(user_id, row.get("post_url") or "")
            if link:
                row["source"] = "internal"
                row["social_post_id"] = link.get("id")
                row["video_job_id"] = link.get("video_job_id")
            saved.append(row)
        saved = analytics_db.upsert_posts(saved)
        _mirror_posts_in_background(saved)
        # History preservation: the long tail is no longer pruned after an
        # account scrape — the dashboard relies on the full post history for
        # accurate long-term trend analysis.

    analytics_db.update_scrape_job(
        job_id,
        {
            "status": result.status,
            "posts_found": len(saved),
            "brightdata_calls": result.brightdata_calls,
            "estimated_cost_usd": result.estimated_cost_usd,
            "error_message": result.error_message,
            "completed_at": _iso_now() if result.status in ("completed", "failed") else None,
        },
    )

    if kind == "account" and platform and username and result.status == "completed":
        account_extras: dict = {
            "last_scraped_at": _iso_now(),
            "total_posts": len(saved) or None,
        }
        if follower_count is not None:
            account_extras["follower_count"] = follower_count
            account_extras["followers"] = follower_count
        if avatar_url:
            account_extras["avatar_url"] = avatar_url
        analytics_db.upsert_tracked_account(
            user_id,
            platform=platform,
            username=username,
            extras=account_extras,
        )

    return saved
