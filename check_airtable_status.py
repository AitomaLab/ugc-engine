import airtable_client
import json

def check_status():
    items = airtable_client.get_ready_items()
    print(f"Ready Items: {len(items)}")
    for item in items:
        fields = item.get("fields", {})
        print(f"ID: {item['id']}")
        print(f"  Assistant: {fields.get('AI Assistant')}")
        print(f"  Theme: {fields.get('Theme')}")
        print(f"  Status: {fields.get('Status')}")
        print(f"  Progress: {fields.get('Progress')}")
        print("-" * 20)

if __name__ == "__main__":
    check_status()
