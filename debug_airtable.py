"""Debug: Dump exact Airtable field names and values to a file."""
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv(".env")

AIRTABLE_TOKEN = os.getenv("AIRTABLE_TOKEN")
BASE_URL = f"https://api.airtable.com/v0/{os.getenv('AIRTABLE_BASE_ID', 'appVAUSKsSNnZNqnt')}"
HEADERS = {"Authorization": f"Bearer {AIRTABLE_TOKEN}"}

output = []

output.append("INFLUENCERS TABLE:")
output.append("=" * 60)
resp = requests.get(f"{BASE_URL}/Influencers", headers=HEADERS)
records = resp.json().get("records", [])
for rec in records:
    output.append(f"\nRecord ID: {rec['id']}")
    fields = rec["fields"]
    for k in sorted(fields.keys()):
        v = fields[k]
        if isinstance(v, list):
            # For attachments, just show key info
            val_str = json.dumps(v, default=str)[:300]
        elif isinstance(v, str) and len(v) > 100:
            val_str = f'"{v[:100]}..."'
        else:
            val_str = json.dumps(v, default=str)
        output.append(f"  [{k}] = {val_str}")

output.append("\n\nAPP CLIPS TABLE:")
output.append("=" * 60)
resp2 = requests.get(f"{BASE_URL}/App Clips", headers=HEADERS)
records2 = resp2.json().get("records", [])
for rec in records2:
    output.append(f"\nRecord ID: {rec['id']}")
    fields = rec["fields"]
    for k in sorted(fields.keys()):
        v = fields[k]
        if isinstance(v, list):
            val_str = json.dumps(v, default=str)[:300]
        elif isinstance(v, str) and len(v) > 100:
            val_str = f'"{v[:100]}..."'
        else:
            val_str = json.dumps(v, default=str)
        output.append(f"  [{k}] = {val_str}")

text = "\n".join(output)
with open("airtable_dump.txt", "w", encoding="utf-8") as f:
    f.write(text)
print(text)
