import requests
import config
import json

def test(model):
    print(f"\n--- Model: {model} ---")
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "A beautiful young woman smiling at the camera in a sunny park, wearing a white t-shirt, cinematic lighting, 4k.",
        "aspectRatio": "9:16",
        "videoDuration": "8", # string
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

# Try the ones that didn't fail with "not supported" but "model error"
models = ["bytedance/v1-5-pro", "seedance-1.5-pro-audio", "seedance-1-5-pro-audio"]
for m in models:
    test(m)

# Also try the jobs endpoint with dots one last time with correct input
def test_jobs(model):
    print(f"\n--- Jobs: {model} ---")
    url = "https://api.kie.ai/api/v1/jobs/createTask"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "input": {
            "prompt": "Authentic UGC selfie of a woman smiling at the camera and saying hello in Spanish.",
            "duration": "8",
            "ratio": "9:16"
        }
    }
    resp = requests.post(url, headers=headers, json=payload)
    print(f"Status: {resp.status_code}, Code: {resp.json().get('code')}, Msg: {resp.json().get('msg')}")

test_jobs("seedance-1.5-pro")
test_jobs("bytedance-v1.5-pro")
