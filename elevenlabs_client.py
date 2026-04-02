"""
Naiara Content Distribution Engine — ElevenLabs Client

Handles high-fidelity TTS generation for premium voiceovers.
"""
import re
import requests
import config
from pathlib import Path


def _number_to_words(n: int) -> str:
    """Convert an integer to its English spoken form."""
    if n == 0:
        return "zero"

    ones = ["", "one", "two", "three", "four", "five", "six", "seven",
            "eight", "nine", "ten", "eleven", "twelve", "thirteen",
            "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"]
    tens = ["", "", "twenty", "thirty", "forty", "fifty",
            "sixty", "seventy", "eighty", "ninety"]

    def _chunk(num: int) -> str:
        if num == 0:
            return ""
        elif num < 20:
            return ones[num]
        elif num < 100:
            return tens[num // 10] + (" " + ones[num % 10] if num % 10 else "")
        else:
            rest = _chunk(num % 100)
            return ones[num // 100] + " hundred" + (" " + rest if rest else "")

    result_parts = []
    billions = n // 1_000_000_000
    millions = (n % 1_000_000_000) // 1_000_000
    thousands = (n % 1_000_000) // 1_000
    remainder = n % 1_000

    if billions:
        result_parts.append(_chunk(billions) + " billion")
    if millions:
        result_parts.append(_chunk(millions) + " million")
    if thousands:
        result_parts.append(_chunk(thousands) + " thousand")
    if remainder:
        result_parts.append(_chunk(remainder))

    return " ".join(result_parts)


def _preprocess_for_tts(text: str) -> str:
    """Convert numbers, currencies, and percentages into spoken-word form
    so ElevenLabs doesn't stumble on complex numeric formats."""

    # --- Currency: $1,234,567.89 → "one million two hundred thirty four thousand five hundred sixty seven dollars and eighty nine cents"
    def _replace_currency(m):
        sign = m.group(1)  # $ or €
        whole_str = m.group(2).replace(",", "")
        cents_str = m.group(4) if m.group(4) else None

        currency_name = "dollars" if sign == "$" else "euros"
        whole = int(whole_str) if whole_str else 0
        words = _number_to_words(whole) + " " + currency_name

        if cents_str:
            cents = int(cents_str)
            if cents > 0:
                words += " and " + _number_to_words(cents) + " cents"
        return words

    text = re.sub(
        r'([$€])\s?([\d,]+)(\.([\d]{1,2}))?',
        _replace_currency,
        text
    )

    # --- Percentages: 216.90% → "two hundred sixteen point nine zero percent"
    def _replace_percent(m):
        whole_str = m.group(1).replace(",", "")
        decimal_str = m.group(3) if m.group(3) else None
        whole = int(whole_str) if whole_str else 0
        words = _number_to_words(whole)
        if decimal_str:
            # Read each digit individually: .90 → "point nine zero"
            digit_words = " ".join(
                _number_to_words(int(d)) for d in decimal_str
            )
            words += " point " + digit_words
        return words + " percent"

    text = re.sub(
        r'([\d,]+)(\.([\d]+))?\s*%',
        _replace_percent,
        text
    )

    # --- Plain large numbers with commas: 1,234,567 → "one million two hundred thirty four thousand five hundred sixty seven"
    def _replace_plain_number(m):
        num_str = m.group(0).replace(",", "")
        # Only convert numbers with commas (i.e. large formatted numbers)
        if "," not in m.group(0):
            return m.group(0)
        num = int(num_str)
        return _number_to_words(num)

    text = re.sub(r'[\d,]{4,}', _replace_plain_number, text)

    return text


def generate_voiceover(text, voice_id, filename="voiceover.mp3"):
    """
    Generate audio from text using ElevenLabs API.
    Returns the local path to the generated MP3 file.
    """
    if not config.ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is not set in .env")

    # Preprocess text: convert numbers/currencies to spoken words
    processed_text = _preprocess_for_tts(text)
    if processed_text != text:
        print(f"   🔢 Numbers preprocessed for TTS")
        print(f"      Before: {text[:100]}...")
        print(f"      After:  {processed_text[:100]}...")

    print(f"🎙️ Generating ElevenLabs voiceover...")
    print(f"   Voice: {voice_id}")
    print(f"   Text: {processed_text[:60]}...")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    payload = {
        "text": processed_text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.70,
            "style": 0.15,
            "use_speaker_boost": True
        },
        "speed": 0.92,
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
