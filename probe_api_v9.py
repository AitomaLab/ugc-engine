import requests
import config
import json

def test(url, model, payload):
    print(f"\n--- Testing: {model} on {url} ---")
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
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

# Payload structure as per user's "input.duration" hint
input_payload = {
    "prompt": "Hello",
    "duration": "8",
    "aspectRatio": "9:16",
    "generate_audio": True
}

models = ["seedance_v1_5_pro", "seedance-1-5-pro", "seedance-v1-5-pro"]
endpoints = [
    "https://api.kie.ai/api/v1/seedance/generate",
    "https://api.kie.ai/api/v1/jobs/createTask"
]

for m in models:
    for e in endpoints:
        if "jobs/createTask" in e:
            p = {"model": m, "input": input_payload}
        else:
            p = {"model": m, **input_payload}
        test(e, m, p)
