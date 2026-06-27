"""
UGC Engine SaaS — Authentication Middleware

Provides a FastAPI dependency that validates Supabase JWTs.
"""
import asyncio
import base64
import hashlib
import hmac
import json as _json
import os
import time
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, ClientOptions
from dotenv import load_dotenv

load_dotenv(".env.saas")

# HTTP Bearer scheme — extracts the token from "Authorization: Bearer <token>"
_bearer_scheme = HTTPBearer(auto_error=False)

# Cache a lightweight Supabase client (uses ANON key for auth validation)
_auth_client = None

# ── Validated-token cache ─────────────────────────────────────────────
_token_cache: dict[str, tuple[dict, float]] = {}
_CACHE_TTL = 300.0  # seconds

_jwt_secret: str | None = None


def _get_jwt_secret() -> str | None:
    global _jwt_secret
    if _jwt_secret is None:
        _jwt_secret = (
            os.getenv("SUPABASE_JWT_SECRET")
            or os.getenv("JWT_SECRET")
            or ""
        ).strip() or None
    return _jwt_secret


def _b64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)


def _user_from_jwt(token: str) -> dict | None:
    """Verify HS256 Supabase JWT locally — no network round-trip."""
    secret = _get_jwt_secret()
    if not secret:
        return None
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        actual_sig = _b64url_decode(sig_b64)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        payload = _json.loads(_b64url_decode(payload_b64))
        exp = payload.get("exp")
        if exp is not None and float(exp) <= time.time():
            return None
        sub = payload.get("sub")
        if not sub:
            return None
        return {
            "id": str(sub),
            "email": payload.get("email"),
        }
    except Exception:
        return None


def _cache_user(token: str, user: dict) -> dict:
    now = time.time()
    ttl_until = now + _CACHE_TTL
    exp = _token_exp(token)
    if exp:
        ttl_until = min(ttl_until, exp - 30)
    if ttl_until > now:
        _token_cache[token] = (user, ttl_until)
        if len(_token_cache) > 500:
            for k in [k for k, (_, e) in _token_cache.items() if e <= now]:
                _token_cache.pop(k, None)
    return user


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
        # trust_env=False so the auth client ignores ambient HTTP(S)_PROXY env
        # vars that can otherwise hijack Supabase auth calls in some hosts.
        hp = httpx.Client(trust_env=False, timeout=10)
        _auth_client = create_client(
            url,
            anon_key,
            options=ClientOptions(postgrest_client_timeout=10, httpx_client=hp),
        )
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
    """FastAPI dependency — validates the JWT and returns {id, email}.

    Caches validated tokens and retries once on transient network timeouts.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    now = time.time()

    cached = _token_cache.get(token)
    if cached and cached[1] > now:
        return cached[0]

    jwt_user = _user_from_jwt(token)
    if jwt_user:
        return _cache_user(token, jwt_user)

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
            }
            return _cache_user(token, user)
        except HTTPException:
            raise
        except Exception as e:
            last_err = e
            if attempt == 0:
                await asyncio.sleep(0.4)
            continue

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Authentication failed: {str(last_err)}",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict | None:
    """Like get_current_user but returns None instead of raising 401.

    Useful for endpoints that work both authenticated and unauthenticated
    (e.g., the worker callback updating job status).
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
