"""
Initializer for prompts module.
"""
import re


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
    text = re.sub(r"\u20ac(\d+)", lambda m: f"{_number_to_words(int(m.group(1)))} euros", text)
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
