"""
UGC Engine — Ayrshare API Client

Encapsulates all direct communication with the Ayrshare Social Media API.
All platform-side OAuth, posting, and profile management flows are handled
through this module so the rest of the backend never touches Ayrshare directly.
"""

import os
import re
from typing import Optional

import httpx

AYRSHARE_BASE = "https://app.ayrshare.com/api"

_INSTA_PATH_SKIP = frozenset(
    {
        "p",
        "reel",
        "reels",
        "stories",
        "explore",
        "tv",
        "oauth",
        "accounts",
        "direct",
    }
)


def _collect_url_strings(blob: dict) -> list[str]:
    """Harvest http(s) URL-looking strings embedded anywhere in an Ayrshare
    nested dict — displayNames payloads vary by platform revision."""
    out: list[str] = []
    for v in blob.values():
        if isinstance(v, str) and ("http://" in v or "https://" in v or ".com/" in v.lower()):
            out.append(v)
    return out


def _handle_from_urls(platform: str, urls: list[str]) -> Optional[str]:
    """Best-effort platform login / @handle extraction from profile URLs."""
    for raw in urls:
        lu = raw.strip().lower()
        if platform == "instagram":
            m = re.search(r"instagram\.com/([^/?#]+)", lu)
            if m:
                slug = m.group(1).rstrip("/")
                seg = slug.split("/")[0]
                if seg and seg not in _INSTA_PATH_SKIP:
                    return seg
        elif platform == "tiktok":
            m = re.search(r"tiktok\.com/@?([^/?#]+)", lu)
            if m and m.group(1) not in ("@", ""):
                return m.group(1).lstrip("@")
        elif platform == "youtube":
            m = re.search(r"youtube\.com/@([^/?#]+)", lu)
            if m:
                return m.group(1)
            m = re.search(r"youtube\.com/channel/([^/?#]+)", lu)
            if m:
                # Channel IDs are not handles — caller may still rely on plain fields.
                continue
            m = re.search(r"youtube\.com/user/([^/?#]+)", lu)
            if m:
                return m.group(1)
        elif platform == "facebook":
            m = re.search(r"facebook\.com/([^/?#]+)", lu)
            if m and m.group(1) not in ("profile", "people", "pages", "oauth"):
                return m.group(1).split("?")[0]
    return None


def _coerce_plain_handle(platform: str, raw: Optional[str]) -> Optional[str]:
    """Normalise username-like strings; reject obvious display-name garbage."""
    if not raw or not isinstance(raw, str):
        return None
    s = raw.strip().lstrip("@")
    lu = raw.strip().lower()
    if lu.startswith(("http://", "https://")):
        slug = _handle_from_urls(platform, [lu])
        if slug:
            return slug.lower().rstrip("@")
        return None
    if "/" in s and "." in s:
        slug = _handle_from_urls(platform, [s])
        if slug:
            return slug.lower()
    if "\n" in s or "\t" in s:
        return None
    if " " in s:
        # "Jane Doe" style — not a TikTok/YT slug; IG sometimes mislabels these.
        return None
    if len(s) > 191:
        return None
    if platform == "youtube" and len(s) == 24 and re.fullmatch(r"UC[\w\-]{22}", s):
        return None  # channel id — useless for scraping by @handle
    return s.lower()


def _best_username(platform: str, entry: dict) -> tuple[Optional[str], Optional[str]]:
    """Return `(login_handle?, human_display)` from a displayNames/active row."""
    urls = _collect_url_strings(entry)
    from_url = _handle_from_urls(platform, urls)

    prioritized_keys = (
        "userName",
        "username",
        "screenName",
        "handle",
        "youtubeChannelTitle",
        "youtubeChannelId",
        "fbPageName",
    )
    for key in prioritized_keys:
        h = _coerce_plain_handle(platform, entry.get(key))
        if h:
            return h, entry.get("displayName")

    dn = entry.get("displayName")
    h_dn = _coerce_plain_handle(platform, dn if isinstance(dn, str) else None)
    if h_dn:
        return h_dn, None

    if from_url:
        return from_url.lower(), entry.get("displayName") if isinstance(dn, str) else None

    return None, entry.get("displayName") if isinstance(dn, str) else None


def _api_key() -> str:
    """Read AYRSHARE_API_KEY on every call (rather than at import time) so
    a `.env.saas` edit picks up on the next request without needing a hard
    uvicorn restart. We also strip whitespace defensively because users
    often paste keys with a trailing space which silently corrupts the
    `Bearer` header."""
    return (os.getenv("AYRSHARE_API_KEY") or "").strip()


class InvalidProfileKey(Exception):
    """Raised when Ayrshare rejects our `profileKey` (error code 144).

    Callers may self-heal when the profile no longer exists on Ayrshare
    (e.g. after an AYRSHARE_API_KEY swap). If a profile with the same
    title still exists, the profileKey cannot be retrieved via API — see
    ``ProfileTitleExists`` / ``delete_profile_by_title`` recovery paths."""
    pass


class ProfileTitleExists(Exception):
    """Raised when Ayrshare rejects profile creation because the title is
    already taken (error code 146). Carries the existing profile's refId."""
    def __init__(self, ref_id: str | None, message: str = "Profile title already exists"):
        super().__init__(message)
        self.ref_id = ref_id


def _headers(profile_key: str | None = None) -> dict:
    """Build standard Ayrshare request headers."""
    h = {
        "Authorization": f"Bearer {_api_key()}",
        "Content-Type": "application/json",
    }
    if profile_key:
        h["Profile-Key"] = profile_key
    return h


# ── Profile Management ──────────────────────────────────────────────────────

def _parse_ayrshare_error(resp: httpx.Response) -> dict | None:
    try:
        body = resp.json()
        return body if isinstance(body, dict) else None
    except Exception:
        return None


async def get_profile_by_title(title: str) -> dict | None:
    """Return the Ayrshare profile envelope for ``title``, or None."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AYRSHARE_BASE}/profiles",
            headers=_headers(),
            params={"title": title},
        )
        resp.raise_for_status()
        profiles = (resp.json() or {}).get("profiles") or []
        if profiles and isinstance(profiles[0], dict):
            return profiles[0]
    return None


async def get_profile_by_ref_id(
    ref_id: str,
    *,
    include: str = "socialHealth,linkingErrors",
) -> dict | None:
    """Return profile detail for ``refId`` (no profileKey in response)."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AYRSHARE_BASE}/profiles",
            headers=_headers(),
            params={"refId": ref_id, "include": include},
        )
        if resp.status_code != 200:
            return None
        profiles = (resp.json() or {}).get("profiles") or []
        if profiles and isinstance(profiles[0], dict):
            return profiles[0]
    return None


def _profile_has_linked_socials(profile_block: dict | None) -> bool:
    if not isinstance(profile_block, dict):
        return False
    active = profile_block.get("activeSocialAccounts") or []
    if active:
        return True
    health = profile_block.get("socialHealth")
    if isinstance(health, dict):
        for item in health.values():
            if isinstance(item, dict) and item.get("linked"):
                return True
    return False


async def delete_profile_by_title(title: str) -> dict:
    """Delete an orphaned sub-profile when we no longer have its profileKey."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            "DELETE",
            f"{AYRSHARE_BASE}/profiles",
            headers=_headers(),
            json={"title": title},
        )
        resp.raise_for_status()
        return resp.json()


async def fetch_user_profile(profile_key: str) -> dict:
    """``GET /user`` for a sub-profile — validates the profileKey."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AYRSHARE_BASE}/user",
            headers=_headers(profile_key),
        )
        if resp.status_code in (401, 403):
            body = _parse_ayrshare_error(resp)
            if body and body.get("code") == 144:
                raise InvalidProfileKey(body.get("message") or "Invalid Profile Key")
        resp.raise_for_status()
        data = resp.json()
        return data if isinstance(data, dict) else {}


async def create_profile(user_id: str) -> dict:
    """
    Create a new Ayrshare sub-profile for this user.
    Returns the full Ayrshare response including ``profileKey`` and ``refId``.
    """
    existing = await get_profile_by_title(user_id)
    if existing:
        ref_id = existing.get("refId")
        raise ProfileTitleExists(
            str(ref_id) if ref_id else None,
            f"Profile title already exists: {user_id}",
        )

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AYRSHARE_BASE}/profiles/profile",
            headers=_headers(),
            json={"title": user_id},
        )
        if resp.status_code == 400:
            body = _parse_ayrshare_error(resp)
            if body and body.get("code") == 146:
                lookup = await get_profile_by_title(user_id)
                ref_id = lookup.get("refId") if lookup else None
                raise ProfileTitleExists(
                    str(ref_id) if ref_id else None,
                    body.get("message") or "Profile title already exists",
                )
        resp.raise_for_status()
        return resp.json()


def _load_private_key() -> str:
    """Load the Ayrshare private key from a .key file or env var."""
    key_path = os.getenv("AYRSHARE_PRIVATE_KEY_PATH", "")
    if key_path and os.path.isfile(key_path):
        with open(key_path, "r") as f:
            return f.read().strip()
    # Fallback: inline env var (may have \\n that need replacing)
    raw = os.getenv("AYRSHARE_PRIVATE_KEY", "")
    return raw.replace("\\n", "\n")


def _normalize_sso_url(raw_url: str) -> str:
    """Ensure ``domain=`` is present in the SSO URL Ayrshare returns.

    Ayrshare docs show URLs as ``https://profile.ayrshare.com?domain=ID&jwt=…``.
    The generateJWT response sometimes omits ``domain`` even when it was sent in
    the body — without it OAuth can attach to the wrong User Profile and
    ``GET /user`` keeps returning empty ``activeSocialAccounts``.
    """
    domain = (os.getenv("AYRSHARE_DOMAIN") or "").strip()
    if not raw_url or not domain:
        return raw_url
    from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

    parsed = urlparse(raw_url)
    qs = parse_qs(parsed.query, keep_blank_values=False)
    if not qs.get("domain", [""])[0]:
        qs["domain"] = [domain]
    flat = {k: v[-1] for k, v in qs.items()}
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        urlencode(flat),
        parsed.fragment,
    ))


async def generate_jwt(
    profile_key: str,
    redirect: str | None = None,
    *,
    logout: bool = False,
) -> dict:
    """
    Generate a short-lived JWT URL that opens the Ayrshare social-linking
    popup so the user can connect their social accounts.

    ``redirect`` (optional): absolute URL Ayrshare sends the user back to once
    they finish (or cancel) linking. Without it, after the OAuth round-trip
    the user is left on the social platform's own site (e.g. instagram.com)
    instead of returning to our app, which looks like "it never connected".
    """
    private_key = _load_private_key()
    if not private_key:
        raise ValueError("Ayrshare private key not configured. Set AYRSHARE_PRIVATE_KEY_PATH in .env.saas")
    
    # Domain is the unique app domain assigned by Ayrshare during onboarding
    domain = os.getenv("AYRSHARE_DOMAIN", "")
    
    payload = {
        "profileKey": profile_key,
        "privateKey": private_key,
    }
    if domain:
        payload["domain"] = domain
    # Prefer an explicit per-request redirect (the frontend passes its real
    # origin); fall back to an env override for non-browser callers.
    redirect_url = redirect or os.getenv("AYRSHARE_LINK_REDIRECT_URL", "")
    if redirect_url:
        payload["redirect"] = redirect_url
    # Clear any stale SSO session so OAuth binds to *this* sub-profile, not a
    # previously-logged-in Primary Profile (common when testing locally).
    if logout:
        payload["logout"] = True
    
    print(f"[Ayrshare] generateJWT payload keys: {list(payload.keys())}, domain={domain or '(not set)'}, redirect={redirect_url or '(none)'}, logout={logout}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AYRSHARE_BASE}/profiles/generateJWT",
            headers=_headers(),
            json=payload,
        )
        if resp.status_code != 200:
            print(f"[Ayrshare] generateJWT failed ({resp.status_code}): {resp.text}")
            print(f"[Ayrshare] privateKey length: {len(private_key)}, starts with: {private_key[:30]}")
            # Code 144 == "The Profile Key is invalid". Surface as a typed
            # exception so the route can self-heal by recreating the profile.
            try:
                body = resp.json()
                if isinstance(body, dict) and body.get("code") == 144:
                    raise InvalidProfileKey(body.get("message") or "Invalid Profile Key")
            except InvalidProfileKey:
                raise
            except Exception:
                pass  # fall through to raise_for_status below
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and isinstance(data.get("url"), str):
            data["url"] = _normalize_sso_url(data["url"])
        return data


def _merge_socials_for_profile(data: dict, profile_key: str) -> list[dict]:
    """Build a `[{platform, username?, profilePic?}, ...]` list from an
    Ayrshare payload.

    Supports both endpoint shapes Ayrshare uses today:
      * `/user`  → `{ activeSocialAccounts, displayNames: [...] }` (single profile)
      * `/profiles` → `{ profiles: [ { profileKey, activeSocialAccounts, displayNames, ... } ] }` (all sub-profiles)

    Crucially, when we get the `/profiles` shape we MUST pick the entry
    whose `profileKey` matches our user's — picking `profiles[0]` (as the
    older code did) silently returns the Primary Profile's accounts, which
    is why a freshly-linked IG never showed up in the SaaS UI.
    """
    if not isinstance(data, dict):
        return []

    block: dict = {}
    profiles = data.get("profiles") if isinstance(data.get("profiles"), list) else None
    if profiles:
        match = next(
            (p for p in profiles
             if isinstance(p, dict)
             and (p.get("profileKey") == profile_key or p.get("profile_key") == profile_key)),
            None,
        )
        block = match or profiles[0] or {}
    else:
        # /user shape — payload is already the per-profile block
        block = data

    active = block.get("activeSocialAccounts") or []
    display_names = block.get("displayNames") or []

    # Build a {platform_lower: {username?, profilePic?}} index from displayNames.
    # Prefer scraped-style login handles (`userName`, URL-derived slugs) over
    # `displayName` — IG often ships the person's real name there, which
    # silently breaks Analytics "Studio accounts" classification when we
    # intersect `(platform, username)` with BrightData scraped handles.
    index: dict[str, dict] = {}
    for entry in display_names:
        if not isinstance(entry, dict):
            continue
        plat = (entry.get("platform") or "").strip().lower()
        if not plat:
            continue
        uname, _disp = _best_username(plat, entry)
        pic = (
            entry.get("userImage")
            or entry.get("profileImage")
            or entry.get("profilePic")
            or entry.get("imageUrl")
        )
        row_pack: dict = {}
        if uname:
            row_pack["username"] = uname
        if pic:
            row_pack["profilePic"] = pic
        if row_pack:
            index[plat] = row_pack

    def _finalize_row(platform: str, fragment: Optional[dict] = None) -> dict:
        """Merge fragments from active (`fragment`) + `displayNames` (`index`)."""
        merged = {"platform": platform}
        idx = index.get(platform)
        if idx:
            merged.update(idx)
        if fragment:
            for k, v in fragment.items():
                if k == "platform" or v is None:
                    continue
                merged.setdefault(k, v)

        handle, _ = _best_username(platform, merged)
        if not handle and merged.get("username"):
            handle = _coerce_plain_handle(platform, merged.get("username"))

        out: dict = {"platform": platform}
        if handle:
            out["username"] = handle
        pic = (
            merged.get("profilePic")
            or merged.get("userImage")
            or merged.get("profileImage")
            or merged.get("imageUrl")
        )
        if pic:
            out["profilePic"] = pic
        return out

    out: list[dict] = []
    for item in active:
        if isinstance(item, str):
            plat = item.strip().lower()
            out.append(_finalize_row(plat, None))
        elif isinstance(item, dict):
            plat = (item.get("platform") or "").strip().lower()
            if not plat:
                continue
            out.append(
                _finalize_row(
                    plat,
                    {
                        "username": item.get("username")
                        or item.get("userName")
                        or item.get("displayName"),
                        "profilePic": item.get("userImage")
                        or item.get("profileImage")
                        or item.get("profilePic")
                        or item.get("imageUrl"),
                    },
                )
            )
    return out


def _socials_from_social_health(social_health: Optional[dict]) -> list[dict]:
    """Build a minimal socials list from Ayrshare's per-platform `socialHealth`
    map (returned by `GET /profiles?refId=…&include=socialHealth`).

    Newer Ayrshare revisions sometimes omit `activeSocialAccounts` on `GET /user`
    for a few minutes after OAuth completes, while `socialHealth.{platform}.linked`
    flips to `true` first — reading both keeps the Connections page from
    showing "Not connected" during that propagation window."""
    if not isinstance(social_health, dict):
        return []
    out: list[dict] = []
    for plat, health in social_health.items():
        if not isinstance(health, dict):
            continue
        if not health.get("linked"):
            continue
        platform = str(plat).strip().lower()
        if platform:
            out.append({"platform": platform})
    return out


def _dedupe_socials(rows: list[dict]) -> list[dict]:
    """Merge duplicate platform entries, preferring rows that carry username
    or profilePic over bare `{platform}` stubs from socialHealth."""
    by_plat: dict[str, dict] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        plat = str(row.get("platform") or "").strip().lower()
        if not plat:
            continue
        prev = by_plat.get(plat)
        if prev is None:
            by_plat[plat] = dict(row)
            continue
        merged = dict(prev)
        for key in ("username", "profilePic"):
            if not merged.get(key) and row.get(key):
                merged[key] = row[key]
        by_plat[plat] = merged
    return list(by_plat.values())


async def get_user_socials(profile_key: str, ref_id: str | None = None) -> list:
    """
    Retrieve the list of connected social accounts for a sub-profile.

    Hits `GET /api/user` with the `Profile-Key` header — that's the canonical
    Ayrshare endpoint that returns ONLY the sub-profile we asked about,
    including `activeSocialAccounts` and per-platform `displayNames`.

    We fall back to `GET /api/profiles` + a `profileKey` filter if the
    `/user` endpoint ever changes shape; the OLD behaviour of returning
    `profiles[0]` (which silently picked the Primary Profile and missed any
    sub-profile's connections) is gone for good.

    Returns a list of `{ platform, username?, profilePic? }` dicts.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AYRSHARE_BASE}/user",
            headers=_headers(profile_key),
        )
        if resp.status_code in (401, 403):
            # Same code-144 "invalid profile key" surface as generate_jwt
            # so the route can self-heal by re-creating the sub-profile.
            try:
                body = resp.json()
                if isinstance(body, dict) and body.get("code") == 144:
                    raise InvalidProfileKey(body.get("message") or "Invalid Profile Key")
            except InvalidProfileKey:
                raise
            except Exception:
                pass

        # Best-effort fallback if /user is unhappy — try the older /profiles
        # endpoint but filter to the right sub-profile this time.
        if resp.status_code != 200:
            print(f"[Ayrshare] /user returned {resp.status_code}; falling back to /profiles")
            fallback = await client.get(
                f"{AYRSHARE_BASE}/profiles",
                headers=_headers(profile_key),
            )
            fallback.raise_for_status()
            data = fallback.json()
            socials = _merge_socials_for_profile(data, profile_key)
            print(f"[Ayrshare] activeSocialAccounts (via /profiles): {socials}")
            return socials

        data = resp.json()
        socials = _merge_socials_for_profile(data, profile_key)

        # Propagation fallback — OAuth can take 1–3 minutes to surface on
        # `GET /user`. `GET /profiles?refId=…&include=socialHealth` often
        # reports `linked: true` sooner, and `activeSocialAccounts` on the
        # profile envelope can appear before `/user` catches up.
        if not socials:
            ref_id = ref_id or data.get("refId")
            if ref_id:
                detail = await client.get(
                    f"{AYRSHARE_BASE}/profiles",
                    headers=_headers(),
                    params={"refId": ref_id, "include": "socialHealth"},
                )
                if detail.status_code == 200:
                    block = ((detail.json() or {}).get("profiles") or [None])[0]
                    if isinstance(block, dict):
                        health_rows = _socials_from_social_health(
                            block.get("socialHealth"),
                        )
                        active_rows = _merge_socials_for_profile(block, profile_key)
                        socials = _dedupe_socials(health_rows + active_rows)
                        if socials:
                            print(
                                f"[Ayrshare] activeSocialAccounts "
                                f"(via /profiles?refId socialHealth): {socials}"
                            )
                            return socials

        print(f"[Ayrshare] activeSocialAccounts (via /user): {socials}")
        return socials


# ── Post Management ─────────────────────────────────────────────────────────

def _collect_post_issues(body: dict) -> list[str]:
    """Surface warnings/errors from Ayrshare's nested post envelope."""
    if not isinstance(body, dict):
        return []
    messages: list[str] = []
    for bucket in (body.get("warnings") or []) + (body.get("errors") or []):
        if isinstance(bucket, dict) and bucket.get("message"):
            messages.append(str(bucket["message"]))
    for post in body.get("posts") or []:
        if not isinstance(post, dict):
            continue
        for err in post.get("errors") or []:
            if isinstance(err, dict) and err.get("message"):
                plat = err.get("platform")
                msg = str(err["message"])
                messages.append(f"{plat}: {msg}" if plat else msg)
        if post.get("status") == "error" and post.get("message"):
            messages.append(str(post["message"]))
    if body.get("message") and body.get("status") == "error":
        messages.append(str(body["message"]))
    return messages


def extract_post_id(body: dict) -> Optional[str]:
    """Resolve the Ayrshare post id from either the top-level or posts[0]."""
    if not isinstance(body, dict):
        return None
    top = body.get("id")
    if top:
        return str(top)
    posts = body.get("posts") or []
    if posts and isinstance(posts[0], dict) and posts[0].get("id"):
        return str(posts[0]["id"])
    return None


def _blocking_post_issues(issues: list[str]) -> list[str]:
    """Issues that mean the post did not actually reach the social network."""
    needles = ("not linked", "invalid profile", "authorization", "permission")
    return [m for m in issues if any(n in m.lower() for n in needles)]


async def create_post(profile_key: str, post_data: dict) -> dict:
    """
    Schedule or immediately publish a post via Ayrshare.

    post_data should include:
      - post (str): caption text
      - platforms (list[str]): target platforms
      - mediaUrls (list[str]): video URLs
      - scheduleDate (str, optional): ISO 8601 UTC datetime for scheduling
    """
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{AYRSHARE_BASE}/post",
            headers=_headers(profile_key),
            json=post_data,
        )
        if resp.status_code >= 400:
            friendly = _friendly_ayrshare_post_error(resp)
            print(f"[Ayrshare] create_post failed ({resp.status_code}): {friendly}")
            raise ValueError(friendly or resp.text[:500])
        body = resp.json()
        issues = _collect_post_issues(body)
        blocking = _blocking_post_issues(issues)
        if blocking:
            print(f"[Ayrshare] create_post blocked by warnings: {blocking}")
            raise ValueError(" · ".join(blocking))
        resolved_id = extract_post_id(body)
        if resolved_id:
            body["_resolved_post_id"] = resolved_id
        return body


def _friendly_ayrshare_post_error(resp: httpx.Response) -> str:
    """Extract human-readable errors from Ayrshare's nested JSON envelope."""
    try:
        body = resp.json()
    except Exception:
        return resp.text[:400]
    if not isinstance(body, dict):
        return str(body)[:400]

    messages: list[str] = []
    for post in body.get("posts") or []:
        if not isinstance(post, dict):
            continue
        for err in post.get("errors") or []:
            if isinstance(err, dict) and err.get("message"):
                plat = err.get("platform")
                msg = str(err["message"])
                messages.append(f"{plat}: {msg}" if plat else msg)
    if messages:
        return " · ".join(messages)
    if body.get("message"):
        return str(body["message"])
    return resp.text[:400]


async def delete_post(profile_key: str, ayrshare_post_id: str) -> dict:
    """Cancel / delete a scheduled post in Ayrshare."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.request(
            "DELETE",
            f"{AYRSHARE_BASE}/post",
            headers=_headers(profile_key),
            json={"id": ayrshare_post_id},
        )
        resp.raise_for_status()
        return resp.json()


async def delete_all_scheduled_posts(profile_key: str) -> dict:
    """Delete every pending scheduled post for this sub-profile."""
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.request(
            "DELETE",
            f"{AYRSHARE_BASE}/post",
            headers=_headers(profile_key),
            json={"deleteAllScheduled": True},
        )
        resp.raise_for_status()
        return resp.json()


async def get_post_analytics(
    profile_key: str,
    ayrshare_post_id: str,
    *,
    platforms: Optional[list[str]] = None,
) -> dict:
    """Real-time engagement for a post published via Ayrshare."""
    payload: dict = {"id": ayrshare_post_id}
    if platforms:
        payload["platforms"] = platforms
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(
            f"{AYRSHARE_BASE}/analytics/post",
            headers=_headers(profile_key),
            json=payload,
        )
        if resp.status_code >= 400:
            friendly = _friendly_ayrshare_post_error(resp)
            raise ValueError(friendly or resp.text[:500])
        data = resp.json()
        return data if isinstance(data, dict) else {}


async def get_post(profile_key: str, ayrshare_post_id: str) -> dict:
    """Fetch Ayrshare post status + platform postIds (GET /post/:id)."""
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.get(
            f"{AYRSHARE_BASE}/post/{ayrshare_post_id}",
            headers=_headers(profile_key),
        )
        if resp.status_code >= 400:
            friendly = _friendly_ayrshare_post_error(resp)
            raise ValueError(friendly or resp.text[:500])
        data = resp.json()
        return data if isinstance(data, dict) else {}
