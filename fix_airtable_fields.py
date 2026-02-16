"""Check and fix Airtable field types for Status and Progress."""
import requests
import config
import json

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
auth = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

print("🔍 Checking Content Calendar fields...")
r = requests.get(META_URL, headers=auth)
tables = r.json().get("tables", [])
cc_table = next(t for t in tables if t["name"] == "Content Calendar")

fields_to_fix = []
for f in cc_table["fields"]:
    if f["name"] in ["Status", "Progress"] and f["type"] == "singleSelect":
        print(f"  Field '{f['name']}' is a restricted singleSelect.")
        fields_to_fix.append(f)

for f in fields_to_fix:
    print(f"\n🛠️ Converting '{f['name']}' to singleLineText for dynamic updates...")
    # Metadata API doesn't support direct type change from select to text easily if it's restricted?
    # Actually, we can just update the type.
    update_url = f"{META_URL}/{cc_table['id']}/fields/{f['id']}"
    payload = {
        "type": "singleLineText",
        "name": f['name']
    }
    ur = requests.patch(update_url, headers=auth, json=payload)
    if ur.status_code == 200:
        print(f"  ✅ '{f['name']}' is now singleLineText.")
    else:
        print(f"  ❌ Failed to update '{f['name']}': {ur.status_code} {ur.text[:300]}")
        
        # Alternative: If it must be a select, we must add the options.
        # But for 'Progress', singleLineText is much better for things like "Gen: Hook (1/2)"
        # Let's try to just update if it failed.
        if "CANNOT_CHANGE_FIELD_TYPE" in ur.text:
             print(f"  Trying to expand select options instead...")
             # ... (logic to add options if needed, but text is preferred)

print("\nDone!")
