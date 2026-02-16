"""Reset specifically identified failed records back to Ready."""
import requests
import config

url = f"{config.AIRTABLE_API_URL}/Content Calendar"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS, params={"filterByFormula": "{Status} = 'Review'"})
records = resp.json().get("records", [])

reset_count = 0
for r in records:
    fields = r["fields"]
    assistant = fields.get("AI Assistant")
    length = fields.get("Length")
    hook = fields.get("Hook", "")
    
    # Target the 15s Spanish hooks recently created
    if length == "15s" and ("organizó" in hook or "zapatillas" in hook):
        print(f"Resetting {r['id']} ({hook[:30]}...)")
        requests.patch(f"{url}/{r['id']}", headers=config.AIRTABLE_HEADERS, json={
            "fields": {"Status": "Ready", "Final Video": None}
        })
        reset_count += 1

print(f"\nDone! Reset {reset_count} records.")
