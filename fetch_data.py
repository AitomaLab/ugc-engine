"""Fetch current Airtable data: influencers, app clips, and content calendar."""
import requests
import config

# Fetch influencers
print("=== INFLUENCERS ===")
url = f"{config.AIRTABLE_API_URL}/Influencers"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS)
for r in resp.json().get("records", []):
    f = r["fields"]
    name = f.get("Name", "?")
    desc = f.get("Description", "?")[:100]
    has_img = bool(f.get("Reference Image"))
    print(f"  Name: {name}")
    print(f"  Description: {desc}")
    print(f"  Has ref image: {has_img}")
    print()

# Fetch app clips
print("=== APP CLIPS ===")
url = f"{config.AIRTABLE_API_URL}/App Clips"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS)
for r in resp.json().get("records", []):
    f = r["fields"]
    clip_name = f.get("Clip Name", "?")
    assistant = f.get("AI Assistant", "?")
    has_vid = bool(f.get("Video"))
    print(f"  Clip: {clip_name} | AI Assistant: {assistant} | Has video: {has_vid}")

# Fetch content calendar
print()
print("=== CONTENT CALENDAR (existing) ===")
url = f"{config.AIRTABLE_API_URL}/Content Calendar"
resp = requests.get(url, headers=config.AIRTABLE_HEADERS)
for r in resp.json().get("records", []):
    f = r["fields"]
    name = f.get("Influencer Name", "?")
    assistant = f.get("AI Assistant", "?")
    status = f.get("Status", "?")
    hook = f.get("Hook", "?")[:80]
    length = f.get("Length", "?")
    print(f"  {name} | {assistant} | {length} | {status} | {hook}")
