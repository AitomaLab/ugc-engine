import requests
import config
import json

headers = {"Authorization": f"Bearer {config.KIE_API_KEY}"}

endpoints = [
    "https://api.kie.ai/api/v1/common/getModels",
    "https://api.kie.ai/api/v1/common/model-list",
    "https://api.kie.ai/api/v1/models/list",
    "https://api.kie.ai/api/v1/video/models",
    "https://api.kie.ai/api/v1/generate/models",
]

for url in endpoints:
    print(f"\n--- Testing Metadata: {url} ---")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        print(f"Status: {resp.status_code}")
        if resp.status_code == 200:
            print(f"Body: {json.dumps(resp.json(), indent=2)[:500]}")
        else:
            print(f"Body: {resp.text[:100]}")
    except Exception as e:
        print(f"Error: {e}")

# Also try a specific Seedance test with the bytedance prefix
def test_btd(model):
    url = "https://api.kie.ai/api/v1/generate"
    payload = {
        "model": model,
        "prompt": "Hello",
        "aspectRatio": "9:16",
        "videoDuration": "8", # string duration
        "callBackUrl": "https://example.com/callback"
    }
    resp = requests.post(url, headers=headers, json=payload)
    print(f"\nModel {model} -> {resp.status_code} - {resp.text[:100]}")

test_btd("bytedance/seedance-1.5-pro")
test_btd("bytedance/v1-5-pro")
