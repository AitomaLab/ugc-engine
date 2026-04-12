"""
Creative OS Microservice — JWT Authentication

Validates Supabase JWTs. Mirrors ugc_backend/auth.py logic
but runs independently on port 8001.
"""
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, ClientOptions
from pathlib import Path

from env_loader import load_env
load_env(Path(__file__))

_bearer_scheme = HTTPBearer(auto_error=False)
_auth_client = None


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


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> dict:
    """Validate JWT and return {id, email}."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    try:
        client = _get_auth_client()
        result = client.auth.get_user(token)
        if not result or not result.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {
            "id": str(result.user.id),
            "email": result.user.email,
            "token": token,  # Pass through for proxying to core API
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
