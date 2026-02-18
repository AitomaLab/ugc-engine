import os
import uuid
from dotenv import load_dotenv
load_dotenv(".env.saas")

import airtable_client
from ugc_db.db_manager import SessionLocal, ScriptLibrary, Influencer

def sync():
    print("⏳ Starting Airtable Script Sync...")
    db = SessionLocal()
    
    # 1. Fetch from Airtable
    try:
        records = airtable_client.get_records("Content Calendar")
    except Exception as e:
        print(f"❌ Failed to fetch from Airtable: {e}")
        return

    print(f"📋 Found {len(records)} records in Airtable.")
    
    # 2. Get existing influencers for mapping
    influencers = db.query(Influencer).all()
    inf_map = {i.name: i.id for i in influencers}
    
    synced = 0
    skipped = 0
    
    for r in records:
        fields = r.get("fields", {})
        hook = fields.get("Hook")
        if not hook:
            skipped += 1
            continue
            
        # Check if already exists (basic text match)
        exists = db.query(ScriptLibrary).filter(ScriptLibrary.text == hook).first()
        if exists:
            skipped += 1
            continue
            
        inf_name = fields.get("Influencer Name")
        inf_id = inf_map.get(inf_name)
        
        category = fields.get("AI Assistant")
        
        new_script = ScriptLibrary(
            id=uuid.uuid4(),
            influencer_id=inf_id,
            category=category,
            text=hook
        )
        db.add(new_script)
        synced += 1
        
    db.commit()
    db.close()
    
    print(f"✅ Sync Complete!")
    print(f"   ✨ Synced: {synced}")
    print(f"   ⏩ Skipped (duplicates/empty): {skipped}")

if __name__ == "__main__":
    sync()
