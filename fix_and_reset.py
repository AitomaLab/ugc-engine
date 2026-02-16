import airtable_client
import config

def fix_and_reset():
    print("🧹 Fixing Airtable records for fresh re-run...")
    
    # 1. Fix Max (English -> Spanish)
    # We find the Max record that was in 'Review'
    records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR, 
                                        filter_formula='{Influencer Name} = "Max"')
    
    for rec in records:
        if rec["fields"].get("Status") == "Review":
            print(f"✅ Resetting Max (ID: {rec['id']})")
            airtable_client.requests.patch(
                f"{config.AIRTABLE_API_URL}/{config.TABLE_CONTENT_CALENDAR}/{rec['id']}",
                headers=config.AIRTABLE_HEADERS,
                json={
                    "fields": {
                        "Hook": "¡Oye, PARA TODO! Si compras online habitualmente, tienes que ver esto.",
                        "Status": "Ready",
                        "Progress": "Ready"
                    }
                }
            )

    # 2. Reset Meg
    meg_records = airtable_client.get_records(config.TABLE_CONTENT_CALENDAR, 
                                           filter_formula='{Influencer Name} = "Meg"')
    for rec in meg_records:
        if rec["fields"].get("Status") == "Review":
             print(f"✅ Resetting Meg (ID: {rec['id']})")
             airtable_client.update_status(rec["id"], "Ready")

if __name__ == "__main__":
    fix_and_reset()
