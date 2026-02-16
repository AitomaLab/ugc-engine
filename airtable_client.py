"""
Naiara Content Distribution Engine — Airtable Client

Handles all communication with Airtable:
- Content Calendar: fetch ready items, update status, attach final video
- Influencers: look up description + reference image
- App Clips: find matching clips by AI Assistant type
"""
import json
import random
import requests
import config


def _headers():
    return dict(config.AIRTABLE_HEADERS)


def _table_url(table_name):
    return f"{config.AIRTABLE_API_URL}/{table_name}"


def get_records(table_name, filter_formula=None):
    """Retrieve all records from a table, optionally filtered."""
    url = _table_url(table_name)
    params = {}
    if filter_formula:
        params["filterByFormula"] = filter_formula
        
    resp = requests.get(url, headers=_headers(), params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Failed to fetch records from '{table_name}': {resp.text}")
        
    return resp.json().get("records", [])


# ---------------------------------------------------------------------------
# Content Calendar
# ---------------------------------------------------------------------------

def get_ready_items(limit=None):
    """
    Fetch rows from Content Calendar where Status = 'Ready'.
    Returns list of record dicts with 'id' and 'fields'.
    """
    url = _table_url(config.TABLE_CONTENT_CALENDAR)
    params = {
        "filterByFormula": '{Status} = "Ready"',
    }
    if limit:
        params["maxRecords"] = limit

    all_records = []
    offset = None

    while True:
        if offset:
            params["offset"] = offset

        resp = requests.get(url, headers=_headers(), params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"Airtable error: {resp.status_code} {resp.text[:500]}")

        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    print(f"📋 Found {len(all_records)} ready items in Content Calendar")
    return all_records


def update_status(record_id, status):
    """
    Update a Content Calendar record's Status and Progress fields.
    
    Status is simplified: Generating, Assembling, Adding Music, Review
    Progress shows granular details: 'Gen: Hook (1/4)', etc.
    """
    url = f"{_table_url(config.TABLE_CONTENT_CALENDAR)}/{record_id}"
    
    # Parse status to extract high-level vs. granular
    if status.startswith("Gen:"):
        # Granular scene update
        high_level_status = "Generating"
        progress = status
    elif status in ["Assembling", "Adding Music", "Ready"]:
        high_level_status = status
        progress = status
    else:
        # Standard status (Generating, Review, Failed, etc.)
        high_level_status = status
        progress = status
    
    try:
        resp = requests.patch(url, headers=_headers(), json={
            "fields": {
                "Status": high_level_status,
                "Progress": progress
            }
        })
        if resp.status_code != 200:
            print(f"   ⚠️ Status update warning: {resp.text[:200]}")
        else:
            print(f"   📝 Status → {high_level_status} | Progress → {progress}")
    except Exception as e:
        print(f"   ⚠️ Status update error: {e}")


def attach_final_video(record_id, video_path):
    """
    Save the final video path to the Content Calendar and set Status → Review.
    
    Uses the 'Final Video Path' text field (not the Attachment field,
    because Airtable attachments require publicly-hosted HTTP URLs).
    """
    url = f"{_table_url(config.TABLE_CONTENT_CALENDAR)}/{record_id}"

    # Strip the file:// prefix if present — keep a clean local path
    clean_path = video_path.replace("file://", "")

    resp = requests.patch(url, headers=_headers(), json={
        "fields": {
            "Final Video Path": clean_path,
            "Status": "Review",
            "Progress": "Review",
        }
    })

    if resp.status_code == 200:
        print(f"   📎 Final video path saved & status → Review")
    else:
        print(f"   ⚠️ Update failed ({resp.status_code}): {resp.text[:200]}")
        # Fallback: at least update status
        requests.patch(url, headers=_headers(), json={
            "fields": {"Status": "Review", "Progress": "Review"}
        })
        print(f"   📝 Status → Review (path save failed)")


#----------------------------------------------------------------------------
# Generated Assets Tracking
# ---------------------------------------------------------------------------

def log_asset(content_title, scene_name, asset_type, source_url, status="Ready", 
              duration=None, model=None, cost=None, error_msg=None):
    """
    Log a generated asset to the Generated Assets table.
    
    Args:
        content_title: Project name (e.g., "meg_30s_20260211_144609")
        scene_name: Scene identifier (e.g., "hook", "reaction", "app_demo")
        asset_type: "Veo Video", "Reference Image", "App Clip", "Music", "Final Video"
        source_url: URL to the asset
        status: "Queued", "Generating", "Ready", "Failed"
        duration: Video length in seconds
        model: Model used (e.g., "veo3_fast", "suno-v4")
        cost: API cost in dollars
        error_msg: Error message if failed
    """
    url = _table_url("Generated Assets")
    
    fields = {
        "Content Title": content_title,
        "Scene Name": scene_name,
        "Asset Type": asset_type,
        "Source URL": source_url,
        "Status": status,
    }
    
    if duration is not None:
        fields["Duration"] = duration
    if model:
        fields["Model Used"] = model
    if cost is not None:
        fields["Cost"] = cost
    if error_msg:
        fields["Error Message"] = error_msg
    
    try:
        resp = requests.post(url, headers=_headers(), json={"fields": fields})
        if resp.status_code != 200:
            # Don't fail the pipeline if asset logging fails — just warn
            print(f"   ⚠️ Asset logging warning: {resp.text[:200]}")
        else:
            print(f"      💾 Logged: {asset_type} ({scene_name})")
    except Exception as e:
        print(f"   ⚠️ Asset logging error: {e}")


# ---------------------------------------------------------------------------
# Influencers
# ---------------------------------------------------------------------------

def get_influencer(name):
    """
    Look up an influencer by name.
    Returns dict with 'description' and 'reference_image_url'.
    """
    url = _table_url(config.TABLE_INFLUENCERS)
    params = {
        "filterByFormula": f'{{Name}} = "{name}"',
        "maxRecords": 1,
    }

    resp = requests.get(url, headers=_headers(), params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Influencer lookup failed: {resp.text[:500]}")

    records = resp.json().get("records", [])
    if not records:
        raise ValueError(f"Influencer '{name}' not found in Airtable")

    fields = records[0]["fields"]
    ref_images = fields.get("Reference Image", [])
    ref_url = ref_images[0]["url"] if ref_images else None

    return {
        "name": fields.get("Name", name),
        "description": fields.get("Description", ""),
        "reference_image_url": ref_url,
        "gender": fields.get("Gender", "Female"),
        "accent": fields.get("Accent", "Castilian Spanish (Spain)"),
        "tone": fields.get("Tone", "Enthusiastic"),
        "age": fields.get("Age", "mid-20s"),
        "visual_description": fields.get("Visual Description", ""),
        "energy_level": fields.get("Energy Level", "High"),
        "personality": fields.get("Personality", "")
    }


def get_influencer_by_category(category):
    """
    Find a random influencer matching the given category (e.g., Travel, Shop).
    """
    url = _table_url(config.TABLE_INFLUENCERS)
    params = {
        "filterByFormula": f'{{Category}} = "{category}"',
    }

    resp = requests.get(url, headers=_headers(), params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"Influencer lookup failed: {resp.text[:500]}")

    records = resp.json().get("records", [])
    if not records:
        print(f"⚠️ No influencers found for category '{category}'")
        return None

    # Pick a random matching influencer
    record = random.choice(records)
    fields = record["fields"]
    ref_images = fields.get("Reference Image", [])
    ref_url = ref_images[0]["url"] if ref_images else None

    return {
        "name": fields.get("Name", "Unknown"),
        "description": fields.get("Description", ""),
        "reference_image_url": ref_url,
        "gender": fields.get("Gender", "Female"),
        "accent": fields.get("Accent", "Castilian Spanish (Spain)"),
        "tone": fields.get("Tone", "Enthusiastic")
    }


# ---------------------------------------------------------------------------
# App Clips
# ---------------------------------------------------------------------------

def get_app_clip(assistant_type, specific_clip_url=None):
    """
    Find an app clip for the given AI Assistant type.
    If specific_clip_url is provided (from Content Calendar), use that.
    Otherwise, pick a random clip matching the assistant type.

    Returns dict with 'name', 'video_url', 'duration'.
    """
    # If a specific clip was attached in the Content Calendar, use it directly
    if specific_clip_url:
        return {
            "name": "custom",
            "video_url": specific_clip_url,
            "duration": 4,  # default, will be trimmed
        }

    url = _table_url(config.TABLE_APP_CLIPS)
    params = {
        "filterByFormula": f'{{AI Assistant}} = "{assistant_type}"',
    }

    resp = requests.get(url, headers=_headers(), params=params)
    if resp.status_code != 200:
        raise RuntimeError(f"App clip lookup failed: {resp.text[:500]}")

    records = resp.json().get("records", [])
    if not records:
        raise ValueError(
            f"No app clips found for AI Assistant type '{assistant_type}'. "
            f"Add clips to the 'App Clips' table in Airtable."
        )

    # Pick a random clip
    record = random.choice(records)
    fields = record["fields"]
    videos = fields.get("Video", [])
    video_url = videos[0]["url"] if videos else None

    if not video_url:
        raise ValueError(f"App clip '{fields.get('Clip Name')}' has no video attached")

    return {
        "name": fields.get("Clip Name", "app_clip"),
        "video_url": video_url,
        "duration": fields.get("Duration", 4),
    }


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------

def _test():
    """Quick connectivity test — reads each table without writing."""
    print("🧪 Testing Airtable connectivity...\n")

    if not config.validate():
        return

    # Test Content Calendar
    try:
        items = get_ready_items(limit=1)
        print(f"   Content Calendar: OK ({len(items)} ready items)\n")
    except Exception as e:
        print(f"   Content Calendar: ❌ {e}\n")

    # Test Influencers
    try:
        url = _table_url(config.TABLE_INFLUENCERS)
        resp = requests.get(url, headers=_headers(), params={"maxRecords": 1})
        records = resp.json().get("records", [])
        if records:
            name = records[0]["fields"].get("Name", "?")
            inf = get_influencer(name)
            print(f"   Influencers: OK (found '{inf['name']}')")
            print(f"     Description: {inf['description'][:80]}...")
            print(f"     Reference image: {'✅' if inf['reference_image_url'] else '❌ missing'}\n")
        else:
            print("   Influencers: ⚠️ Table is empty\n")
    except Exception as e:
        print(f"   Influencers: ❌ {e}\n")

    # Test App Clips
    try:
        url = _table_url(config.TABLE_APP_CLIPS)
        resp = requests.get(url, headers=_headers(), params={"maxRecords": 5})
        records = resp.json().get("records", [])
        types = set()
        for r in records:
            t = r["fields"].get("AI Assistant", "?")
            types.add(t)
        print(f"   App Clips: OK ({len(records)} clips, types: {', '.join(types)})\n")
    except Exception as e:
        print(f"   App Clips: ❌ {e}\n")

    print("✅ Airtable test complete!")


if __name__ == "__main__":
    import sys
    if "--test" in sys.argv:
        _test()
    else:
        print("Usage: python airtable_client.py --test")
