"""
Wrapper to analyze UGCvideo1.mp4 for the Naiara project
"""
import sys
sys.path.append('tools')
from pathlib import Path
from analyze_video import analyze_video

# Analyze the UGC video
video_path = Path("inputs/project3 - naiara/UGCvideo1.mp4")
output_path = Path("inputs/project3 - naiara/analysis.txt")

print("🎬 Analyzing UGCvideo1.mp4 for Naiara App Clone")
print("=" * 60)

analysis = analyze_video(str(video_path), str(output_path))

print("\n" + "=" * 60)
print("✅ Analysis complete!")
print(f"📄 Results saved to: {output_path}")
