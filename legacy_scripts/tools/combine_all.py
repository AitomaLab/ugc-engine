"""
Combine video clips and add music using FFmpeg
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path


def combine_videos(video_files, output_path, music_path=None):
    """
    Combine multiple video clips into one final video.
    Optionally adds background music with fade-out.
    
    Args:
        video_files: List of video file paths (in order)
        output_path: Where to save the final video
        music_path: Optional path to music file to overlay
    
    Returns:
        Path to the output file
    """
    print("📹 Combining videos...")
    print(f"   Input clips: {len(video_files)}")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Create file list for FFmpeg concat
    list_file = output_path.parent / "videos.txt"
    with open(list_file, "w") as f:
        for video in video_files:
            # Use absolute paths and escape for FFmpeg
            abs_path = str(Path(video).absolute()).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
    
    # Concatenate videos
    combined = output_path.parent / "combined_temp.mp4"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-c", "copy",
        str(combined)
    ]
    
    print("   Running FFmpeg concat...")
    result = subprocess.run(concat_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"   ⚠️ FFmpeg error: {result.stderr[:200]}")
        # Cleanup
        if list_file.exists():
            list_file.unlink()
        return None
    
    print("   ✅ Videos combined!")
    
    # Add music if provided
    if music_path and os.path.exists(music_path):
        print("🎵 Adding music overlay...")
        
        # Calculate fade out point (total duration - 2 seconds)
        # Estimate: 5 seconds per clip
        estimated_duration = len(video_files) * 5
        fade_start = max(estimated_duration - 2, 1)
        
        music_cmd = [
            "ffmpeg", "-y",
            "-i", str(combined),
            "-i", str(music_path),
            "-filter_complex", f"[1:a]afade=t=out:st={fade_start}:d=2[a]",
            "-map", "0:v",
            "-map", "[a]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-shortest",
            str(output_path)
        ]
        
        result = subprocess.run(music_cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"   ⚠️ Music overlay failed: {result.stderr[:200]}")
            # Fall back to video without music
            shutil.copy(str(combined), str(output_path))
        else:
            print("   ✅ Music added!")
    else:
        # No music, just rename the combined file
        shutil.copy(str(combined), str(output_path))
        print("   ✅ Video ready (no music)")
    
    # Cleanup temp files
    if list_file.exists():
        list_file.unlink()
    if combined.exists():
        combined.unlink()
    
    print(f"   💾 Final video: {output_path}")
    return output_path


if __name__ == "__main__":
    print("This script is meant to be imported and used by other scripts.")
    print("Functions available:")
    print("  - combine_videos(video_files, output_path, music_path=None)")
    print("")
    print("Example usage:")
    print("  from combine_all import combine_videos")
    print("  combine_videos(['scene1.mp4', 'scene2.mp4'], 'final.mp4', 'music.mp3')")
