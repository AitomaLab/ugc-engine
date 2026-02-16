import airtable_client
import config

def check_ultra_captions():
    print(f"{'ID':<20} | {'Influencer':<10} | {'Caption'}")
    print("-" * 100)
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR)
    for r in records:
        f = r["fields"]
        hook = f.get("Hook", "")
        if "BARATA" in hook or "PARA TODO" in hook:
            print(f"{r['id']:<20} | {f.get('Influencer Name', 'N/A'):<10} | {f.get('Caption', 'N/A')}")

if __name__ == "__main__":
    check_ultra_captions()
