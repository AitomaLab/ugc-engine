"""
Vision Analysis for Cinematic Transition Shots.

Analyzes the final frame of a UGC video scene to extract visual context
(framing, camera angle, lighting) for generating seamless transition shots.
"""

import os
import json
import subprocess
from openai import OpenAI


def extract_last_frame(video_path: str, output_path: str) -> str:
    """
    Extracts the final frame of a video file using FFmpeg.

    Args:
        video_path: Path to the input video file.
        output_path: Path where the extracted frame image will be saved.

    Returns:
        The output_path on success.

    Raises:
        RuntimeError: If FFmpeg extraction fails.
    """
    cmd = [
        "ffmpeg", "-y",
        "-sseof", "-0.1",       # Seek to 0.1s before end
        "-i", str(video_path),
        "-frames:v", "1",       # Extract exactly 1 frame
        "-q:v", "2",            # High quality JPEG
        str(output_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"FFmpeg frame extraction failed: {result.stderr[:300]}")
    return output_path


def analyze_ugc_frame(image_url_or_path: str) -> dict:
    """
    Analyzes a UGC video frame using GPT-4o Vision to extract visual context
    for generating a matching cinematic transition shot.

    Args:
        image_url_or_path: A public URL or local file path to the frame image.

    Returns:
        A dict with keys:
          - product_bounding_box: [x1, y1, x2, y2] approximate normalized coords
          - product_framing_style: e.g. 'close_up', 'medium_shot', 'wide_shot'
          - camera_angle: e.g. 'eye_level', 'low_angle', 'high_angle'
          - lighting_description: e.g. 'soft natural light from the left'
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set. Returning default analysis.")
        return _default_analysis()

    client = OpenAI(api_key=api_key)

    # Determine if input is a URL or local file
    if image_url_or_path.startswith("http"):
        image_content = {
            "type": "image_url",
            "image_url": {"url": image_url_or_path, "detail": "high"},
        }
    else:
        import base64
        with open(image_url_or_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = image_url_or_path.rsplit(".", 1)[-1].lower()
        mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png"}.get(ext, "image/jpeg")
        image_content = {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
        }

    prompt_text = """Analyze this video frame of a person holding or presenting a product.
Return ONLY a JSON object (no markdown, no explanation) with these exact keys:

{
  "product_bounding_box": [x1, y1, x2, y2],
  "product_framing_style": "close_up|medium_shot|wide_shot",
  "camera_angle": "eye_level|low_angle|high_angle",
  "lighting_description": "describe the lighting direction, quality, and color temperature"
}

Rules:
- product_bounding_box: Normalized coordinates (0.0-1.0) of the product's position in the frame.
- product_framing_style: How much of the frame the product occupies.
- camera_angle: The vertical angle of the camera relative to the subject.
- lighting_description: A concise phrase describing the scene's lighting."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt_text},
                        image_content,
                    ],
                }
            ],
            max_tokens=300,
        )

        content = response.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if content.startswith("```"):
            content = content.split("\n", 1)[1] if "\n" in content else content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        return json.loads(content)

    except Exception as e:
        print(f"Vision analysis failed: {e}. Using defaults.")
        return _default_analysis()


def _default_analysis() -> dict:
    """Fallback analysis when GPT-4o is unavailable."""
    return {
        "product_bounding_box": [0.3, 0.3, 0.7, 0.7],
        "product_framing_style": "medium_shot",
        "camera_angle": "eye_level",
        "lighting_description": "soft natural light from the front",
    }
