"""
Veo 3.1 Client — AI Video Generation

Wrapper for Google DeepMind's Veo 3.1 model via Kie.ai.
Supports text-to-video and image-to-video.
"""
import time
import requests
import json
import logging
from typing import Optional

try:
    import config
except ImportError:
    import sys
    from pathlib import Path
    sys.path.append(str(Path(__file__).parent.parent))
    import config

logger = logging.getLogger(__name__)

class VeoClient:
    def __init__(self):
        self.api_key = config.KIE_API_KEY
        self.base_url = config.KIE_API_URL
        self.headers = config.KIE_HEADERS
        self.model = "veo-3.1-fast"  # Default to fast for cost efficiency

    def generate_video(
        self,
        prompt: str,
        image_url: Optional[str] = None,
        model: Optional[str] = None,
        aspect_ratio: str = "9:16"
    ) -> str:
        """
        Generate a video from text prompt and optional reference image.
        
        Args:
            prompt: Text description of the video
            image_url: Optional reference image (for image-to-video)
            model: Override default model (e.g. "veo-3.1")
            aspect_ratio: Video aspect ratio
            
        Returns:
            str: Public URL of the generated video
        """
        target_model = model or self.model
        api_model_id = config.MODEL_REGISTRY.get(target_model, target_model)
        
        print(f"🎥 Veo: Generating video ({target_model})...")
        print(f"   Prompt: {prompt[:60]}...")
        if image_url:
            print(f"   Ref Image: {image_url}")

        payload = {
            "prompt": prompt,
            "model": api_model_id,
            "aspect_ratio": "9:16",
            "enableFallback": False,
        }
        
        if image_url:
            payload["imageUrls"] = [image_url]
            payload["generationType"] = "FIRST_AND_LAST_FRAMES_2_VIDEO"

        # 1. Submit Generation
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/veo/generate",
                headers=self.headers,
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            
            if data.get("code") != 200:
                raise RuntimeError(f"Veo API Error: {data.get('msg')}")
                
            task_id = data["data"]["taskId"]
            print(f"   Task ID: {task_id}")
            
        except Exception as e:
            print(f"❌ Veo Generate Failed: {e}")
            raise

        # 2. Poll for Result
        for i in range(120): # 20 mins max (Veo can be slow)
            time.sleep(10)
            
            try:
                poll_resp = requests.get(
                    f"{self.base_url}/api/v1/veo/record-info",
                    headers=self.headers,
                    params={"taskId": task_id}
                )
                poll_data = poll_resp.json()
                
                if poll_data.get("code") != 200:
                    print(f"   ⚠️ Poll Error: {poll_data.get('msg')} ({i*10}s)")
                    continue

                data = poll_data.get("data", {})
                flag = data.get("successFlag", 0)
                
                if flag == 1:
                     # Extract URL
                    response_obj = data.get("response") or {}
                    if isinstance(response_obj, str):
                        try:
                            response_obj = json.loads(response_obj)
                        except:
                            response_obj = {}
                            
                    result_urls = response_obj.get("resultUrls") or data.get("resultUrls") or []
                    if isinstance(result_urls, str):
                        result_urls = json.loads(result_urls)
                        
                    if result_urls and len(result_urls) > 0:
                        final_url = result_urls[0]
                        print(f"   ✅ Veo Success: {final_url}")
                        return final_url
                    
                    print(f"   ⚠️ Success flag but no URL found ({i*10}s)")
                    
                elif flag in (2, 3):
                    error_msg = data.get("failMsg", data.get("statusDescription", "Unknown error"))
                    raise RuntimeError(f"Veo Generation Failed: {error_msg}")
                    
                status = data.get("statusDescription", "generating")
                print(f"   ⏳ {status}... ({i*10}s)")
                
            except Exception as e:
                # if "Veo" in str(e): raise e
                print(f"   ⚠️ Poll Exception: {e}")
                
        raise RuntimeError("Veo generation timed out")

# Singleton
client = VeoClient()
