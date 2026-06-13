"""
Creative OS — prompts module

Standalone version of the sanitize_dialogue utility from the repo-root
prompts package. Used by the UGC video pipeline to clean dialogue text
before sending to Veo/Seedance for speech generation.
"""
import re


# ---------------------------------------------------------------------------
# Spain-detection from free-form script text
# ---------------------------------------------------------------------------
def _detect_spain_from_text(text) -> bool:
    """Heuristic: does this text look like it was written for a Spain speaker?

    Used by the create_ugc_video tool as a fallback when the agent forgot
    to forward language_accent — if the script contains unambiguous Spain
    signals we set it server-side rather than letting the job row stay
    NULL (which would default to LATAM in the downstream prompt builder).
    """
    if not text:
        return False
    t = str(text).lower()
    if "€" in t:
        return True
    if any(w in t for w in (
        "vosotros", "vosotras",
        " vale", " móvil", " movil", " ordenador", " plátano", " platano",
        " gilipollas", " coche", " zumo",
    )):
        return True
    import re as _re
    if _re.search(r"\b\w+(áis|éis|íais|isteis)\b", t):
        return True
    return False


# ---------------------------------------------------------------------------
# Spanish accent line for Veo voice_type (Spain vs Latin America)
# ---------------------------------------------------------------------------
def spanish_accent_line(code, hint_text=None) -> str:
    """Return the `voice_type:` accent description for a Spanish video.

    `code`: "spain" / "es-es" / "castilian" / "castellano" → Castilian (Spain),
    anything else → neutral LATAM. Free-form influencer accent strings also
    accepted via substring match. When `code` carries no explicit Spain/LATAM
    marker, `hint_text` (the script) is scanned for Spain signals as a safety
    net — mirrors the repo-root prompts package.
    """
    if not code:
        norm = ""
    else:
        norm = str(code).lower()
    is_spain = (
        "spain" in norm
        or "españa" in norm
        or "espana" in norm
        or "castilian" in norm
        or "castellano" in norm
        or norm in ("es-es", "es_es")
    )
    # Explicit LATAM markers block the safety net — a deliberate LATAM choice
    # must never be overridden by script-text detection.
    is_latam_explicit = any(w in norm for w in (
        "latam", "latin", "mexican", "colombian", "argentine",
        "argentino", "peruvian", "es-419",
    ))
    if not is_spain and not is_latam_explicit and _detect_spain_from_text(hint_text):
        is_spain = True
        print(f"      [spanish_accent_line] safety net fired: detected Spain from script text (code={code!r})")
    if is_spain:
        return (
            "native CASTILIAN Spanish from SPAIN (Madrid speaker, NOT Latin American) — "
            "use peninsular DISTINCIÓN pronunciation: the letters c (before e/i) and z must "
            "sound like English 'th' — say 'gra-THIAS' not 'gra-SIAS', 'THIU-dad' not "
            "'SIU-dad', 'cora-THON' not 'cora-SON', 'deli-THIO-sas' not 'deli-SIO-sas'; "
            "use VOSOTROS conjugations for plural-you, never ustedes; "
            "Spain vocabulary ('plátano' not 'banana', 'móvil' not 'celular', "
            "'ordenador' not 'computadora', 'vale' not 'okey'); "
            "speaking entirely in Spanish from Spain"
        )
    return (
        "neutral Latin American Spanish (Mexican/Colombian baseline), seseo "
        "pronunciation (c/z sound like 's', NOT like 'th'), use ustedes for "
        "plural-you, speaking entirely in Spanish"
    )


# ---------------------------------------------------------------------------
# English accent line for Veo voice_type (US vs UK)
# ---------------------------------------------------------------------------
def english_accent_line(code=None, hint_text=None) -> str:
    """Return the `voice_type:` accent description for an English video.

    Veo 3.1 drifts between US and UK accents when prompts only say
    "neutral English" — especially harmful for parallel_i2v where each clip
    is generated independently. Default to explicit General American US.

    `code` may be an influencer accent string or language_accent override.
    UK is used only when the code explicitly mentions British/UK markers.
    """
    del hint_text  # reserved for future script-based detection
    norm = str(code or "").lower()
    is_uk = any(w in norm for w in (
        "uk", "british", "england", "scottish", "irish", "welsh",
        "received pronunciation", "oxford", "bbc", "cockney",
    )) or norm in ("en-gb", "en_gb", "gb")
    if is_uk:
        return (
            "native British English from England (Received Pronunciation / London baseline, NOT American) — "
            "non-rhotic pronunciation where applicable, British vocabulary and intonation, "
            "speaking entirely in English with a consistent British UK accent"
        )
    return (
        "native General American English from the United States (NOT British, NOT UK) — "
        "standard American pronunciation with rhotic r sounds, American vocabulary and intonation, "
        "speaking entirely in English with a consistent US American accent"
    )


# ---------------------------------------------------------------------------
# Number-to-words expansion (0-999)
# ---------------------------------------------------------------------------
_NUMBER_WORDS = {
    0: "zero", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five",
    6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten",
    11: "eleven", 12: "twelve", 13: "thirteen", 14: "fourteen", 15: "fifteen",
    16: "sixteen", 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
    30: "thirty", 40: "forty", 50: "fifty", 60: "sixty", 70: "seventy",
    80: "eighty", 90: "ninety", 100: "one hundred",
}


def _number_to_words(n: int) -> str:
    if n in _NUMBER_WORDS:
        return _NUMBER_WORDS[n]
    if n < 100:
        tens, ones = divmod(n, 10)
        return f"{_NUMBER_WORDS[tens * 10]}-{_NUMBER_WORDS[ones]}" if ones else _NUMBER_WORDS[tens * 10]
    if n < 1000:
        hundreds, remainder = divmod(n, 100)
        if remainder == 0:
            return f"{_NUMBER_WORDS[hundreds]} hundred"
        return f"{_NUMBER_WORDS[hundreds]} hundred {_number_to_words(remainder)}"
    return str(n)


def _expand_numbers_and_symbols(text: str) -> str:
    text = re.sub(r"(\d+)%", lambda m: f"{_number_to_words(int(m.group(1)))} percent", text)
    text = re.sub(r"\$(\d+)", lambda m: f"{_number_to_words(int(m.group(1)))} dollars", text)
    text = re.sub(r"\u20ac(\d+)", lambda m: f"{_number_to_words(int(m.group(1)))} euros", text)
    text = re.sub(r"#(\d+)", lambda m: f"number {_number_to_words(int(m.group(1)))}", text)
    return text


_TRAILING_CONJUNCTIONS = {
    "and", "but", "so", "or", "because", "like", "then",
    "plus", "also", "yet", "nor", "while", "although", "since",
}


def sanitize_dialogue(text: str) -> str:
    """Sanitize dialogue text before sending to Veo/Seedance for speech generation."""
    text = _expand_numbers_and_symbols(text)

    # Strip system prompt artifacts
    text = re.sub(
        r'^(?:They\s+say\s+this\s+in\s+\w+\s+in\s+a\s+\w+\s+tone:\s*)',
        '', text, flags=re.IGNORECASE
    )
    text = re.sub(
        r'^(?:(?:She|He|They)\s+says?\s+(?:this\s+)?in\s+\w+(?:\s+in\s+a\s+\w+\s+tone)?:\s*)',
        '', text, flags=re.IGNORECASE
    )

    # Remove bracketed action/stage directions
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)

    # Veo TTS pronounces "." literally — collapse ellipses to a comma pause.
    text = text.replace("\u2026", ", ")
    text = re.sub(r"\.{2,}", ", ", text)

    # Convert dashes to a comma pause (NOT "..." — Veo TTS reads each period
    # aloud as "dot", so "game-changer" → "game...changer" → "game dot changer").
    text = text.replace("\u2014", ", ").replace("-", ", ")

    # Remove emojis and non-Latin/non-punctuation symbols
    text = re.sub(
        r"[^\w\s.,!?;:'\u00C0-\u024F\u1E00-\u1EFF]",
        "",
        text,
    )
    text = text.replace('"', '')

    # Remove pure stage direction lines
    lines = text.split("\n")
    spoken_lines = [
        ln for ln in lines
        if ln.strip() and not re.match(
            r"^(scene|hook|cta|reaction|body|intro|outro)\s*\d*\s*:",
            ln.strip(), re.IGNORECASE
        )
    ]
    text = " ".join(spoken_lines)

    # Collapse whitespace
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r",\s*,", ",", text)
    text = text.strip().strip(",")

    # Strip trailing conjunctions
    words = text.split()
    while words and words[-1].lower().rstrip(".,!?;:") in _TRAILING_CONJUNCTIONS:
        words.pop()
    text = " ".join(words)

    # Ensure sentence punctuation
    if text and text[-1] not in ".!?":
        text += "."

    return text
