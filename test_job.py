"""Test POST /jobs endpoint to see what error occurs."""
import requests
import json

# Get first influencer ID
r = requests.get("http://localhost:8000/influencers")
influencers = r.json()
if not influencers:
    print("No influencers found!")
    exit(1)

inf_id = influencers[0]["id"]
print(f"Using influencer: {influencers[0]['name']} ({inf_id})")

# Try creating a job
payload = {
    "influencer_id": inf_id,
    "script_id": None,
    "app_clip_id": None,
}

print(f"\nPOST /jobs with payload: {json.dumps(payload, indent=2)}")
resp = requests.post("http://localhost:8000/jobs", json=payload)
print(f"Status: {resp.status_code}")
print(f"Response: {resp.text[:500]}")
