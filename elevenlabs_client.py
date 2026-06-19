"""
Naiara Content Distribution Engine — ElevenLabs Client

Handles high-fidelity TTS generation for premium voiceovers.
"""
import re
import time
import requests
import config
from pathlib import Path


class ElevenLabsAPIError(RuntimeError):
    """Structured ElevenLabs HTTP failure for voiceover tooling."""

    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = (detail or "")[:500]
        super().__init__(f"ElevenLabs error ({status_code}): {self.detail}")


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

    def _replace_currency(m):
        sign = m.group(1)
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

    def _replace_percent(m):
        whole_str = m.group(1).replace(",", "")
        decimal_str = m.group(3) if m.group(3) else None
        whole = int(whole_str) if whole_str else 0
        words = _number_to_words(whole)
        if decimal_str:
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

    def _replace_plain_number(m):
        num_str = m.group(0).replace(",", "")
        if "," not in m.group(0):
            return m.group(0)
        num = int(num_str)
        return _number_to_words(num)

    text = re.sub(r'[\d,]{4,}', _replace_plain_number, text)

    return text


def ping_elevenlabs_tts() -> dict:
    """Lightweight connectivity check (no audio saved). Returns {ok, status_code}."""
    if not config.ELEVENLABS_API_KEY:
        return {"ok": False, "status_code": None, "detail": "ELEVENLABS_API_KEY missing"}
    voice_id = config.VOICE_MAP.get("Meg", "hpp4J3VqNfWAUOO0d1Us")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": "ping",
        "model_id": config.ELEVENLABS_MODEL_ID,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        return {
            "ok": resp.status_code == 200,
            "status_code": resp.status_code,
            "detail": resp.text[:200] if resp.status_code != 200 else "",
        }
    except Exception as e:
        return {"ok": False, "status_code": None, "detail": str(e)[:200]}


def generate_voiceover(
    text,
    voice_id,
    filename="voiceover.mp3",
    *,
    language_code=None,
    max_retries=3,
):
    """
    Generate audio from text using ElevenLabs API.
    Returns the local path to the generated MP3 file.
    """
    if not config.ELEVENLABS_API_KEY:
        raise ValueError("ELEVENLABS_API_KEY is not set in .env")

    processed_text = _preprocess_for_tts(text)
    if processed_text != text:
        print("   🔢 Numbers preprocessed for TTS")
        print(f"      Before: {text[:100]}...")
        print(f"      After:  {processed_text[:100]}...")

    print("🎙️ Generating ElevenLabs voiceover...")
    print(f"   Voice: {voice_id}")
    if language_code:
        print(f"   Language: {language_code}")
    print(f"   Text: {processed_text[:60]}...")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": config.ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "text": processed_text,
        "model_id": config.ELEVENLABS_MODEL_ID,
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.70,
            "style": 0.15,
            "use_speaker_boost": True,
            "speed": 0.92,
        },
    }
    if language_code:
        payload["language_code"] = language_code

    retriable = {429, 500, 502, 503, 504}
    last_error = None

    for attempt in range(max_retries):
        resp = requests.post(url, headers=headers, json=payload, timeout=120)

        if resp.status_code == 402:
            print("   ⚠️ ElevenLabs Payment Required (402). Falling back to standard voice...")
            fallback_voice = "pNInz6obpgDQGcFmaJgB"
            if voice_id == fallback_voice:
                raise ElevenLabsAPIError(resp.status_code, resp.text)
            return generate_voiceover(
                text,
                fallback_voice,
                filename,
                language_code=language_code,
                max_retries=max_retries,
            )

        if resp.status_code == 200:
            output_path = config.TEMP_DIR / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(resp.content)
            print(f"   ✅ Voiceover saved: {output_path}")
            return str(output_path)

        last_error = ElevenLabsAPIError(resp.status_code, resp.text)
        print(f"   [ElevenLabs] HTTP {resp.status_code} (attempt {attempt + 1}/{max_retries})")

        if resp.status_code in retriable and attempt < max_retries - 1:
            wait = (2 ** attempt) * 2
            print(f"   [ElevenLabs] Retrying in {wait}s...")
            time.sleep(wait)
            continue
        raise last_error

    if last_error:
        raise last_error
    raise ElevenLabsAPIError(0, "ElevenLabs TTS failed with no response")


if __name__ == "__main__":
    try:
        if config.ELEVENLABS_API_KEY:
            test_voice = config.VOICE_MAP["Meg"]
            generate_voiceover(
                "¡Hola! Esto es una prueba del nuevo sistema de voz de ElevenLabs.",
                test_voice,
                "test_eleven.mp3",
                language_code="es",
            )
        else:
            print("❌ ELEVENLABS_API_KEY not found. Skipping test.")
    except Exception as e:
        print(f"❌ Test failed: {e}")
