"""
Generate Kling 3.0 animation preview clips for the Creative OS image-edit modal.

Each style can have its own source image (so e.g. 'tracking' uses a walking
person scene, 'pan' uses a wide cinematic landscape, etc.) and its own
Kling prompt. The source image is generated once per scene via NanoBanana
Pro and cached to References/inputs/preview_sources/.

Run:
  python scripts/generate_animation_previews.py

Edit STYLES_TO_GENERATE below to control which styles are produced.
"""
import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "env.saas", override=False)
load_dotenv(ROOT / ".env.saas", override=False)
load_dotenv(ROOT / "env", override=False)
load_dotenv(ROOT / ".env", override=False)

KIE_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
KIE_KEY = os.getenv("KIE_API_KEY")
if not KIE_KEY:
    print("ERROR: KIE_API_KEY not set. Check env.saas / .env.")
    sys.exit(1)

SOURCES_DIR = ROOT / "References" / "inputs" / "preview_sources"
SOURCES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT / "frontend" / "public" / "animation-previews"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Styles to (re)generate this run.
STYLES_TO_GENERATE = [
    "pan",
]

# Per-style scene + prompt. Each style has:
#   - source_scene: short id used for the cached source filename (multiple styles
#                   can share a scene to save credits)
#   - source_prompt: NanoBanana Pro prompt to generate that source image
#   - kling_prompt: prompt sent to Kling 3.0 along with the source image
STYLE_CONFIGS = {
    # ── Existing perfume bottle scene (already generated) ──
    "dolly_in": {
        "source_scene": "perfume_bottle",
        "source_prompt": "A premium glass perfume bottle resting on a circular marble plinth, neutral soft beige background, soft studio lighting from the upper-left, subtle reflections on the glass, ultra-detailed product photography, 9:16 vertical framing, 4K, cinematic depth of field, elegant minimalist composition.",
        "kling_prompt": "Camera slowly pushes forward toward the perfume bottle, smooth dolly-in, cinematic depth, soft studio lighting, realistic physics, elegant product shot.",
    },
    "dolly_out": {
        "source_scene": "perfume_bottle",
        "source_prompt": "",
        "kling_prompt": "Camera slowly pulls back away from the perfume bottle, smooth dolly-out, revealing the surrounding plinth, cinematic depth, soft studio lighting, elegant product shot.",
    },
    "orbit": {
        "source_scene": "perfume_bottle",
        "source_prompt": "",
        "kling_prompt": "Camera smoothly orbits 180 degrees around the perfume bottle on its plinth, circular tracking shot, perfectly stable arc, soft studio lighting, premium product showcase.",
    },
    "tilt": {
        "source_scene": "perfume_bottle",
        "source_prompt": "",
        "kling_prompt": "Camera slowly tilts upward starting from the base of the plinth and rising to reveal the perfume bottle, smooth vertical pivot, soft studio lighting.",
    },
    "crane": {
        "source_scene": "perfume_bottle",
        "source_prompt": "",
        "kling_prompt": "Camera rises from low angle to a high overhead view of the perfume bottle on its plinth, smooth crane lift, cinematic depth, soft studio lighting.",
    },
    "static": {
        "source_scene": "perfume_bottle",
        "source_prompt": "",
        "kling_prompt": "Locked-off camera, fixed framing of the perfume bottle on its plinth, only subtle ambient motion in the lighting, premium product still life.",
    },

    # ── NEW: bespoke scenes that actually showcase each camera move ──
    "tracking": {
        "source_scene": "walking_woman_street",
        "source_prompt": "A young woman walking confidently along a sunlit European city sidewalk, full body shot from the side, fashion magazine style, soft golden hour light, blurred shopfronts in background, cinematic 9:16 vertical framing, 4K.",
        "kling_prompt": "Smooth lateral tracking shot following the young woman walking from left to right along the sunlit sidewalk, perfectly synced to her pace, parallax background, cinematic depth, golden hour light, fashion editorial style.",
    },
    "pan": {
        "source_scene": "mountain_valley_panorama",
        "source_prompt": "Vertical portrait photograph, 9:16 aspect ratio, taller than wide, of a breathtaking mountain valley at golden hour. Snow-capped peaks rise on the right side of the frame, a winding river flows through the green valley floor in the center, dense pine forest on the left. Warm sunset light from the right casts long shadows. Ultra-detailed cinematic landscape, deep depth of field, 4K. The image MUST be in portrait orientation, taller than wide.",
        "kling_prompt": "Smooth horizontal camera pan from left to right across the mountain valley landscape, the camera rotates from a fixed position sweeping past the pine forest and revealing the snow-capped peaks, cinematic establishing shot, no forward movement, pure rotational pan, golden hour light.",
    },
    "handheld": {
        "source_scene": "ugc_influencer_bedroom",
        "source_prompt": "A young woman influencer holding a small skincare bottle up toward the camera in her aesthetic bedroom, soft natural window light from the side, plants and warm decor in the background, casual UGC selfie style, slightly imperfect framing, 9:16 vertical, 4K.",
        "kling_prompt": "Natural handheld smartphone camera with subtle organic shake and tiny drift, capturing the young influencer holding the skincare bottle to the camera, casual UGC vlog style, soft window lighting, authentic micro-movements, slightly imperfect framing.",
    },
    "reveal": {
        "source_scene": "covered_sports_car_garage",
        "source_prompt": "A luxury sports car covered with a flowing silk sheet inside a dimly lit private garage, single dramatic spotlight from above, dust particles floating in the light beam, mysterious cinematic mood, 9:16 vertical framing, 4K.",
        "kling_prompt": "Dramatic reveal as the silk sheet slides slowly off the luxury sports car, dust particles swirling in the spotlight, slow cinematic unveiling, the car's curves and headlights gradually emerging from beneath the silk, mysterious atmosphere.",
    },
    "float": {
        "source_scene": "woman_white_dress_field",
        "source_prompt": "A young woman in a flowing white dress standing in a sunlit field of tall wildflowers, dreamy ethereal mood, soft golden hour backlighting, lens flare, cinematic 9:16 vertical framing, 4K.",
        "kling_prompt": "Smooth floating dreamlike camera glides weightlessly in a gentle arc around the young woman in the white dress, the wildflowers gently sway, ethereal slow motion, cinematic depth, no shake at all, pure suspended motion.",
    },
    "drift": {
        "source_scene": "ocean_horizon_sailboat",
        "source_prompt": "A wide cinematic view of a calm ocean horizon at sunset, a single white sailboat in the distance, pastel pink and orange sky, glassy reflective water, peaceful meditative mood, 9:16 vertical framing, 4K.",
        "kling_prompt": "Subtle very slow lateral camera drift from right to left across the ocean horizon at sunset, the sailboat barely moving, calm meditative pacing, soft pastel light, no zoom or rotation, pure horizontal drift, cinematic establishing shot.",
    },
}


async def kie_create_task(payload: dict) -> str:
    headers = {"Authorization": f"Bearer {KIE_KEY}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=60.0) as http:
        resp = await http.post(f"{KIE_URL}/api/v1/jobs/createTask", headers=headers, json=payload)
        resp.raise_for_status()
        result = resp.json()
        if result.get("code") != 200:
            raise RuntimeError(f"KIE createTask error: {result}")
        return result["data"]["taskId"]


async def kie_poll(task_id: str, label: str, max_iters: int = 120) -> dict:
    headers = {"Authorization": f"Bearer {KIE_KEY}"}
    async with httpx.AsyncClient(timeout=30.0) as http:
        for i in range(max_iters):
            await asyncio.sleep(10)
            try:
                resp = await http.get(
                    f"{KIE_URL}/api/v1/jobs/recordInfo",
                    headers=headers,
                    params={"taskId": task_id},
                )
                data = resp.json()
            except Exception as e:
                print(f"  [{label}] poll error (continuing): {e}")
                continue

            if data.get("code") != 200:
                continue
            state = data.get("data", {}).get("state", "processing").lower()
            print(f"  [{label}] {state} ({(i + 1) * 10}s)")
            if state == "success":
                rj = data["data"].get("resultJson")
                if isinstance(rj, str):
                    rj = json.loads(rj)
                return rj or {}
            if state == "fail":
                raise RuntimeError(f"{label} failed: {data['data'].get('failMsg')}")
    raise RuntimeError(f"{label} timed out")


async def ensure_source_image(scene: str, prompt: str) -> Path:
    """Generate (or reuse cached) NanoBanana source image for a given scene."""
    cache_path = SOURCES_DIR / f"{scene}.png"
    if cache_path.exists():
        print(f"[scene:{scene}] using cached {cache_path.name}")
        return cache_path

    if not prompt:
        raise RuntimeError(f"No source_prompt for scene '{scene}' and no cached image at {cache_path}")

    print(f"[scene:{scene}] generating via NanoBanana Pro...")
    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "resolution": "4K",
        },
    }
    task_id = await kie_create_task(payload)
    print(f"[scene:{scene}] task: {task_id}")
    result = await kie_poll(task_id, f"scene:{scene}", max_iters=60)
    urls = result.get("resultUrls") or []
    if not urls:
        raise RuntimeError(f"NanoBanana returned no image: {result}")
    image_url = urls[0]

    async with httpx.AsyncClient(timeout=120.0) as http:
        resp = await http.get(image_url)
        resp.raise_for_status()
        cache_path.write_bytes(resp.content)
    print(f"[scene:{scene}] cached → {cache_path.name}")
    return cache_path


def upload_image(local_path: Path) -> str:
    """Upload a local file to Supabase storage and return its public URL."""
    sys.path.insert(0, str(ROOT))
    from storage_helper import upload_temporary_file
    return upload_temporary_file(str(local_path))


async def generate_one_preview(style: str, source_image_url: str, kling_prompt: str):
    print(f"\n[{style}] starting Kling animation...")
    payload = {
        "model": "kling-3.0/video",
        "input": {
            "prompt": kling_prompt,
            "image_urls": [source_image_url],
            "sound": False,
            "duration": "5",
            "aspect_ratio": "9:16",
            "mode": "std",
            "multi_shots": False,
            "multi_prompt": [],
        },
    }
    task_id = await kie_create_task(payload)
    print(f"[{style}] task: {task_id}")
    result = await kie_poll(task_id, style, max_iters=120)
    urls = result.get("resultUrls") or result.get("videos") or []
    if not urls:
        raise RuntimeError(f"[{style}] no video url in result: {result}")
    video_url = urls[0]
    print(f"[{style}] video url: {video_url[:80]}...")

    raw_path = OUTPUT_DIR / f"{style}_raw.mp4"
    async with httpx.AsyncClient(timeout=300.0) as http:
        resp = await http.get(video_url)
        resp.raise_for_status()
        raw_path.write_bytes(resp.content)
    print(f"[{style}] downloaded raw → {raw_path.name}")

    final_path = OUTPUT_DIR / f"{style}.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", str(raw_path),
        "-an",
        "-vf", "scale=320:-2",
        "-c:v", "libx264", "-preset", "slow", "-crf", "28",
        "-movflags", "+faststart",
        str(final_path),
    ]
    print(f"[{style}] transcoding...")
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raw_path.unlink()
    size_kb = final_path.stat().st_size // 1024
    print(f"[{style}] DONE → {final_path.name} ({size_kb} KB)")


async def main():
    # Group styles by their source scene so we only generate each scene once
    scenes_needed: dict[str, str] = {}
    for style in STYLES_TO_GENERATE:
        cfg = STYLE_CONFIGS[style]
        scene = cfg["source_scene"]
        if scene not in scenes_needed and cfg["source_prompt"]:
            scenes_needed[scene] = cfg["source_prompt"]
        elif scene not in scenes_needed:
            scenes_needed[scene] = ""  # Will require cache hit

    # Step 1: ensure all source images exist (generate if missing)
    print(f"[plan] {len(STYLES_TO_GENERATE)} styles using {len(scenes_needed)} unique scene(s)")
    scene_paths: dict[str, Path] = {}
    for scene, prompt in scenes_needed.items():
        scene_paths[scene] = await ensure_source_image(scene, prompt)

    # Step 2: upload each scene to Supabase once and get a public URL
    scene_urls: dict[str, str] = {}
    for scene, path in scene_paths.items():
        print(f"[scene:{scene}] uploading to Supabase...")
        scene_urls[scene] = upload_image(path)

    # Step 3: animate each style with its scene
    for style in STYLES_TO_GENERATE:
        cfg = STYLE_CONFIGS[style]
        try:
            await generate_one_preview(
                style,
                scene_urls[cfg["source_scene"]],
                cfg["kling_prompt"],
            )
        except Exception as e:
            print(f"[{style}] FAILED: {e}")

    print("\nAll done.")


if __name__ == "__main__":
    asyncio.run(main())
