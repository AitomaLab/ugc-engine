import os
import time
from openai import OpenAI
from pathlib import Path

class TranscriptionClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY not found. Transcription will fail.")
        self.client = OpenAI(api_key=self.api_key)

    def transcribe_audio(self, file_path: str) -> dict:
        """
        Transcribe audio file using OpenAI Whisper to get word-level timestamps.
        
        Args:
            file_path: Absolute path to the audio file (mp3/wav/etc)
            
        Returns:
            Dictionary with transcription data, including 'words' list with timestamps.
            Returns None if transcription fails.
        """
        if not self.api_key:
            print("❌ Cannot transcribe: No API Key")
            return None
            
        if not Path(file_path).exists():
            print(f"❌ Cannot transcribe: File not found {file_path}")
            return None

        print(f"      🎙️ Transcribing audio with Whisper: {Path(file_path).name}...")
        
        try:
            with open(file_path, "rb") as audio_file:
                # Use verbose_json to get timestamp_granularity="word"
                # Note: 'timestamp_granularity' param is supported in recent API versions
                # If using generic transcription, we might need to rely on segment level or 'word' level if available
                response = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    response_format="verbose_json",
                    timestamp_granularity="word" 
                )
                
            # Response is a TranscriptionVerboseJson object (pydantic model in recent SDKs)
            # We access .words directly
            # It has .text, .segments, .words
            
            # Extract words with start/end
            # The SDK might return an object, let's look at attributes or dict
            if hasattr(response, 'words'):
                words = response.words
            elif isinstance(response, dict):
                words = response.get('words', [])
            else:
                # Fallback check
                words = getattr(response, 'words', [])

            print(f"      ✅ Transcription complete: {len(words)} words found.")
            return {"words": words, "text": response.text}

        except Exception as e:
            print(f"      ❌ Transcription failed: {e}")
            return None
