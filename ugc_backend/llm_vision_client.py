
import os
import yaml
from openai import OpenAI
from pydantic import BaseModel
from typing import Optional, Dict, Any

class LLMVisionClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("⚠️ OPENAI_API_KEY not found. Vision analysis will fail.")
        self.client = OpenAI(api_key=self.api_key)

    def describe_product_image(self, image_url: str) -> Dict[str, Any]:
        """
        Analyzes a product image using OpenAI GPT-4o Vision to extract
        visual details in YAML format, then parses it to a dict.
        """
        if not self.api_key:
            return {}

        prompt_text = """
Describe product image:
Return the analysis in YAML format with the following fields:

brand_name: (Name of the brand shown in the image, if visible or inferable)
color_scheme:
 - hex: (Hex code of each prominent color used)
   name: (Descriptive name of the color)
font_style: (Describe the font family or style used: serif/sans-serif, bold/thin, etc.)
visual_description: |
  (A highly detailed paragraph describing the product's visual appearance. Include details about shape, material, texture, lighting, and any visible text or logos on the packaging. Do not summarize; be exhaustive.)

Only return the YAML. Do not explain or add any other comments.
"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt_text},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url,
                                    "detail": "high"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=500
            )

            content = response.choices[0].message.content
            # Strip markdown code blocks if present
            if content.startswith("```yaml"):
                content = content.replace("```yaml", "").replace("```", "")
            elif content.startswith("```"):
                content = content.replace("```", "")
            
            return yaml.safe_load(content.strip())

        except Exception as e:
            print(f"❌ LLM Vision Analysis Failed: {e}")
            import traceback
            traceback.print_exc()
            return {}
