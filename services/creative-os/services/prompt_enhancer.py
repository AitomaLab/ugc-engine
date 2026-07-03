"""
Creative OS — Prompt Enhancement Engine

Enhances user prompts into professional-grade options using GPT-4o
with mode-specific system prompts (CinePrompt Pro, iPhone Look, Kling Director).
"""
import os
import re
from pathlib import Path
from openai import AsyncOpenAI
from env_loader import load_env
load_env(Path(__file__))

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"

# Lazy-init OpenAI client
_openai_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY must be set in .env.saas")
        _openai_client = AsyncOpenAI(api_key=api_key)
    return _openai_client


def _load_system_prompt(mode: str) -> str:
    """Load the appropriate system prompt for the given mode."""
    prompt_files = {
        "cinematic": "cineprompt_pro.txt",
        "iphone_look": "iphone_look.txt",
        "kling_director": "kling_director.txt",
        "cinematic_video": "kling_director.txt",
        "ugc": "veo_ugc_director.txt",
        "luxury": "luxury_editorial.txt",
        "ugc_composite": "ugc_scene_enhancer.txt",
        "seedance_director": "seedance_director.txt",
        "seedance_2_ugc": "seedance_director.txt",
        "seedance_2_cinematic": "seedance_director.txt",
        "seedance_2_product": "seedance_director.txt",
    }
    filename = prompt_files.get(mode)
    if not filename:
        raise ValueError(f"Unknown mode: {mode}. Available: {list(prompt_files.keys())}")

    filepath = PROMPTS_DIR / filename
    if not filepath.exists():
        raise FileNotFoundError(f"System prompt not found: {filepath}")

    return filepath.read_text(encoding="utf-8")


def _build_user_message(user_prompt: str, language: str = "en", context: dict | None = None) -> str:
    """Build the user message with context from the Create Bar."""
    lang_name = "English" if language == "en" else "Spanish"
    is_seedance = context and context.get("mode", "").startswith("seedance_2_")
    parts = []

    if is_seedance:
        seedance_lang = "Spanish (Latin American accent)" if language == "es" else "English"
        parts.append(f"[Video language: {seedance_lang}]")
    else:
        parts.append(f"Language for introductions and non-prompt text: {lang_name}")

    # ── Clip duration ──
    if context and context.get("duration"):
        dur = int(context["duration"])
        if is_seedance:
            # The new Seedance director prompt handles timing internally —
            # just pass the duration as simple context.
            parts.append(f"\n[Duration: {dur} seconds]")
        else:
            # Non-Seedance modes: keep the detailed word-budget injection
            word_budgets = {5: "12–15", 8: "20–24", 10: "25–30", 15: "40–50"}
            budget = word_budgets.get(dur, f"~{int(dur * 2.5)}–{int(dur * 3)}")
            parts.append(
                f"\n[CLIP DURATION: {dur} seconds] "
                f"ALL timestamps in Dynamic Description must end at or before {dur}s. "
                f"Dialogue word budget: {budget} words MAXIMUM. "
                f"Script must end 1 second before the clip ends ({dur - 1}s). "
                f"Use the {dur}-second beat structure from the mode specification. "
                f"Do NOT write beats or dialogue for a longer clip."
            )

    if context:
        if context.get("product_name"):
            parts.append(f"Product: {context['product_name']}")
        if context.get("product_description"):
            parts.append(f"Product description: {context['product_description']}")
        if context.get("influencer_name"):
            parts.append(f"Influencer: {context['influencer_name']}")

        # ── Reference images with @ImageN indexing (KIE API format) ──
        # KIE's Seedance 2.0 uses @Image1, @Image2, etc. to bind the
        # reference_image_urls array to specific roles in the scene.
        # We tell GPT-4o which index maps to which image.
        if is_seedance:
            image_urls = context.get("image_urls") or []
            if not image_urls and context.get("image_url"):
                image_urls = [context["image_url"]]
            if image_urls:
                parts.append("\n[Reference images provided]")
                for idx, url in enumerate(image_urls, 1):
                    parts.append(f"  @Image{idx}: {url}")
                parts.append(
                    "Use @Image1, @Image2, etc. in your prompt to reference "
                    "each image in the scene. Seedance only preserves visual "
                    "identity if you use these references explicitly."
                )
        else:
            if context.get("image_url"):
                parts.append(f"Reference image uploaded: {context['image_url']}")

        if context.get("elements"):
            element_names = [f"@{e['name']}" for e in context["elements"]]
            parts.append(f"\nAvailable Kling 3.0 element references: {', '.join(element_names)}")
            for elem in context["elements"]:
                parts.append(f"  • {elem['name']}: {elem.get('description', 'N/A')}")
            parts.append(
                "IMPORTANT: You MUST append these element tags at the END of your prompt text, "
                "e.g. '...scene description @element_product @element_character'. "
                "Do NOT describe the element content in the prompt — only reference them by tag name."
            )

    # ── Dynamic-speaking mode (ADDITIVE, flag-gated) ──────────────────
    # Only appended when the dynamic-speaking Seedance route fires. When the
    # flag is absent the message above is byte-for-byte identical to today, so
    # seedance_2_cinematic / seedance_2_product and every other mode are
    # unaffected. The shared seedance_director.txt is never modified.
    if is_seedance and context and context.get("dynamic_speaking"):
        leg_index = context.get("leg_index")
        leg_total = context.get("leg_total") or 2
        leg_rules = ""
        if leg_index in (1, 2):
            if leg_index == 1:
                leg_rules = (
                    f"\n- THIS IS LEG 1 OF {leg_total} for a 30s video: include ONLY the "
                    "OPENING visual beats (approximately the first half of the beat table). "
                    "Do NOT start from the middle or include the brand CTA — that belongs in leg 2.\n"
                    "- Time blocks must fit within 0–15s only.\n"
                )
            else:
                leg_rules = (
                    f"\n- THIS IS LEG 2 OF {leg_total} for a 30s video: include ONLY the "
                    "CLOSING visual beats (approximately the second half of the beat table). "
                    "Do NOT repeat the opening apartment/intro beats — the character continues "
                    "mid-action from leg 1.\n"
                    "- Time blocks must fit within 0–15s only; end with brand name / website / CTA.\n"
                )
        parts.append(
            "\n[DYNAMIC SPEAKING MODE]\n"
            "This is a continuous walk-and-talk UGC clip: ONE character speaking "
            "while moving through MULTIPLE actions/beats in a single uninterrupted "
            "take (e.g. walking through a space, interacting with people/objects, "
            "then addressing the camera or presenting a brand).\n"
            "- Override the 'maximum one short line' dialogue limit: DISTRIBUTE the "
            "spoken script across the time blocks so the character is talking "
            "throughout, naturally integrated with the action in each block "
            "(e.g. '[0-4s] walks across the room and says: \"...\"').\n"
            "- Keep ONE continuous scene — no hard cuts, no separate shots; the "
            "camera follows the character through the beats.\n"
            "- Put the FULL spoken script verbatim in the Audio section as Dialogue, "
            "AND weave the matching lines into the relevant time blocks.\n"
            "- Preserve any brand name, website, or CTA exactly as given, in the "
            "final block."
            + leg_rules
        )
        user_script = (context or {}).get("user_script")
        if user_script:
            parts.append(
                f"\n[USER SCRIPT — use EXACTLY this text for Dialogue; do NOT invent "
                f"alternate lines]\n{user_script}"
            )
        image_urls = (context or {}).get("image_urls") or []
        if (
            len(image_urls) >= 2
            and (context or {}).get("product_type") == "physical"
        ):
            parts.append(
                "\n[PHYSICAL PRODUCT DEMO — dual references]\n"
                "- @Image1 = influencer/presenter identity (face, hair, skin tone).\n"
                "- @Image2 = physical product appearance (packaging, color, logos).\n"
                "- The product must stay visible during demo beats (hold, show, wet, pour, absorb)."
            )

    parts.append(f"\nUser request: {user_prompt}")
    return "\n".join(parts)


def parse_prompt_options(response_text: str) -> list[dict]:
    """Parse GPT response into structured prompt options.

    Expects format with titles like "Option 1", "0.5x – Ultra Wide", etc.
    and prompts inside triple-backtick code blocks.
    """
    options = []

    # Split by option markers — handles both "Option N" and lens-specific titles
    # Pattern: find title lines followed by code blocks
    blocks = re.split(r'\n(?=(?:Option \d|0\.5x|1x|Selfie|Shot \d))', response_text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        # Extract title (first line)
        lines = block.split("\n", 1)
        title = lines[0].strip().strip("#").strip("*").strip()

        # Skip if it's just the intro text (no code block)
        if len(lines) < 2 or "```" not in lines[1]:
            # Try to find a code block anywhere in the block
            if "```" not in block:
                continue

        # Extract prompt from code block
        code_match = re.search(r'```(?:text|markdown)?\s*\n(.*?)\n```', block, re.DOTALL)
        if code_match:
            prompt = code_match.group(1).strip()
            if prompt and len(prompt) > 20:
                options.append({
                    "title": title,
                    "prompt": prompt,
                })

    # If we couldn't parse structured options, try a simpler approach
    if not options:
        # Try splitting by code blocks
        code_blocks = re.findall(r'```(?:text|markdown)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        for i, prompt in enumerate(code_blocks):
            prompt = prompt.strip()
            if prompt and len(prompt) > 20:
                options.append({
                    "title": f"Option {i + 1}",
                    "prompt": prompt,
                })

    return options[:3]  # Always return max 3


async def enhance_prompt(
    user_prompt: str,
    mode: str,
    language: str = "en",
    context: dict | None = None,
) -> list[dict]:
    """Enhance a user prompt into 3 professional options.

    Args:
        user_prompt: The user's raw prompt text
        mode: Generation mode (cinematic, iphone_look, kling_director, cinematic_video)
        language: UI language (en/es) for non-prompt text
        context: Optional dict with product_name, product_description, influencer_name, image_url

    Returns:
        List of dicts with {title, prompt} for each option
    """
    system_prompt = _load_system_prompt(mode)
    ctx_with_mode = {**(context or {}), "mode": mode}
    user_text = _build_user_message(user_prompt, language, ctx_with_mode)

    client = _get_openai()

    # Build the user message — include image as vision input if provided
    image_url = context.get("image_url") if context else None

    if image_url:
        # GPT-4o vision: send the reference image so it can see the actual content
        print(f"[PromptEnhancer] VISION mode — sending image to GPT-4o: {image_url[:80]}...")
        user_content = [
            {
                "type": "image_url",
                "image_url": {"url": image_url, "detail": "high"},
            },
            {
                "type": "text",
                "text": user_text,
            },
        ]
    else:
        print(f"[PromptEnhancer] TEXT-ONLY mode — no image provided")
        user_content = user_text

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.85,
        max_tokens=3000,
    )

    raw_text = response.choices[0].message.content or ""
    print(f"[PromptEnhancer] GPT-4o raw response ({len(raw_text)} chars):\n{raw_text[:300]}...")

    options = parse_prompt_options(raw_text)

    if not options:
        # Fallback: return the enhanced text as a single option
        options = [{
            "title": "Option 1",
            "prompt": raw_text.strip(),
        }]

    return options
