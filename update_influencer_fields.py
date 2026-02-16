import os
import requests
import json
import config

def update_schema():
    # 1. Add fields to Influencers
    url = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
    headers = {
        "Authorization": f"Bearer {config.AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Find table ID
    resp = requests.get(url, headers=headers)
    tables = resp.json()["tables"]
    inf_table_id = next(t["id"] for t in tables if t["name"] == "Influencers")
    
    field_url = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables/{inf_table_id}/fields"
    
    # Add Accent field
    print(f"Adding 'Accent' field to table {inf_table_id}...")
    accent_data = {
        "name": "Accent",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Castilian Spanish (Spain)"},
                {"name": "Latino Spanish"},
                {"name": "Neutral Spanish"}
            ]
        }
    }
    requests.post(field_url, headers=headers, json=accent_data)

    # Add Tone field
    print(f"Adding 'Tone' field...")
    tone_data = {
        "name": "Tone",
        "type": "singleSelect",
        "options": {
            "choices": [
                {"name": "Excited"},
                {"name": "Enthusiastic"},
                {"name": "Casual"},
                {"name": "Professional"},
                {"name": "Urgent"}
            ]
        }
    }
    requests.post(field_url, headers=headers, json=tone_data)

    # 2. Update records
    records_url = f"{config.AIRTABLE_API_URL}/Influencers"
    resp = requests.get(records_url, headers=config.AIRTABLE_HEADERS)
    records = resp.json()["records"]
    
    updates = []
    for r in records:
        name = r["fields"].get("Name")
        # Set defaults to Spain/Castilian and Enthusiastic
        updates.append({
            "id": r["id"],
            "fields": {
                "Accent": "Castilian Spanish (Spain)",
                "Tone": "Enthusiastic"
            }
        })
    
    resp = requests.patch(records_url, headers=config.AIRTABLE_HEADERS, json={"records": updates})
    print(f"Update records status: {resp.status_code}")

if __name__ == "__main__":
    update_schema()
