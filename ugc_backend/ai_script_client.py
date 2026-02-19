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

        system_prompt = f"""You are a world-class copywriter specializing in viral User-Generated Content (UGC) for social media platforms like TikTok and Instagram.

Your task is to generate a compelling, authentic, and high-energy UGC script for a {duration}-second video based on the provided product analysis.

**Instructions:**
1.  The script MUST start with a strong, attention-grabbing hook (the first 3 seconds).
2.  The body of the script should naturally highlight the product's key benefits and features based on its description.
3.  The tone should be conversational, enthusiastic, and genuine, as if a real person is sharing a discovery.
4.  The language should be simple, direct, and persuasive.
5.  The script must be approximately {int(duration * 3.5)} words long to fit the video duration.
6.  Only return the script text. Do not include any other comments, titles, or explanations."""

        user_prompt = f"""**Product Analysis:**

```yaml
brand_name: {brand}
color_scheme:
{color_str}
font_style: {font}
visual_description: {visuals}
```

Generate the UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300,
                temperature=0.8,
                top_p=1.0,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"❌ AI Script Generation Failed: {e}")
            return f"Check out {brand}! It's amazing. You have to try it."
