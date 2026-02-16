"""Reset Content Calendar entries to Ready status for testing."""
import requests
import config

url = f"{config.AIRTABLE_API_URL}/Content Calendar"

# Get all records
r = requests.get(url, headers=config.AIRTABLE_HEADERS)
records = r.json().get("records", [])

print(f"Found {len(records)} Content Calendar entries")

# Reset all records to Ready
for rec in records:
    rec_id = rec["id"]
    hook = rec["fields"].get("Hook", "")
    
    # Update to Ready
    patch_url = f"{url}/{rec_id}"
    payload = {"fields": {"Status": "Ready"}}
    r = requests.patch(patch_url, headers=config.AIRTABLE_HEADERS, json=payload)
    
    if r.status_code == 200:
        print(f"✅ Reset to Ready: {hook[:60]}...")
    else:
        print(f"❌ Failed for {rec_id}: {r.text[:300]}")
