import os
from openai import OpenAI
from typing import Dict, Any, Optional

class AIScriptClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY not found. Script generation will fail.")
        self.client = OpenAI(api_key=self.api_key)

    def generate_physical_product_script(self, product_analysis: Dict[str, Any], duration: int, product_name: str = "") -> str:
        """
        Generates a compelling UGC script for a physical product.
        
        Args:
            product_analysis: The visual description/analysis dict from the DB.
            duration: Target duration in seconds (15 or 30).
            product_name: Name of the product (optional fallback if not in analysis).
            
        Returns:
            The generated script text.
        """
        if not self.api_key:
            return "Error: OpenAI API Key not configured."

        # Prepare data for prompt
        brand = product_analysis.get("brand_name") or product_name or "the product"
        visuals = product_analysis.get("visual_description", "A product.")
        colors = product_analysis.get("color_scheme", [])
        font = product_analysis.get("font_style", "N/A")
        
        # Format colors for prompt
        color_str = ""
        if isinstance(colors, list):
            color_str = "\n".join([f"  - hex: {c.get('hex', '')}, name: {c.get('name', '')}" for c in colors if isinstance(c, dict)])

        # Word budget per scene: ~2.5 words/sec spoken, 7s of dialogue per 8s scene
        words_per_scene = 17
        total_words = words_per_scene * 2  # 2 scenes

        system_prompt = f"""You are a world-class copywriter specializing in viral User-Generated Content (UGC) for social media platforms like TikTok and Instagram.

Your task is to generate a UGC script for a {duration}-second video that will be split across 2 video scenes (8 seconds each). The dialogue in each scene must last approximately 7 seconds so it finishes naturally before the scene ends.

**STRUCTURE — output exactly 2 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity. Max {words_per_scene} words.
Part 2 (Benefits + CTA): Highlight the product's key benefit and end with a soft call-to-action. Max {words_per_scene} words.

**Example format:**
You guys, I finally found the one product that completely changed my skin game. ||| The texture is insane, it absorbs in seconds and leaves your skin glowing. Link in bio!

**RULES:**
- Total script must be approximately {total_words} words. Do NOT exceed this.
- Each part must be a complete, natural-sounding sentence or two.
- Tone: conversational, enthusiastic, genuine, as if sharing a real discovery.
- Language: simple, direct, persuasive.

**CRITICAL FORMAT RULES — the script will be spoken aloud by an AI video model:**
- Output ONLY the exact words to be spoken, separated by |||
- Do NOT include emojis, hashtags, or special symbols.
- Do NOT include stage directions, actions, or annotations like [Shows product], (holds up), *smiles*, etc.
- Do NOT include scene labels like "Hook:", "Scene 1:", "Part 1:", etc.
- Do NOT use ellipsis (...). Use a comma or period instead for pauses.
- Do NOT add any text before Part 1 or after Part 2."""

        user_prompt = f"""**Product Analysis:**

```yaml
brand_name: {brand}
color_scheme:
{color_str}
font_style: {font}
visual_description: {visuals}
```

Generate the 2-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.8,
                top_p=1.0,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ AI Script Generation Failed: {e}")
            return f"Check out {brand}! It's amazing. You have to try it."
