import airtable_client
import config

def check_status():
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR)
    print(f"{'Influencer':<15} | {'Status':<15} | {'Progress':<20} | {'Title'}")
    print("-" * 80)
    for rec in records:
        f = rec["fields"]
        if f.get("Status") in ["Review", "Processing", "Ready"]:
            print(f"{f.get('Influencer Name', 'N/A'):<15} | {f.get('Status', 'N/A'):<15} | {f.get('Progress', 'N/A'):<20} | {f.get('Content Title', 'N/A')}")

if __name__ == "__main__":
    check_status()
