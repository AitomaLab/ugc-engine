import airtable_client
import config

def list_all_ultra():
    print(f"{'ID':<20} | {'Influencer':<10} | {'Len':<4} | {'Status':<10} | {'Hook'}")
    print("-" * 120)
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR)
    for r in records:
        f = r["fields"]
        hook = f.get("Hook", "")
        if "BARATA" in hook or "PARA TODO" in hook:
            print(f"{r['id']:<20} | {f.get('Influencer Name', 'N/A'):<10} | {f.get('Length', 'N/A'):<4} | {f.get('Status', 'N/A'):<10} | {hook}")
            print(f"      Path: {f.get('Final Video Path', 'N/A')}")

if __name__ == "__main__":
    list_all_ultra()
