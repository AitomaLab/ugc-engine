import os
import requests
import json
import config

def update_schema():
    # 1. Add 'Gender' field to Influencers
    url = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
    headers = {
        "Authorization": f"Bearer {config.AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # We need the table ID. Let's find it.
    resp = requests.get(url, headers=headers)
    tables = resp.json()["tables"]
    inf_table_id = next(t["id"] for t in tables if t["name"] == "Influencers")
    
    print(f"Adding 'Gender' field to table {inf_table_id}...")
    field_url = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables/{inf_table_id}/fields"
    field_data = {
        "name": "Gender",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Male"},
                {"name": "Female"}
            ]
        }
    }
    
    resp = requests.post(field_url, headers=headers, json=field_data)
    print(f"Status: {resp.status_code}")
    print(resp.json())

    # 2. Update records
    # Meg -> Female, Max -> Male
    records_url = f"{config.AIRTABLE_API_URL}/Influencers"
    resp = requests.get(records_url, headers=config.AIRTABLE_HEADERS)
    records = resp.json()["records"]
    
    updates = []
    for r in records:
        name = r["fields"].get("Name")
        gender = "Female" if name == "Meg" else "Male"
        updates.append({
            "id": r["id"],
            "fields": {"Gender": gender}
        })
    
    resp = requests.patch(records_url, headers=config.AIRTABLE_HEADERS, json={"records": updates})
    print(f"Update records status: {resp.status_code}")

if __name__ == "__main__":
    update_schema()
