import airtable_client
import config

def list_latest_assets():
    print(f"{'Influencer/Title':<40} | {'Type':<12} | {'Time'}")
    print("-" * 100)
    records = airtable_client.get_records("Generated Assets")
    # Sort by creation time (if available) or just take last 20
    # records are usually returned in insertion order or by ID
    for r in records[-20:]:
        f = r["fields"]
        print(f"{f.get('Content Title', 'N/A'):<40} | {f.get('Asset Type', 'N/A'):<12} | {r.get('createdTime')}")

if __name__ == "__main__":
    list_latest_assets()
