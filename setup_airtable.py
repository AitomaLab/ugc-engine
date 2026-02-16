"""
Naiara Content Distribution Engine — Airtable Setup

Creates the 3 required tables in your Airtable base:
1. Content Calendar — drives the pipeline
2. Influencers — AI persona library
3. App Clips — pre-recorded app footage

Run once: python setup_airtable.py
"""
import requests
import json
import sys
import config


def _headers():
    return {
        "Authorization": f"Bearer {config.AIRTABLE_TOKEN}",
        "Content-Type": "application/json",
    }


def _meta_url():
    return f"https://api.airtable.com/v0/meta/bases/{config.AIRTABLE_BASE_ID}/tables"


def get_existing_tables():
    """Get list of existing table names in the base."""
    resp = requests.get(_meta_url(), headers=_headers())
    if resp.status_code != 200:
        print(f"❌ Can't read base: {resp.status_code} {resp.text[:300]}")
        return None
    return {t["name"]: t["id"] for t in resp.json().get("tables", [])}


def create_table(name, fields, description=""):
    """Create a table with the given fields."""
    payload = {
        "name": name,
        "description": description,
        "fields": fields,
    }
    resp = requests.post(_meta_url(), headers=_headers(), json=payload)
    if resp.status_code == 200:
        table_id = resp.json()["id"]
        print(f"   ✅ Created '{name}' ({table_id})")
        return table_id
    elif resp.status_code == 422 and "DUPLICATE_TABLE_NAME" in resp.text:
        print(f"   ⏩ '{name}' already exists — skipping")
        return None
    else:
        print(f"   ❌ Failed to create '{name}': {resp.status_code}")
        print(f"      {resp.text[:300]}")
        return None


def setup_content_calendar():
    """Create the Content Calendar table."""
    fields = [
        {"name": "Hook", "type": "multilineText",
         "description": "The viral hook line the influencer says"},
        {"name": "AI Assistant", "type": "singleSelect",
         "options": {"choices": [
             {"name": "Travel"},
             {"name": "Shop"},
             {"name": "Cooking"},
             {"name": "Fitness"},
         ]}},
        {"name": "Theme", "type": "singleLineText",
         "description": "Scene context: beach vacation, shopping haul, etc."},
        {"name": "Caption", "type": "multilineText",
         "description": "Full caption/CTA text"},
        {"name": "Influencer", "type": "singleSelect",
         "options": {"choices": [
             {"name": "Sofia"},
         ]}},
        {"name": "Length", "type": "singleSelect",
         "options": {"choices": [
             {"name": "15s"},
             {"name": "30s"},
         ]}},
        {"name": "Status", "type": "singleSelect",
         "options": {"choices": [
             {"name": "Draft"},
             {"name": "Ready"},
             {"name": "Generating"},
             {"name": "Review"},
             {"name": "Approved"},
             {"name": "Scheduled"},
         ]}},
        {"name": "Final Video", "type": "multipleAttachments",
         "description": "The finished UGC video"},
    ]
    return create_table("Content Calendar", fields,
                        "Main pipeline driver — each row = one UGC video")


def setup_influencers():
    """Create the Influencers table."""
    fields = [
        {"name": "Name", "type": "singleLineText",
         "description": "Influencer persona name (e.g. Sofia)"},
        {"name": "Description", "type": "multilineText",
         "description": "Physical appearance + style for Veo prompt"},
        {"name": "Reference Image", "type": "multipleAttachments",
         "description": "First-frame reference photo for Veo 3.1"},
    ]
    return create_table("Influencers", fields,
                        "AI influencer personas with reference images")


def setup_app_clips():
    """Create the App Clips table."""
    fields = [
        {"name": "Clip Name", "type": "singleLineText",
         "description": "e.g. Travel assistant demo"},
        {"name": "AI Assistant", "type": "singleSelect",
         "options": {"choices": [
             {"name": "Travel"},
             {"name": "Shop"},
             {"name": "Cooking"},
             {"name": "Fitness"},
         ]}},
        {"name": "Video", "type": "multipleAttachments",
         "description": "The actual screen recording / real-life footage"},
        {"name": "Duration", "type": "number",
         "options": {"precision": 0},
         "description": "Clip length in seconds"},
    ]
    return create_table("App Clips", fields,
                        "Pre-recorded app usage footage library")


def main():
    print("🔧 Naiara Airtable Setup")
    print("=" * 50)

    if not config.validate():
        sys.exit(1)

    # Check existing tables
    print("\n📋 Checking existing tables...")
    existing = get_existing_tables()
    if existing is None:
        sys.exit(1)
    if existing:
        print(f"   Found: {', '.join(existing.keys())}")
    else:
        print("   Base is empty — creating tables now")

    # Create tables
    print("\n📊 Creating tables...")
    setup_content_calendar()
    setup_influencers()
    setup_app_clips()

    print(f"\n{'=' * 50}")
    print("✅ Airtable setup complete!")
    print(f"\n📌 Next steps:")
    print(f"   1. Open your Airtable base: https://airtable.com/{config.AIRTABLE_BASE_ID}")
    print(f"   2. Go to 'App Clips' → upload your app recordings")
    print(f"      - Set 'AI Assistant' to 'Shop' or 'Travel'")
    print(f"      - Set 'Duration' to the clip length in seconds")
    print(f"   3. Go to 'Influencers' → add your first AI persona")
    print(f"      - Name, physical description, reference photo")
    print(f"   4. Go to 'Content Calendar' → add your first hooks")
    print(f"      - Set Status to 'Ready' when you want to generate")


if __name__ == "__main__":
    main()
