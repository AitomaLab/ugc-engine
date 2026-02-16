"""Create the Generated Assets table for tracking all created assets."""
import requests
import config

META_URL = f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"
auth = {"Authorization": f"Bearer {config.AIRTABLE_TOKEN}", "Content-Type": "application/json"}

# Check if table already exists
r = requests.get(META_URL, headers=auth)
tables = r.json().get("tables", [])
existing_names = [t["name"] for t in tables]

if "Generated Assets" in existing_names:
    print("✅ 'Generated Assets' table already exists")
    exit(0)

# Create the table
fields = [
    {"name": "Content Title", "type": "singleLineText",
     "description": "Parent project name (primary field)"},
    {"name": "Asset Type", "type": "singleSelect",
     "options": {"choices": [
         {"name": "Veo Video"},
         {"name": "Reference Image"},
         {"name": "App Clip"},
         {"name": "Music"},
         {"name": "Final Video"},
     ]}},
    {"name": "Scene Name", "type": "singleLineText",
     "description": "e.g. hook, reaction, app_demo, cta"},
    {"name": "Source URL", "type": "url",
     "description": "CDN or Airtable attachment URL"},
    {"name": "Status", "type": "singleSelect",
     "options": {"choices": [
         {"name": "Queued"},
         {"name": "Generating"},
         {"name": "Ready"},
         {"name": "Failed"},
     ]}},
    {"name": "Duration", "type": "number",
     "options": {"precision": 1},
     "description": "Video length in seconds"},
    {"name": "Model Used", "type": "singleLineText",
     "description": "e.g. veo3_fast, suno-v4"},
    {"name": "Cost", "type": "currency",
     "options": {"precision": 2, "symbol": "$"},
     "description": "API cost for this asset"},
    {"name": "Error Message", "type": "multilineText"},
]

payload = {
    "name": "Generated Assets",
    "description": "Tracks all AI-generated assets (videos, images, music) with metadata",
    "fields": fields,
}

r = requests.post(META_URL, headers=auth, json=payload)
if r.status_code == 200:
    table_id = r.json()["id"]
    print(f"✅ Created 'Generated Assets' table (id: {table_id})")
else:
    print(f"❌ Failed: {r.status_code}")
    print(f"Full response: {r.text}")
