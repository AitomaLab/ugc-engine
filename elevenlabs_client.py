"""
Naiara Content Distribution Engine — ElevenLabs Client

Handles high-fidelity TTS generation for premium voiceovers.
"""
import requests
import config
from pathlib import Path

def generate_voiceover(text, voice_id, filename="voiceover.mp3"):
    """
    Generate audio from text using ElevenLabs API.
    Returns the local path to the generated MP3 file.
    """
    if not config.ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is not set in .env")

    print(f"🎙️ Generating ElevenLabs voiceover...")
    print(f"   Voice: {voice_id}")
    print(f"   Text: {text[:60]}...")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75,
            "style": 0.0,
            "use_speaker_boost": True
        }
    }

    resp = requests.post(url, headers=headers, json=payload)
    
    if resp.status_code == 402:
        print(f"   ⚠️ ElevenLabs Payment Required (402). Falling back to standard voice...")
        fallback_voice = "pNInz6obpgDQGcFmaJgB" # Adam (Standard/High Quality)
        if voice_id == fallback_voice:
             raise RuntimeError(f"ElevenLabs error ({resp.status_code}): {resp.text[:500]}")
        return generate_voiceover(text, fallback_voice, filename)

    if resp.status_code != 200:
        raise RuntimeError(f"ElevenLabs error ({resp.status_code}): {resp.text[:500]}")

    output_path = config.TEMP_DIR / filename
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "wb") as f:
        f.write(resp.content)

    print(f"   ✅ Voiceover saved: {output_path}")
    return str(output_path)

if __name__ == "__main__":
    # Test generation if run directly
    try:
        if config.ELEVENLABS_API_KEY:
            test_voice = config.VOICE_MAP["Meg"]
            generate_voiceover("¡Hola! Esto es una prueba del nuevo sistema de voz de ElevenLabs.", test_voice, "test_eleven.mp3")
        else:
            print("❌ ELEVENLABS_API_KEY not found. Skipping test.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
