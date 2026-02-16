import airtable_client
import config

def list_latest_50_assets():
    print(f"{'Title':<40} | {'Type':<12} | {'Time'}")
    print("-" * 100)
    records = airtable_client.get_records("Generated Assets")
    for r in records[-50:]:
        f = r["fields"]
        print(f"{f.get('Content Title', 'N/A'):<40} | {f.get('Asset Type', 'N/A'):<12} | {r.get('createdTime')}")

if __name__ == "__main__":
    list_latest_50_assets()
