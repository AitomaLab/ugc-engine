"""Quick check: list all tables and their records."""
import config
import requests
import json

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
AUTH = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}"}

# List all tables
r = requests.get(META_URL, headers=AUTH)
tables = r.json().get("tables", [])
print(f"=== ALL TABLES ({len(tables)}) ===")
for t in tables:
    print(f"  {t['name']} (id: {t['id']}, fields: {len(t.get('fields', []))})")
    # Show field names
    for f in t.get("fields", []):
        print(f"    - {f['name']} ({f['type']})")

# Check record counts in key tables
print()
for tbl_name in [t["name"] for t in tables]:
    url = f"{config.AIRTABLE_API_URL}/{tbl_name}"
    r = requests.get(url, headers=config.AIRTABLE_HEADERS)
    data = r.json()
    records = data.get("records", [])
    print(f"\n=== {tbl_name} ({len(records)} records) ===")
    for rec in records:
        fields = rec.get("fields", {})
        # Print fields, skip attachment data for readability
        clean = {}
        for k, v in fields.items():
            if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict) and "url" in v[0]:
                clean[k] = f"[{len(v)} attachment(s)]"
            else:
                clean[k] = v
        print(f"  {json.dumps(clean, indent=4)}")
