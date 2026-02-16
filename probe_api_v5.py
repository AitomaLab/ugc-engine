import requests
import config
import json

def test_endpoint(url, payload, description):
    print(f"\n--- Testing: {description} ---")
    print(f"URL: {url}")
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"Status: {resp.status_code}")
        try:
            body = resp.json()
            code = body.get("code")
            msg = body.get("msg", body.get("message", ""))
            print(f"Response Code: {code}")
            print(f"Message: {msg}")
            if code == 200:
                print(f"✅ Potential Match! Data: {json.dumps(body.get('data'), indent=2)}")
        except:
            print(f"Body: {resp.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

# Base payload based on user details
base_input = {
    "prompt": "Authentic UGC selfie of a woman smiling at the camera and saying hello in Spanish.",
    "aspect_ratio": "9:16",
    "duration": "8", # String as per user note
    "generate_audio": True
}

# Test different model identifiers and endpoints
models = ["seedance-1-5-pro", "seedance-v1.5-pro", "seedance-1.5-pro", "bytedance-v1.5-pro"]
endpoints = [
    "https://api.kie.ai/api/v1/generate",
    "https://api.kie.ai/api/v1/seedance/generate",
    "https://api.kie.ai/api/v1/jobs/createTask",
]

for model in models:
    for endpoint in endpoints:
        if "jobs/createTask" in endpoint:
            payload = {"model": model, "input": base_input}
        else:
            payload = {"model": model, **base_input}
        
        test_endpoint(endpoint, payload, f"Model: {model} on {endpoint}")

# Also try the specific pattern found in some docs: {model}/generate
for model in models:
    url = f"https://api.kie.ai/api/v1/{model}/generate"
    test_endpoint(url, base_input, f"Path-based: {url}")
