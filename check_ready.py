"""Check for any items in the Content Calendar with status 'Ready'."""
import airtable_client
import config

try:
    items = airtable_client.get_ready_items()
    if not items:
        print("NO_READY_ITEMS")
    else:
        print(f"FOUND_{len(items)}_READY_ITEMS")
        for i in items:
            f = i["fields"]
            print(f" - {f.get('Influencer Name')} | {f.get('AI Assistant')} | {f.get('Hook')} (ID: {i['id']})")
except Exception as e:
    print(f"ERROR: {e}")
