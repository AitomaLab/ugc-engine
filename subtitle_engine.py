"""
Naiara Content Distribution Engine — Subtitle Engine

Generates Hormozi-style subtitles as ASS (Advanced SubStation Alpha) files.
These get burned into the video by FFmpeg during assembly.

Style: Big, bold, centered, word-by-word with power-word highlighting.
"""
import re
from pathlib import Path
import subprocess
import json
from difflib import SequenceMatcher
from openai import OpenAI
import os


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


def _correct_brand_in_text(text, brand_names):
    """
    Fix misspelled brand/product names in transcribed text.
    Uses fuzzy matching to catch common Whisper mistakes like
    'Phoebus' instead of 'Phebus', 'Naira' instead of 'Naiara', etc.
    """
    if not brand_names:
        return text

    words = text.split()
    corrected = []
    for word in words:
        # Strip punctuation for comparison, preserve it for output
        stripped = re.sub(r'[^\w]', '', word)
        if not stripped:
            corrected.append(word)
            continue

        best_match = None
        best_ratio = 0.0
        for brand in brand_names:
            # Compare case-insensitively
            ratio = SequenceMatcher(None, stripped.lower(), brand.lower()).ratio()
            # Threshold: 0.7 means ~70% similar (catches Phoebus/Phebus, Naira/Naiara)
            # But only if the lengths are somewhat similar (avoid matching short words)
            if ratio >= 0.7 and len(stripped) >= 3 and abs(len(stripped) - len(brand)) <= 3:
                if ratio > best_ratio and stripped.lower() != brand.lower():
                    best_ratio = ratio
                    best_match = brand

        if best_match:
            # Preserve any surrounding punctuation from the original word
            prefix = ''
            suffix = ''
            m = re.match(r'^([^\w]*)(\w+)([^\w]*)$', word)
            if m:
                prefix, _, suffix = m.groups()
            corrected.append(f"{prefix}{best_match}{suffix}")
            print(f"      [BRAND FIX] '{stripped}' → '{best_match}'")
        else:
            corrected.append(word)

    return " ".join(corrected)


def _correct_brand_in_words(words_list, brand_names):
    """
    Fix misspelled brand names in Whisper's word-level output.
    Modifies the 'word' field of each word dict in place.
    """
    if not brand_names or not words_list:
        return words_list

    for w in words_list:
        original = w.get("word", "").strip()
        stripped = re.sub(r'[^\w]', '', original)
        if not stripped or len(stripped) < 3:
            continue

        for brand in brand_names:
            ratio = SequenceMatcher(None, stripped.lower(), brand.lower()).ratio()
            if ratio >= 0.7 and abs(len(stripped) - len(brand)) <= 3:
                if stripped.lower() != brand.lower():
                    print(f"      [BRAND FIX] '{stripped}' → '{brand}'")
                    # Preserve leading/trailing whitespace from original
                    w["word"] = original.replace(stripped, brand)
                    break
    return words_list


def _restore_numbers_in_words(words_list, original_script):
    """Replace spelled-out number sequences in Whisper output with the original
    numeric forms from the script (e.g. 'three hundred sixteen thousand ...' → '$316,897').

    This is needed because elevenlabs_client preprocesses numbers to spoken form
    for better TTS, but subtitles should display the original numbers.
    """
    if not words_list or not original_script:
        return words_list

    import re as _re
    from elevenlabs_client import _preprocess_for_tts

    # Build a mapping: spoken form → original form
    # Find all numbers/currencies/percentages in the original script
    number_patterns = [
        _re.compile(r'[$€]\s?[\d,]+(?:\.[\d]{1,2})?'),   # $316,897.50
        _re.compile(r'[\d,]+(?:\.[\d]+)?\s*%'),            # 216.90%
        _re.compile(r'[\d,]{4,}'),                          # 1,000,000
    ]

    replacements = []  # list of (spoken_words_list, original_text)
    for pattern in number_patterns:
        for match in pattern.finditer(original_script):
            original = match.group(0)
            spoken = _preprocess_for_tts(original).strip()
            spoken_words = spoken.lower().split()
            if spoken_words and spoken.lower() != original.lower():
                replacements.append((spoken_words, original))

    if not replacements:
        return words_list

    # Sort by longest spoken form first (greedy matching)
    replacements.sort(key=lambda x: len(x[0]), reverse=True)

    # Scan through words_list and replace matching sequences
    result = []
    i = 0
    while i < len(words_list):
        matched = False
        for spoken_words, original_text in replacements:
            seq_len = len(spoken_words)
            if i + seq_len <= len(words_list):
                # Check if the next N words match the spoken form
                candidate = [words_list[j]["word"].strip().lower().rstrip(".,!?;:") for j in range(i, i + seq_len)]
                if candidate == spoken_words:
                    # Replace: keep the timing of first and last word, merge into one word
                    merged = dict(words_list[i])  # copy first word's data
                    merged["word"] = original_text
                    merged["end"] = words_list[i + seq_len - 1]["end"]
                    result.append(merged)
                    i += seq_len
                    matched = True
                    print(f"      [NUM FIX] '{' '.join(candidate)}' → '{original_text}'")
                    break
        if not matched:
            result.append(words_list[i])
            i += 1

    return result


def extract_transcription_with_whisper(video_path, brand_names=None, script_text=None):
    """
    Extracts word-level timestamps using the OpenAI Whisper API.
    
    Args:
        video_path: Path to the video file
        brand_names: Optional list of brand/product names to guide Whisper spelling
        script_text: Optional known script text to guide Whisper accuracy
    """
    try:
        print(f"   🎤 Extracting audio and transcribing with Whisper API...")
        audio_path = Path(video_path).parent / f"{Path(video_path).stem}.mp3"
        ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(video_path), "-q:a", "0", "-map", "a", str(audio_path)]
        subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Build Whisper prompt with script text + brand names for maximum accuracy
        prompt_parts = []
        if script_text:
            prompt_parts.append(script_text)
            print(f"      [PROMPT] Guiding Whisper with full script text")
        if brand_names:
            prompt_parts.append(f"Brand names mentioned: {', '.join(brand_names)}.")
            print(f"      [BRAND] Guiding Whisper with: {brand_names}")
        
        whisper_prompt = " ".join(prompt_parts) if prompt_parts else None

        with open(audio_path, "rb") as audio_file:
            kwargs = {
                "model": "whisper-1",
                "file": audio_file,
                "response_format": "verbose_json",
                "timestamp_granularities": ["word"],
            }
            if whisper_prompt:
                kwargs["prompt"] = whisper_prompt
            response = client.audio.transcriptions.create(**kwargs)
        
        os.remove(audio_path)
        
        result = response.model_dump()
        
        # Post-process: fix any remaining brand misspellings in word-level data
        if brand_names and result and result.get("words"):
            _correct_brand_in_words(result["words"], brand_names)
        
        # Post-process: restore original numeric forms for subtitle display
        if script_text and result and result.get("words"):
            result["words"] = _restore_numbers_in_words(result["words"], script_text)
        
        print("   ✅ Whisper transcription successful.")
        return result
    except Exception as e:
        print(f"   ❌ Error during Whisper transcription: {e}")
        return None


def generate_subtitles_from_whisper(transcription, output_path, max_words=3, brand_names=None):
    """Generates an ASS subtitle file from a Whisper API verbose_json response."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_content = _build_ass_header()
    
    if not transcription or "words" not in transcription or not transcription["words"]:
        print("   ⚠️ No words found in transcription. Skipping subtitle generation.")
        with open(output_path, "w") as f: f.write(ass_content)
        return None

    all_words = transcription["words"]
    
    # Apply brand name corrections if not already done during extraction
    if brand_names:
        _correct_brand_in_words(all_words, brand_names)
    
    MAX_CHUNK_DURATION = 2.5  # seconds — Hormozi-style subtitles should flash quickly

    chunks = []
    for i in range(0, len(all_words), max_words):
        chunk_words = all_words[i:i + max_words]
        text = " ".join([word["word"].strip() for word in chunk_words])
        start_time = chunk_words[0]["start"]
        end_time = chunk_words[-1]["end"]
        # Cap duration to prevent long-lingering subtitles
        if end_time - start_time > MAX_CHUNK_DURATION:
            end_time = start_time + MAX_CHUNK_DURATION
        chunks.append({"text": text, "start": start_time, "end": end_time})

    # Shift first subtitle to start at 0.0s if it begins within 1.5s
    if chunks and chunks[0]["start"] > 0 and chunks[0]["start"] < 2.0:
        chunks[0]["start"] = 0.0

    for chunk in chunks:
        start = _format_ass_time(chunk["start"])
        end = _format_ass_time(chunk["end"])
        styled_chunk = _highlight_power_words(chunk["text"])
        ass_content += f"Dialogue: 0,{start},{end},Hormozi,,0,0,0,,{styled_chunk}\n"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    
    print(f"   🔤 Synchronized subtitles saved: {output_path}")
    return str(output_path)


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
        transcription = scene.get("transcription")

        if transcription and transcription.get("words"):
            # ✨ SYNCED LOGIC: Use Whisper timestamps
            words = transcription["words"]
            
            # Apply brand name corrections from scene data
            scene_brand_names = scene.get("brand_names", [])
            if scene_brand_names:
                _correct_brand_in_words(words, scene_brand_names)
            
            chunk_size = 3
            
            for i in range(0, len(words), chunk_size):
                chunk_words = words[i:i + chunk_size]
                
                # Timestamps relative to clip start -> offset by current_time
                start_time = chunk_words[0]["start"] + current_time
                end_time = chunk_words[-1]["end"] + current_time
                
                text_content = " ".join([w["word"] for w in chunk_words])
                
                # Formatting
                start = _format_ass_time(start_time)
                end = _format_ass_time(end_time)
                styled_chunk = _highlight_power_words(text_content)
                
                ass_content += (
                    f"Dialogue: 0,{start},{end},Hormozi,,0,0,0,,"
                    f"{styled_chunk}\n"
                )
            
            # Advance time by full duration of the clip (not just the last word)
            current_time += duration

        elif text:
            # 🕰️ LEGACY LOGIC: Dead reckoning
            chunks = _split_into_chunks(text, max_words=3)
            chunk_duration = duration / max(len(chunks), 1)

            for chunk in chunks:
                start = _format_ass_time(current_time)
                end = _format_ass_time(current_time + chunk_duration)
                styled_chunk = _highlight_power_words(chunk)

                ass_content += (
                    f"Dialogue: 0,{start},{end},Hormozi,,0,0,0,,"
                    f"{styled_chunk}\n"
                )
                current_time += chunk_duration
        else:
            # No text
            current_time += duration

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"   🔤 Subtitles saved: {output_path}")
    return str(output_path)


def generate_synced_subtitles(transcription_data, output_path):
    """
    Generate an ASS subtitle file from precise Whisper timestamps.
    
    Args:
        transcription_data: Dict with 'words' list from TranscriptionClient
        output_path: Where to save the .ass file
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ass_content = _build_ass_header()
    
    words = transcription_data.get("words", [])
    if not words:
        print("   ⚠️ No words found in transcription to subtitle.")
        return None

    # Hormozi style: Group words into small chunks (1-3 words)
    # But now we use exact start/end times from the words themselves.
    
    chunk_size = 3
    for i in range(0, len(words), chunk_size):
        chunk_words = words[i:i + chunk_size]
        
        # Start time of first word
        start_time = chunk_words[0]["start"]
        # End time of last word
        end_time = chunk_words[-1]["end"]
        
        # Build text string
        text_content = " ".join([w["word"] for w in chunk_words])
        
        start_str = _format_ass_time(start_time)
        end_str = _format_ass_time(end_time)
        
        # Apply power word highlighting
        styled_text = _highlight_power_words(text_content)
        
        ass_content += (
            f"Dialogue: 0,{start_str},{end_str},Hormozi,,0,0,0,,"
            f"{styled_text}\n"
        )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)

    print(f"   🔤 Synced Subtitles saved: {output_path}")
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
