import airtable_client
import config

def list_review_records():
    print(f"{'Influencer':<15} | {'Length':<8} | {'Status':<10} | {'Hook'}")
    print("-" * 100)
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR)
    for r in records:
        f = r["fields"]
        if f.get("Status") == "Review":
            print(f"ID: {r['id']:<20} | {f.get('Influencer Name', 'N/A'):<10} | {f.get('Length', 'N/A'):<5} | Path: {f.get('Final Video Path', 'N/A')}")

if __name__ == "__main__":
    list_review_records()
