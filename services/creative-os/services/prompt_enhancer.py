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
    parts = []
    if context and context.get("mode") in ("seedance_2_ugc", "seedance_2_cinematic", "seedance_2_product"):
        seedance_lang = "Spanish (Latin American accent)" if language == "es" else "English"
        parts.append(f"[Language: {seedance_lang}]")
    parts.append(f"Language for introductions and non-prompt text: {lang_name}")

    if context:
        if context.get("product_name"):
            parts.append(f"Product: {context['product_name']}")
        if context.get("product_description"):
            parts.append(f"Product description: {context['product_description']}")
        if context.get("influencer_name"):
            parts.append(f"Influencer: {context['influencer_name']}")
        if context.get("image_url"):
            parts.append(f"Reference image uploaded: {context['image_url']}")
            # For Seedance modes, instruct GPT-4o to use @Image1 binding
            # so the engine locks onto the exact product text/labels.
            if context.get("mode", "").startswith("seedance_2_"):
                parts.append(
                    "CRITICAL: This image is mapped to @Image1 in the Seedance engine. "
                    "You MUST use @Image1 in your Dynamic and Static descriptions to anchor "
                    "the product's visual identity. Without @Image1, the engine will hallucinate text."
                )
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
        code_match = re.search(r'```(?:text)?\s*\n(.*?)\n```', block, re.DOTALL)
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
        code_blocks = re.findall(r'```(?:text)?\s*\n(.*?)\n```', response_text, re.DOTALL)
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
