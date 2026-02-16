import requests
import config
import json

def test(model):
    print(f"\n--- Model: {model} ---")
    url = "https://api.kie.ai/api/v1/jobs/createTask"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "input": {
            "prompt": "Selfie of a woman.",
            "duration": "8",
            "ratio": "9:16"
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        body = resp.json()
        print(f"Code: {body.get('code')}")
        print(f"Msg: {body.get('msg', body.get('message', ''))}")
        if body.get('code') == 200:
             print(f"✅ FOUND IT! Data: {json.dumps(body.get('data'), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

# Try exact documentation strings and common patterns
models = [
    "Seedance 1.5 Pro", 
    "seedance-1.5-pro", 
    "seedance_v1.5_pro", 
    "seedance-v1.5-pro",
    "btd-v1.5-pro",
    "bytedance-v1.5-pro",
    "v1.5-pro"
]
for m in models:
    test(m)
