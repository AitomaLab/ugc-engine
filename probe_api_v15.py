import requests
import config
import json

def test(model):
    print(f"\n--- Model: {model} ---")
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "An authentic UGC selfie video of a friendly travel agent smiling and speaking directly to the camera.",
        "aspectRatio": "9:16",
        "duration": "8",
        "quality": "720p",
        "generate_audio": True,
        "callBackUrl": "https://example.com/callback",
        "customMode": False,
        "instrumental": False
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        body = resp.json()
        code = body.get("code")
        msg = body.get("msg", body.get("message", ""))
        print(f"Code: {code}")
        print(f"Msg: {msg}")
        if code == 200:
             print(f"✅ SUCCESS! Data: {json.dumps(body.get('data'), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

models = ["seedance-pro-audio", "seedance-1-5-pro", "bytedance/v1-5-pro", "btd-v1-5-pro"]
for m in models:
    test(m)
