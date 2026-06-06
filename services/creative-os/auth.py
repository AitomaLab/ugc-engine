"""
Creative OS Microservice — JWT Authentication

Validates Supabase JWTs. Mirrors ugc_backend/auth.py logic
but runs independently on port 8001.
"""
import asyncio
import base64
import json as _json
import os
import time
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, ClientOptions
from pathlib import Path

from env_loader import load_env
load_env(Path(__file__))

_bearer_scheme = HTTPBearer(auto_error=False)
_auth_client = None

# ── Validated-token cache ─────────────────────────────────────────────
# Every request used to make a network round-trip to Supabase Auth
# (auth.get_user). Under frequent polling (the project page polls
# /jobs-status every 5s while a generation is in flight) those calls
# occasionally time out ("The read operation timed out") and surface as
# 401s in the UI. We cache each validated token → user for a short TTL
# (bounded by the token's own `exp`) so repeated requests reuse the result
# instead of re-hitting Supabase, and retry once on transient timeouts.
_token_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 300.0  # seconds


def _get_auth_client():
    """Get a Supabase client configured with the ANON key for JWT validation."""
    global _auth_client
    if _auth_client is None:
        url = os.getenv("SUPABASE_URL")
        anon_key = os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY")
        if not url or not anon_key:
            raise RuntimeError(
                "SUPABASE_URL and SUPABASE_ANON_KEY must be set in .env.saas"
            )
        _auth_client = create_client(url, anon_key, options=ClientOptions(postgrest_client_timeout=10))
    return _auth_client


def _token_exp(token: str) -> float | None:
    """Decode (without verifying) the JWT `exp` claim so the cache entry never
    outlives the token itself."""
    try:
        payload_b64 = token.split(".")[1]
        padding = "=" * (-len(payload_b64) % 4)
        decoded = base64.urlsafe_b64decode(payload_b64 + padding)
        exp = _json.loads(decoded).get("exp")
        return float(exp) if exp else None
    except Exception:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """Validate JWT and return {id, email}. Caches validated tokens and retries
    once on transient network timeouts."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    now = time.time()

    cached = _token_cache.get(token)
    if cached and cached[1] > now:
        return cached[0]

    last_err: Exception | None = None
    for attempt in range(2):
        try:
            client = _get_auth_client()
            result = await asyncio.to_thread(client.auth.get_user, token)
            if not result or not result.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token.",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            user = {
                "id": str(result.user.id),
                "email": result.user.email,
                "token": token,  # Pass through for proxying to core API
            }
            # Cache until min(now + TTL, token exp - 30s) so a revoked/expired
            # token is never served stale beyond its own lifetime.
            ttl_until = now + _CACHE_TTL
            exp = _token_exp(token)
            if exp:
                ttl_until = min(ttl_until, exp - 30)
            if ttl_until > now:
                _token_cache[token] = (user, ttl_until)
                # Opportunistic prune of expired entries to bound memory.
                if len(_token_cache) > 500:
                    for k in [k for k, (_, e) in _token_cache.items() if e <= now]:
                        _token_cache.pop(k, None)
            return user
        except HTTPException:
            raise
        except Exception as e:
            last_err = e
            if attempt == 0:
                await asyncio.sleep(0.4)  # brief backoff before one retry
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Authentication failed: {str(last_err)}",
        headers={"WWW-Authenticate": "Bearer"},
    )
