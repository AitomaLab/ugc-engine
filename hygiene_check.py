import airtable_client
import config
import requests
import json

def hygiene_check():
    print("=== HYGIENE CHECK ===")
    
    # 1. Influencers
    records_url = f"{config.AIRTABLE_API_URL}/Influencers"
    resp = requests.get(records_url, headers=config.AIRTABLE_HEADERS)
    records = resp.json()["records"]
    
    updates = []
    for r in records:
        f = r["fields"]
        name = f.get("Name")
        current_gender = f.get("Gender")
        current_accent = f.get("Accent")
        current_tone = f.get("Tone")
        current_category = f.get("Category")
        
        needs_update = False
        new_fields = {}
        
        # Gender fix
        target_gender = "Female" if name == "Meg" else "Male"
        if current_gender != target_gender:
            print(f"  Fixing gender for {name}: {current_gender} -> {target_gender}")
            new_fields["Gender"] = target_gender
            needs_update = True
            
        # Accent fix
        if current_accent != "Castilian Spanish (Spain)":
            print(f"  Fixing accent for {name}: {current_accent} -> Castilian Spanish (Spain)")
            new_fields["Accent"] = "Castilian Spanish (Spain)"
            needs_update = True
            
        # Tone fix
        if current_tone != "Enthusiastic":
            print(f"  Fixing tone for {name}: {current_tone} -> Enthusiastic")
            new_fields["Tone"] = "Enthusiastic"
            needs_update = True
            
        # Category check
        target_cat = "Travel" if name == "Meg" else "Shop"
        if current_category != target_cat:
             print(f"  Fixing category for {name}: {current_category} -> {target_cat}")
             new_fields["Category"] = target_cat
             needs_update = True
             
        if needs_update:
            updates.append({"id": r["id"], "fields": new_fields})
            
    if updates:
        requests.patch(records_url, headers=config.AIRTABLE_HEADERS, json={"records": updates})
        print(f"  Updated {len(updates)} influencer records.")
    else:
        print("  Influencer data is correct.")

    # 2. App Clips check
    print("\n=== APP CLIPS CHECK ===")
    clips_url = f"{config.AIRTABLE_API_URL}/App Clips"
    resp = requests.get(clips_url, headers=config.AIRTABLE_HEADERS)
    clips = resp.json()["records"]
    
    cats = [c["fields"].get("AI Assistant") for c in clips]
    print(f"  Categories available: {list(set(cats))}")
    if "Travel" not in cats or "Shop" not in cats:
        print("  ⚠️ Missing App Clips for Travel or Shop!")
    else:
        print("  App clips OK.")

if __name__ == "__main__":
    hygiene_check()
