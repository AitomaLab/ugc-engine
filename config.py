"""
Naiara Content Distribution Engine — Configuration

Central config loaded from .env file.
All modules import from here instead of reading env vars directly.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
PROJECT_ROOT = Path(__file__).parent
load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# API Keys
# ---------------------------------------------------------------------------
KIE_API_KEY = os.getenv("KIE_API_KEY")
AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Optional: Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ---------------------------------------------------------------------------
# Kie.ai API Endpoints
# ---------------------------------------------------------------------------
KIE_API_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
KIE_HEADERS = {
    "Authorization": f"Bearer {KIE_API_KEY}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Airtable Table Names
# ---------------------------------------------------------------------------
TABLE_CONTENT_CALENDAR = "Content Calendar"
TABLE_INFLUENCERS = "Influencers"
TABLE_APP_CLIPS = "App Clips"

# ---------------------------------------------------------------------------
# Airtable API
# ---------------------------------------------------------------------------
AIRTABLE_API_URL = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}"
AIRTABLE_HEADERS = {
    "Authorization": f"Bearer {AIRTABLE_TOKEN}",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Video Settings
# ---------------------------------------------------------------------------
VIDEO_ASPECT_RATIO = "9:16"       # Vertical (Shorts/Reels/TikTok)
VALID_LENGTHS = ["15s", "30s"]

# Scene durations per video length (AI clips are always 8s)
AI_CLIP_DURATION = 8                  # Full AI-generated clip duration

SCENE_DURATIONS = {
    "15s": {                          # 2 scenes, 1 Seedance call = $0.38
        "hook": 8,                    # Full Seedance clip
        "app_demo": 7,               # Pre-recorded clip trimmed to fit
    },
    "30s": {                          # 4 scenes, 3 Seedance calls = $0.94
        "hook": 8,                    # Full Seedance clip
        "app_demo": 8,               # Pre-recorded clip
        "reaction": 8,               # Full Seedance clip
        "cta": 8,                     # Full Seedance clip
    },
}

VIDEO_MAX_DURATION = 35  # Absolute cap to prevent runaway files

def get_max_duration(length):
    """Get the max video duration for a given length setting."""
    return int(length.replace("s", ""))

def get_scene_durations(length):
    """Get scene durations dict for a given length setting."""
    return SCENE_DURATIONS.get(length, SCENE_DURATIONS["15s"])

# ---------------------------------------------------------------------------
# Video Generation Model (swap via .env)
# ---------------------------------------------------------------------------
# Supported models and their Kie.ai API identifiers:
MODEL_REGISTRY = {
    "seedance-1.5-pro": "bytedance/seedance-1.5-pro",      # $0.28/clip 720p+audio, lip-sync, Spanish
    "seedance-2.0":     "seedance-2-0",           # Feb 24 — 2K, faster, better lip-sync
    "veo-3.1-fast":     "veo3_fast",              # $0.30/clip, speech+audio (no lang control)
    "veo-3.1":          "veo3",                    # higher quality, slower
    "kling-2.6":        "kling-2.6/image-to-video", # silent video only, requires image_urls
}

# Default: seedance-1.5-pro (native lip-sync + Spanish support)
# Override in .env: VIDEO_MODEL=seedance-2.0 | veo-3.1-fast | kling-2.6
VIDEO_MODEL = os.getenv("VIDEO_MODEL", "seedance-1.5-pro")
VIDEO_MODEL_API = MODEL_REGISTRY.get(VIDEO_MODEL, VIDEO_MODEL)

# Seedance-specific settings
SEEDANCE_QUALITY = os.getenv("SEEDANCE_QUALITY", "720p")   # 720p or 1080p
SEEDANCE_AUDIO = True                                       # Always generate audio for lip-sync

# ElevenLabs Settings
ELEVENLABS_MODEL_ID = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")
# Default voices for influencers (using premade IDs for Free Tier compatibility)
VOICE_MAP = {
    "Meg": "hpp4J3VqNfWAUOO0d1Us",  # Bella (Premade)
    "Max": "pNInz6obpgDQGcFmaJgB",  # Adam (Premade)
}

# Celery Transport Options for Redis Stability (Render Free Tier)
CELERY_TRANSPORT_OPTIONS = {
    'socket_timeout': 30,
    'socket_connect_timeout': 30,
    'socket_keepalive': True,
    'visibility_timeout': 3600,
}

# Lip-Sync Model
LIPSYNC_MODEL = os.getenv("LIPSYNC_MODEL", "infinitalk/from-audio")
LIPSYNC_QUALITY = os.getenv("LIPSYNC_QUALITY", "720p")

# ---------------------------------------------------------------------------
# Output Paths
# ---------------------------------------------------------------------------
OUTPUT_DIR = PROJECT_ROOT / "outputs"
TEMP_DIR = PROJECT_ROOT / "temp"
OUTPUT_DIR.mkdir(exist_ok=True)
TEMP_DIR.mkdir(exist_ok=True)


def validate():
    """Check that all required env vars are set."""
    missing = []
    if not KIE_API_KEY:
        missing.append("KIE_API_KEY")
    if not AIRTABLE_TOKEN:
        missing.append("AIRTABLE_TOKEN")
    if not AIRTABLE_BASE_ID:
        missing.append("AIRTABLE_BASE_ID")
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print(f"   Copy .env.example to .env and fill in your keys.")
        return False
    print("✅ All required environment variables are set.")
    return True


if __name__ == "__main__":
    validate()
