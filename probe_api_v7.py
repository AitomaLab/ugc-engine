import requests
import config
import json

def test(model, endpoint="https://api.kie.ai/api/v1/generate"):
    print(f"\n--- Model: {model} ---")
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "Authentic UGC selfie of a woman smiling at the camera and saying hello in Spanish.",
        "aspectRatio": "9:16",
        "videoDuration": 8,
        "generate_audio": True,
        "callBackUrl": "https://example.com/callback"
    }
    try:
        resp = requests.post(endpoint, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        print(f"Body: {json.dumps(resp.json(), indent=2)}")
    except Exception as e:
        print(f"Error: {e}")

models = ["seedance-1.5-pro-audio", "seedance-1-5-pro-audio", "seedance-1.5-pro", "seedance-1.5-pro-t2v"]
for m in models:
    test(m)
