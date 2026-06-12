"""URL / handle parser for the Analytics module.

Detects platform, kind (post vs account), and extracts a canonical post URL +
identifier from any input the user pastes into the Analyze search bar.

Examples
--------
>>> detect("https://www.tiktok.com/@nike/video/7395812345678901234")
{'platform': 'tiktok', 'kind': 'post', 'normalized_url': 'https://www.tiktok.com/@nike/video/7395812345678901234',
 'username': 'nike', 'post_id': '7395812345678901234'}

>>> detect("@nike")
{'platform': None, 'kind': 'account', 'normalized_url': None, 'username': 'nike', 'post_id': None}

>>> detect("https://www.instagram.com/reel/CxYz1AbCd23/")
{'platform': 'instagram', 'kind': 'post', 'normalized_url': 'https://www.instagram.com/reel/CxYz1AbCd23/',
 'username': None, 'post_id': 'CxYz1AbCd23'}
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Literal, Optional
from urllib.parse import urlparse, urlunparse

Platform = Literal["tiktok", "instagram", "youtube", "facebook"]
Kind = Literal["post", "account"]


@dataclass
class ParsedInput:
    platform: Optional[Platform]
    kind: Kind
    normalized_url: Optional[str]
    username: Optional[str]
    post_id: Optional[str]

    def as_dict(self) -> dict:
        return asdict(self)


# ── Patterns ────────────────────────────────────────────────────────────────

_TIKTOK_VIDEO_RE = re.compile(
    r"^https?://(?:www\.|m\.)?tiktok\.com/"
    r"(?:@(?P<user>[^/]+)/(?:video|photo)/(?P<id>\d+)"
    r"|t/(?P<short>[A-Za-z0-9]+)|v/(?P<vid>\d+))",
    re.IGNORECASE,
)
_TIKTOK_SHORT_HOST_RE = re.compile(
    r"^https?://(?:vm|vt)\.tiktok\.com/(?P<short>[A-Za-z0-9]+)/?",
    re.IGNORECASE,
)
_TIKTOK_PROFILE_RE = re.compile(
    r"^https?://(?:www\.|m\.)?tiktok\.com/@(?P<user>[^/?#]+)/?$",
    re.IGNORECASE,
)

_INSTAGRAM_POST_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?:p|reel|reels|tv)/(?P<id>[A-Za-z0-9_-]+)/?",
    re.IGNORECASE,
)
_INSTAGRAM_PROFILE_RE = re.compile(
    r"^https?://(?:www\.)?instagram\.com/(?P<user>[A-Za-z0-9_.]+)/?$",
    re.IGNORECASE,
)

_YOUTUBE_WATCH_RE = re.compile(
    r"^https?://(?:www\.|m\.)?youtube\.com/watch\?(?:[^#]*&)?v=(?P<id>[A-Za-z0-9_-]{6,})",
    re.IGNORECASE,
)
_YOUTUBE_SHORT_RE = re.compile(
    r"^https?://(?:www\.|m\.)?youtube\.com/(?:shorts|live|embed)/(?P<id>[A-Za-z0-9_-]{6,})",
    re.IGNORECASE,
)
_YOUTU_BE_RE = re.compile(
    r"^https?://youtu\.be/(?P<id>[A-Za-z0-9_-]{6,})",
    re.IGNORECASE,
)
_YOUTUBE_CHANNEL_RE = re.compile(
    r"^https?://(?:www\.|m\.)?youtube\.com/(?:@(?P<at>[^/?#]+)|c/(?P<c>[^/?#]+)|channel/(?P<ch>[^/?#]+)|user/(?P<u>[^/?#]+))/?$",
    re.IGNORECASE,
)

_FACEBOOK_POST_RE = re.compile(
    r"^https?://(?:www\.|m\.|web\.)?facebook\.com/(?:[^/?#]+/(?:posts|videos|reel)/(?P<id>[A-Za-z0-9_-]+)"
    r"|reel/(?P<reel>\d+)"
    r"|watch/?\?v=(?P<v>\d+)"
    r"|share/(?:v|p|r)/(?P<share>[A-Za-z0-9_-]+))",
    re.IGNORECASE,
)
_FACEBOOK_PROFILE_RE = re.compile(
    r"^https?://(?:www\.|m\.|web\.)?facebook\.com/(?P<user>[A-Za-z0-9_.\-]+)/?$",
    re.IGNORECASE,
)

_PLATFORM_DOMAINS = {
    "tiktok":    ("tiktok.com", "vt.tiktok.com", "vm.tiktok.com"),
    "instagram": ("instagram.com",),
    "youtube":   ("youtube.com", "youtu.be"),
    "facebook":  ("facebook.com", "fb.com", "fb.watch"),
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _strip_url(url: str) -> str:
    """Drop fragments + tracking query parameters; keep the path tidy."""
    parsed = urlparse(url.strip())
    # Drop fragments and trailing slashes; keep query as-is to preserve ?v= etc.
    path = parsed.path.rstrip("/") if parsed.path != "/" else parsed.path
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def _platform_from_domain(url: str) -> Optional[Platform]:
    host = urlparse(url).netloc.lower().lstrip("www.")
    for platform, domains in _PLATFORM_DOMAINS.items():
        for d in domains:
            if host == d or host.endswith("." + d):
                return platform  # type: ignore[return-value]
    return None


# ── Public API ──────────────────────────────────────────────────────────────

def detect(raw: str) -> ParsedInput:
    """Parse a user-supplied URL or @handle.

    Returns a ParsedInput. ``kind`` defaults to ``'post'`` for URLs that point
    at a single piece of content, ``'account'`` for profile URLs or bare handles.
    ``platform`` is None only when a bare handle is given without a platform
    hint — callers must then ask the user to pick a platform.
    """
    if raw is None:
        raise ValueError("Input is empty")
    s = raw.strip()
    if not s:
        raise ValueError("Input is empty")

    # Bare @handle → account, unknown platform
    if s.startswith("@") and "/" not in s and " " not in s:
        return ParsedInput(
            platform=None,
            kind="account",
            normalized_url=None,
            username=s[1:].lower(),
            post_id=None,
        )

    # Plain handle without @ — treat as account if no spaces/slashes
    if not s.lower().startswith(("http://", "https://")) and "/" not in s and " " not in s:
        return ParsedInput(
            platform=None,
            kind="account",
            normalized_url=None,
            username=s.lower(),
            post_id=None,
        )

    if not s.lower().startswith(("http://", "https://")):
        s = "https://" + s

    platform = _platform_from_domain(s)
    normalized = _strip_url(s)

    # ── TikTok ─────────────────────────────────────────────────────────────
    if platform == "tiktok":
        m = _TIKTOK_VIDEO_RE.match(normalized)
        if m:
            pid = m.group("id") or m.group("short") or m.group("vid")
            return ParsedInput(
                platform="tiktok",
                kind="post",
                normalized_url=normalized,
                username=(m.group("user") or "").lower() or None,
                post_id=pid,
            )
        m = _TIKTOK_SHORT_HOST_RE.match(normalized)
        if m:
            return ParsedInput(
                platform="tiktok",
                kind="post",
                normalized_url=normalized,
                username=None,
                post_id=m.group("short"),
            )
        m = _TIKTOK_PROFILE_RE.match(normalized)
        if m:
            return ParsedInput(
                platform="tiktok",
                kind="account",
                normalized_url=normalized,
                username=m.group("user").lower(),
                post_id=None,
            )

    # ── Instagram ──────────────────────────────────────────────────────────
    if platform == "instagram":
        m = _INSTAGRAM_POST_RE.match(normalized)
        if m:
            return ParsedInput(
                platform="instagram",
                kind="post",
                normalized_url=normalized,
                username=None,
                post_id=m.group("id"),
            )
        m = _INSTAGRAM_PROFILE_RE.match(normalized)
        if m:
            return ParsedInput(
                platform="instagram",
                kind="account",
                normalized_url=normalized,
                username=m.group("user").lower(),
                post_id=None,
            )

    # ── YouTube ────────────────────────────────────────────────────────────
    if platform == "youtube":
        for regex in (_YOUTUBE_WATCH_RE, _YOUTUBE_SHORT_RE, _YOUTU_BE_RE):
            m = regex.match(normalized)
            if m:
                return ParsedInput(
                    platform="youtube",
                    kind="post",
                    normalized_url=normalized,
                    username=None,
                    post_id=m.group("id"),
                )
        m = _YOUTUBE_CHANNEL_RE.match(normalized)
        if m:
            user = m.group("at") or m.group("c") or m.group("ch") or m.group("u")
            return ParsedInput(
                platform="youtube",
                kind="account",
                normalized_url=normalized,
                username=user.lower() if user else None,
                post_id=None,
            )

    # ── Facebook ───────────────────────────────────────────────────────────
    if platform == "facebook":
        m = _FACEBOOK_POST_RE.match(normalized)
        if m:
            pid = m.group("id") or m.group("reel") or m.group("v") or m.group("share")
            return ParsedInput(
                platform="facebook",
                kind="post",
                normalized_url=normalized,
                username=None,
                post_id=pid,
            )
        m = _FACEBOOK_PROFILE_RE.match(normalized)
        if m:
            return ParsedInput(
                platform="facebook",
                kind="account",
                normalized_url=normalized,
                username=m.group("user").lower(),
                post_id=None,
            )

    # Fallback — known platform, unknown shape: treat as post URL so the
    # scraper still gets a chance to handle it.
    return ParsedInput(
        platform=platform,
        kind="post" if platform else "account",
        normalized_url=normalized if platform else None,
        username=None,
        post_id=None,
    )
