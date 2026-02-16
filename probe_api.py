import requests
import config
import json

def test_endpoint(url, payload):
    print(f"Testing {url}...")
    try:
        resp = requests.post(url, headers=config.KIE_HEADERS, json=payload, timeout=10)
        print(f"  Status: {resp.status_code}")
        try:
            print(f"  Body: {json.dumps(resp.json(), indent=2)}")
        except:
            print(f"  Body: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

payload = {
    "model": "seedance-1-5-pro",
    "prompt": "A woman saying hello in Spanish.",
    "quality": "720p",
    "aspectRatio": "9:16",
    "videoDuration": 8,
    "generate_audio": True
}

# Try different combinations
test_endpoint("https://api.kie.ai/api/v1/seedance/generate", payload)
test_endpoint("https://api.kie.ai/api/v1/generate", payload)
test_endpoint("https://api.kie.ai/api/v1/jobs", payload)
test_endpoint("https://api.kie.ai/api/v1/veo/generate", payload)
