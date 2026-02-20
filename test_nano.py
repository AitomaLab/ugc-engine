import os
import time
import requests
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.saas")
KIE_API_KEY = os.getenv("KIE_API_KEY")
KIE_API_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
headers = {"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"}

def test_payload():
    url1 = "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"
    url2 = "https://upload.wikimedia.org/wikipedia/commons/4/47/PNG_transparency_demonstration_1.png"

    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": "Test photo of a person holding a product",
            "negative_prompt": "blurry",
            "image_input": [url1, url2],
            "aspect_ratio": "9:16",
            "resolution": "2K"
        }
    }
    
    print("Testing payload format: EXACT LEGACY")
    resp = requests.post(f"{KIE_API_URL}/api/v1/jobs/createTask", headers=headers, json=payload)
    data = resp.json()
    task_id = data["data"]["taskId"]
    print(f"Task ID: {task_id}")
    
    for i in range(12):
        time.sleep(5)
        p_resp = requests.get(f"{KIE_API_URL}/api/v1/jobs/recordInfo", headers=headers, params={"taskId": task_id})
        state = p_resp.json().get("data", {}).get("state")
        print(f"[{i*5}s] State: {state}")
        if state in ["success", "fail"]:
            print(f"Finished early with state: {state}")
            return
            
if __name__ == "__main__":
    test_payload()
