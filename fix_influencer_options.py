"""Convert Influencer field from singleSelect to singleLineText."""
import requests
import config

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
auth = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

r = requests.get(META_URL, headers=auth)
tables = r.json().get("tables", [])

cc_table = next(t for t in tables if t["name"] == "Content Calendar")
inf_field = next(f for f in cc_table["fields"] if f["name"] == "Influencer")

field_id = inf_field["id"]
print(f"Field: {inf_field['name']} (id: {field_id}, type: {inf_field['type']})")

# Convert to singleLineText — no more select restrictions
UPDATE_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables/{cc_table['id']}/fields/{field_id}"
payload = {"type": "singleLineText"}

r = requests.patch(UPDATE_URL, headers=auth, json=payload)
print(f"Status: {r.status_code}")
if r.status_code == 200:
    print("✅ Influencer field converted to text — any name works now!")
else:
    print(f"Response: {r.text[:500]}")
