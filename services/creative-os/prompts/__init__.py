"""
Creative OS — prompts module

Standalone version of the sanitize_dialogue utility from the repo-root
prompts package. Used by the UGC video pipeline to clean dialogue text
before sending to Veo/Seedance for speech generation.
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
