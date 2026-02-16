import airtable_client
import config

def list_15s_records():
    print(f"{'ID':<20} | {'Influencer':<10} | {'Status':<10} | {'Hook'}")
    print("-" * 100)
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR)
    for r in records:
        f = r["fields"]
        if f.get("Length") == "15s":
            status = f.get("Status", "N/A")
            print(f"ID: {r['id']:<20} | {f.get('Influencer Name', 'N/A'):<10} | Status: [{status}] | Hook: {f.get('Hook')[:50]}...")

if __name__ == "__main__":
    list_15s_records()
