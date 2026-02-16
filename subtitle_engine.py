"""
Naiara Content Distribution Engine — Subtitle Engine

Generates Hormozi-style subtitles as ASS (Advanced SubStation Alpha) files.
These get burned into the video by FFmpeg during assembly.

Style: Big, bold, centered, word-by-word with power-word highlighting.
"""
import re
from pathlib import Path


# Pro UGC subtitle style constants (Alex Hormozi / Mr Beast style)
FONT_NAME = "Impact"           # Usually pre-installed on Windows
FONT_SIZE = 140                # Massive impact on 1080x1920
PRIMARY_COLOR = "&H0000FFFF"   # Yellow primary (Mr Beast style)
OUTLINE_COLOR = "&H00000000"   # Thick black outline
HIGHLIGHT_COLOR = "&H00FFFFFF" # White highlight for power words
SHADOW_COLOR = "&H80000000"    # Semi-transparent black shadow
OUTLINE_WIDTH = 8
SHADOW_DEPTH = 5
BOLD = -1                      # Bold

# Words that get highlighted in yellow (like Hormozi does)
POWER_WORDS = {
    "literally", "insane", "incredible", "amazing", "seriously",
    "actually", "never", "best", "perfect", "every", "entire",
    "changed", "life", "free", "now", "download", "need",
    "seconds", "fast", "easy", "simple", "just", "wow",
    "unbelievable", "mind-blowing", "game-changer", "instantly",
}


def _format_ass_time(seconds):
    """Convert seconds to ASS timestamp format (H:MM:SS.cc)."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int((seconds % 1) * 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _split_into_chunks(text, max_words=3):
    """
    Split text into display chunks of max_words each.
    Hormozi style shows 2-3 words at a time.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
        chunks.append(chunk)
    return chunks


def _highlight_power_words(text):
    """
    Apply yellow highlight to power words using ASS override tags.
    Returns text with inline ASS formatting.
    """
    words = text.split()
    result = []
    for word in words:
        clean = re.sub(r'[^\w]', '', word.lower())
        if clean in POWER_WORDS:
            # Yellow highlight + slightly bigger
            result.append(
                f"{{\\c{HIGHLIGHT_COLOR}\\fscx130\\fscy130}}{word}"
                f"{{\\c{PRIMARY_COLOR}\\fscx100\\fscy100}}"
            )
        else:
            result.append(word)
    return " ".join(result)


def generate_subtitles(scenes, output_path):
    """
    Generate an ASS subtitle file from scene subtitle texts.

    Args:
        scenes: List of scene dicts (each has 'subtitle_text' and 'target_duration')
        output_path: Where to save the .ass file

    Returns:
        Path to the generated ASS file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build ASS header
    ass_content = _build_ass_header()

    # Build dialogue lines
    current_time = 0.0

    for scene in scenes:
        text = scene.get("subtitle_text", "").strip()
        duration = scene["target_duration"]

        if not text:
            # No subtitles for this scene (e.g., app demo)
            current_time += duration
            continue

        # Split into chunks shown sequentially
        chunks = _split_into_chunks(text, max_words=3)
        chunk_duration = duration / max(len(chunks), 1)

        for chunk in chunks:
            start = _format_ass_time(current_time)
            end = _format_ass_time(current_time + chunk_duration)

            # Apply power word highlighting
            styled_chunk = _highlight_power_words(chunk)

            # Add dialogue line
            ass_content += (
                f"Dialogue: 0,{start},{end},Hormozi,,0,0,0,,"
                f"{styled_chunk}\n"
            )

            current_time += chunk_duration

        # If no chunks but had text, still advance time
        if not chunks:
            current_time += duration

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"   🔤 Subtitles saved: {output_path}")
    return str(output_path)


def _build_ass_header():
    """Build the ASS file header with Hormozi-style formatting."""
    return f"""[Script Info]
Title: Naiara UGC Subtitles
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Hormozi,{FONT_NAME},{FONT_SIZE},{PRIMARY_COLOR},&H000000FF,{OUTLINE_COLOR},{SHADOW_COLOR},{BOLD},0,0,0,100,100,1,0,1,{OUTLINE_WIDTH},{SHADOW_DEPTH},5,40,40,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        # Get test text from args
        test_text = "This app planned my entire trip in 30 seconds"
        for i, arg in enumerate(sys.argv):
            if arg == "--test" and i + 1 < len(sys.argv):
                test_text = sys.argv[i + 1]

        mock_scenes = [
            {
                "name": "hook",
                "subtitle_text": test_text,
                "target_duration": 3,
            },
            {
                "name": "app_demo",
                "subtitle_text": "",
                "target_duration": 4,
            },
            {
                "name": "reaction",
                "subtitle_text": "It literally planned my whole itinerary in seconds!",
                "target_duration": 4,
            },
            {
                "name": "cta",
                "subtitle_text": "Download Naiara now, link in bio!",
                "target_duration": 4,
            },
        ]

        output = Path("temp/test_subtitles.ass")
        generate_subtitles(mock_scenes, output)

        # Display the file
        print(f"\n📄 Generated ASS file:")
        print("-" * 50)
        with open(output, "r") as f:
            print(f.read())
    else:
        print('Usage: python subtitle_engine.py --test "Your hook text here"')
