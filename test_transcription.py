
import os
import sys
from dotenv import load_dotenv

# Load env
load_dotenv(".env")

try:
    from ugc_backend.transcription_client import TranscriptionClient
    print("✅ Imported TranscriptionClient")
except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)

def test_client():
    client = TranscriptionClient()
    if not client.api_key:
        print("❌ SKIPPING TEST: No OpenAI API Key found")
        return

    # Create dummy audio file if none exists
    # We can't easily create a valid audio file without libraries, 
    # so we'll just check if the client initializes and warns us.
    print("✅ Client initialized successfully")
    
    # Check if we have a sample audio file to test
    sample_audio = "sample_audio.mp3"
    if os.path.exists(sample_audio):
        print(f"🎙️ Testing transcription on {sample_audio}...")
        result = client.transcribe_audio(sample_audio)
        if result:
            print(f"✅ Transcription success: {len(result.get('words', []))} words")
            print(f"   Text: {result.get('text', '')[:50]}...")
        else:
            print("❌ Transcription returned None")
    else:
        print("ℹ️ No sample_audio.mp3 found, skipping actual API call test.")

if __name__ == "__main__":
    test_client()
