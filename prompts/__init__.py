"""
Initializer for prompts module.
"""
import re


# ---------------------------------------------------------------------------
# Spanish accent line for Veo voice_type (Spain vs Latin America)
# ---------------------------------------------------------------------------
def _detect_spain_from_text(text) -> bool:
    """Heuristic: does this text look like it was written by/for a Spain
    speaker? Used as a safety net when the explicit `language_accent`
    field is missing — we'd rather pick Castilian over LATAM when there
    are unambiguous Spain signals in the script itself.

    Triggers on:
      - € symbol (only Eurozone Spanish-speaking country is Spain)
      - vosotros / -áis / -éis verb conjugations (Spain-only)
      - Spain vocabulary: vale, móvil, ordenador, plátano, gilipollas,
        coche (LATAM uses "carro"), zumo (LATAM uses "jugo")
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
    # Conjugation suffixes that only appear in vosotros forms
    import re as _re
    if _re.search(r"\b\w+(áis|éis|íais|isteis)\b", t):
        return True
    return False


def spanish_accent_line(code, hint_text=None) -> str:
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
    # Detect explicit LATAM markers separately so we know whether to trust
    # the `code` field as a deliberate LATAM choice vs treating it as a
    # generic non-Spanish accent string ("neutral English") that should
    # NOT block the safety net.
    is_latam_explicit = any(w in norm for w in (
        "latam", "latin", "mexican", "colombian", "argentine",
        "argentino", "peruvian", "es-419",
    ))
    # Safety net: when there's no explicit Spain/LATAM marker (the
    # influencer's stored accent might just say "neutral English" or be
    # blank), fall back to detecting Spain signals from the script text
    # itself. Catches the very common case where the agent forgets to
    # forward language_accent OR the user typed Spain in prose without
    # clicking the picker. Earlier check `not norm` was too strict — it
    # only fired when the code arg was completely empty, but the call
    # site does `ctx.get('language_accent') or ctx.get('accent')` so the
    # arg is almost never empty.
    if not is_spain and not is_latam_explicit and _detect_spain_from_text(hint_text):
        is_spain = True
        print(f"      [spanish_accent_line] safety net fired: detected Spain from script text (code={code!r})")
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


def _looks_spanish(text: str) -> bool:
    """Cheap signal: does this text look like Spanish?

    We use this to skip the English-only number-to-words expansion below
    when running inside a Spanish dialogue — Veo pronounces "80 euros" or
    "80€" correctly in Spanish on its own, but if we expand to "eighty
    euros" inside Spanish text the model briefly switches language and
    the audio destabilizes.
    """
    if not text:
        return False
    t = str(text).lower()
    # Diacritics or ñ
    if any(ch in t for ch in "áéíóúñ¿¡"):
        return True
    # Common Spanish stop words / short markers
    spanish_markers = {
        " la ", " el ", " los ", " las ", " que ", " una ", " uno ",
        " para ", " con ", " sin ", " pero ", " esta ", " esto ", " esa ",
        " del ", " por ", " muy ", " más ", " mas ", " sin ",
    }
    padded = f" {t} "
    if any(m in padded for m in spanish_markers):
        return True
    return False


def _expand_numbers_and_symbols(text: str) -> str:
    """Expand numbers with symbols into spoken-word equivalents before sanitization.

    English-only by default. When the surrounding text looks Spanish
    (_looks_spanish), we localize currency symbols to the Spanish word
    ("80€" -> "80 euros") but leave digits intact — Veo pronounces digits
    correctly in Spanish on its own. Without this guard, calling the
    English expansion mid-Spanish-sentence injects "eighty euros", Veo
    briefly switches languages, and the audio destabilizes.
    """
    if _looks_spanish(text):
        text = re.sub(r"(\d+)\s*€", lambda m: f"{m.group(1)} euros", text)
        text = re.sub(r"€\s*(\d+)", lambda m: f"{m.group(1)} euros", text)
        text = re.sub(r"(\d+)\s*\$", lambda m: f"{m.group(1)} dólares", text)
        text = re.sub(r"\$\s*(\d+)", lambda m: f"{m.group(1)} dólares", text)
        text = re.sub(r"(\d+)\s*£", lambda m: f"{m.group(1)} libras", text)
        text = re.sub(r"£\s*(\d+)", lambda m: f"{m.group(1)} libras", text)
        text = re.sub(r"(\d+)\s*%", lambda m: f"{m.group(1)} por ciento", text)
        return text
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
