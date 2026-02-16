"""
Workaround: Create content entries without the restricted singleSelect Influencer field.
Instead, use an 'Influencer Name' text field (created via metadata API).
Then update config + airtable_client to use 'Influencer Name' instead.
"""
import requests
import json
import config

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
auth = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

# --- Step 1: Try to add a new text field 'Influencer Name' ---
print("Step 1: Adding 'Influencer Name' text field...")
r = requests.get(META_URL, headers=auth)
tables = r.json().get("tables", [])
cc_table = next(t for t in tables if t["name"] == "Content Calendar")

existing_fields = [f["name"] for f in cc_table["fields"]]
print(f"  Existing fields: {existing_fields}")

if "Influencer Name" not in existing_fields:
    ADD_FIELD_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables/{cc_table['id']}/fields"
    payload = {"name": "Influencer Name", "type": "singleLineText", "description": "Name matching Influencers table"}
    r = requests.post(ADD_FIELD_URL, headers=auth, json=payload)
    if r.status_code == 200:
        print("  ✅ Added 'Influencer Name' field")
    else:
        print(f"  ❌ Failed: {r.status_code} {r.text[:300]}")
        # If we can't add fields either, just skip the field
        print("  Will create entries without influencer field...")
else:
    print("  Already exists")

# --- Step 2: Create content entries ---
print("\nStep 2: Creating Content Calendar entries...")

url = f"{config.AIRTABLE_API_URL}/Content Calendar"

entries = [
    {
        "fields": {
            "Hook": "This app literally found me the best deal on sneakers in 10 seconds",
            "AI Assistant": "Shop",
            "Theme": "online shopping discovery",
            "Caption": "Naiara's shopping assistant just changed the way I buy things online. Download now!",
            "Influencer Name": "Meg",
            "Length": "30s",
            "Status": "Ready",
        }
    },
    {
        "fields": {
            "Hook": "I just planned my entire Bali trip in 30 seconds with this app",
            "AI Assistant": "Travel",
            "Theme": "tropical vacation planning",
            "Caption": "Naiara is the AI travel assistant you didn't know you needed. Download now, link in bio!",
            "Influencer Name": "Meg",
            "Length": "30s",
            "Status": "Ready",
        }
    },
]

for entry in entries:
    resp = requests.post(url, headers=config.AIRTABLE_HEADERS, json=entry)
    if resp.status_code == 200:
        rec = resp.json()
        f = rec["fields"]
        print(f"  ✅ Created: {f.get('Hook', '')[:60]}...")
        print(f"     Record ID: {rec['id']}")
    else:
        print(f"  ❌ Failed: {resp.status_code}")
        print(f"     {resp.text[:300]}")
        # If Influencer Name field doesn't exist, try without it
        if "UNKNOWN_FIELD_NAME" in resp.text:
            print("  Retrying without 'Influencer Name'...")
            del entry["fields"]["Influencer Name"]
            entry["fields"]["Influencer"] = "Meg"
            resp2 = requests.post(url, headers=config.AIRTABLE_HEADERS, json=entry)
            if resp2.status_code == 200:
                print(f"  ✅ Created (without influencer name)")
            else:
                print(f"  ❌ Still failed: {resp2.text[:300]}")

print("\nDone!")
