import sys
import logging
from kie_ai.veo_client import client

logging.basicConfig(level=logging.INFO)

# Use the exact prompt that failed earlier, but genericized
prompt = (
    "## 1. Core Concept\n"
    "An authentic, high-energy, handheld smartphone selfie video. The person, a 25-year-old female with casual style, is excitedly sharing an amazing discovery.\n\n"
    "## 2. Visual Style\n"
    "- **Camera**: Close-up shot, arm's length, slight arm movement and natural handheld shake.\n"
    "- **Lighting**: Bright natural light from a window, creating a sparkle in her eyes.\n"
    "- **Environment**: cozy bedroom with a bookshelf and a travel map on the wall. Slightly blurry background.\n"
    "- **Aesthetic**: Raw, genuine TikTok/Reels style. Spontaneous, not polished.\n\n"
    "## 3. Performance - Visual\n"
    "- **Eye Contact**: CRITICAL: The person MUST maintain direct eye contact with the lens throughout.\n"
    "**Expressions**:\n"
    "- [0-2s]: Opens with wide eyes and raised eyebrows in disbelief.\n"
    "- [2-5s]: Transitions to a huge, genuine smile showing teeth.\n"
    "- [5-8s]: Confident nod and knowing smirk.\n"
    "- **Body**: Leans INTO the camera for emphasis. Highly animated.\n"
    "**Gestures**:\n"
    "- [1s]: Places hand on chest in disbelief.\n"
    "- [4s]: Points directly at the viewer.\n"
    "- [7s]: Gives an enthusiastic thumbs up.\n\n"
    "## 4. Performance - Vocal\n"
    "- **Language**: Natural, conversational Castilian Spanish (Spain).\n"
    "- **Tone**: Enthusiastic. Rising pitch on emphasized words.\n"
    "- **Pacing**: Fast start, dramatic micro-pauses, punchy ending.\n\n"
    "## 5. Script\n"
    "\"Check this out!\"\n\n"
    "## 6. Technical Specifications\n"
    "Vertical 9:16, handheld (fixed_lens: false)."
)

# Use the exact image that was flagged
image_url = "https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/influencer-images/naiara_reference.jpeg"

try:
    print("🚀 Triggering Veo 3.1 with Fallback enabled...")
    url = client.generate_video(
        prompt=prompt,
        image_url=image_url,
        model="veo3_fast"
    )
    print(f"\n✅ Success! Video URL: {url}")
except Exception as e:
    print(f"\n❌ Failure: {e}")
    sys.exit(1)
