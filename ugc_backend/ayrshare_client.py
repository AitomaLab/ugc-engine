"""
UGC Engine — Ayrshare API Client

Encapsulates all direct communication with the Ayrshare Social Media API.
All platform-side OAuth, posting, and profile management flows are handled
through this module so the rest of the backend never touches Ayrshare directly.
"""

import os
import httpx

AYRSHARE_BASE = "https://app.ayrshare.com/api"
AYRSHARE_API_KEY = os.getenv("AYRSHARE_API_KEY", "")


def _headers(profile_key: str | None = None) -> dict:
    """Build standard Ayrshare request headers."""
    h = {
        "Authorization": f"Bearer {AYRSHARE_API_KEY}",
        "Content-Type": "application/json",
    }
    if profile_key:
        h["Profile-Key"] = profile_key
    return h


# ── Profile Management ──────────────────────────────────────────────────────

async def create_profile(user_id: str) -> dict:
    """
    Create a new Ayrshare sub-profile for this user.
    Returns the full Ayrshare response including `profileKey`.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AYRSHARE_BASE}/profiles/profile",
            headers=_headers(),
            json={"title": user_id},
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


async def generate_jwt(profile_key: str) -> dict:
    """
    Generate a short-lived JWT URL that opens the Ayrshare social-linking
    popup so the user can connect their social accounts.
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
    
    print(f"[Ayrshare] generateJWT payload keys: {list(payload.keys())}, domain={domain or '(not set)'}")
    
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{AYRSHARE_BASE}/profiles/generateJWT",
            headers=_headers(),
            json=payload,
        )
        if resp.status_code != 200:
            print(f"[Ayrshare] generateJWT failed ({resp.status_code}): {resp.text}")
            print(f"[Ayrshare] privateKey length: {len(private_key)}, starts with: {private_key[:30]}")
        resp.raise_for_status()
        return resp.json()


async def get_user_socials(profile_key: str) -> list:
    """
    Retrieve the list of connected social accounts for a sub-profile.
    Returns a list of { platform, username? } objects.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{AYRSHARE_BASE}/profiles",
            headers=_headers(profile_key),
        )
        resp.raise_for_status()
        data = resp.json()
        print(f"[Ayrshare] get_user_socials raw response type: {type(data)}")
        
        # Ayrshare wraps the data inside { profiles: [ { activeSocialAccounts: [...] } ] }
        if isinstance(data, dict):
            profiles = data.get("profiles", [])
            if profiles and isinstance(profiles, list):
                # Get activeSocialAccounts from the first profile
                active = profiles[0].get("activeSocialAccounts", [])
                print(f"[Ayrshare] activeSocialAccounts: {active}")
                # Convert string list to SocialConnection objects
                if active and isinstance(active[0], str):
                    return [{"platform": p} for p in active]
                return active
            # Fallback: check top-level (in case API format differs)
            active = data.get("activeSocialAccounts", [])
            if active:
                if isinstance(active[0], str):
                    return [{"platform": p} for p in active]
                return active
        return []


# ── Post Management ─────────────────────────────────────────────────────────

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
        resp.raise_for_status()
        return resp.json()


async def delete_post(profile_key: str, ayrshare_post_id: str) -> dict:
    """Cancel / delete a scheduled post in Ayrshare."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{AYRSHARE_BASE}/post",
            headers=_headers(profile_key),
            json={"id": ayrshare_post_id},
        )
        resp.raise_for_status()
        return resp.json()
