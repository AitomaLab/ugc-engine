"""
Creative OS — Environment loader

Walks up from a starting path to find .env / .env.saas files and loads them.
Works in both local dev (deep nesting under repo root) and Railway (/app/).
On Railway, env vars are already set so load_dotenv is a no-op — but this
keeps local dev working without hardcoded parent depths.
"""
from pathlib import Path
from dotenv import load_dotenv


def load_env(start: Path | None = None) -> Path | None:
    """Find the nearest ancestor containing .env or .env.saas and load them.

    Returns the directory found, or None if no env files were found
    (normal on Railway where env vars are injected directly).
    """
    here = (start or Path(__file__)).resolve().parent
    for ancestor in (here, *here.parents):
        if (ancestor / ".env").exists() or (ancestor / ".env.saas").exists():
            for candidate in ("env.saas", ".env.saas", "env", ".env"):
                load_dotenv(ancestor / candidate, override=False)
            return ancestor
    return None
