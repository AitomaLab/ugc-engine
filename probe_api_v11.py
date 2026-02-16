import requests
import config
import json

def test(model):
    print(f"\n--- Model: {model} ---")
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "Authentic UGC selfie.",
        "aspectRatio": "9:16",
        "videoDuration": 8,
        "generate_audio": True,
        "callBackUrl": "https://example.com/callback",
        # Try to explicitly disable Suno fields if it's being routed there
        "customMode": False,
        "instrumental": False
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        body = resp.json()
        print(f"Code: {body.get('code')}")
        print(f"Msg: {body.get('msg', body.get('message', ''))}")
        if body.get('code') == 200:
             print(f"✅ SUCCESS! Data: {json.dumps(body.get('data'), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

models = ["seedance-1-5-pro-audio", "seedance-1.5-pro-audio", "seedance-1-5-pro", "bytedance/seedance-1.5-pro"]
for m in models:
    test(m)
