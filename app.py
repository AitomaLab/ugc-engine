import os
import shutil
import platform
from dotenv import load_dotenv

# Load SaaS production environment if present
load_dotenv(".env.saas")
import sys
from pathlib import Path

# Force the project root into the path
root_dir = str(Path(__file__).parent.absolute())
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from ugc_backend.main import app

def validate_dependencies():
    """Validate that all required external dependencies are available."""
    print("\n🔎 Validating external dependencies...")
    system = platform.system()
    
    if not shutil.which("ffmpeg"):
        error_msg = (
            "❌ CRITICAL: FFmpeg not found in PATH.\n"
            "   Please install FFmpeg and add it to your system PATH.\n"
            "   Download: https://ffmpeg.org/download.html\n"
            "   Windows Installation Guide: https://www.wikihow.com/Install-FFmpeg-on-Windows"
        )
        print(error_msg)
        raise RuntimeError(error_msg)
    
    if not shutil.which("ffprobe"):
        error_msg = (
            "❌ CRITICAL: FFprobe not found in PATH.\n"
            "   FFprobe is included with FFmpeg. Ensure the bin directory is in your PATH."
        )
        print(error_msg)
        raise RuntimeError(error_msg)
    
    print(f"   ✅ FFmpeg and FFprobe validated (Platform: {system})")

if __name__ == "__main__":
    import uvicorn
    # ✨ NEW: Validate dependencies at startup
    validate_dependencies()
    
    # Use the port provided by Railway or fallback to 8000
    port = int(os.environ.get("PORT", 8000))
    # Enable reload for better development experience
    uvicorn.run("ugc_backend.main:app", host="0.0.0.0", port=port, reload=True)
