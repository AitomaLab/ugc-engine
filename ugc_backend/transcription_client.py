import os
import time
from openai import OpenAI
from pathlib import Path
import re
from difflib import SequenceMatcher

class TranscriptionClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("!! OPENAI_API_KEY not found. Transcription will fail.")
        self.client = OpenAI(api_key=self.api_key)

    def transcribe_audio(
        self,
        file_path: str,
        brand_names: list = None,
        script_prompt: str = None,
        language: str = None,
    ) -> dict:
        """
        Transcribe audio file using OpenAI Whisper to get word-level timestamps.

        Args:
            file_path: Absolute path to the audio file (mp3/wav/etc)
            brand_names: Optional list of brand/product names for correct spelling
            script_prompt: Optional full script text. Used as Whisper's `prompt` to
                bias decoding toward every word of the known dialogue — dramatically
                reduces gaps in word-level timestamps when audio is ducked/noisy.
            language: Optional ISO-639-1 language code (e.g. "en", "es") to skip
                Whisper's language detection and improve segmentation accuracy.

        Returns:
            Dictionary with transcription data, including 'words' list with timestamps.
            Returns None if transcription fails.
        """
        if not self.api_key:
            print("[FAIL] Cannot transcribe: No API Key")
            return None

        if not Path(file_path).exists():
            print(f"[FAIL] Cannot transcribe: File not found {file_path}")
            return None

        print(f"      [MIC] Transcribing audio with Whisper: {Path(file_path).name}...")

        try:
            with open(file_path, "rb") as audio_file:
                kwargs = {
                    "model": "whisper-1",
                    "file": audio_file,
                    "response_format": "verbose_json",
                    "timestamp_granularities": ["word"],
                }
                # Whisper's `prompt` param maxes at 224 tokens — trim from the end
                # to keep the full opening of the script (Whisper biases decoding
                # toward the prompt vocabulary, so sentence boundaries matter less
                # than covering the unique words in the script).
                prompt_parts = []
                if script_prompt:
                    # ~4 chars/token for English-ish text; 224 tokens ≈ 900 chars
                    prompt_parts.append(script_prompt.strip()[:900])
                if brand_names:
                    prompt_parts.append(f"Brand names mentioned: {', '.join(brand_names)}.")
                if prompt_parts:
                    kwargs["prompt"] = " ".join(prompt_parts)
                    if script_prompt:
                        print(f"      [SCRIPT] Guiding Whisper with {len(script_prompt.split())}-word script prompt")
                    if brand_names:
                        print(f"      [BRAND] Guiding Whisper with brand names: {brand_names}")
                if language:
                    kwargs["language"] = language
                    print(f"      [LANG] Forcing Whisper language: {language}")
                
                response = self.client.audio.transcriptions.create(**kwargs)
                
            # Extract words with start/end
            if hasattr(response, 'words'):
                words = response.words
            elif isinstance(response, dict):
                words = response.get('words', [])
            else:
                words = getattr(response, 'words', [])

            # Post-process: fix misspelled brand names in word-level data
            if brand_names and words:
                for w in words:
                    word_text = (w.word if hasattr(w, 'word') else w.get('word', '')).strip()
                    stripped = re.sub(r'[^\w]', '', word_text)
                    if not stripped or len(stripped) < 3:
                        continue
                    for brand in brand_names:
                        ratio = SequenceMatcher(None, stripped.lower(), brand.lower()).ratio()
                        if ratio >= 0.7 and abs(len(stripped) - len(brand)) <= 3:
                            if stripped.lower() != brand.lower():
                                print(f"      [BRAND FIX] '{stripped}' → '{brand}'")
                                if hasattr(w, 'word'):
                                    w.word = w.word.replace(stripped, brand)
                                else:
                                    w['word'] = w.get('word', '').replace(stripped, brand)
                                break

            # Convert Pydantic TranscriptionWord objects to plain dicts for JSON serialization
            words_plain = []
            for w in words:
                if hasattr(w, 'model_dump'):
                    words_plain.append(w.model_dump())
                elif isinstance(w, dict):
                    words_plain.append(w)
                else:
                    words_plain.append({"word": str(getattr(w, 'word', '')), "start": getattr(w, 'start', 0), "end": getattr(w, 'end', 0)})

            print(f"      [OK] Transcription complete: {len(words_plain)} words found.")
            return {"words": words_plain, "text": response.text}

        except Exception as e:
            print(f"      [FAIL] Transcription failed: {e}")
            return None
