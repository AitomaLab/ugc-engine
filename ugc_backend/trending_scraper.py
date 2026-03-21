"""
UGC Engine — Trending Script Scraper

Background job that uses GPT-4o to generate trending UGC script patterns
based on current best practices and proven ad formulas.

Triggered via POST /api/scripts/find-trending.
"""
import json
import os
import traceback
from typing import List, Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None  # type: ignore


def scrape_trending_scripts(
    topic: str = "UGC ads",
    sources: List[str] | None = None,
    max_scripts: int = 5,
) -> List[Dict[str, Any]]:
    """Generate trending script patterns using GPT-4o.

    Uses the LLM as a creative strategist to produce realistic, diverse
    trending-style scripts based on proven UGC ad formulas for the
    given topic/niche.

    Args:
        topic: The topic/niche to generate trending scripts for.
        sources: Optional list of source types (for context in the prompt).
        max_scripts: Maximum number of scripts to generate.

    Returns:
        A list of script_json dicts ready for database insertion.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("      [Trending] OPENAI_API_KEY not set, returning empty list.")
        return []
    if not OpenAI:
        print("      [Trending] OpenAI package not installed, returning empty list.")
        return []

    client = OpenAI(api_key=api_key)

    # Build source context for the prompt
    source_context = ""
    if sources and len(sources) > 0:
        source_names = {
            "tiktok": "TikTok Ads Library",
            "instagram": "Instagram Reels",
            "youtube": "YouTube Shorts",
            "blogs": "Ad Intelligence Blogs (Motion, Foreplay, AdSpy)",
        }
        source_labels = [source_names.get(s, s) for s in sources]
        source_context = f"\nBase your scripts on the styles trending on: {', '.join(source_labels)}."

    system_prompt = f"""You are a senior UGC ad script analyst who studies high-performing ads across TikTok, Instagram Reels, and YouTube Shorts. Your job is to generate {max_scripts} trending UGC ad script patterns for the niche: "{topic}".{source_context}

CRITICAL RULES:
1. Each script MUST use a DIFFERENT marketing methodology from this list:
   - Problem/Agitate/Solve
   - Hook/Benefit/CTA
   - Contrarian/Shock
   - Social Proof
   - Aspiration/Dream
   - Curiosity/Cliffhanger

2. Each script has exactly 2 scenes (for a ~15 second video).
   - Scene 1 is the HOOK (~17 words, ~7 seconds of speaking)
   - Scene 2 is the BENEFIT/CTA (~17 words, ~7 seconds of speaking)

3. Language rules:
   - Use contractions naturally (it's, I've, don't, you're, can't)
   - Use conversational, authentic creator language
   - NEVER use these words: game-changer, level up, hack, elevate, seamless, robust, delve, revolutionise, transform your life, I'm obsessed
   - No emojis, no hashtags
   - Each script should sound like a different real person

4. You MUST respond with a JSON object containing a key "scripts" which is an array of exactly {max_scripts} script objects.

Each script object must have this EXACT structure:
{{
  "name": "A descriptive title for the script",
  "target_duration_sec": 15,
  "target_platform": "TikTok",
  "methodology": "One of the six methodologies listed above",
  "hook": "The exact opening hook line (same as scene 1 dialogue)",
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "Hook",
      "dialogue": "The spoken hook text, approximately 17 words long",
      "word_count": 17,
      "estimated_duration_sec": 7.0,
      "visual_cue": "Brief visual direction for this scene",
      "on_screen_text": "Short text overlay if any, or empty string"
    }},
    {{
      "scene_number": 2,
      "scene_title": "CTA",
      "dialogue": "The spoken CTA/benefit text, approximately 17 words long",
      "word_count": 17,
      "estimated_duration_sec": 7.0,
      "visual_cue": "Brief visual direction for this scene",
      "on_screen_text": "Short text overlay if any, or empty string"
    }}
  ]
}}

Remember: respond ONLY with valid JSON in the format {{"scripts": [...]}}."""

    print(f"      [Trending] Calling GPT-4o for {max_scripts} scripts on topic: '{topic}'...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Generate {max_scripts} diverse, authentic trending UGC ad scripts for the niche: {topic}"}
            ],
            max_tokens=3000,
            temperature=0.9,
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content
        if not raw:
            print("      [Trending] GPT returned empty content.")
            return []

        raw = raw.strip()
        print(f"      [Trending] GPT response length: {len(raw)} chars")
        # Debug: print first 200 chars
        print(f"      [Trending] Response preview: {raw[:200]}...")

        parsed = json.loads(raw)

        # Extract the scripts array from the response
        scripts_list: list = []
        if isinstance(parsed, list):
            # GPT returned a bare array (unlikely with json_object but handle it)
            scripts_list = parsed
        elif isinstance(parsed, dict):
            # GPT returned an object -- try common keys
            for key in ["scripts", "trending_scripts", "results", "data"]:
                if key in parsed and isinstance(parsed[key], list):
                    scripts_list = parsed[key]
                    print(f"      [Trending] Found scripts under key: '{key}'")
                    break
            # If no known key found, try the first list value
            if not scripts_list:
                for key, val in parsed.items():
                    if isinstance(val, list) and len(val) > 0:
                        scripts_list = val
                        print(f"      [Trending] Found scripts under fallback key: '{key}'")
                        break

        if not scripts_list:
            print(f"      [Trending] Could not extract scripts array from response. Keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
            print(f"      [Trending] Full response: {raw[:500]}")
            return []

        print(f"      [Trending] Found {len(scripts_list)} raw script objects")

        # Validate and normalize each script
        valid_scripts = []
        for i, s in enumerate(scripts_list[:max_scripts]):
            if not isinstance(s, dict):
                print(f"      [Trending] Script {i} skipped: not a dict ({type(s)})")
                continue
            if "scenes" not in s or not isinstance(s.get("scenes"), list):
                print(f"      [Trending] Script {i} skipped: no 'scenes' array. Keys: {list(s.keys())}")
                continue
            if len(s["scenes"]) == 0:
                print(f"      [Trending] Script {i} skipped: empty scenes array")
                continue

            # Ensure the hook field exists
            if "hook" not in s and s["scenes"]:
                s["hook"] = s["scenes"][0].get("dialogue", "")

            # Ensure name exists
            if "name" not in s:
                s["name"] = s.get("hook", f"Trending Script {i + 1}")[:60]

            # Enforce estimated_duration_sec on all scenes
            for scene in s.get("scenes", []):
                scene["estimated_duration_sec"] = 7.0
                # Ensure word_count is an integer
                if "word_count" not in scene and "dialogue" in scene:
                    scene["word_count"] = len(scene["dialogue"].split())

            valid_scripts.append(s)

        print(f"      [Trending] Validated {len(valid_scripts)} trending scripts for '{topic}'")
        return valid_scripts

    except json.JSONDecodeError as e:
        print(f"      [Trending] JSON parse error: {e}")
        print(f"      [Trending] Raw content: {raw[:500] if raw else 'None'}")
        return []
    except Exception as e:
        print(f"      [Trending] Script extraction failed: {e}")
        traceback.print_exc()
        return []
