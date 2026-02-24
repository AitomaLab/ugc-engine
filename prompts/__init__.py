"""
Initializer for prompts module.
"""
import re


def sanitize_dialogue(text: str) -> str:
    """
    Sanitize dialogue text before sending to Veo 3.1.
    Strips anything that isn't pure spoken words so Veo can generate
    clean audio without hallucinations or errors.
    """
    # Remove bracketed action/stage directions: [Shows pouch], (holds product)
    text = re.sub(r"\[.*?\]", "", text)
    text = re.sub(r"\(.*?\)", "", text)

    # Remove emojis and other non-Latin/non-punctuation symbols
    # Keeps: letters (any script), digits, basic punctuation, spaces
    text = re.sub(
        r"[^\w\s.,!?;:'\u00C0-\u024F\u1E00-\u1EFF-]",
        "",
        text,
    )

    # Replace '...' with comma (natural breath pause) before Veo hallucinates filler
    text = text.replace("...", ",")

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

    return text.strip().strip(",")
