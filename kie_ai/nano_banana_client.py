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
        seed: Optional[int] = None,
        negative_prompt: str = "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, (mutated hands and fingers:1.4), disconnected limbs, mutation, mutated, ugly, disgusting, blurry, amputation, (3rd hand:1.5)"
    ) -> str:
        """
        Generate a composite image of the influencer interacting with the product.
        
        Args:
            product_image_url: URL of the product image (transparent BG preferred)
            influencer_image_url: URL of the influencer's reference photo
            prompt: Description of the scene/action
            seed: Random seed for reproducibility and character consistency
            
        Returns:
            str: Public URL of the generated image
        """
        print(f"🍌 NanoBanana: Generating composite image...")
        print(f"   Product: {product_image_url}")
        print(f"   Influencer: {influencer_image_url}")
        if seed is not None:
            print(f"   Seed: {seed}")

        # Enhanced prompt for identity consistency
        # Explicitly referencing the woman in the image and adding face consistency weight
        final_prompt = (
            f"photorealistic, professional UGC, 8k, sharp focus, {prompt}, "
            f"featuring the specific woman from the reference image, (face consistency:1.5)"
        )

        payload = {
            "model": self.model,
            "input": {
                "prompt": final_prompt,
                "negative_prompt": negative_prompt,
                "product_image_url": product_image_url,
                "reference_image_url": influencer_image_url,
                "num_inference_steps": 60,
                "guidance_scale": 8.5,
                "width": 768,   # Standard vertical aspect ratio optimized
                "height": 1344, 
            },
            "callBackUrl": "https://example.com/callback"
        }
        
        if seed is not None:
            payload["input"]["seed"] = seed

        # 1. Submit Task with Retry Logic for Concurrency Limits
        max_retries = 3
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v1/jobs/createTask",
                    headers=self.headers,
                    json=payload
                )
                
                # Check for rate limit or specific concurrency error in text before json parse if possible, 
                # but usually it's in the JSON 200 OK response with a non-200 code, or a 429 status.
                if resp.status_code == 429:
                    print(f"   ⚠️ Concurrency Limit Hit (429). Retrying in 30s... ({attempt+1}/{max_retries})")
                    time.sleep(30)
                    continue

                resp.raise_for_status()
                data = resp.json()
                
                # specific check for Kie.ai / Nano Banana concurrency msg
                if data.get("code") != 200:
                    msg = data.get("msg", "")
                    if "concurrent" in msg.lower() or "limit" in msg.lower():
                        print(f"   ⚠️ Concurrency Limit Hit ('{msg}'). Retrying in 30s... ({attempt+1}/{max_retries})")
                        time.sleep(30)
                        continue
                    # Other error
                    raise RuntimeError(f"NanoBanana API Error: {msg}")
                    
                task_id = data["data"]["taskId"]
                print(f"   Task ID: {task_id}")
                break # Success
                
            except Exception as e:
                # If it's the last attempt, raise
                if attempt == max_retries - 1:
                    print(f"❌ NanoBanana Submit Failed after {max_retries} attempts: {e}")
                    raise
                
                # If it's a network error, maybe wait shorter? 
                # But for safety let's just wait a bit and retry.
                if "NanoBanana API Error" in str(e):
                    # logic handled above for distinct API errors
                    raise 
                
                print(f"   ⚠️ Network/Unknown Error: {e}. Retrying in 5s...")
                time.sleep(5)

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
