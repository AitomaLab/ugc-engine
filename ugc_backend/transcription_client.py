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

    def transcribe_audio(self, file_path: str, brand_names: list = None) -> dict:
        """
        Transcribe audio file using OpenAI Whisper to get word-level timestamps.
        
        Args:
            file_path: Absolute path to the audio file (mp3/wav/etc)
            brand_names: Optional list of brand/product names for correct spelling
            
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
                # Use brand names as Whisper prompt to guide correct spelling
                if brand_names:
                    kwargs["prompt"] = f"Brand names mentioned: {', '.join(brand_names)}."
                    print(f"      [BRAND] Guiding Whisper with brand names: {brand_names}")
                
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

            print(f"      [OK] Transcription complete: {len(words)} words found.")
            return {"words": words, "text": response.text}

        except Exception as e:
            print(f"      [FAIL] Transcription failed: {e}")
            return None
