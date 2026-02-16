import requests
import config
import json

def test(model):
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "Hello",
        "aspectRatio": "9:16",
        "videoDuration": 8,
        "generate_audio": True
    }
    resp = requests.post(url, headers=headers, json=payload)
    print(f"Model: {model} -> Status: {resp.status_code}, Code: {resp.json().get('code')}, Msg: {resp.json().get('msg')}")

models = ["bytedance-seedance-v1-5-pro", "seedance-v1-5-pro", "btd-v1-5-pro", "seedance-1-5-pro-audio"]
for m in models:
    test(m)
