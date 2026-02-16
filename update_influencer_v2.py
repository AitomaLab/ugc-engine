import requests
import json
import config

def update_schema():
    print("🚀 Updating Influencers table schema for Ultra-Realistic features...")
    url = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
    headers = {
        "Authorization": f"Bearer {config.AIRTABLE_TOKEN}",
        "Content-Type": "application/json"
    }

    # First, get the table ID for Influencers
    resp = requests.get(url, headers=headers)
    tables = resp.json().get("tables", [])
    influencers_table = next((t for t in tables if t["name"] == config.TABLE_INFLUENCERS), None)
    
    if not influencers_table:
        print(f"❌ Could not find table: {config.TABLE_INFLUENCERS}")
        return
        
    table_id = influencers_table["id"]
    existing_fields = [f["name"] for f in influencers_table["fields"]]
    
    new_fields = [
        {"name": "Age", "type": "singleLineText"},
        {"name": "Visual Description", "type": "multilineText"},
        {"name": "Energy Level", "type": "singleSelect", "options": {"choices": [{"name": "High"}, {"name": "Medium"}, {"name": "Calm"}]}},
        {"name": "Personality", "type": "multilineText"}
    ]
    
    for field in new_fields:
        if field["name"] in existing_fields:
            print(f"   ℹ️ Field '{field['name']}' already exists.")
            continue
            
        print(f"   ➕ Adding field: {field['name']}...")
        f_url = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables/{table_id}/fields"
        f_resp = requests.post(f_url, headers=headers, json=field)
        if f_resp.status_code == 200:
            print(f"      ✅ Success")
        else:
            print(f"      ❌ Failed: {f_resp.text}")

def populate_data():
    print("\n📝 Populating Meg and Max with ultra-realistic traits...")
    url = f"{config.AIRTABLE_API_URL}/{config.TABLE_INFLUENCERS}"
    headers = config.AIRTABLE_HEADERS
    
    # Get existing records
    resp = requests.get(url, headers=headers)
    records = resp.json().get("records", [])
    
    # Meg data
    meg_traits = {
        "Age": "28",
        "Visual Description": "Long wavy brown hair, wearing a stylish but cozy emerald green sweater and subtle gold hoop earrings. She has a warm, inviting presence.",
        "Energy Level": "High",
        "Personality": "Grounded, quietly confident travel agent who feels like a knowledgeable friend. She values authenticity and hidden gems over tourist traps."
    }
    
    # Max data
    max_traits = {
        "Age": "25",
        "Visual Description": "Styled short dark hair with a slight fade, wearing a modern casual red bomber jacket over a gray hoodie. Sharp, tech-forward aesthetic.",
        "Energy Level": "High",
        "Personality": "Fast-talking, precision-driven personal shopping assistant. He’s the guy who knows every hack to get the best value without compromising quality."
    }
    
    for record in records:
        name = record["fields"].get("Name")
        rid = record["id"]
        
        updates = None
        if name == "Meg":
            updates = meg_traits
        elif name == "Max":
            updates = max_traits
            
        if updates:
            print(f"   Updating {name} ({rid})...")
            u_resp = requests.patch(f"{url}/{rid}", headers=headers, json={"fields": updates})
            if u_resp.status_code == 200:
                print(f"      ✅ Success")
            else:
                print(f"      ❌ Failed: {u_resp.text}")

if __name__ == "__main__":
    update_schema()
    populate_data()
