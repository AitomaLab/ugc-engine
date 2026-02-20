import os
import requests
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.saas")
KIE_API_KEY = os.getenv("KIE_API_KEY")
KIE_API_URL = os.getenv("KIE_API_URL", "https://api.kie.ai")
headers = {"Authorization": f"Bearer {KIE_API_KEY}", "Content-Type": "application/json"}

def list_models():
    # Try different standard model listing endpoints
    endpoints = [
        f"{KIE_API_URL}/api/v1/models",
        f"{KIE_API_URL}/v1/models"
    ]
    
    for endpoint in endpoints:
        print(f"Trying: {endpoint}")
        resp = requests.get(endpoint, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            if "data" in data:
                models = data["data"]
                if isinstance(models, list):
                    image_models = [m.get("id", m.get("model")) for m in models if "nano" in str(m).lower() or "image" in str(m).lower() or "flux" in str(m).lower() or "midjourney" in str(m).lower()]
                    if not image_models:
                        # Print first 20 model IDs if filtering fails
                        image_models = [m.get("id", m.get("model")) for m in models][:20]
                    print("Found models:", image_models)
                    return
            elif isinstance(data, list):
                print("Models list:", [m.get("id", m) for m in data[:20]])
                return
            else:
                print("Unknown structure:", data)
                return
        else:
            print("Failed:", resp.status_code, resp.text[:100])

if __name__ == "__main__":
    list_models()
