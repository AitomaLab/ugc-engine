import requests
import config
import json
import time

def test_seedance_official():
    print("Testing Seedance 1.5 Pro with official documentation specs...")
    url = "https://api.kie.ai/api/v1/jobs/createTask"
    headers = {
        "Authorization": f"Bearer {config.KIE_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # Official payload structure
    payload = {
        "model": "bytedance/seedance-1.5-pro",
        "input": {
            "prompt": "Authentic UGC selfie of a woman smiling at the camera and saying hello in Spanish.",
            "input_urls": ["https://v5.airtableusercontent.com/v3/u/50/50/1770847200000/0j6-C3_D6O0P8vjD6pW1-Q/p-m7vT6f0O2O-m7vT6f0O2O/Sofia_ref.jpg"],
            "aspect_ratio": "9:16",
            "resolution": "720p",
            "duration": "8",
            "fixed_lens": True,
            "generate_audio": True
        },
        "callBackUrl": "https://example.com/callback"
    }
    
    try:
        print(f"Submitting task to {url}...")
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        print(f"Status: {resp.status_code}")
        result = resp.json()
        print(f"Response: {json.dumps(result, indent=2)}")
        
        if result.get("code") == 200:
            task_id = result["data"]["taskId"]
            print(f"✅ Task created! ID: {task_id}")
            
            # Poll once to check state
            print("Polling state...")
            poll_url = f"https://api.kie.ai/api/v1/jobs/recordInfo?taskId={task_id}"
            poll_resp = requests.get(poll_url, headers=headers)
            poll_result = poll_resp.json()
            print(f"Poll Result: {json.dumps(poll_result, indent=2)}")
        else:
            print(f"❌ Creation failed: {result.get('msg')}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_seedance_official()
