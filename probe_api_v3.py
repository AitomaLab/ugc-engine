import requests
import config
import json

def test_endpoint(url, model_name):
    print(f"Testing {url} with {model_name}...")
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "prompt": "Hello",
        "aspectRatio": "9:16",
        "videoDuration": 8,
        "generate_audio": True
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"  Status: {resp.status_code}")
        try:
            body = resp.json()
            print(f"  Body: {body.get('code')} - {body.get('msg', body.get('message', ''))}")
        except:
            print(f"  Body: {resp.text[:100]}")
    except Exception as e:
        print(f"  Error: {e}")

models = ["seedance-1-5-pro", "seedance-1.5-pro", "bytedance-v1-5-pro"]
endpoints = [
    "https://api.kie.ai/api/v1/bytedance/generate",
    "https://api.kie.ai/api/v1/seedance/v1/generate",
    "https://api.kie.ai/api/v1/btd/generate",
]

for e in endpoints:
    for m in models:
        test_endpoint(e, m)
