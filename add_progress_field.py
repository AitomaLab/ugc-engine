"""Add a Progress text field to Content Calendar for granular status updates."""
import requests
import config

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
auth = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

# Get tables
r = requests.get(META_URL, headers=auth)
tables = r.json().get("tables", [])
cc_table = next(t for t in tables if t["name"] == "Content Calendar")

# Check if Progress field already exists
existing_fields = [f["name"] for f in cc_table["fields"]]
if "Progress" in existing_fields:
    print("✅ 'Progress' field already exists")
    exit(0)

# Add Progress field
ADD_FIELD_URL = f"{META_URL}/{cc_table['id']}/fields"
payload = {
    "name": "Progress",
    "type": "singleLineText",
    "description": "Detailed generation progress (e.g., 'Gen: Hook (1/4)', 'Assembling')"
}

r = requests.post(ADD_FIELD_URL, headers=auth, json=payload)
if r.status_code == 200:
    print("✅ Added 'Progress' field to Content Calendar")
else:
    print(f"❌ Failed: {r.status_code}")
    print(f"Response: {r.text}")
