"""
Initializer for prompts module.
"""
import re


# ---------------------------------------------------------------------------
# Spanish accent line for Veo voice_type (Spain vs Latin America)
# ---------------------------------------------------------------------------
def spanish_accent_line(code) -> str:
    """Return the `voice_type:` accent description for a Spanish video.

    Veo 3.1 defaults to neutral Latin American Spanish whenever the prompt
    just says "Spanish accent". To produce Castilian / peninsular pronunciation
    the prompt must explicitly anchor on Spain and the distinción/'th' sound
    AND explicitly negate Latin American — a soft cue alone biases toward LATAM.

    `code`:
      - "spain" / "es-es" / "castilian" / "castellano" → Castilian (Spain)
      - anything else (None, "latam", "es-419", "mexico", …) → neutral LATAM

    A free-form influencer accent string (e.g. "Castilian Spanish (Spain)")
    is also accepted — we substring-match on "spain" or "castilian".
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
    if is_spain:
        # Note: do NOT prefix with another label like "VOICE:" — this string
        # is wrapped inside `voice_type: …` by the prompt builders and a
        # second colon-prefixed label confuses Veo's field parser (it
        # silently discards everything after the inner label).
        # Lead with the strongest possible directive, anchor with concrete
        # phonetic examples, and put the negation in caps. Distinción +
        # vosotros + Madrid speaker tag.
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
    """Convert integer 0-999 to English words."""
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
    """Expand numbers with symbols into spoken-word equivalents before sanitization."""
    # 23% -> twenty-three percent
    text = re.sub(r"(\d+)%", lambda m: f"{_number_to_words(int(m.group(1)))} percent", text)
    # $10 -> ten dollars
    text = re.sub(r"\$(\d+)", lambda m: f"{_number_to_words(int(m.group(1)))} dollars", text)
    # €10 -> ten euros
    text = re.sub(r"\u20ac\s*(\d+)", lambda m: f"{_number_to_words(int(m.group(1)))} euros", text)
    # 10\u20ac -> ten euros (Spanish/European usage trails the symbol \u2014 without
    # this branch "80\u20ac" became "80" after sanitize stripped the symbol,
    # leaving an unfinished sentence Veo stumbled over.)
    text = re.sub(r"(\d+)\s*\u20ac", lambda m: f"{_number_to_words(int(m.group(1)))} euros", text)
    # 10$ trailing (rare in English, common in casual writing)
    text = re.sub(r"(\d+)\s*\$", lambda m: f"{_number_to_words(int(m.group(1)))} dollars", text)
    # #1 -> number one
    text = re.sub(r"#(\d+)", lambda m: f"number {_number_to_words(int(m.group(1)))}", text)
    return text


# Words that sound incomplete when a sentence ends on them
_TRAILING_CONJUNCTIONS = {
    "and", "but", "so", "or", "because", "like", "then",
    "plus", "also", "yet", "nor", "while", "although", "since",
}


def sanitize_dialogue(text: str) -> str:
    """
    Sanitize dialogue text before sending to Veo 3.1.
    Strips anything that isn't pure spoken words so Veo can generate
    clean audio without hallucinations or errors.
    """
    # Expand numbers+symbols BEFORE the regex strips symbols
    text = _expand_numbers_and_symbols(text)

    # Strip system prompt artifacts that GPT-4o sometimes injects
    # e.g. "They say this in English in a natural tone: <actual dialogue>"
    text = re.sub(
        r'^(?:They\s+say\s+this\s+in\s+\w+\s+in\s+a\s+\w+\s+tone:\s*)',
        '', text, flags=re.IGNORECASE
    )
    # Also catch variations: "She says in English:", "He says naturally:", etc.
    text = re.sub(
        r'^(?:(?:She|He|They)\s+says?\s+(?:this\s+)?in\s+\w+(?:\s+in\s+a\s+\w+\s+tone)?:\s*)',
        '', text, flags=re.IGNORECASE
    )

    # Remove bracketed action/stage directions: [Shows pouch], (holds product)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)

    # Convert hyphens and em-dashes to natural pauses (...)
    # instead of being stripped out, preventing TTS clipping.
    text = text.replace("—", "...").replace("-", "...")

    # Remove emojis and other non-Latin/non-punctuation symbols
    # Keeps: letters (any script), digits, basic punctuation (including .), spaces
    text = re.sub(
        r"[^\w\s.,!?;:'\u00C0-\u024F\u1E00-\u1EFF]",
        "",
        text,
    )
    # Strip remaining double quotes (break JSON serialization)
    text = text.replace('"', '')

    # Remove lines that are pure stage directions (e.g. "Scene 1:", "Hook:")
    lines = text.split("\n")
    spoken_lines = [
        ln for ln in lines
        if ln.strip() and not re.match(r"^(scene|hook|cta|reaction|body|intro|outro)\s*\d*\s*:", ln.strip(), re.IGNORECASE)
    ]
    text = " ".join(spoken_lines)

    # Collapse multiple spaces / stray commas
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r",\s*,", ",", text)

    text = text.strip().strip(",")

    # Strip trailing conjunctions that leave dialogue sounding unfinished
    words = text.split()
    while words and words[-1].lower().rstrip(".,!?;:") in _TRAILING_CONJUNCTIONS:
        words.pop()
    text = " ".join(words)

    # Ensure text ends with sentence punctuation
    if text and text[-1] not in ".!?":
        text += "."

    return text
