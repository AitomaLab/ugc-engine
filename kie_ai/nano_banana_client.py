"""
Nano Banana Pro Client — AI Image Composition

Generates realistic composite images of influencers holding products.
Used as the first step in the Physical Product video generation pipeline.
"""
import time
import requests
import json
import logging
from typing import Optional

try:
    import config
except ImportError:
    # Fallback for when running as standalone script or in different context
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    import config

logger = logging.getLogger(__name__)

class NanoBananaClient:
    def __init__(self):
        self.api_key = config.KIE_API_KEY
        self.base_url = config.KIE_API_URL
        self.headers = config.KIE_HEADERS
        self.model = "nano-banana-pro"  # Default model ID

    def generate_composite_image(
        self,
        product_image_url: str,
        influencer_image_url: str,
        prompt: str,
        negative_prompt: str = ""
    ) -> str:
        """
        Generate a composite image of the influencer interacting with the product.
        
        Args:
            product_image_url: URL of the product image (transparent BG preferred)
            influencer_image_url: URL of the influencer's reference photo
            prompt: Description of the scene/action
            
        Returns:
            str: Public URL of the generated image
        """
        print(f"🍌 NanoBanana: Generating composite image...")
        print(f"   Product: {product_image_url}")
        print(f"   Influencer: {influencer_image_url}")

        payload = {
            "model": self.model,
            "input": {
                "prompt": prompt,
                "negative_prompt": negative_prompt,
                "product_image_url": product_image_url,
                "reference_image_url": influencer_image_url,
                "num_inference_steps": 30,
                "guidance_scale": 7.5,
                "width": 768,   # Standard vertical aspect ratio optimized
                "height": 1344, 
            },
            "callBackUrl": "https://example.com/callback"
        }

        # 1. Submit Task
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/jobs/createTask",
                headers=self.headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") != 200:
                raise RuntimeError(f"NanoBanana API Error: {data.get('msg')}")
                
            task_id = data["data"]["taskId"]
            print(f"   Task ID: {task_id}")
            
        except Exception as e:
            print(f"❌ NanoBanana Submit Failed: {e}")
            raise

        # 2. Poll for Result
        for i in range(120): # 10 mins max
            time.sleep(5)
            
            try:
                poll_resp = requests.get(
                    f"{self.base_url}/api/v1/jobs/recordInfo",
                    headers=self.headers,
                    params={"taskId": task_id}
                )
                poll_data = poll_resp.json()
                
                if poll_data.get("code") != 200:
                    print(f"   ⚠️ Poll Error: {poll_data.get('msg')} ({i*5}s)")
                    continue

                state = poll_data["data"].get("state", "processing")
                
                if state == "success":
                    result_json = poll_data["data"].get("resultJson")
                    if isinstance(result_json, str):
                        result_data = json.loads(result_json)
                    else:
                        result_data = result_json or {}
                        
                    # Extract URL - typically in resultUrls array
                    image_urls = result_data.get("resultUrls") or result_data.get("images")
                    
                    if image_urls and len(image_urls) > 0:
                        final_url = image_urls[0]
                        print(f"   ✅ NanoBanana Success: {final_url}")
                        return final_url
                    else:
                        raise RuntimeError("Success state but no image URL found")
                        
                elif state == "fail":
                    error_msg = poll_data["data"].get("failMsg", "Unknown failure")
                    raise RuntimeError(f"NanoBanana Generation Failed: {error_msg}")
                    
                print(f"   ⏳ Generating composite... ({i*5}s)")
                
            except Exception as e:
                if "NanoBanana" in str(e): raise e
                print(f"   ⚠️ Poll Exception: {e}")
                
        raise RuntimeError("NanoBanana generation timed out")

# Singleton instance
client = NanoBananaClient()
