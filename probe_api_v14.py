import requests
import config
import json

def test(url, model, is_task=True):
    print(f"\n--- URL: {url} | Model: {model} ---")
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    if is_task:
        payload = {
            "model": model,
            "input": {
                "prompt": "Selfie of a woman smiling.",
                "duration": "8",
                "aspectRatio": "9:16"
            },
            "callBackUrl": "https://example.com/callback"
        }
    else:
        payload = {
            "model": model,
            "prompt": "Selfie of a woman smiling.",
            "duration": "8",
            "aspectRatio": "9:16",
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

# Try the BytePlus style endpoint
test("https://api.kie.ai/api/v1/contents/generations/tasks", "seedance-1.5-pro")
test("https://api.kie.ai/api/v1/contents/generations/tasks", "seedance-1-5-pro")

# Try specific provider prefixes on generate
test("https://api.kie.ai/api/v1/btd-v1.5-pro/generate", "seedance-1.5-pro", False)
test("https://api.kie.ai/api/v1/ark-v1.5-pro/generate", "seedance-1.5-pro", False)
test("https://api.kie.ai/api/v1/byteplus/generate", "seedance-1.5-pro", False)
