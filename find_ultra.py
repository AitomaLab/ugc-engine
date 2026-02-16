import airtable_client
import config

def find_ultra_records():
    print(f"{'ID':<20} | {'Influencer':<10} | {'Status':<10} | {'Length':<5} | {'Hook'}")
    print("-" * 120)
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR)
    for r in records:
        f = r["fields"]
        hook = f.get("Hook", "")
        if "BARATA" in hook or "PARA TODO" in hook:
            print(f"{r['id']:<20} | {f.get('Influencer Name', 'N/A'):<10} | {f.get('Status', 'N/A'):<10} | {f.get('Length', 'N/A'):<5} | {hook[:60]}...")
            print(f"      👉 Final Video Path: {f.get('Final Video Path', 'N/A')}")
            print(f"      👉 Progress: {f.get('Progress', 'N/A')}")

if __name__ == "__main__":
    find_ultra_records()
