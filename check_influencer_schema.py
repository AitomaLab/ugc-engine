"""Check Influencers table schema and records."""
import requests
import config

print("=== INFLUENCERS TABLE CHECK ===")
url = f"{config.AIRTABLE_API_URL}/Influencers"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS)
if resp.status_code == 200:
    records = resp.json().get("records", [])
    print(f"Found {len(records)} records.")
    for r in records:
        print(f"ID: {r['id']} | Fields: {list(r['fields'].keys())}")
        print(f"  Name: {r['fields'].get('Name')}")
else:
    print(f"Error: {resp.status_code} {resp.text}")
