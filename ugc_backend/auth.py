"""
UGC Engine SaaS — Authentication Middleware

Provides a FastAPI dependency that validates Supabase JWTs.
"""
import os
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, ClientOptions
from dotenv import load_dotenv

load_dotenv(".env.saas")

# HTTP Bearer scheme — extracts the token from "Authorization: Bearer <token>"
_bearer_scheme = HTTPBearer(auto_error=False)

# Cache a lightweight Supabase client (uses ANON key for auth validation)
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
    """FastAPI dependency — validates the JWT and returns {id, email}.

    Usage:
        @app.get("/api/protected")
        def my_endpoint(user: dict = Depends(get_current_user)):
            user_id = user["id"]
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in.",
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
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
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
