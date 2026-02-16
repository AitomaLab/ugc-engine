"""Select two random hooks (one Travel, one Shop) and mark them as Ready."""
import requests
import config
import random

url = f"{config.AIRTABLE_API_URL}/Content Calendar"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS, params={"filterByFormula": "{Status} = 'Draft'"})
records = resp.json().get("records", [])

travel_hooks = [r for r in records if r["fields"].get("AI Assistant") == "Travel"]
shop_hooks = [r for r in records if r["fields"].get("AI Assistant") == "Shop"]

selected = []
if travel_hooks:
    selected.append(random.choice(travel_hooks))
if shop_hooks:
    selected.append(random.choice(shop_hooks))

print(f"🎯 Selected {len(selected)} hooks for generation:")

for s in selected:
    rid = s["id"]
    hook = s["fields"].get("Hook")
    assistant = s["fields"].get("AI Assistant")
    influencer = s["fields"].get("Influencer Name")
    print(f"  - [{assistant}] {influencer}: {hook[:60]}...")
    
    # Update status to Ready
    requests.patch(f"{url}/{rid}", headers=config.AIRTABLE_HEADERS, json={
        "fields": {"Status": "Ready"}
    })

print("\n🚀 Ready for generation! Run: python pipeline.py --batch --limit 2")
