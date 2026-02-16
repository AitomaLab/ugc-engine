"""Test Kie.ai Veo 3.1 API — try different model names and endpoints."""
import requests
import json
import config

API_KEY = config.KIE_API_KEY
BASE_HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# Test different endpoint/model combinations
tests = [
    # (endpoint, model_name, description)
    ("https://api.kie.ai/api/v1/jobs/createTask", "google/veo-3.1-fast", "jobs endpoint + google/ prefix"),
    ("https://api.kie.ai/api/v1/jobs/createTask", "veo-3.1-fast", "jobs endpoint + no prefix"),
    ("https://api.kie.ai/api/v1/jobs/createTask", "veo3.1 fast", "jobs endpoint + space format"),
    ("https://api.kie.ai/api/v1/veo/generate", None, "veo endpoint + no model field"),
]

prompt = "A young woman smiling at the camera and saying hello."

for endpoint, model_name, desc in tests:
    print(f"\n{'='*60}")
    print(f"Test: {desc}")
    print(f"  Endpoint: {endpoint}")
    print(f"  Model: {model_name}")

    if "veo/generate" in endpoint:
        # Different payload format for veo endpoint
        payload = {
            "prompt": prompt,
            "aspect_ratio": "9:16",
            "model": "veo3.1 fast",
            "callBackUrl": "https://example.com/callback",
        }
    else:
        payload = {
            "model": model_name,
            "input": {
                "prompt": prompt,
                "aspect_ratio": "9:16",
            }
        }

    try:
        resp = requests.post(endpoint, headers=BASE_HEADERS, json=payload, timeout=15)
        result = resp.json()
        code = result.get("code")
        msg = result.get("message", "")
        data = result.get("data")

        print(f"  Status: {resp.status_code}")
        print(f"  Code: {code}")
        print(f"  Message: {msg[:200]}")
        if data and isinstance(data, dict) and "taskId" in data:
            print(f"  ✅ SUCCESS! Task ID: {data['taskId'][:30]}...")
            print(f"  Full response: {json.dumps(result, indent=2)[:300]}")
            break  # Don't waste credits testing more
        else:
            print(f"  Data: {str(data)[:200]}")
    except Exception as e:
        print(f"  ❌ Error: {e}")
