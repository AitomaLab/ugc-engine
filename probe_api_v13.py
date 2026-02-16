import requests
import config
import json

def test(model, duration_val):
    print(f"\n--- Testing: {model} with duration={duration_val} ---")
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "A beautiful young woman smiling at the camera in a sunny park, wearing a white t-shirt, talking naturally.",
        "aspectRatio": "9:16",
        "duration": duration_val,
        "quality": "720p",
        "generate_audio": True,
        "callBackUrl": "https://example.com/callback"
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

# Try both seedance-1-5-pro and seedance-1-5-pro-audio
# Using string "8" as per user's hint
for m in ["seedance-1-5-pro", "seedance-1-5-pro-audio", "seedance-1.5-pro", "seedance-1.5-pro-audio"]:
    test(m, "8")
    test(m, 8)
