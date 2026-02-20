import os
import urllib.request
import zipfile
from pathlib import Path

def install_ffmpeg():
    print("Downloading FFmpeg...")
    url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    zip_path = "ffmpeg.zip"
    
    urllib.request.urlretrieve(url, zip_path)
    print("Download complete. Extracting...")
    
    venv_scripts = Path(".venv/Scripts")
    venv_scripts.mkdir(parents=True, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        for file_info in zip_ref.infolist():
            if file_info.filename.endswith("ffmpeg.exe"):
                # Extract specifically to .venv/Scripts
                file_info.filename = "ffmpeg.exe"
                zip_ref.extract(file_info, venv_scripts)
                print("Extracted ffmpeg.exe")
            elif file_info.filename.endswith("ffprobe.exe"):
                file_info.filename = "ffprobe.exe"
                zip_ref.extract(file_info, venv_scripts)
                print("Extracted ffprobe.exe")
                
    # Cleanup
    os.remove(zip_path)
    print("FFmpeg installation complete!")

if __name__ == "__main__":
    install_ffmpeg()
