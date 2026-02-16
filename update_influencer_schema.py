"""
Add 'Category' field to Influencers table and update Meg/Max categories.
"""
import requests
import config

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
auth = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

print("Step 1: Adding 'Category' field to Influencers table...")
r = requests.get(META_URL, headers=auth)
tables = r.json().get("tables", [])
inf_table = next(t for t in tables if t["name"] == "Influencers")

existing_fields = [f["name"] for f in inf_table["fields"]]
print(f"  Existing fields: {existing_fields}")

if "Category" not in existing_fields:
    ADD_FIELD_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables/{inf_table['id']}/fields"
    # Using singleLineText for simplicity as it's more flexible than singleSelect via API
    payload = {"name": "Category", "type": "singleLineText", "description": "Niche category (e.g., Travel, Shop)"}
    r = requests.post(ADD_FIELD_URL, headers=auth, json=payload)
    if r.status_code == 200:
        print("  ✅ Added 'Category' field")
    else:
        print(f"  ❌ Failed to add field: {r.status_code} {r.text[:300]}")
else:
    print("  'Category' field already exists")

# --- Step 2: Update existing influencers ---
print("\nStep 2: Updating influencers with categories...")

# Get records to find IDs
url = f"{config.AIRTABLE_API_URL}/Influencers"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS)
records = resp.json().get("records", [])

for r in records:
    name = r["fields"].get("Name")
    rid = r["id"]
    category = "Travel" if name == "Meg" else ("Shop" if name == "Max" else None)
    
    if category:
        print(f"  Updating {name} to category '{category}'...")
        patch_url = f"{url}/{rid}"
        presp = requests.patch(patch_url, headers=config.AIRTABLE_HEADERS, json={
            "fields": {"Category": category}
        })
        if presp.status_code == 200:
            print(f"    ✅ Updated {name}")
        else:
            print(f"    ❌ Failed to update {name}: {presp.text[:200]}")

print("\nDone!")
