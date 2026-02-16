import requests
import config
import json

def test_endpoint(url, payload):
    print(f"Testing {url}...")
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=10)
        print(f"  Status: {resp.status_code}")
        try:
            print(f"  Body: {json.dumps(resp.json(), indent=2)}")
        except:
            print(f"  Body: {resp.text[:200]}")
    except Exception as e:
        print(f"  Error: {e}")

# Try the jobs/createTask payload format
payload_jobs = {
    "model": "seedance-1-5-pro",
    "input": {
        "prompt": "Authentic UGC selfie of a woman smiling at the camera and saying hello in Spanish.",
        "aspect_ratio": "9:16",
        "video_duration": 8,
        "generate_audio": True
    }
}

test_endpoint("https://api.kie.ai/api/v1/jobs/createTask", payload_jobs)
