import requests
import config
import json

def test(model, img_field):
    print(f"\n--- Model: {model} | Field: {img_field} ---")
    url = "https://api.kie.ai/api/v1/generate"
    headers = {"Authorization": f"Bearer {config.KIE_API_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": model,
        "prompt": "Authentic UGC selfie video of this woman speaking directly to the camera in Spanish.",
        "aspectRatio": "9:16",
        "duration": "8",
        img_field: "https://v5.airtableusercontent.com/v3/u/50/50/1770847200000/0j6-C3_D6O0P8vjD6pW1-Q/p-m7vT6f0O2O-m7vT6f0O2O/Sofia_ref.jpg",
        "generate_audio": True,
        "callBackUrl": "https://example.com/callback",
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

# Try both field names for image
for field in ["imageUrl", "image_url"]:
    test("seedance-1.5-pro-audio", field)
    test("seedance-1-5-pro", field)
    test("bytedance-v1.5-pro", field)
