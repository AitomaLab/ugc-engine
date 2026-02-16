import requests
import config
import json

def test_endpoint(url, payload):
    print(f"Testing {url}...")
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"  Status: {resp.status_code}")
        try:
            print(f"  Body: {json.dumps(resp.json(), indent=2)}")
        except:
            print(f"  Body: {resp.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")

payload = {
    "model": "seedance-1-5-pro",
    "prompt": "Hello",
    "aspectRatio": "9:16",
    "videoDuration": 8,
    "generate_audio": True
}

test_endpoint("https://api.kie.ai/api/v1/video-generation/seedance-1-5-pro/generate", payload)
test_endpoint("https://api.kie.ai/api/v1/btd-v1/generate", payload)
test_endpoint("https://api.kie.ai/api/v1/seedance-v1-5-pro/generate", payload)
