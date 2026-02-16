import requests
import config
import json

def test(model):
    print(f"\n--- Model: {model} ---")
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "Authentic UGC selfie of a woman smiling at the camera and saying hello in Spanish.",
        "aspectRatio": "9:16",
        "duration": "8",
        "callBackUrl": "https://example.com/callback"
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        body = resp.json()
        print(f"Code: {body.get('code')} - Msg: {body.get('msg', body.get('message', ''))}")
        if body.get('code') == 200:
             print(f"✅ SUCCESS! Data: {json.dumps(body.get('data'), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

# Try the -8-generate suffix
for base in ["seedance-1-5-pro", "bytedance-v1-5-pro", "bytedance-v1.5-pro", "seedance-1.5-pro"]:
    test(f"{base}-8-generate")
    test(f"{base}-generate")
